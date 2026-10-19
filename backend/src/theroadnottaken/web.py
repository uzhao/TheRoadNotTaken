"""知识网的只读视图：领域侧栏与主题看板需要的数据（规格用户故事 1、2、5）。

视图把骨架（启动时读入）与状态文件（每次请求读取）合在一起：
- 领域：名称、主干/分支、主题数与已掌握 / 学习中 / 声称掌握计数（侧栏三色进度条）。
- 主题：名称、概念提纲、状态、薄弱点，以及「不可学」——有直接前置尚未掌握，并列出缺哪些。
  声称掌握的主题下一步是验证而非学习（规格的候选规则不看它的前置），故不算不可学。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from theroadnottaken.datadir import DataDir
from theroadnottaken.skeleton import Field, Skeleton, Topic
from theroadnottaken.state import State, Status

router = APIRouter(prefix="/api")


class FieldView(BaseModel):
    id: str
    name: str
    kind: Literal["core", "branch"]
    order: int
    total: int
    mastered: int
    learning: int
    claimed: int


class FieldsResponse(BaseModel):
    fields: list[FieldView]
    mastered: int
    total: int


class PrerequisiteRef(BaseModel):
    id: str
    name: str


class TopicView(BaseModel):
    id: str
    name: str
    field: str
    concepts: list[str]
    prerequisites: list[str]
    status: Status
    weak_points: list[str]
    locked: bool
    missing_prerequisites: list[PrerequisiteRef]


class TopicsResponse(BaseModel):
    topics: list[TopicView]


def _store(request: Request) -> DataDir:
    return request.app.state.store


@router.get("/fields")
def list_fields(request: Request) -> FieldsResponse:
    store = _store(request)
    return fields_view(store, store.read_state())


@router.get("/topics")
def list_topics(request: Request, field: str | None = Query(default=None)) -> TopicsResponse:
    store = _store(request)
    if field is not None and all(f.id != field for f in store.skeleton.fields):
        raise HTTPException(status_code=404, detail=f"领域不存在：{field}")
    return TopicsResponse(topics=topics_view(store, store.read_state(), field))


def fields_view(store: DataDir, state: State) -> FieldsResponse:
    views: list[FieldView] = []
    for f in fields_ordered(store.skeleton):
        statuses = [state.status_of(t.id) for t in topics_in_field(store.skeleton, f.id)]
        views.append(
            FieldView(
                id=f.id,
                name=f.name,
                kind=f.kind,
                order=f.order,
                total=len(statuses),
                mastered=statuses.count("mastered"),
                learning=statuses.count("learning"),
                claimed=statuses.count("claimed"),
            )
        )
    return FieldsResponse(
        fields=views,
        mastered=sum(v.mastered for v in views),
        total=sum(v.total for v in views),
    )


def topics_view(store: DataDir, state: State, field: str | None) -> list[TopicView]:
    sk = store.skeleton
    by_id = {t.id: t for t in sk.topics}
    topics = topics_in_field(sk, field) if field is not None else list(sk.topics)
    views: list[TopicView] = []
    for t in topics:
        status = state.status_of(t.id)
        missing = [
            PrerequisiteRef(id=p, name=by_id[p].name)
            for p in t.prerequisites
            if state.status_of(p) != "mastered"
        ]
        entry = state.topics.get(t.id)
        views.append(
            TopicView(
                id=t.id,
                name=t.name,
                field=t.field,
                concepts=list(t.concepts),
                prerequisites=list(t.prerequisites),
                status=status,
                weak_points=entry.weak_points if entry else [],
                locked=status in ("unlearned", "learning", "deferred") and bool(missing),
                missing_prerequisites=missing,
            )
        )
    return views


def fields_ordered(sk: Skeleton) -> list[Field]:
    """主干在前、分支在后，各按 `order` 升序（与校验脚本的前置清单同序）。"""
    return sorted(sk.fields, key=lambda f: (f.kind != "core", f.order, f.id))


def topics_in_field(sk: Skeleton, field_id: str) -> list[Topic]:
    """领域内主题按骨架列表顺序。"""
    return [t for t in sk.topics if t.field == field_id]
