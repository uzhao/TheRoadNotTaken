"""生成任务运行器：经 HTTP 创建任务、经 SSE 订阅事件，agy 由假 agy 代替。"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import agy_steps as s
import pytest
from conftest import FakeAgy
from fastapi.testclient import TestClient

from theroadnottaken.agy import Invocation
from theroadnottaken.jobs import JobSpec


def sse_events(client: TestClient, job_id: str, last_event_id: str | None = None) -> list[dict]:
    """读完一个任务的事件流（流在终止事件后关闭），返回 `{"id", "event", "data"}` 列表。"""
    headers = {"Last-Event-ID": last_event_id} if last_event_id else {}
    resp = client.get(f"/api/jobs/{job_id}/events", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in resp.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append(
            {"id": fields["id"], "event": fields["event"], "data": json.loads(fields["data"])}
        )
    return events


def wait_until(predicate: Callable[[], bool], timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "等待超时"
        time.sleep(0.02)


def git_log(data_dir: Path) -> list[str]:
    """数据目录的提交信息，最新的在前。"""
    out = subprocess.run(
        ["git", "-C", str(data_dir), "log", "--format=%s"], capture_output=True, text=True
    )
    return out.stdout.splitlines()


def kinds(events: list[dict]) -> list[str]:
    return [e["event"] for e in events]


def test_ping_job_streams_events_in_order(client: TestClient, fake_agy: FakeAgy) -> None:
    fake_agy.script(
        s.run(
            s.init("conv-1"),
            s.text("O"),
            s.tool("run_command", CommandLine="python3 plot.py"),
            s.text("K"),
            s.result(),
        )
    )

    resp = client.post("/api/jobs", json={"kind": "ping"})
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    events = sse_events(client, job_id)

    assert kinds(events) == ["started", "conversation", "delta", "tool", "tool", "delta", "done"]
    assert events[1]["data"] == {"conversation_id": "conv-1"}
    assert [e["data"]["text"] for e in events if e["event"] == "delta"] == ["O", "K"]
    assert [(e["data"]["name"], e["data"]["state"]) for e in events if e["event"] == "tool"] == [
        ("run_command", "ACTIVE"),
        ("run_command", "DONE"),
    ]
    done = events[-1]["data"]
    assert done["status"] == "succeeded"
    assert done["response"] == "OK"
    assert [int(e["id"]) for e in events] == list(range(1, len(events) + 1))


def submit(client: TestClient, spec: JobSpec) -> str:
    """提交一个尚无 HTTP 入口的任务（讲义、追问等由后续工单接上路由），返回任务 id。"""
    jobs = client.app.state.jobs
    return client.portal.call(jobs.submit, spec).id


def lecture_spec(
    topic: str = "c02-derivative-definition", conversation_id: str | None = None
) -> JobSpec:
    return JobSpec(
        kind="lecture",
        invocation=Invocation(prompt="写讲义", effort="high", conversation_id=conversation_id),
        timeout=30,
        conversation_topic=topic,
    )


def test_ping_command_line_follows_agy_conventions(client: TestClient, fake_agy: FakeAgy) -> None:
    job_id = client.post("/api/jobs", json={"kind": "ping"}).json()["id"]
    sse_events(client, job_id)

    (call,) = fake_agy.calls()
    argv = call["argv"]
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--disable-slash-commands" in argv
    assert "--effort=medium" in argv
    assert "--conversation" not in argv
    assert argv[-1] == "--print=只回复两个字母：OK"
    assert call["prompt"] == "只回复两个字母：OK"
    assert Path(call["cwd"]) == client.app.state.data_dir / "jobs" / job_id


def test_init_event_records_topic_conversation_while_job_still_runs(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mapping = data_dir / "conversations.json"
    fake_agy.script(s.run(s.init("conv-new"), s.hang()))

    job_id = submit(client, lecture_spec())

    wait_until(lambda: "c02-derivative-definition" in git_log(data_dir)[0])
    assert json.loads(mapping.read_text(encoding="utf-8")) == {
        "c02-derivative-definition": "conv-new"
    }
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "running"
    assert "--effort=high" in fake_agy.calls()[0]["argv"]
    client.delete(f"/api/jobs/{job_id}")


def test_continuation_passes_conversation_id_and_keeps_other_topics(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mapping = data_dir / "conversations.json"
    mapping.write_text(
        json.dumps({"c04-gauss-elimination": "conv-x", "c02-derivative-definition": "conv-old"})
    )
    fake_agy.script(s.ok(conversation_id="conv-old"))

    sse_events(client, submit(client, lecture_spec(conversation_id="conv-old")))

    argv = fake_agy.calls()[0]["argv"]
    assert argv[argv.index("--conversation") + 1] == "conv-old"
    assert argv[-1] == "--print=写讲义"
    assert json.loads(mapping.read_text(encoding="utf-8")) == {
        "c04-gauss-elimination": "conv-x",
        "c02-derivative-definition": "conv-old",
    }


def run_ping(client: TestClient) -> tuple[str, list[dict]]:
    job_id = client.post("/api/jobs", json={"kind": "ping"}).json()["id"]
    return job_id, sse_events(client, job_id)


def test_retryable_agy_error_fails_job_with_error_details(
    client: TestClient, fake_agy: FakeAgy
) -> None:
    fake_agy.script(s.quota_error(retryable=True))

    _, events = run_ping(client)

    done = events[-1]["data"]
    assert done["status"] == "failed"
    assert done["error"]["kind"] == "agy_error"
    assert done["error"]["retryable"] is True
    assert done["error"]["short_error"].startswith("RESOURCE_EXHAUSTED")
    assert done["error"]["error_id"] == "fake-error-id"


def test_non_retryable_agy_error_is_reported_as_such(client: TestClient, fake_agy: FakeAgy) -> None:
    fake_agy.script(s.quota_error(retryable=False))

    _, events = run_ping(client)

    error = events[-1]["data"]["error"]
    assert error["retryable"] is False
    assert error["status"] == "UNAUTHENTICATED"


def test_failed_job_keeps_directory_with_raw_ndjson_including_non_json_lines(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    fake_agy.script(
        s.run(
            s.init("conv-1"),
            s.raw("jetski: some log line"),
            s.raw('{"event": "step_update", "step_update": {"step_type": "tool"}}'),
            s.text("半"),
            s.agy_error(),
            exit=3,
        )
    )

    job_id, events = run_ping(client)

    assert kinds(events) == ["started", "conversation", "delta", "done"]
    raw = (data_dir / "jobs" / job_id / "agy.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(raw) == 4
    assert json.loads(raw[0])["event"] == "init"
    assert raw[1] == "jetski: some log line"
    assert json.loads(raw[3])["step_update"]["text_delta"] == "半"


def test_successful_ping_directory_is_removed(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    job_id, events = run_ping(client)

    assert events[-1]["data"]["status"] == "succeeded"
    assert not (data_dir / "jobs" / job_id).exists()


def test_successful_job_keeps_outputs_for_the_caller_to_move(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    fake_agy.script(
        s.run(s.init(), s.write("figures/x.svg", "<svg/>"), s.text("# 导数"), s.result())
    )

    job_id = submit(client, lecture_spec())
    events = sse_events(client, job_id)

    assert events[-1]["data"]["status"] == "succeeded"
    assert (data_dir / "jobs" / job_id / "figures" / "x.svg").read_text() == "<svg/>"


def test_exit_zero_without_result_fails(client: TestClient, fake_agy: FakeAgy) -> None:
    fake_agy.script(s.run(s.init(), s.text("O")))

    _, events = run_ping(client)

    assert events[-1]["data"]["status"] == "failed"
    assert events[-1]["data"]["error"]["kind"] == "no_result"


def test_denied_actions_are_passed_through(client: TestClient, fake_agy: FakeAgy) -> None:
    fake_agy.script(s.denied())

    _, events = run_ping(client)

    assert events[-1]["data"]["denied_actions"] == [
        {"action": "command", "display_name": "RunCommand"}
    ]


def test_structured_output_is_passed_through_only_when_present(
    client: TestClient, fake_agy: FakeAgy
) -> None:
    fake_agy.script(
        s.no_structured_output(),
        s.run(s.init(), s.result(structured_output={"verdict": "uphold"})),
    )

    _, without = run_ping(client)
    _, with_schema = run_ping(client)

    assert "structured_output" not in without[-1]["data"]
    assert with_schema[-1]["data"]["structured_output"] == {"verdict": "uphold"}


def alive(pid: int) -> bool:
    """进程存在且不是僵尸（被杀的孤儿可能尚未被 init 回收）。"""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def test_timeout_kills_process_group_and_fails_job(
    client: TestClient, fake_agy: FakeAgy, tmp_path: Path
) -> None:
    pid_file = tmp_path / "child.pid"
    fake_agy.script(s.run(s.init(), s.text("部分"), s.hang(pid_file=str(pid_file))))
    spec = JobSpec(kind="lecture", invocation=Invocation("写讲义", "high"), timeout=1.0)

    events = sse_events(client, submit(client, spec))

    assert kinds(events) == ["started", "conversation", "delta", "done"]
    done = events[-1]["data"]
    assert done["status"] == "failed"
    assert done["error"]["kind"] == "timeout"
    child = int(pid_file.read_text())
    wait_until(lambda: not alive(child))


def test_third_job_queues_and_starts_when_a_slot_frees(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    fake_agy.script(s.run(s.init(), s.hang()), s.run(s.init(), s.hang()), s.ok())

    first, second, third = (
        client.post("/api/jobs", json={"kind": "ping"}).json() for _ in range(3)
    )

    assert [first["status"], second["status"]] == ["running", "running"]
    assert third["status"] == "queued"
    assert third["position"] == 1
    assert client.get(f"/api/jobs/{third['id']}").json()["position"] == 1

    wait_until(lambda: len(fake_agy.calls()) == 2)
    assert client.delete(f"/api/jobs/{first['id']}").status_code == 204

    events = sse_events(client, third["id"])
    assert kinds(events)[:2] == ["queued", "started"]
    assert events[0]["data"] == {"position": 1}
    assert events[-1]["data"]["status"] == "succeeded"
    client.delete(f"/api/jobs/{second['id']}")


def test_queue_positions_move_up(client: TestClient, fake_agy: FakeAgy) -> None:
    fake_agy.script(s.run(s.init(), s.hang()))
    ids = [client.post("/api/jobs", json={"kind": "ping"}).json()["id"] for _ in range(4)]

    assert [client.get(f"/api/jobs/{i}").json()["position"] for i in ids] == [None, None, 1, 2]
    client.delete(f"/api/jobs/{ids[2]}")

    assert client.get(f"/api/jobs/{ids[3]}").json()["position"] == 1
    events = sse_events(client, ids[2])
    assert kinds(events) == ["queued", "done"]
    assert events[-1]["data"]["status"] == "cancelled"
    for i in ids:
        client.delete(f"/api/jobs/{i}")


def test_cancel_running_job_kills_it_removes_directory_and_keeps_state(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path, tmp_path: Path
) -> None:
    pid_file = tmp_path / "child.pid"
    state = data_dir / "state.json"
    state.write_text('{"c02-derivative-definition": {"status": "learning"}}', encoding="utf-8")
    fake_agy.script(s.run(s.init(), s.hang(pid_file=str(pid_file))))

    job_id = submit(client, lecture_spec())
    wait_until(pid_file.exists)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204

    events = sse_events(client, job_id)
    assert events[-1]["data"] == {"status": "cancelled"}
    assert not (data_dir / "jobs" / job_id).exists()
    assert (
        state.read_text(encoding="utf-8") == '{"c02-derivative-definition": {"status": "learning"}}'
    )
    wait_until(lambda: not alive(int(pid_file.read_text())))
    assert client.delete(f"/api/jobs/{job_id}").status_code == 409


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404
    assert client.delete("/api/jobs/nope").status_code == 404


def test_events_resume_after_last_event_id(client: TestClient, fake_agy: FakeAgy) -> None:
    job_id, events = run_ping(client)

    resumed = sse_events(client, job_id, last_event_id=events[1]["id"])

    assert resumed == events[2:]


def test_missing_agy_executable_fails_job(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    _, events = run_ping(client)

    assert events[-1]["data"]["status"] == "failed"
    assert events[-1]["data"]["error"]["kind"] == "spawn"
