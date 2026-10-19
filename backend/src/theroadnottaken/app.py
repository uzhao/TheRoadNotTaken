"""FastAPI 应用工厂。所有测试与命令行入口都从这里创建应用实例。"""

from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

PACKAGE_NAME = "theroadnottaken"


def create_app(*, data_dir: Path, static_dir: Path | None = None) -> FastAPI:
    """创建指向指定数据目录的应用实例。

    `static_dir` 为前端构建产物目录（`frontend/dist`）；给定时后端同时托管它，
    并把非 `/api` 的未知路径回退到 `index.html` 供单页应用路由。
    """
    app = FastAPI(title=PACKAGE_NAME, version=version(PACKAGE_NAME))
    app.state.data_dir = data_dir

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "name": PACKAGE_NAME,
            "version": app.version,
            "data_dir": str(data_dir),
        }

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
