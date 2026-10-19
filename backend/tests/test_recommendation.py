"""推荐卡：候选规则与六级字典序（规格「推荐」一节、工单 013）。

每条用例构造一份状态文件后请求 `/api/recommendation`；排序每一级各一个用例，
构造使得去掉该级规则时推荐会变成另一个主题。
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from theroadnottaken.app import create_app


def write_state(data_dir: Path, entries: dict[str, tuple[str, str]], **extra: object) -> None:
    """`entries`：主题 id → (状态, updated_at)。"""
    raw: dict[str, object] = {
        tid: {"status": status, "weak_points": [], "verifications": [], "updated_at": at}
        for tid, (status, at) in entries.items()
    }
    raw.update(extra)
    (data_dir / "state.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def recommend(client: TestClient) -> dict | None:
    resp = client.get("/api/recommendation")
    assert resp.status_code == 200
    return resp.json()["recommendation"]


def test_fresh_start_ties_are_broken_by_topic_id(client: TestClient) -> None:
    """三个初始前沿主题各解锁 1 个主题，前五级全平 → id 升序。"""
    rec = recommend(client)

    assert rec == {
        "topic": {
            "id": "c02-function-limit-continuity",
            "name": "函数极限与连续函数",
            "field": "c02",
            "field_name": "单变量微积分与数学分析基础",
            "concepts": ["ε-δ 定义", "单侧极限", "连续函数的局部性质", "间断点分类"],
            "status": "unlearned",
        },
        "kind": "learn",
        "reason": "它解锁 1 个主题",
        "was_deferred": False,
    }


OLD, MID, NEW = (
    "2026-10-01T10:00:00+00:00",
    "2026-10-02T10:00:00+00:00",
    "2026-10-03T10:00:00+00:00",
)
ALL_CORE = [
    "c02-function-limit-continuity",
    "c02-derivative-definition",
    "c04-gauss-elimination",
    "c04-eigenvalue-diagonalization",
    "c14-probability-space",
    "c14-continuous-random-variable",
]


def test_level1_claimed_verification_comes_before_learning(
    client: TestClient, data_dir: Path
) -> None:
    write_state(
        data_dir,
        {
            "c02-function-limit-continuity": ("learning", NEW),
            "c04-gauss-elimination": ("claimed", OLD),
        },
    )
    rec = recommend(client)

    assert (rec["topic"]["id"], rec["kind"]) == ("c04-gauss-elimination", "verify")
    assert rec["reason"] == "你声称掌握，先验证"


def test_claimed_topic_is_recommended_even_with_unmastered_prerequisites(
    client: TestClient, data_dir: Path
) -> None:
    write_state(data_dir, {"c04-eigenvalue-diagonalization": ("claimed", OLD)})
    rec = recommend(client)

    assert (rec["topic"]["id"], rec["kind"]) == ("c04-eigenvalue-diagonalization", "verify")


def test_level2_learning_comes_before_unlearned(client: TestClient, data_dir: Path) -> None:
    """不看本级时 c02 会凭 id 排在 c14 前。"""
    write_state(data_dir, {"c14-probability-space": ("learning", OLD)})
    rec = recommend(client)

    assert (rec["topic"]["id"], rec["kind"]) == ("c14-probability-space", "learn")
    assert rec["reason"] == "上次没学完"


def test_level3_core_comes_before_included_branch(client: TestClient, data_dir: Path) -> None:
    """候选只剩 c14 连续型与 b06 凸集：后继数相同、都不与最近领域（c04）同领域，b06 的 id 更小。"""
    mastered = {t: ("mastered", OLD) for t in ALL_CORE[:5]}
    mastered["c04-eigenvalue-diagonalization"] = ("mastered", NEW)
    write_state(data_dir, mastered, included_branches=["b06"])
    rec = recommend(client)

    assert rec["topic"]["id"] == "c14-continuous-random-variable"
    assert rec["reason"] == "主干优先于分支"


def test_level4_same_field_as_latest_change_comes_before_more_successors(
    client: TestClient, data_dir: Path
) -> None:
    """候选：c02 导数（2 个后继）、c04 特征值（1）、c14 概率空间（1）；最近掌握的是 c04 的消元。"""
    write_state(
        data_dir,
        {
            "c02-function-limit-continuity": ("mastered", OLD),
            "c04-gauss-elimination": ("mastered", NEW),
        },
    )
    rec = recommend(client)

    assert rec["topic"]["id"] == "c04-eigenvalue-diagonalization"
    assert rec["reason"] == "接着「线性代数 I：矩阵、方程组与几何直观」往下"


def test_latest_change_ignores_deferred(client: TestClient, data_dir: Path) -> None:
    """「最近一次状态变化」只算开始学习与验证通过；更晚的暂不学不改变领域连续。"""
    write_state(
        data_dir,
        {
            "c02-function-limit-continuity": ("mastered", OLD),
            "c04-gauss-elimination": ("mastered", MID),
            "c14-probability-space": ("deferred", NEW),
        },
    )
    rec = recommend(client)

    assert rec["topic"]["id"] == "c04-eigenvalue-diagonalization"


TINY_SKELETON = """\
version: 1
fields:
  - {id: c01, name: 小领域, kind: core, order: 1}
