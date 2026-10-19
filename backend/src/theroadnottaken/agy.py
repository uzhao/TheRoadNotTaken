"""agy print 模式的调用约定：拼命令行、逐行解析 stream-json、读 stderr 的 `AGY_ERROR`。

约定来自 research/agy-print-mode.md：`-p`/`--print` 的下一个词即 prompt，所以 prompt 必须写成
`--print=…` 并放在最后；续接会话用 `--conversation <id>`（不用 `--continue`）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

log = logging.getLogger(__name__)

Effort = Literal["high", "medium"]


@dataclass(frozen=True)
class Invocation:
    """一次 agy 调用的输入。`conversation_id` 给定时续接该会话，否则开新会话。"""

    prompt: str
    effort: Effort
    conversation_id: str | None = None


def command(invocation: Invocation) -> list[str]:
    args = [
        "agy",
        "--output-format",
        "stream-json",
        "--disable-slash-commands",
        f"--effort={invocation.effort}",
    ]
    if invocation.conversation_id:
        args += ["--conversation", invocation.conversation_id]
    args.append(f"--print={invocation.prompt}")
    return args


@dataclass(frozen=True)
class Init:
    conversation_id: str


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolStep:
    step_index: int
    name: str
    state: Literal["ACTIVE", "DONE"]
    # 工具步的要点（命令行或目标文件），供界面显示「画图 xxx」；DONE 事件不带参数，为空
    detail: str = ""


@dataclass(frozen=True)
class Result:
    payload: dict


Event = Init | TextDelta | ToolStep | Result


def parse_line(line: str) -> Event | None:
    """把 stream-json 的一行解析为事件；非 JSON 行与不关心的事件返回 None。"""
    try:
        obj = json.loads(line)
    except ValueError:
        log.info("agy 输出非 JSON 行：%s", line)
        return None
    if not isinstance(obj, dict):
        return None
    match obj.get("event"):
        case "init" if obj.get("conversation_id"):
            return Init(obj["conversation_id"])
        case "step_update":
            step = obj.get("step_update") or {}
            if step.get("step_type") == "agent_response" and step.get("text_delta"):
                return TextDelta(step["text_delta"])
            if step.get("step_type") == "tool" and step.get("state") in ("ACTIVE", "DONE"):
                params = (step.get("tool_info") or {}).get("parameters") or {}
                detail = params.get("CommandLine") or params.get("TargetFile") or ""
                return ToolStep(
                    step.get("step_index", 0),
                    step.get("tool_name", ""),
                    step["state"],
                    detail if isinstance(detail, str) else "",
                )
        case "result":
            return Result(obj)
    return None


AGY_ERROR_PREFIX = "AGY_ERROR:"


def parse_agy_error(stderr: str) -> dict | None:
    """取 stderr 最后一行 `AGY_ERROR: {...}` 的 JSON（含 retryable、short_error、error_id）。"""
    for line in reversed(stderr.splitlines()):
        if line.startswith(AGY_ERROR_PREFIX):
            try:
                error = json.loads(line.removeprefix(AGY_ERROR_PREFIX))
            except ValueError:
                return None
            return error if isinstance(error, dict) else None
    return None
