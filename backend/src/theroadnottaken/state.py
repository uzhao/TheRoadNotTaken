"""掌握状态文件 `state.json` 的 schema 与读取（见规格「数据目录」一节与 GLOSSARY「掌握状态」）。

键为主题 id，每项含状态、薄弱点、验证记录与更新时间；退役主题的条目移入 `archived` 段；
保留键 `included_branches` 列出开启了「纳入推荐」的分支领域 id（缺省为空：分支默认不参与推荐）。
高中数学不入此文件；骨架里有、文件里没有的主题视为「未学」。
只有后端写这个文件（ADR-0001）：写前按同一 schema 校验，写到同目录的临时文件再原子改名，
因此任何时刻文件要么是旧版、要么是新版，不会出现半个 JSON。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

Status = Literal["unlearned", "learning", "deferred", "claimed", "mastered"]

ARCHIVED_KEY = "archived"
INCLUDED_BRANCHES_KEY = "included_branches"


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
    included_branches: list[str] = []

    def recommends_field(self, field_id: str, kind: str) -> bool:
        """领域是否参与推荐：主干恒参与，分支看「纳入推荐」开关。"""
        return kind == "core" or field_id in self.included_branches

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
    included = data.pop(INCLUDED_BRANCHES_KEY, [])
    try:
        # 走 JSON 模式：严格模式下 ISO 时间字符串只在 JSON 输入里被接受
        return State.model_validate_json(
            json.dumps({"topics": data, "archived": archived, "included_branches": included})
        )
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = list(err["loc"])
            if loc and loc[0] == "topics":
                loc = loc[1:]  # 文件里没有 topics 这一层
            errors.append((".".join(str(x) for x in loc), err["msg"]))
        raise StateError(source, errors) from exc


def dump_state(state: State) -> str:
    """文件形态：主题条目在顶层，`archived` 与 `included_branches` 仅在非空时写出。"""
    raw: dict[str, object] = {
        tid: entry.model_dump(mode="json") for tid, entry in state.topics.items()
    }
    if state.archived:
        raw[ARCHIVED_KEY] = {tid: e.model_dump(mode="json") for tid, e in state.archived.items()}
    if state.included_branches:
        raw[INCLUDED_BRANCHES_KEY] = list(state.included_branches)
    return json.dumps(raw, ensure_ascii=False, indent=2) + "\n"


def save_state(path: Path, state: State) -> None:
    """校验后写临时文件并原子替换 `path`；中途失败时原文件不变、临时文件被清理。"""
    text = dump_state(state)
    parse_state(json.loads(text), source=str(path))  # 写前校验：写出的内容必须能被读回
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
