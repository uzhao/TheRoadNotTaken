"""假 agy 场景的步骤构造函数（步骤含义见 `fake_agy.py` 文档）。"""

from __future__ import annotations

from typing import Any


def run(*steps: dict, exit: int = 0) -> dict:
    return {"steps": list(steps), "exit": exit}


def init(conversation_id: str | None = None) -> dict:
    return {"init": {"conversation_id": conversation_id}}


def text(delta: str) -> dict:
    return {"text": delta}


def tool(name: str, seconds: float = 0, **parameters: Any) -> dict:
    return {"tool": {"name": name, "seconds": seconds, "parameters": parameters}}


def result(**overrides: Any) -> dict:
    return {"result": overrides}


def raw(line: str) -> dict:
    return {"raw": line}


def stderr(line: str) -> dict:
    return {"stderr": line}


def agy_error(**overrides: Any) -> dict:
    return {"agy_error": overrides}


def write(path: str, content: str = "", size: int | None = None) -> dict:
    arg: dict[str, Any] = {"path": path, "content": content}
    if size is not None:
        arg["size"] = size
    return {"write": arg}


def sleep(seconds: float) -> dict:
    return {"sleep": seconds}


def hang(pid_file: str | None = None) -> dict:
    return {"hang": {"pid_file": pid_file}}


# 常用整次调用


def ok(response: str = "OK", conversation_id: str | None = None) -> dict:
    """正常的一次调用：init → 正文增量 → result。"""
    return run(init(conversation_id), text(response), result())


def quota_error(retryable: bool = True) -> dict:
    """模型/配额错误：exit 3，stderr 带 `AGY_ERROR`。"""
    if retryable:
        return run(init(), stderr("error: Individual quota reached"), agy_error(), exit=3)
    return run(
        stderr("error: not logged in"),
        agy_error(
            short_error="UNAUTHENTICATED (code 401): not logged in",
            status="UNAUTHENTICATED",
            error_code=401,
            retryable=False,
        ),
        exit=3,
    )


def denied(action: str = "command") -> dict:
    """工具权限被自动拒绝：exit 0，stderr 一行 jetski 提示，result 带 `denied_actions`。"""
    return run(
        init(),
        stderr(
            f'jetski: no output produced — a tool required the "{action}" permission that '
            "headless mode cannot prompt for, so it was auto-denied."
        ),
        result(response="", denied_actions=[{"action": action, "display_name": "RunCommand"}]),
    )


def no_structured_output() -> dict:
    """`--json-schema` 不可满足：`SUCCESS` 但结果里没有 `structured_output`。"""
    return run(init(), text("我无法满足该 schema。"), result())
