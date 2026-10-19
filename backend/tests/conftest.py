"""主缝夹具：真实 FastAPI 应用 + 临时数据目录（见规格 Testing Decisions）。"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theroadnottaken.app import create_app


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """每个测试一个空的临时数据目录。"""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def client(data_dir: Path, sample_skeleton: Path) -> Iterator[TestClient]:
    """指向临时数据目录的应用实例的 HTTP 客户端（不托管前端）；以样例骨架为种子。"""
    with TestClient(create_app(data_dir=data_dir, seed_skeleton=sample_skeleton)) as c:
        yield c


@pytest.fixture
def build_dir(tmp_path: Path) -> Path:
    """一份最小的前端构建产物：index.html + assets/app.js。"""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>shell</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


@pytest.fixture
def static_client(data_dir: Path, build_dir: Path, sample_skeleton: Path) -> Iterator[TestClient]:
    """同时托管前端构建产物的应用实例的 HTTP 客户端。"""
    app = create_app(data_dir=data_dir, static_dir=build_dir, seed_skeleton=sample_skeleton)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_skeleton() -> Path:
    """随仓库提交的样例骨架（7 个主题、含主干与分支、含跨领域前置），后续工单的测试都用它。"""
    return Path(__file__).parent / "fixtures" / "sample-skeleton.yaml"
