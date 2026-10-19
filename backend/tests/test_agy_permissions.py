"""agy 全局 settings 的 allow 规则：缺失时报告并给出片段，确认后追加且不覆盖其它键。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theroadnottaken.app import create_app

REQUIRED = ["command(python3)", "command(python3 *)", "command(mkdir)", "write_file(*)"]


def test_missing_settings_file_reports_all_rules_with_snippet(
    client: TestClient, agy_settings: Path
) -> None:
    body = client.get("/api/agy/permissions").json()

    assert body["ok"] is False
    assert body["missing"] == REQUIRED
    assert body["settings_path"] == str(agy_settings)
    assert json.loads(body["snippet"]) == {"permissions": {"allow": REQUIRED}}


def test_partially_configured_settings_report_only_missing_rules(
    client: TestClient, agy_settings: Path
) -> None:
    agy_settings.parent.mkdir(parents=True)
    agy_settings.write_text(
        json.dumps({"permissions": {"allow": ["command(python3)", "write_file(*)"]}})
    )

    body = client.get("/api/agy/permissions").json()

    assert body["missing"] == ["command(python3 *)", "command(mkdir)"]


def test_complete_settings_are_ok(client: TestClient, agy_settings: Path) -> None:
    agy_settings.parent.mkdir(parents=True)
    agy_settings.write_text(json.dumps({"permissions": {"allow": ["command(go)", *REQUIRED]}}))

    body = client.get("/api/agy/permissions").json()

    assert body["ok"] is True
    assert body["missing"] == []


def test_writing_rules_appends_without_touching_other_keys(
    client: TestClient, agy_settings: Path
) -> None:
    agy_settings.parent.mkdir(parents=True)
    original = {
        "model": "gemini-4-argon",
        "statusLine": {"enabled": True},
        "permissions": {"allow": ["command(go test -v *)", "command(mkdir)"], "deny": ["x"]},
    }
    agy_settings.write_text(json.dumps(original))

    resp = client.post("/api/agy/permissions")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert json.loads(agy_settings.read_text()) == {
        "model": "gemini-4-argon",
        "statusLine": {"enabled": True},
        "permissions": {
            "allow": [
                "command(go test -v *)",
                "command(mkdir)",
                "command(python3)",
                "command(python3 *)",
                "write_file(*)",
            ],
            "deny": ["x"],
        },
    }


def test_writing_rules_creates_missing_settings_file(
    client: TestClient, agy_settings: Path
) -> None:
    client.post("/api/agy/permissions")

    assert json.loads(agy_settings.read_text()) == {"permissions": {"allow": REQUIRED}}


def test_unparseable_settings_are_reported_and_never_overwritten(
    client: TestClient, agy_settings: Path
) -> None:
    agy_settings.parent.mkdir(parents=True)
    agy_settings.write_text("{not json")

    assert client.get("/api/agy/permissions").json()["error"]
    assert client.post("/api/agy/permissions").status_code == 409
    assert agy_settings.read_text() == "{not json"


def test_startup_warns_when_rules_are_missing(
    data_dir: Path, agy_settings: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with TestClient(create_app(data_dir=data_dir, agy_settings=agy_settings)):
        pass

    assert "agy 权限规则缺失" in caplog.text
    assert "command(mkdir)" in caplog.text
