"""FastAPI 应用工厂。所有测试与命令行入口都从这里创建应用实例。"""

from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from theroadnottaken.datadir import open_data_dir
from theroadnottaken.web import router as web_router

PACKAGE_NAME = "theroadnottaken"

# 仓库内的种子骨架：backend/src/theroadnottaken/app.py → 仓库根 / seed / skeleton.yaml
SEED_SKELETON = Path(__file__).resolve().parents[3] / "seed" / "skeleton.yaml"


def create_app(
    *, data_dir: Path, static_dir: Path | None = None, seed_skeleton: Path | None = None
) -> FastAPI:
    """创建指向指定数据目录的应用实例。

    首次启动时用 `seed_skeleton` 初始化数据目录；骨架或状态文件不合法抛 `StartupError`。
    `static_dir` 为前端构建产物目录（`frontend/dist`）；给定时后端同时托管它，
    并把非 `/api` 的未知路径回退到 `index.html` 供单页应用路由。
    """
    store = open_data_dir(data_dir, seed_skeleton or SEED_SKELETON)
    app = FastAPI(title=PACKAGE_NAME, version=version(PACKAGE_NAME))
    app.state.data_dir = data_dir
    app.state.store = store

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "name": PACKAGE_NAME,
            "version": app.version,
            "data_dir": str(data_dir),
        }

    app.include_router(web_router)

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
