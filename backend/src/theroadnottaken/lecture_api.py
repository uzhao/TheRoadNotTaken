"""学习页的 API：开始学习、读讲义缓存、插图静态路由。

- `POST /api/lectures/{主题id}`：开始学习。未学 / 暂不学 → 学习中（提交 git）；有缓存直接返回讲义，
  不启动 agy；否则提交讲义任务（同一主题已有在跑的就返回它），前端经任务事件流看生成过程。
- `GET /api/lectures/{主题id}`：只读——主题（状态与薄弱点）、缓存的讲义、在跑的讲义任务。
- `GET /api/lectures/{主题id}/figures/{文件名}`：讲义插图；只服务 `lectures/<主题id>/figures/`
  下的 svg / png，越界或不存在一律 404。前端用 `<img>` 引用，不内联 SVG。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from theroadnottaken import actions
from theroadnottaken.datadir import DataDir
from theroadnottaken.lecture import FIGURE_NAME_RE, FIGURES_DIR, Lectures
from theroadnottaken.skeleton import Topic
from theroadnottaken.state import State
from theroadnottaken.web import TopicView, topic_view

router = APIRouter(prefix="/api/lectures")

MEDIA_TYPES = {".svg": "image/svg+xml", ".png": "image/png"}
# 直接打开插图地址时也不让 SVG 里的脚本或外链生效
FIGURE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
}


class LectureView(BaseModel):
    markdown: str
    meta: dict[str, Any]


class LecturePage(BaseModel):
    topic: TopicView
    lecture: LectureView | None
    job: dict[str, Any] | None  # 在跑的讲义任务（任务快照）


def _store(request: Request) -> DataDir:
    return request.app.state.store


def _lectures(request: Request) -> Lectures:
    return request.app.state.lectures


def _topic(store: DataDir, topic_id: str) -> Topic:
    topic = next((t for t in store.skeleton.topics if t.id == topic_id), None)
    if topic is None:
        raise HTTPException(status_code=404, detail=f"主题不存在：{topic_id}")
    return topic


def _page(request: Request, topic: Topic, state: State) -> LecturePage:
    lectures = _lectures(request)
    cached = lectures.cached(topic.id)
    job = lectures.running(topic.id)
    return LecturePage(
        topic=topic_view(_store(request).skeleton, state, topic),
        lecture=LectureView(**cached) if cached else None,
        job=job.snapshot() if job else None,
    )


@router.post("/{topic_id}")
async def start_learning(request: Request, topic_id: str) -> LecturePage:
    store = _store(request)
    topic = _topic(store, topic_id)
    state = store.read_state()
    view = topic_view(store.skeleton, state, topic)
    if view.locked and state.status_of(topic.id) in actions.START_FROM:
        missing = "、".join(p.name for p in view.missing_prerequisites)
        raise HTTPException(status_code=409, detail=f"「{topic.name}」前置未掌握：{missing}")
    # 写状态文件并提交 git，放到线程里免得卡住事件循环
    state = await asyncio.to_thread(store.update_state, lambda s: actions.start(s, topic))
    lectures = _lectures(request)
    if lectures.cached(topic.id) is None:
        lectures.generate(topic, state)
    return _page(request, topic, state)


@router.get("/{topic_id}")
def get_lecture(request: Request, topic_id: str) -> LecturePage:
    store = _store(request)
    topic = _topic(store, topic_id)
    return _page(request, topic, store.read_state())


@router.get("/{topic_id}/figures/{name:path}")
def get_figure(request: Request, topic_id: str, name: str) -> FileResponse:
    topic = _topic(_store(request), topic_id)
    figures = (_lectures(request).lecture_dir(topic.id) / FIGURES_DIR).resolve()
    suffix = name[name.rfind(".") :].lower() if "." in name else ""
    if not FIGURE_NAME_RE.match(name) or suffix not in MEDIA_TYPES:
        raise HTTPException(status_code=404, detail="插图不存在")
    path = (figures / name).resolve()
    if path.parent != figures or not path.is_file():
        raise HTTPException(status_code=404, detail="插图不存在")
    return FileResponse(path, media_type=MEDIA_TYPES[suffix], headers=FIGURE_HEADERS)
