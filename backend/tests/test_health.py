from pathlib import Path

from fastapi.testclient import TestClient


def test_health_reports_name_version_and_data_dir(client: TestClient, data_dir: Path) -> None:
    resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "theroadnottaken"
    assert body["version"] == "0.1.0"
    assert body["data_dir"] == str(data_dir)
