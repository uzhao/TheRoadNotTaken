"""FastAPI 应用工厂。所有测试与命令行入口都从这里创建应用实例。"""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from theroadnottaken import agy, agy_permissions
from theroadnottaken.datadir import JOBS_DIR, open_data_dir
from theroadnottaken.jobs import Job, JobRunner, JobSpec
from theroadnottaken.web import router as web_router

PACKAGE_NAME = "theroadnottaken"

# 仓库内的种子骨架：backend/src/theroadnottaken/app.py → 仓库根 / seed / skeleton.yaml
SEED_SKELETON = Path(__file__).resolve().parents[3] / "seed" / "skeleton.yaml"

log = logging.getLogger(__name__)

# 「重试连接」用的最小调用
PING_PROMPT = "只回复两个字母：OK"
PING_TIMEOUT = 60.0


class CreateJob(BaseModel):
    kind: Literal["ping"]


def create_app(
    *,
    data_dir: Path,
    static_dir: Path | None = None,
    seed_skeleton: Path | None = None,
    agy_settings: Path | None = None,
) -> FastAPI:
    """创建指向指定数据目录的应用实例。

    首次启动时用 `seed_skeleton` 初始化数据目录；骨架或状态文件不合法抛 `StartupError`。
    `agy_settings` 为 agy 全局 settings 的位置（缺省 `~/.gemini/antigravity-cli/settings.json`）。
    `static_dir` 为前端构建产物目录（`frontend/dist`）；给定时后端同时托管它，
    并把非 `/api` 的未知路径回退到 `index.html` 供单页应用路由。
    """
    store = open_data_dir(data_dir, seed_skeleton or SEED_SKELETON)
    jobs = JobRunner(data_dir / JOBS_DIR, store)

    settings_path = agy_settings or agy_permissions.DEFAULT_SETTINGS

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        permissions = agy_permissions.status(settings_path)
        if not permissions["ok"]:
            log.warning(
                "agy 权限规则缺失：%s（%s）",
                ", ".join(permissions["missing"]),
                permissions["error"] or permissions["settings_path"],
            )
        yield
        await jobs.shutdown()

    app = FastAPI(title=PACKAGE_NAME, version=version(PACKAGE_NAME), lifespan=lifespan)
    app.state.data_dir = data_dir
    app.state.store = store
    app.state.jobs = jobs

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "name": PACKAGE_NAME,
            "version": app.version,
            "data_dir": str(data_dir),
        }

    app.include_router(web_router)

    def find_job(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return job

    @app.post("/api/jobs", status_code=201)
    async def create_job(body: CreateJob) -> dict:
        spec = JobSpec(
            kind=body.kind,
            invocation=agy.Invocation(prompt=PING_PROMPT, effort="medium"),
            timeout=PING_TIMEOUT,
            delete_dir_on_success=True,
        )
        return jobs.submit(spec).snapshot()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        return find_job(job_id).snapshot()

    @app.get("/api/jobs/{job_id}/events")
    def job_events(
        job_id: str, last_event_id: int = Header(default=0, alias="Last-Event-ID")
    ) -> StreamingResponse:
        job = find_job(job_id)

        async def stream() -> AsyncIterator[str]:
            async for event in jobs.events(job, after=last_event_id):
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"id: {event['id']}\nevent: {event['event']}\ndata: {data}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.delete("/api/jobs/{job_id}", status_code=204)
    async def cancel_job(job_id: str) -> Response:
        job = find_job(job_id)
        if job.finished:
            raise HTTPException(status_code=409, detail="任务已结束")
        await jobs.cancel(job)
        return Response(status_code=204)

    @app.get("/api/agy/permissions")
    def permissions() -> dict:
        return agy_permissions.status(settings_path)

    @app.post("/api/agy/permissions")
    def write_permissions() -> dict:
        try:
            agy_permissions.add_missing_rules(settings_path)
        except agy_permissions.SettingsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return agy_permissions.status(settings_path)

    if static_dir is not None:
        _mount_frontend(app, static_dir)

    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    static = StaticFiles(directory=static_dir)

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str, request: Request):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        try:
            return await static.get_response(path, request.scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        return FileResponse(index)
