"""假 agy：按场景文件回放 stream-json 事件，供测试替代真实 agy（见规格 Testing Decisions）。

环境变量：
- `FAKE_AGY_SCENARIO`：场景 JSON 文件，形如 `{"runs": [{"steps": [...], "exit": 0}, ...]}`；
  第 n 次调用用第 n 个 run，调用次数超出时重复最后一个。
- `FAKE_AGY_LOG`：调用记录（JSONL），每次调用追加一行：argv、cwd、prompt、会话 id、effort 等。

步骤（每步一个单键对象，键为步骤类型）：
- `init`：`{"conversation_id"?}`，缺省沿用 `--conversation`，再缺省生成一个
- `text`：正文增量（`agent_response` 步的 ACTIVE 事件，带 `text_delta`）
- `tool`：`{"name", "parameters"?, "seconds"?}`，工具步的 ACTIVE 与 DONE 两条事件，中间停 `seconds`
- `result`：`{...}` 覆盖默认结果对象（缺省 `SUCCESS`、`response` 为已流出正文之和）
- `raw`：原样写一行 stdout（模拟混入的非 JSON 行）
- `stderr`：写一行 stderr
- `agy_error`：`{...}` 覆盖默认错误对象，写 `AGY_ERROR: {...}` 到 stderr
- `write`：`{"path", "content"?, "size"?}` 在 cwd 下写文件，不做路径检查（可写越界路径或超大文件）
- `sleep`：秒数
- `hang`：`{"pid_file"?}` 永不退出；给定 `pid_file` 时先起一个子进程并把它的 pid 写进去
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

TOOLS = ["run_command", "write_to_file", "view_file", "replace_file_content"]


def parse_args(argv: list[str]) -> dict:
    """按 agy 的 Go 风格 flag 解析：`-p`/`--print` 的下一个词即 prompt。"""
    opts: dict = {"prompt": None, "conversation": None, "effort": None, "output_format": None}
    flags: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        name, eq, value = arg.partition("=")
        if name in ("-p", "--print"):
            if not eq:
                i += 1
                value = argv[i] if i < len(argv) else ""
                if value.startswith("-"):
                    sys.stderr.write(f'-p took "{value}" as its prompt\n')
                    sys.exit(1)
            opts["prompt"] = value
        elif name in ("--conversation", "--output-format", "--effort", "--model"):
            if not eq:
                i += 1
                value = argv[i]
            opts[name.lstrip("-").replace("-", "_")] = value
        else:
            flags.append(arg)
        i += 1
    opts["flags"] = flags
    return opts


def emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    argv = sys.argv[1:]
    opts = parse_args(argv)

    # 加锁读写调用记录，并发调用也各自拿到不同的序号
    with Path(os.environ["FAKE_AGY_LOG"]).open("a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        previous = f.read().splitlines()
        record = {"argv": argv, "cwd": os.getcwd(), **opts}
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    runs = json.loads(Path(os.environ["FAKE_AGY_SCENARIO"]).read_text(encoding="utf-8"))["runs"]
    run = runs[min(len(previous), len(runs) - 1)]

    conversation_id = opts["conversation"] or f"fake-conv-{uuid.uuid4().hex[:8]}"
    response = ""
    step_index = 0
    in_response = False

    for step in run.get("steps", []):
        ((kind, arg),) = step.items()
        if kind == "init":
            conversation_id = arg.get("conversation_id") or conversation_id
            emit(
                {
                    "event": "init",
                    "conversation_id": conversation_id,
                    "init": {
                        "cwd": os.getcwd(),
                        "tools": TOOLS,
                        "permission_mode": "request-review",
                    },
                }
            )
        elif kind == "text":
            if not in_response:
                step_index += 1
                in_response = True
            response += arg
            emit(
                {
                    "event": "step_update",
                    "step_update": {
                        "step_index": step_index,
                        "state": "ACTIVE",
                        "step_type": "agent_response",
                        "text_delta": arg,
                    },
                }
            )
        elif kind == "tool":
            step_index += 1
            in_response = False
            base = {"step_index": step_index, "step_type": "tool", "tool_name": arg["name"]}
            emit(
                {
                    "event": "step_update",
                    "step_update": {
                        **base,
                        "state": "ACTIVE",
                        "tool_info": {"parameters": arg.get("parameters", {})},
                    },
                }
            )
            time.sleep(arg.get("seconds", 0))
            emit(
                {
                    "event": "step_update",
                    "step_update": {
                        **base,
                        "state": "DONE",
                        "duration_seconds": arg.get("seconds", 0),
                    },
                }
            )
        elif kind == "result":
            emit(
                {
                    "event": "result",
                    "conversation_id": conversation_id,
                    "status": "SUCCESS",
                    "response": response,
                    "duration_seconds": 1.0,
                    "num_turns": 1,
                    "usage": {"input_tokens": 12803, "output_tokens": len(response)},
                    **arg,
                }
            )
        elif kind == "raw":
            sys.stdout.write(arg + "\n")
            sys.stdout.flush()
        elif kind == "stderr":
            sys.stderr.write(arg + "\n")
            sys.stderr.flush()
        elif kind == "agy_error":
            error = {
                "short_error": "RESOURCE_EXHAUSTED (code 429): quota reached",
                "status": "RESOURCE_EXHAUSTED",
                "error_code": 429,
                "code_kind": "http",
                "retryable": True,
                "error_id": "fake-error-id",
                **arg,
            }
            sys.stderr.write("AGY_ERROR: " + json.dumps(error, ensure_ascii=False) + "\n")
            sys.stderr.flush()
        elif kind == "write":
            path = Path(arg["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            if "size" in arg:
                path.write_bytes(b"x" * arg["size"])
            else:
                path.write_text(arg.get("content", ""), encoding="utf-8")
        elif kind == "sleep":
            time.sleep(arg)
        elif kind == "hang":
            if arg.get("pid_file"):
                child = subprocess.Popen(["sleep", "3600"])
                Path(arg["pid_file"]).write_text(str(child.pid), encoding="utf-8")
            while True:
                time.sleep(3600)
        else:
            raise SystemExit(f"fake agy: unknown step {kind!r}")

    sys.exit(run.get("exit", 0))


if __name__ == "__main__":
    main()
