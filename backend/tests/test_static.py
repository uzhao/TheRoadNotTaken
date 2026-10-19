from fastapi.testclient import TestClient


def test_serves_frontend_build_at_root(static_client: TestClient) -> None:
    assert static_client.get("/").text == "<!doctype html><title>shell</title>"
    assert static_client.get("/assets/app.js").text == "console.log(1)"


def test_unknown_page_falls_back_to_index_for_spa_routing(static_client: TestClient) -> None:
    resp = static_client.get("/learn/c02-derivative-definition")
    assert resp.status_code == 200
    assert resp.text == "<!doctype html><title>shell</title>"


def test_unknown_api_path_is_404_not_index(static_client: TestClient) -> None:
    assert static_client.get("/api/nope").status_code == 404


def test_without_build_dir_root_is_404_but_api_works(client: TestClient) -> None:
    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