topics:
  - id: c01-a
    name: 甲
    field: c01
    concepts: [一, 二, 三]
    prerequisites: []
    history: h
    references: []
  - id: c01-b
    name: 乙
    field: c01
    concepts: [一, 二, 三]
    prerequisites: []
    history: h
    references: []
  - id: c01-c
    name: 丙
    field: c01
    concepts: [一, 二, 三]
    prerequisites: [c01-b]
    history: h
    references: []
  - id: c01-d
    name: 丁
    field: c01
    concepts: [一, 二, 三]
    prerequisites: [c01-b]
    history: h
    references: []
retired: []
"""


def test_level5_more_direct_successors_comes_first(tmp_path: Path) -> None:
    """甲（0 个后继）的 id 比乙（2 个后继）小；乙胜出。"""
    data_dir = tmp_path / "tiny"
    data_dir.mkdir()
    (data_dir / "skeleton.yaml").write_text(TINY_SKELETON, encoding="utf-8")
    with TestClient(create_app(data_dir=data_dir)) as client:
        rec = recommend(client)

    assert rec["topic"]["id"] == "c01-b"
    assert rec["reason"] == "它解锁 2 个主题"


def test_deferred_topics_stay_out_until_other_candidates_run_out(
    client: TestClient, data_dir: Path
) -> None:
    write_state(data_dir, {"c02-function-limit-continuity": ("deferred", NEW)})
    assert recommend(client)["topic"]["id"] == "c04-gauss-elimination"

    write_state(
        data_dir,
        {
            "c02-function-limit-continuity": ("deferred", NEW),
            "c04-gauss-elimination": ("deferred", NEW),
            "c14-probability-space": ("deferred", NEW),
        },
    )
    rec = recommend(client)
    assert rec["topic"]["id"] == "c02-function-limit-continuity"
    assert rec["was_deferred"] is True


def test_branch_topics_appear_only_when_the_branch_is_included(
    client: TestClient, data_dir: Path
) -> None:
    """全部主干已掌握，只剩分支 b06 的凸集可学。"""
    write_state(data_dir, {t: ("mastered", OLD) for t in ALL_CORE})
    resp = client.get("/api/recommendation").json()
    assert resp["recommendation"] is None

    write_state(data_dir, {t: ("mastered", OLD) for t in ALL_CORE}, included_branches=["b06"])
    assert recommend(client)["topic"]["id"] == "b06-convex-sets-functions"


def test_claimed_branch_topic_is_hidden_while_the_branch_is_off(
    client: TestClient, data_dir: Path
) -> None:
    write_state(data_dir, {"b06-convex-sets-functions": ("claimed", NEW)})
    assert recommend(client)["kind"] == "learn"


def test_no_candidates_and_nothing_deferred_shows_hint(client: TestClient, data_dir: Path) -> None:
    write_state(data_dir, {t: ("mastered", OLD) for t in ALL_CORE})
    body = client.get("/api/recommendation").json()

    assert body["recommendation"] is None
    assert "当前没有可学的主题" in body["hint"]
    assert "纳入推荐" in body["hint"] and "看板" in body["hint"]
