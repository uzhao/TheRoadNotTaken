"""讲义生成与学习页的后端：开始学习、流式生成、搬运校验与一次重试、缓存、插图静态路由。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import agy_steps as s
import pytest
from conftest import FakeAgy
from fastapi.testclient import TestClient
from test_jobs import git_log, kinds, sse_events

DERIV = "c02-derivative-definition"
LIMIT = "c02-function-limit-continuity"
OLD = "2026-10-01T10:00:00+00:00"

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect/></svg>'
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
LECTURE = (
    "# 导数、微分与求导法则\n\n## 历史动机\n\n切线问题……\n\n"
    "![割线逼近切线：$h\\to 0$ 时割线斜率趋于导数](figures/secant-to-tangent.svg)\n\n"
    "## 小结\n\n- 导数是变化率\n"
)


def write_state(data_dir: Path, entries: dict[str, dict]) -> None:
    raw = {
        tid: {"weak_points": [], "verifications": [], "updated_at": OLD, **entry}
        for tid, entry in entries.items()
    }
    (data_dir / "state.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def read_state(data_dir: Path) -> dict:
    return json.loads((data_dir / "state.json").read_text(encoding="utf-8"))


def mastered_limit(data_dir: Path, **deriv: object) -> None:
    """导数的前置（函数极限）已掌握，导数本身按 `deriv` 给出（缺省不写，即未学）。"""
    entries: dict[str, dict] = {LIMIT: {"status": "mastered"}}
    if deriv:
        entries[DERIV] = dict(deriv)
    write_state(data_dir, entries)


def lecture_run(text: str = LECTURE, *, figure: str = SVG, conv: str = "conv-lec") -> dict:
    """正常的讲义调用：写脚本、跑脚本出图、流式正文。"""
    return s.run(
        s.init(conv),
        s.write("figures/secant-to-tangent.py", "import matplotlib"),
        s.tool("run_command", CommandLine="python3 figures/secant-to-tangent.py"),
        s.write("figures/secant-to-tangent.svg", figure),
        *[s.text(text[i : i + 40]) for i in range(0, len(text), 40)],
        s.result(),
    )


def start(client: TestClient, topic: str = DERIV) -> dict:
    resp = client.post(f"/api/lectures/{topic}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def worktree_clean(data_dir: Path) -> bool:
    out = subprocess.run(
        ["git", "-C", str(data_dir), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out == ""


def test_lecture_job_streams_and_lands_in_data_dir(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    fake_agy.script(lecture_run())

    body = start(client)
    assert body["lecture"] is None
    job_id = body["job"]["id"]
    events = sse_events(client, job_id)

    assert kinds(events)[:2] == ["started", "conversation"]
    assert kinds(events)[-1] == "done"
    assert "".join(e["data"]["text"] for e in events if e["event"] == "delta") == LECTURE
    tools = [e["data"] for e in events if e["event"] == "tool"]
    assert [(t["state"], t["detail"]) for t in tools] == [
        ("ACTIVE", "python3 figures/secant-to-tangent.py"),
        ("DONE", "python3 figures/secant-to-tangent.py"),
    ]
    assert events[-1]["data"]["status"] == "succeeded"

    lec = data_dir / "lectures" / DERIV
    assert (lec / "lecture.md").read_text(encoding="utf-8") == LECTURE
    assert (lec / "figures" / "secant-to-tangent.svg").read_text(encoding="utf-8") == SVG
    assert (lec / "figures" / "secant-to-tangent.py").exists()
    meta = json.loads((lec / "meta.json").read_text(encoding="utf-8"))
    assert meta["job_id"] == job_id
    assert meta["effort"] == "high"
    assert meta["template"] == "lecture.v1"
    assert meta["weak_points"] == []
    assert meta["regenerations"] == 0
    assert len(meta["definition_hash"]) == 64
    assert {"generated_at", "model", "conversation_id"} <= meta.keys()

    assert not (data_dir / "jobs" / job_id).exists()  # 搬运后立即删除
    assert json.loads((data_dir / "conversations.json").read_text())[DERIV] == "conv-lec"
    assert git_log(data_dir)[0] == "生成讲义：导数、微分与求导法则（c02-derivative-definition）"
    assert worktree_clean(data_dir)


def test_start_learning_moves_unlearned_to_learning_and_commits(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    fake_agy.script(lecture_run())

    body = start(client)
    assert body["topic"]["status"] == "learning"
    assert read_state(data_dir)[DERIV]["status"] == "learning"
    assert "开始学习：导数、微分与求导法则（c02-derivative-definition）未学 → 学习中" in git_log(
        data_dir
    )
    sse_events(client, body["job"]["id"])


def test_lecture_prompt_carries_topic_definition_and_weak_points(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir, status="learning", weak_points=["链式法则：把外层导数漏乘了内层导数"])
    fake_agy.script(lecture_run())

    sse_events(client, start(client)["job"]["id"])

    (call,) = fake_agy.calls()
    prompt = call["prompt"]
    for expected in [
        "导数、微分与求导法则",
        "单变量微积分与数学分析基础",  # 领域
        "1. 切线与瞬时变化率",
        "4. 高阶导数与 Leibniz 公式",
        "已掌握的直接前置：函数极限与连续函数",
        "Kline Ch.17",
        "- 链式法则：把外层导数漏乘了内层导数",
        "figures/<名>.py",  # 插图契约
        "proposals.yaml",  # 提议规则
        "# 导数、微分与求导法则",  # 输出格式
    ]:
        assert expected in prompt, expected
    assert "$${" not in prompt and "${" not in prompt  # 模板占位符都已替换
    assert "--effort=high" in call["argv"]
    assert "--conversation" not in call["argv"]
    assert Path(call["cwd"]).parent == data_dir / "jobs"


def test_job_dir_has_shared_matplotlibrc(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    fake_agy.script(s.run(s.init("c"), s.text("前言"), s.result()), s.run(s.result()))

    job_id = start(client)["job"]["id"]
    sse_events(client, job_id)

    rc = (data_dir / "jobs" / job_id / "matplotlibrc").read_text(encoding="utf-8")
    assert "Noto Sans CJK" in rc
    assert "svg.fonttype: none" in rc
    assert "text.usetex: False" in rc


def fig(path: str, caption: str = "割线逼近切线") -> str:
    return f"# 导数、微分与求导法则\n\n正文\n\n![{caption}]({path})\n"


def five_figures() -> list[dict]:
    names = [f"f{i}" for i in range(5)]
    text = "# 导数\n\n" + "".join(f"![第 {n} 张图](figures/{n}.svg)\n" for n in names)
    return [*[s.write(f"figures/{n}.svg", SVG) for n in names], s.text(text)]


# 每条搬运校验规则一个失败用例：(第一次调用的步骤, 错误说明里应有的片段)
INVALID_OUTPUTS = {
    "empty": ([], "讲义为空"),
    "no-h1": ([s.text("好的，下面是讲义。\n\n# 导数\n")], "一级标题"),
    "absolute-path": (
        [s.text(fig("/etc/secant.svg"))],
        "插图路径 /etc/secant.svg 不合规",
    ),
    "dotdot": ([s.write("x.svg", SVG), s.text(fig("figures/../x.svg"))], "不能含 .."),
    "outside-figures": ([s.write("x.svg", SVG), s.text(fig("x.svg"))], "figures/<名>.svg"),
    "wrong-suffix": (
        [s.write("figures/x.gif", "GIF89a"), s.text(fig("figures/x.gif"))],
        "figures/<名>.svg",
    ),
    "missing-file": ([s.text(fig("figures/secant.svg"))], "figures/secant.svg 不存在"),
    "missing-file-single-quoted-title": (
        [s.text("# 导数\n\n![割线](figures/secant.svg 'title')\n")],
        "figures/secant.svg 不存在",
    ),
    "missing-file-paren-title": (
        [s.text("# 导数\n\n![割线](figures/secant.svg (title))\n")],
        "figures/secant.svg 不存在",
    ),
    "bad-xml": (
        [s.write("figures/secant.svg", "<svg"), s.text(fig("figures/secant.svg"))],
        "XML 无法解析",
    ),
    "not-svg-root": (
        [s.write("figures/secant.svg", "<html/>"), s.text(fig("figures/secant.svg"))],
        "根元素不是 <svg>",
    ),
    "bad-png": (
        [s.write("figures/surface.png", "not a png"), s.text(fig("figures/surface.png"))],
        "不是合法的 PNG",
    ),
    "too-large": (
        [s.write("figures/secant.svg", size=500 * 1024 + 1), s.text(fig("figures/secant.svg"))],
        "过大",
    ),
    "too-many": (five_figures(), "插图过多"),
    "no-caption": (
        [s.write("figures/secant.svg", SVG), s.text(fig("figures/secant.svg", caption=""))],
        "缺少图注",
    ),
    "reference-image": (
        [s.text("# 导数\n\n![割线][s]\n\n[s]: /etc/passwd\n")],
        "引用式",
    ),
}


@pytest.mark.parametrize("case", INVALID_OUTPUTS)
def test_each_check_rule_fails_twice_then_job_fails_and_keeps_dir(
    case: str, client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    steps, expected = INVALID_OUTPUTS[case]
    mastered_limit(data_dir)
    # 两次都交同样不合格的产出
    fake_agy.script(s.run(s.init("conv-bad"), *steps, s.result()), s.run(*steps, s.result()))

    body = start(client)
    job_id = body["job"]["id"]
    events = sse_events(client, job_id)

    (retry,) = [e["data"] for e in events if e["event"] == "retry"]
    assert retry["attempt"] == 2
    assert any(expected in err for err in retry["errors"]), retry["errors"]
    done = events[-1]["data"]
    assert done["status"] == "failed"
    assert done["error"]["kind"] == "validation"
    assert any(expected in err for err in done["error"]["errors"])

    first, second = fake_agy.calls()
    assert second["conversation"] == "conv-bad"  # 同一会话重试
    assert second["cwd"] == first["cwd"]
    assert expected in second["prompt"]
    assert "修好这张图" in second["prompt"] and "删掉对它的引用" in second["prompt"]

    assert (data_dir / "jobs" / job_id).is_dir()  # 失败的任务目录保留
    assert not (data_dir / "lectures" / DERIV).exists()
    assert read_state(data_dir)[DERIV]["status"] == "learning"
    assert not any(m.startswith("生成讲义") for m in git_log(data_dir))
    assert client.get(f"/api/lectures/{DERIV}").json()["lecture"] is None


def test_retry_that_fixes_the_figure_is_cached(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    fake_agy.script(
        s.run(
            s.init("conv-fix"),
            s.write("figures/secant-to-tangent.svg", "<svg"),
            s.text(LECTURE),
            s.result(),
        ),
        s.run(s.write("figures/secant-to-tangent.svg", SVG), s.text(LECTURE), s.result()),
    )

    job_id = start(client)["job"]["id"]
    events = sse_events(client, job_id)

    assert "retry" in kinds(events)
    assert events[-1]["data"]["status"] == "succeeded"
    lec = data_dir / "lectures" / DERIV
    assert (lec / "figures" / "secant-to-tangent.svg").read_text(encoding="utf-8") == SVG
    assert json.loads((lec / "meta.json").read_text())["attempts"] == 2
    assert not (data_dir / "jobs" / job_id).exists()


def test_retry_may_drop_the_figure_reference(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    rewritten = "# 导数、微分与求导法则\n\n割线斜率的极限就是切线斜率。\n"
    fake_agy.script(
        s.run(s.init("conv-fix"), s.text(fig("figures/secant.svg")), s.result()),
        s.run(s.text(rewritten), s.result()),
    )

    sse_events(client, start(client)["job"]["id"])

    lec = data_dir / "lectures" / DERIV
    assert (lec / "lecture.md").read_text(encoding="utf-8") == rewritten
    assert list((lec / "figures").iterdir()) == []


def test_only_lecture_referenced_figures_and_their_scripts_are_moved(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    fake_agy.script(
        s.run(
            s.init("c"),
            s.write("figures/secant-to-tangent.py", "print()"),
            s.write("figures/secant-to-tangent.svg", SVG),
            s.write("figures/unused.svg", SVG),
            s.write("figures/notes.txt", "x"),
            s.write("scratch.py", "x"),
            s.write("proposals.yaml", "[]"),
            s.text(LECTURE),
            s.result(),
        )
    )

    sse_events(client, start(client)["job"]["id"])

    lec = data_dir / "lectures" / DERIV
    assert sorted(p.name for p in lec.iterdir()) == ["figures", "lecture.md", "meta.json"]
    assert sorted(p.name for p in (lec / "figures").iterdir()) == [
        "secant-to-tangent.py",
        "secant-to-tangent.svg",
    ]


def generate(client: TestClient, fake_agy: FakeAgy, data_dir: Path, **deriv: object) -> None:
    mastered_limit(data_dir, **deriv)
    fake_agy.script(lecture_run())
    sse_events(client, start(client)["job"]["id"])


def test_cached_lecture_opens_without_starting_agy(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    generate(client, fake_agy, data_dir)
    commits = git_log(data_dir)

    body = start(client)

    assert body["job"] is None
    assert body["lecture"]["markdown"] == LECTURE
    assert body["lecture"]["meta"]["template"] == "lecture.v1"
    assert len(fake_agy.calls()) == 1
    assert git_log(data_dir) == commits  # 已在学习中，不再改状态


def test_lecture_page_shows_status_and_weak_points(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    weak = ["链式法则：把外层导数漏乘了内层导数"]
    generate(client, fake_agy, data_dir, status="learning", weak_points=weak)

    body = client.get(f"/api/lectures/{DERIV}").json()

    assert body["topic"]["status"] == "learning"
    assert body["topic"]["weak_points"] == weak
    assert body["lecture"]["meta"]["weak_points"] == weak
    assert body["job"] is None


def test_second_start_while_generating_joins_the_running_job(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    fake_agy.script(s.run(s.init("c"), s.hang()))

    first = start(client)["job"]["id"]
    assert start(client)["job"]["id"] == first
    assert client.get(f"/api/lectures/{DERIV}").json()["job"]["id"] == first
    client.delete(f"/api/jobs/{first}")


def test_figures_are_served_by_static_route(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    generate(client, fake_agy, data_dir)

    resp = client.get(f"/api/lectures/{DERIV}/figures/secant-to-tangent.svg")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.text == SVG
    assert "default-src 'none'" in resp.headers["content-security-policy"]


@pytest.mark.parametrize(
    "name",
    [
        "..%2F..%2Fstate.json",
        "..%2Fmeta.json",
        "%2Fetc%2Fpasswd",
        "secant-to-tangent.py",  # 脚本不经插图路由
        "missing.svg",
        "sub%2Fx.svg",
    ],
)
def test_figure_route_rejects_out_of_bounds_paths(
    name: str, client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    generate(client, fake_agy, data_dir)
    (data_dir / "lectures" / DERIV / "figures" / "sub").mkdir()
    (data_dir / "lectures" / DERIV / "figures" / "sub" / "x.svg").write_text(SVG)

    assert client.get(f"/api/lectures/{DERIV}/figures/{name}").status_code == 404


def test_figure_route_rejects_symlink_out_of_lecture(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    generate(client, fake_agy, data_dir)
    (data_dir / "lectures" / DERIV / "figures" / "leak.svg").symlink_to(data_dir / "state.json")

    assert client.get(f"/api/lectures/{DERIV}/figures/leak.svg").status_code == 404


def test_locked_topic_cannot_start(client: TestClient, fake_agy: FakeAgy, data_dir: Path) -> None:
    resp = client.post(f"/api/lectures/{DERIV}")  # 前置「函数极限」未掌握

    assert resp.status_code == 409
    assert "函数极限与连续函数" in resp.json()["detail"]
    assert fake_agy.calls() == []
    assert DERIV not in read_state(data_dir)


def test_unknown_topic_is_404(client: TestClient) -> None:
    assert client.post("/api/lectures/nope").status_code == 404
    assert client.get("/api/lectures/nope").status_code == 404


def test_deferred_topic_starts_learning_but_mastered_stays_mastered(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    write_state(data_dir, {LIMIT: {"status": "mastered"}, DERIV: {"status": "deferred"}})
    fake_agy.script(lecture_run())

    sse_events(client, start(client, DERIV)["job"]["id"])
    body = start(client, LIMIT)  # 回看已掌握主题的讲义：照常生成，不改状态
    sse_events(client, body["job"]["id"])

    state = read_state(data_dir)
    assert state[DERIV]["status"] == "learning"
    assert state[LIMIT]["status"] == "mastered"


def test_figure_is_served_from_running_job_once_drawn(
    client: TestClient, fake_agy: FakeAgy, data_dir: Path
) -> None:
    mastered_limit(data_dir)
    pid = data_dir.parent / "pid"
    fake_agy.script(
        s.run(s.init("c"), s.write("figures/secant-to-tangent.svg", SVG), s.hang(str(pid)))
    )
    job_id = start(client)["job"]["id"]
    url = f"/api/lectures/{DERIV}/figures/secant-to-tangent.svg"

    from test_jobs import wait_until

    wait_until(lambda: client.get(url).status_code == 200)
    assert client.get(url).text == SVG
    client.delete(f"/api/jobs/{job_id}")
    assert client.get(url).status_code == 404
