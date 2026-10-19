"""知识网页的 API：领域侧栏、主题看板、推荐卡与学习者的状态操作（规格用户故事 1、2、5、11–19、46）。

视图把骨架（启动时读入）与状态文件（每次请求读取）合在一起：
- 领域：名称、主干/分支、主题数与已掌握 / 学习中 / 声称掌握计数（侧栏三色进度条）。
- 主题：名称、概念提纲、状态、薄弱点，以及「不可学」——有直接前置尚未掌握，并列出缺哪些。
  声称掌握的主题下一步是验证而非学习（规格的候选规则不看它的前置），故不算不可学。
- 推荐：唯一一张推荐卡（见 `recommend`），没有候选时给出提示。
- 写操作：主题的四个状态操作（见 `actions`）与分支领域的「纳入推荐」开关，
  每次经 `DataDir.update_state` 原子写入并提交 git。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from theroadnottaken import actions
from theroadnottaken.datadir import DataDir
from theroadnottaken.recommend import EMPTY_HINT, recommend
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
    included: bool  # 是否参与推荐：主干恒为真，分支看「纳入推荐」开关


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


class RecommendedTopic(BaseModel):
    id: str
    name: str
    field: str
    field_name: str
    concepts: list[str]
    status: Status


class RecommendationView(BaseModel):
    topic: RecommendedTopic
    kind: Literal["learn", "verify"]
    reason: str
    was_deferred: bool


class RecommendationResponse(BaseModel):
    recommendation: RecommendationView | None
    hint: str | None  # 没有推荐时的提示


class IncludedRequest(BaseModel):
    included: bool


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


@router.get("/recommendation")
def get_recommendation(request: Request) -> RecommendationResponse:
    store = _store(request)
    state = store.read_state()
    rec = recommend(store.skeleton, state)
    if rec is None:
        return RecommendationResponse(recommendation=None, hint=EMPTY_HINT)
    field_name = next(f.name for f in store.skeleton.fields if f.id == rec.topic.field)
    return RecommendationResponse(
        recommendation=RecommendationView(
            topic=RecommendedTopic(
                id=rec.topic.id,
                name=rec.topic.name,
                field=rec.topic.field,
                field_name=field_name,
                concepts=list(rec.topic.concepts),
                status=state.status_of(rec.topic.id),
            ),
            kind=rec.kind,
            reason=rec.reason,
            was_deferred=rec.was_deferred,
        ),
        hint=None,
    )


@router.post("/topics/{topic_id}/{action}")
def topic_action(request: Request, topic_id: str, action: actions.Action) -> TopicView:
    store = _store(request)
    topic = next((t for t in store.skeleton.topics if t.id == topic_id), None)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"主题不存在：{topic_id}")
    try:
        state = store.update_state(lambda s: actions.apply(s, topic, action))
    except actions.TransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return topic_view(store.skeleton, state, topic)


@router.put("/fields/{field_id}/included")
def set_included(request: Request, field_id: str, body: IncludedRequest) -> FieldView:
    store = _store(request)
    f = next((f for f in store.skeleton.fields if f.id == field_id), None)
    if f is None:
        raise HTTPException(status_code=404, detail=f"领域不存在：{field_id}")
    if f.kind != "branch":
        raise HTTPException(status_code=400, detail=f"主干领域恒参与推荐：{f.name}")

    def change(state: State) -> tuple[State, str]:
        rest = [b for b in state.included_branches if b != field_id]
        included = [*rest, field_id] if body.included else rest
        verb = "纳入推荐" if body.included else "取消纳入推荐"
        return state.model_copy(
            update={"included_branches": included}
        ), f"{verb}：{f.name}（{f.id}）"

    state = store.update_state(change)
    return field_view(store.skeleton, state, f)


def fields_view(store: DataDir, state: State) -> FieldsResponse:
    views = [field_view(store.skeleton, state, f) for f in fields_ordered(store.skeleton)]
    return FieldsResponse(
        fields=views,
        mastered=sum(v.mastered for v in views),
        total=sum(v.total for v in views),
    )


def field_view(sk: Skeleton, state: State, f: Field) -> FieldView:
    statuses = [state.status_of(t.id) for t in topics_in_field(sk, f.id)]
    return FieldView(
        id=f.id,
        name=f.name,
        kind=f.kind,
        order=f.order,
        total=len(statuses),
        mastered=statuses.count("mastered"),
        learning=statuses.count("learning"),
        claimed=statuses.count("claimed"),
        included=f.kind == "core" or f.id in state.included_branches,
    )


def topics_view(store: DataDir, state: State, field: str | None) -> list[TopicView]:
    sk = store.skeleton
    topics = topics_in_field(sk, field) if field is not None else list(sk.topics)
    return [topic_view(sk, state, t) for t in topics]


def topic_view(sk: Skeleton, state: State, t: Topic) -> TopicView:
    by_id = {x.id: x for x in sk.topics}
    status = state.status_of(t.id)
    missing = [
        PrerequisiteRef(id=p, name=by_id[p].name)
        for p in t.prerequisites
        if state.status_of(p) != "mastered"
    ]
    entry = state.topics.get(t.id)
    return TopicView(
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


def fields_ordered(sk: Skeleton) -> list[Field]:
    """主干在前、分支在后，各按 `order` 升序（与校验脚本的前置清单同序）。"""
    return sorted(sk.fields, key=lambda f: (f.kind != "core", f.order, f.id))


def topics_in_field(sk: Skeleton, field_id: str) -> list[Topic]:
    """领域内主题按骨架列表顺序。"""
    return [t for t in sk.topics if t.field == field_id]
