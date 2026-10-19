"""命令行入口：一条命令启动后端并托管前端构建产物。

数据目录来自 `--data-dir` 参数，其次环境变量 `ROAD_DATA_DIR`，缺省为 `~/.theroadnottaken`。
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import uvicorn

from theroadnottaken.app import create_app

DATA_DIR_ENV = "ROAD_DATA_DIR"
DEFAULT_DATA_DIR_NAME = ".theroadnottaken"

# 仓库内前端构建产物的位置：backend/src/theroadnottaken/cli.py → 仓库根 / frontend / dist
REPO_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    static_dir: Path | None
    host: str
    port: int

    @classmethod
    def parse(cls, argv: Sequence[str], env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        parser = argparse.ArgumentParser(prog="theroadnottaken", description=__doc__)
        parser.add_argument(
            "--data-dir",
            type=Path,
            default=None,
            help=f"数据目录（缺省取环境变量 {DATA_DIR_ENV}，再缺省为 ~/{DEFAULT_DATA_DIR_NAME}）",
        )
        parser.add_argument(
            "--static-dir",
            type=Path,
            default=None,
            help="前端构建产物目录（缺省为仓库内 frontend/dist，不存在则只提供 API）",
        )
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8000)
        args = parser.parse_args(argv)

        data_dir = args.data_dir
        if data_dir is None and env.get(DATA_DIR_ENV):
            data_dir = Path(env[DATA_DIR_ENV])
        if data_dir is None:
            home = Path(env["HOME"]) if env.get("HOME") else Path.home()
            data_dir = home / DEFAULT_DATA_DIR_NAME

        static_dir = args.static_dir
        if static_dir is None and REPO_FRONTEND_DIST.is_dir():
            static_dir = REPO_FRONTEND_DIST

        return cls(
            data_dir=data_dir.expanduser(), static_dir=static_dir, host=args.host, port=args.port
        )


def main(argv: Sequence[str] | None = None) -> None:
    settings = Settings.parse(argv if argv is not None else sys.argv[1:])
    app = create_app(data_dir=settings.data_dir, static_dir=settings.static_dir)
    print(f"数据目录：{settings.data_dir}")
    if settings.static_dir is None:
        print("未找到前端构建产物，只提供 API（先运行 pnpm --dir frontend build）")
    uvicorn.run(app, host=settings.host, port=settings.port)
