"""生成任务运行器：在一次性的生成任务目录里跑 agy 子进程，把事件推给订阅者。

- 每个任务一个目录 `jobs/<任务id>/`，作为 agy 的 cwd；原始 stdout 逐行落 `agy.ndjson`，
  stderr 落 `agy.stderr`。成功的任务目录由调用方搬运产出后删除（无产出的任务可让运行器直接删），
  失败的保留供查看，取消的删除。
- 并发上限 `max_running`，其余按提交顺序排队并上报位次。
- 硬超时到期杀整个进程组（agy 会起 python3 等子进程），任务标记失败。
- `init` 事件到达时，若任务绑定了主题会话，立即把会话 id 写进会话映射。
- 任务可带产出的后处理（如讲义的搬运校验）：通过则并入 `done`；要求重试时在同一任务目录里
  再调一次 agy（发 `retry` 事件）；拒绝则任务失败、目录保留。
- 任务状态只在内存；订阅者从任意事件序号起回放并跟随，流在终止事件 `done` 后结束。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from theroadnottaken import agy
from theroadnottaken.datadir import DataDir

log = logging.getLogger(__name__)

STREAM_LIMIT = 16 * 1024 * 1024  # result 事件带全文，单行可能很长


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


FINISHED = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


@dataclass(frozen=True)
class Retry:
    """产出没通过后处理：在同一任务目录里按 `invocation` 再调一次 agy（通常续接同一会话）。"""

    invocation: agy.Invocation
    errors: list[str]


@dataclass(frozen=True)
class Reject:
    """产出没通过后处理且不再重试：任务失败，`error` 并入 `done`。"""

    error: dict[str, Any]


# 后处理的裁决：dict 表示通过（并入 `done` 的数据），或 Retry / Reject
Verdict = dict[str, Any] | Retry | Reject
# (任务目录, agy 成功结果, 第几次尝试) → 裁决；在线程里执行，可以写数据目录
Postprocess = Callable[[Path, dict[str, Any], int], Verdict]


@dataclass(frozen=True)
class JobSpec:
    kind: str
    invocation: agy.Invocation
    timeout: float
    # 绑定的主题：`init` 到达时把会话 id 写进该主题的会话映射（验证会话不绑定）
    conversation_topic: str | None = None
    # 无产出要搬运的任务（如「重试连接」）成功后由运行器直接删目录
    delete_dir_on_success: bool = False
    # agy 成功后对产出的后处理（校验、搬运）；None 表示 agy 成功即任务成功
    postprocess: Postprocess | None = None
    # 启动前放进任务目录的文件（相对路径 → 内容），如统一的 `matplotlibrc`
    files: tuple[tuple[str, str], ...] = ()


@dataclass(eq=False)
class Job:
    id: str
    spec: JobSpec
    dir: Path
    status: JobStatus = JobStatus.QUEUED
    position: int | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    task: asyncio.Task | None = None
    # 工具步 ACTIVE 事件的要点，DONE 事件不带参数，按步序号补上
    _tool_details: dict[int, str] = field(default_factory=dict)
    _wakeup: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def finished(self) -> bool:
        return self.status in FINISHED

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.spec.kind,
            "status": self.status,
            "position": self.position,
        }


class JobRunner:
    def __init__(
        self,
        jobs_dir: Path,
        store: DataDir,
        *,
        max_running: int = 2,
    ) -> None:
        self.jobs_dir = jobs_dir
        self.store = store
        self.max_running = max_running
        self._jobs: dict[str, Job] = {}
        self._queue: deque[Job] = deque()
        self._running: set[Job] = set()

    def submit(self, spec: JobSpec) -> Job:
        """登记任务并建好任务目录；有空位立即启动，否则排队。须在事件循环内调用。"""
        job_id = f"{datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        job = Job(id=job_id, spec=spec, dir=self.jobs_dir / job_id)
        job.dir.mkdir(parents=True)
        for name, content in spec.files:
            (job.dir / name).write_text(content, encoding="utf-8")
        self._jobs[job_id] = job
        self._queue.append(job)
        self._schedule()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def cancel(self, job: Job) -> None:
        """取消排队中或运行中的任务：杀进程组、删任务目录。已结束的任务不受影响。"""
        if job.finished:
            return
        if job.status is JobStatus.QUEUED:
            self._queue.remove(job)
        elif job.task is not None:
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)
        shutil.rmtree(job.dir, ignore_errors=True)
        self._finish(job, JobStatus.CANCELLED, {})
        self._schedule()

    async def events(self, job: Job, after: int = 0) -> AsyncIterator[dict[str, Any]]:
        """从序号 `after` 之后回放事件并跟随，直到终止事件。"""
        i = after
        while True:
            while i < len(job.events):
                yield job.events[i]
                i += 1
            if job.finished:
                return
            await job._wakeup.wait()

    async def shutdown(self) -> None:
        for job in list(self._queue) + list(self._running):
            await self.cancel(job)

    # ---- 内部 ----

    def _emit(self, job: Job, event: str, data: dict[str, Any]) -> None:
        job.events.append({"id": len(job.events) + 1, "event": event, "data": data})
        job._wakeup.set()
        job._wakeup = asyncio.Event()

    def _finish(self, job: Job, status: JobStatus, data: dict[str, Any]) -> None:
        job.status = status
        job.position = None
        self._emit(job, "done", {"status": status, **data})

    def _schedule(self) -> None:
        while self._queue and len(self._running) < self.max_running:
            job = self._queue.popleft()
            self._running.add(job)
            job.status = JobStatus.RUNNING
            job.position = None
            self._emit(job, "started", {})
            job.task = asyncio.create_task(self._run(job))
        for position, job in enumerate(self._queue, start=1):
            if job.position != position:
                job.position = position
                self._emit(job, "queued", {"position": position})

    async def _run(self, job: Job) -> None:
        try:
            status, data = await self._attempts(job)
        except asyncio.CancelledError:
            self._running.discard(job)
            raise
        self._running.discard(job)
        if status is JobStatus.SUCCEEDED and job.spec.delete_dir_on_success:
            shutil.rmtree(job.dir, ignore_errors=True)
        self._finish(job, status, data)
        self._schedule()

    async def _attempts(self, job: Job) -> tuple[JobStatus, dict[str, Any]]:
        """调 agy，成功则交给后处理；后处理要求重试时再调一次，直到通过或被拒。"""
        invocation = job.spec.invocation
        attempt = 1
        while True:
            status, data = await self._execute(job, invocation)
            if status is not JobStatus.SUCCEEDED or job.spec.postprocess is None:
                return status, data
            try:
                verdict = await asyncio.to_thread(job.spec.postprocess, job.dir, data, attempt)
            except Exception as exc:
                log.exception("任务 %s 的后处理出错", job.id)
                error = {"kind": "postprocess", "message": f"后处理出错：{exc}"}
                return JobStatus.FAILED, {**data, "error": error}
            match verdict:
                case Retry(next_invocation, errors):
                    attempt += 1
                    invocation = next_invocation
                    self._emit(job, "retry", {"attempt": attempt, "errors": errors})
                case Reject(error):
                    return JobStatus.FAILED, {**data, "error": error}
                case _:
                    return status, {**data, **verdict}

    async def _execute(
        self, job: Job, invocation: agy.Invocation
    ) -> tuple[JobStatus, dict[str, Any]]:
        cmd = agy.command(invocation)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=job.dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                limit=STREAM_LIMIT,
            )
        except OSError as exc:
            return JobStatus.FAILED, {"error": {"kind": "spawn", "message": str(exc)}}

        assert proc.stdout is not None and proc.stderr is not None
        stderr_task = asyncio.create_task(proc.stderr.read())
        result: dict | None = None
        try:
            async with asyncio.timeout(job.spec.timeout):
                # 追加：重试的那次调用接在同一份原始事件记录后面
                with (job.dir / "agy.ndjson").open("a", encoding="utf-8") as raw:
                    async for line_bytes in proc.stdout:
                        line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                        raw.write(line + "\n")
                        raw.flush()
                        event = agy.parse_line(line)
                        if isinstance(event, agy.Init) and job.spec.conversation_topic:
                            # 写文件并提交 git，放到线程里免得卡住事件循环
                            await asyncio.to_thread(
                                self.store.set_conversation,
                                job.spec.conversation_topic,
                                event.conversation_id,
                            )
                        result = self._handle(job, event) or result
                returncode = await proc.wait()
        except TimeoutError:
            await _kill_group(proc)
            return JobStatus.FAILED, {
                "error": {"kind": "timeout", "message": f"超过 {job.spec.timeout:g} 秒未完成"}
            }
        finally:
            if proc.returncode is None:  # 被取消
                await _kill_group(proc)
            stderr = (await stderr_task).decode("utf-8", errors="replace")
            with (job.dir / "agy.stderr").open("a", encoding="utf-8") as f:
                f.write(stderr)

        return _outcome(returncode, result, stderr)

    def _handle(self, job: Job, event: agy.Event | None) -> dict | None:
        match event:
            case agy.Init(conversation_id):
                self._emit(job, "conversation", {"conversation_id": conversation_id})
            case agy.TextDelta(text):
                self._emit(job, "delta", {"text": text})
            case agy.ToolStep(step_index, name, state, detail):
                detail = detail or job._tool_details.get(step_index, "")
                job._tool_details[step_index] = detail
                self._emit(
                    job,
                    "tool",
                    {"step_index": step_index, "name": name, "state": state, "detail": detail},
                )
            case agy.Result(payload):
                return payload
        return None


def _outcome(returncode: int, result: dict | None, stderr: str) -> tuple[JobStatus, dict]:
    if returncode != 0:
        error = agy.parse_agy_error(stderr)
        if error is not None:
            return JobStatus.FAILED, {"error": {"kind": "agy_error", **error}}
        message = f"agy 退出码 {returncode}"
        return JobStatus.FAILED, {"error": {"kind": "exit", "message": message}}
    if result is None:
        return JobStatus.FAILED, {"error": {"kind": "no_result", "message": "agy 未给出 result"}}
    data = {
        key: result[key]
        for key in ("conversation_id", "response", "usage", "denied_actions", "structured_output")
        if key in result
    }
    if result.get("status") != "SUCCESS":
        message = result.get("error") or f"agy 结果状态 {result.get('status')}"
        return JobStatus.FAILED, {**data, "error": {"kind": "result", "message": message}}
    return JobStatus.SUCCEEDED, data


async def _kill_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await proc.wait()
