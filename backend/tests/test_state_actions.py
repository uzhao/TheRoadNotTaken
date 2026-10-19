"""学习者的状态操作与「纳入推荐」开关：只改目标、更新时间、人可读的 git 提交、原子写入。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

OLD = "2026-10-01T10:00:00+00:00"
LIMIT = "c02-function-limit-continuity"
GAUSS = "c04-gauss-elimination"


def write_state(data_dir: Path, entries: dict[str, str]) -> None:
    raw = {
        tid: {
            "status": status,
            "weak_points": ["ε-δ 定义：把 δ 写成了依赖 x"] if status == "learning" else [],
            "verifications": [],
            "updated_at": OLD,
        }
        for tid, status in entries.items()
    }
    (data_dir / "state.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def read_state(data_dir: Path) -> dict:
    return json.loads((data_dir / "state.json").read_text(encoding="utf-8"))


def others(state: dict) -> dict:
    """除目标外的条目；时间按值比较（写回时 `+00:00` 会规范为 `Z`）。"""
    return {
        k: {**v, "updated_at": datetime.fromisoformat(v["updated_at"])}
        for k, v in state.items()
        if k != LIMIT
    }


def last_commit(data_dir: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(data_dir), "log", "-1", "--format=%s"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def worktree_clean(data_dir: Path) -> bool:
    out = subprocess.run(
        ["git", "-C", str(data_dir), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out == ""


@pytest.mark.parametrize(
    ("before", "action", "after", "message"),
    [
        (
            "unlearned",
            "claim",
            "claimed",
            "我已掌握：函数极限与连续函数（c02-function-limit-continuity）未学 → 声称掌握",
        ),
        (
            "learning",
            "claim",
            "claimed",
            "我已掌握：函数极限与连续函数（c02-function-limit-continuity）学习中 → 声称掌握",
        ),
        (
            "claimed",
            "unclaim",
            "unlearned",
            "其实没学过：函数极限与连续函数（c02-function-limit-continuity）声称掌握 → 未学",
        ),
        (
            "learning",
            "defer",
            "deferred",
            "暂不学：函数极限与连续函数（c02-function-limit-continuity）学习中 → 暂不学",
        ),
        (
            "deferred",
            "restore",
            "unlearned",
            "恢复推荐：函数极限与连续函数（c02-function-limit-continuity）暂不学 → 未学",
        ),
    ],
)
def test_action_changes_only_the_target_and_commits(
    client: TestClient, data_dir: Path, before: str, action: str, after: str, message: str
) -> None:
    write_state(data_dir, {LIMIT: before, GAUSS: "learning"})
    subprocess.run(["git", "-C", str(data_dir), "commit", "-qam", "构造"], check=True)
    others_before = others(read_state(data_dir))

    resp = client.post(f"/api/topics/{LIMIT}/{action}")

    assert resp.status_code == 200
    assert resp.json()["status"] == after
    state = read_state(data_dir)
    assert state[LIMIT]["status"] == after
    assert datetime.fromisoformat(state[LIMIT]["updated_at"]) > datetime.fromisoformat(OLD)
    assert state[LIMIT]["weak_points"] == (
        ["ε-δ 定义：把 δ 写成了依赖 x"] if before == "learning" else []
    )
    assert others(state) == others_before
    assert last_commit(data_dir) == message
    assert worktree_clean(data_dir)


def test_claim_turns_the_recommendation_into_a_verification(client: TestClient) -> None:
    client.post(f"/api/topics/{GAUSS}/claim")
    rec = client.get("/api/recommendation").json()["recommendation"]
    assert (rec["topic"]["id"], rec["kind"]) == (GAUSS, "verify")

    client.post(f"/api/topics/{GAUSS}/unclaim")
    rec = client.get("/api/recommendation").json()["recommendation"]
    assert rec["topic"]["id"] == LIMIT


def test_defer_switches_to_the_next_recommendation_and_restore_brings_it_back(
    client: TestClient,
) -> None:
    client.post(f"/api/topics/{LIMIT}/defer")
    assert client.get("/api/recommendation").json()["recommendation"]["topic"]["id"] == GAUSS

    client.post(f"/api/topics/{LIMIT}/restore")
    assert client.get("/api/recommendation").json()["recommendation"]["topic"]["id"] == LIMIT


@pytest.mark.parametrize(
    ("status", "action"),
    [
        ("mastered", "claim"),
        ("claimed", "claim"),
        ("unlearned", "unclaim"),
        ("mastered", "defer"),
        ("claimed", "defer"),
        ("learning", "restore"),
    ],
)
def test_action_from_a_disallowed_status_is_rejected_without_writing(
    client: TestClient, data_dir: Path, status: str, action: str
) -> None:
    write_state(data_dir, {LIMIT: status})
    before = (data_dir / "state.json").read_text(encoding="utf-8")
    head = last_commit(data_dir)

    resp = client.post(f"/api/topics/{LIMIT}/{action}")

    assert resp.status_code == 409
    assert "函数极限与连续函数" in resp.json()["detail"]
    assert (data_dir / "state.json").read_text(encoding="utf-8") == before
    assert last_commit(data_dir) == head


def test_unknown_topic_or_action(client: TestClient) -> None:
    assert client.post("/api/topics/no-such-topic/claim").status_code == 404
    assert client.post(f"/api/topics/{LIMIT}/master").status_code == 422


def test_branch_inclusion_toggle_defaults_off_and_persists(
    client: TestClient, data_dir: Path
) -> None:
    fields = {f["id"]: f for f in client.get("/api/fields").json()["fields"]}
    assert fields["b06"]["included"] is False
    assert fields["c02"]["included"] is True

    resp = client.put("/api/fields/b06/included", json={"included": True})

    assert resp.status_code == 200 and resp.json()["included"] is True
    assert read_state(data_dir)["included_branches"] == ["b06"]
    assert last_commit(data_dir) == "纳入推荐：最优化方法与凸优化（b06）"
    fields = {f["id"]: f for f in client.get("/api/fields").json()["fields"]}
    assert fields["b06"]["included"] is True

    client.put("/api/fields/b06/included", json={"included": False})
    assert "included_branches" not in read_state(data_dir)
    assert last_commit(data_dir) == "取消纳入推荐：最优化方法与凸优化（b06）"


def test_core_fields_cannot_be_toggled(client: TestClient) -> None:
    assert client.put("/api/fields/c02/included", json={"included": False}).status_code == 400
    assert client.put("/api/fields/zz/included", json={"included": True}).status_code == 404


def test_interrupted_write_leaves_the_old_state_file_intact(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """在原子改名前中断：`state.json` 仍是完整的旧版，临时文件被清理，之后照常可写。"""
    write_state(data_dir, {GAUSS: "learning"})
    before = (data_dir / "state.json").read_text(encoding="utf-8")

    def interrupted(src: str, dst: str) -> None:
        raise OSError("模拟断电")

    monkeypatch.setattr("theroadnottaken.state.os.replace", interrupted)
    with pytest.raises(OSError, match="模拟断电"):
        client.post(f"/api/topics/{LIMIT}/claim")

    assert (data_dir / "state.json").read_text(encoding="utf-8") == before
    assert sorted(p.name for p in data_dir.iterdir() if p.name.endswith(".tmp")) == []

    monkeypatch.undo()
    assert client.post(f"/api/topics/{LIMIT}/claim").status_code == 200
    assert read_state(data_dir)[LIMIT]["status"] == "claimed"
