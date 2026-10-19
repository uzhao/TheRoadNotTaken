"""掌握状态文件 `state.json` 的 schema 与读取（见规格「数据目录」一节与 GLOSSARY「掌握状态」）。

键为主题 id，每项含状态、薄弱点、验证记录与更新时间；退役主题的条目移入 `archived` 段。
高中数学不入此文件；骨架里有、文件里没有的主题视为「未学」。
只有后端写这个文件（ADR-0001）；写入由后续工单实现，本模块先提供读取与校验。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

Status = Literal["unlearned", "learning", "deferred", "claimed", "mastered"]

ARCHIVED_KEY = "archived"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Question(_Strict):
    concept: str
    stem: str
    options: list[str]
    answer: int
    picked: int | None = None
    explanations: list[str]


class Appeal(_Strict):
    question: int
    reason: str
    verdict: Literal["uphold", "overturn", "void"]
    explanation: str
    at: datetime


class Verification(_Strict):
    at: datetime
    conversation_id: str
    questions: list[Question]
    right: int
    denom: int
    passed: bool
    appeal: Appeal | None = None


class TopicState(_Strict):
    status: Status
    weak_points: list[str] = []
    verifications: list[Verification] = []
    updated_at: datetime


class State(BaseModel):
    """整份状态文件：现役主题的条目 + `archived` 段。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    topics: dict[str, TopicState] = {}
    archived: dict[str, TopicState] = {}

    def status_of(self, topic_id: str) -> Status:
        entry = self.topics.get(topic_id)
        return entry.status if entry else "unlearned"


class StateError(Exception):
    """状态文件不合法。`errors` 为 `(位置, 说明)` 列表。"""

    def __init__(self, source: str, errors: list[tuple[str, str]]) -> None:
        self.source = source
        self.errors = errors
        super().__init__(
            "\n".join(
                f"{source}: {loc}: {msg}" if loc else f"{source}: {msg}" for loc, msg in errors
            )
        )


def load_state(path: Path) -> State:
    """读取并校验 `state.json`；不合法抛 `StateError`。"""
    source = str(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateError(source, [("", f"无法读取：{exc.strerror}")]) from exc
    except json.JSONDecodeError as exc:
        raise StateError(
            source, [(f"第 {exc.lineno} 行第 {exc.colno} 列", f"JSON 语法错误：{exc.msg}")]
        ) from exc
    return parse_state(raw, source=source)


def parse_state(raw: object, *, source: str = "state.json") -> State:
    if not isinstance(raw, dict):
        raise StateError(source, [("", "顶层必须是对象（键为主题 id）")])
    data = dict(raw)
    archived = data.pop(ARCHIVED_KEY, {})
    try:
        # 走 JSON 模式：严格模式下 ISO 时间字符串只在 JSON 输入里被接受
        return State.model_validate_json(json.dumps({"topics": data, "archived": archived}))
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = list(err["loc"])
            if loc and loc[0] == "topics":
                loc = loc[1:]  # 文件里没有 topics 这一层
            errors.append((".".join(str(x) for x in loc), err["msg"]))
        raise StateError(source, errors) from exc
