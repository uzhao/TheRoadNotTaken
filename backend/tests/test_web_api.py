"""知识网的只读视图：领域（含进度）、主题（含状态、不可学与缺失前置）。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient


def write_state(data_dir: Path, statuses: dict[str, str]) -> None:
    entries = {
        tid: {
            "status": status,
            "weak_points": ["链式法则：忘了乘内层导数"] if status == "learning" else [],
            "verifications": [],
            "updated_at": "2026-10-01T10:00:00+00:00",
        }
        for tid, status in statuses.items()
    }
    (data_dir / "state.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


def test_fields_fresh_start_have_no_progress_and_core_comes_first(client: TestClient) -> None:
    body = client.get("/api/fields").json()

    assert body["mastered"] == 0
    assert body["total"] == 7
    assert [f["id"] for f in body["fields"]] == ["c02", "c04", "c14", "b06"]
    assert body["fields"][0] == {
        "id": "c02",
        "name": "单变量微积分与数学分析基础",
        "kind": "core",
        "order": 2,
        "total": 2,
        "mastered": 0,
        "learning": 0,
        "claimed": 0,
        "included": True,
    }


def test_fields_progress_reflects_state_file(client: TestClient, data_dir: Path) -> None:
    write_state(
        data_dir,
        {
            "c02-function-limit-continuity": "mastered",
            "c02-derivative-definition": "learning",
            "c04-gauss-elimination": "claimed",
        },
    )
    body = client.get("/api/fields").json()

    assert body["mastered"] == 1
    by_id = {f["id"]: f for f in body["fields"]}
    c02, c04 = by_id["c02"], by_id["c04"]
    assert (c02["mastered"], c02["learning"], c02["claimed"]) == (1, 1, 0)
    assert (c04["mastered"], c04["learning"], c04["claimed"]) == (0, 0, 1)


def test_topics_of_a_field_with_status_lock_and_missing_prerequisites(
    client: TestClient, data_dir: Path
) -> None:
    write_state(
        data_dir,
        {
            "c14-probability-space": "mastered",
            "c02-function-limit-continuity": "mastered",
            "c02-derivative-definition": "learning",
        },
    )
    topics = client.get("/api/topics", params={"field": "c14"}).json()["topics"]

    assert [t["id"] for t in topics] == [
        "c14-probability-space",
        "c14-continuous-random-variable",
    ]
    space, continuous = topics
    assert space["status"] == "mastered"
    assert space["locked"] is False
    assert space["missing_prerequisites"] == []
    # 跨领域前置「导数」仍在学习中 → 不可学，并指出缺哪个
    assert continuous == {
        "id": "c14-continuous-random-variable",
        "name": "连续型随机变量与密度函数",
        "field": "c14",
        "concepts": ["概率密度函数", "均匀分布与指数分布", "正态分布", "随机变量函数的分布变换"],
        "prerequisites": ["c14-probability-space", "c02-derivative-definition"],
        "status": "unlearned",
        "weak_points": [],
        "locked": True,
        "missing_prerequisites": [
            {"id": "c02-derivative-definition", "name": "导数、微分与求导法则"}
        ],
    }


def test_claimed_topic_is_not_locked_even_with_unmastered_prerequisites(
    client: TestClient, data_dir: Path
) -> None:
    """声称掌握的主题下一步是验证，不看前置（规格的候选规则），但仍列出缺的前置。"""
    write_state(data_dir, {"c04-eigenvalue-diagonalization": "claimed"})
    resp = client.get("/api/topics", params={"field": "c04"})
    topics = {t["id"]: t for t in resp.json()["topics"]}

    eigen = topics["c04-eigenvalue-diagonalization"]
    assert eigen["status"] == "claimed"
    assert eigen["locked"] is False
    assert eigen["missing_prerequisites"] == [
        {"id": "c04-gauss-elimination", "name": "线性方程组与 Gauss 消元法"}
    ]


def test_topics_unlocked_when_all_prerequisites_mastered(
    client: TestClient, data_dir: Path
) -> None:
    write_state(
        data_dir,
        {"c02-function-limit-continuity": "mastered", "c02-derivative-definition": "learning"},
    )
    resp = client.get("/api/topics", params={"field": "c02"})
    topics = {t["id"]: t for t in resp.json()["topics"]}

    assert topics["c02-function-limit-continuity"]["locked"] is False  # 初始前沿
    derivative = topics["c02-derivative-definition"]
    assert derivative["locked"] is False
    assert derivative["missing_prerequisites"] == []
    assert derivative["weak_points"] == ["链式法则：忘了乘内层导数"]


def test_topics_without_field_filter_returns_all(client: TestClient) -> None:
    topics = client.get("/api/topics").json()["topics"]
    assert len(topics) == 7
    assert topics[-1]["field"] == "b06"


def test_unknown_field_is_404(client: TestClient) -> None:
    resp = client.get("/api/topics", params={"field": "c99"})
    assert resp.status_code == 404
    assert "c99" in resp.json()["detail"]
