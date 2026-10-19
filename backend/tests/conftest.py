"""主缝夹具：真实 FastAPI 应用 + 假 agy + 临时数据目录（见规格 Testing Decisions）。"""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import agy_steps
import pytest
from fastapi.testclient import TestClient

from theroadnottaken.app import create_app

FAKE_AGY = Path(__file__).with_name("fake_agy.py")


class FakeAgy:
    """`PATH` 前置的假 agy：`script()` 设定每次调用的场景，`calls()` 读回收到的调用。"""

    def __init__(self, root: Path) -> None:
        self.bin_dir = root / "bin"
        self.scenario = root / "scenario.json"
        self.log = root / "calls.jsonl"
        self.bin_dir.mkdir(parents=True)
        exe = self.bin_dir / "agy"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_AGY}" "$@"\n', encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
        self.script(agy_steps.ok())

    def script(self, *runs: dict) -> None:
        self.scenario.write_text(json.dumps({"runs": list(runs)}), encoding="utf-8")

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def fake_agy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeAgy:
    fake = FakeAgy(tmp_path / "fake-agy")
    monkeypatch.setenv("PATH", f"{fake.bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_AGY_SCENARIO", str(fake.scenario))
    monkeypatch.setenv("FAKE_AGY_LOG", str(fake.log))
    return fake


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """每个测试一个空的临时数据目录。"""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def agy_settings(tmp_path: Path) -> Path:
    """agy 全局 settings 的位置（缺省不存在），代替 `~/.gemini/antigravity-cli/settings.json`。"""
    return tmp_path / "gemini" / "antigravity-cli" / "settings.json"


@pytest.fixture
def client(
    data_dir: Path, sample_skeleton: Path, agy_settings: Path, fake_agy: FakeAgy
) -> Iterator[TestClient]:
    """指向临时数据目录与假 agy 的应用实例的 HTTP 客户端（不托管前端）；以样例骨架为种子。"""
    app = create_app(data_dir=data_dir, seed_skeleton=sample_skeleton, agy_settings=agy_settings)
    with TestClient(app) as c:
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
def static_client(
    data_dir: Path, build_dir: Path, sample_skeleton: Path, agy_settings: Path, fake_agy: FakeAgy
) -> Iterator[TestClient]:
    """同时托管前端构建产物的应用实例的 HTTP 客户端。"""
    app = create_app(
        data_dir=data_dir,
        static_dir=build_dir,
        seed_skeleton=sample_skeleton,
        agy_settings=agy_settings,
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_skeleton() -> Path:
    """随仓库提交的样例骨架（7 个主题、含主干与分支、含跨领域前置），后续工单的测试都用它。"""
    return Path(__file__).parent / "fixtures" / "sample-skeleton.yaml"
