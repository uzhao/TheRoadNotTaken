"""骨架校验脚本按命令行方式测试：argv 进、stdout 与退出码出（见规格 Testing Decisions）。"""

from pathlib import Path

import pytest

from theroadnottaken.skeleton import main


def run(path: Path, *flags: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main([str(path), *flags])
    return code, capsys.readouterr().out


def test_sample_skeleton_passes(sample_skeleton: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(sample_skeleton, capsys=capsys)

    assert code == 0
    assert "通过" in out
    assert "4 个领域" in out and "7 个主题" in out


MINIMAL_FIELDS = """\
fields:
  - {id: c02, name: 单变量微积分, kind: core, order: 2}
  - {id: b06, name: 最优化, kind: branch, order: 6}
"""


def topic(tid: str, field: str = "c02", prereqs: str = "[]", concepts: int = 3) -> str:
    cs = ", ".join(f"概念{i}" for i in range(1, concepts + 1))
    return (
        f"  - {{id: {tid}, name: 主题 {tid}, field: {field}, "
        f"concepts: [{cs}], prerequisites: {prereqs}, history: '', references: []}}\n"
    )


def skeleton(tmp_path: Path, topics: str, version: str = "1", retired: str = "[]") -> Path:
    path = tmp_path / "skeleton.yaml"
    path.write_text(
        f"version: {version}\n{MINIMAL_FIELDS}topics:\n{topics}retired: {retired}\n",
        encoding="utf-8",
    )
    return path


def test_version_must_be_positive_integer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(skeleton(tmp_path, topic("c02-a"), version="0"), capsys=capsys)

    assert code == 1
    assert "version" in out and "正整数" in out


def test_duplicate_topic_id_is_located(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(skeleton(tmp_path, topic("c02-a") + topic("c02-a")), capsys=capsys)

    assert code == 1
    assert "c02-a" in out and "重复" in out


def test_topic_id_must_not_reuse_retired_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    retired = "[{id: c02-a, retired_at: 2026-01-01, successors: [], proposal: 1}]"
    code, out = run(skeleton(tmp_path, topic("c02-a"), retired=retired), capsys=capsys)

    assert code == 1
    assert "c02-a" in out and "退役" in out


def test_missing_prerequisite_is_located(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(
        skeleton(tmp_path, topic("c02-a") + topic("c02-b", prereqs="[c02-a, c02-ghost]")),
        capsys=capsys,
    )

    assert code == 1
    assert "c02-b" in out and "c02-ghost" in out and "不存在" in out


def test_retired_prerequisite_names_successor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    retired = "[{id: c02-old, retired_at: 2026-01-01, successors: [c02-a], proposal: 1}]"
    code, out = run(
        skeleton(tmp_path, topic("c02-a") + topic("c02-b", prereqs="[c02-old]"), retired=retired),
        capsys=capsys,
    )

    assert code == 1
    assert "c02-b" in out and "c02-old" in out and "已退役" in out and "c02-a" in out


def test_topic_field_must_be_defined(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(skeleton(tmp_path, topic("c99-a", field="c99")), capsys=capsys)

    assert code == 1
    assert "c99-a" in out and "领域 c99" in out and "未定义" in out


def test_concepts_must_number_three_to_five(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(
        skeleton(
            tmp_path, topic("c02-a", concepts=2) + topic("c02-b", prereqs="[c02-a]", concepts=6)
        ),
        capsys=capsys,
    )

    assert code == 1
    assert "c02-a" in out and "c02-b" in out and "3–5" in out


def test_core_topic_may_only_depend_on_core(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(
        skeleton(tmp_path, topic("b06-a", field="b06") + topic("c02-b", prereqs="[b06-a]")),
        capsys=capsys,
    )

    assert code == 1
    assert "c02-b" in out and "b06-a" in out and "主干" in out


def test_cycle_is_reported_with_its_topics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    topics = (
        topic("c02-a", prereqs="[c02-c]")
        + topic("c02-b", prereqs="[c02-a]")
        + topic("c02-c", prereqs="[c02-b]")
    )
    code, out = run(skeleton(tmp_path, topics), capsys=capsys)

    assert code == 1
    assert "环" in out and "c02-a → c02-b → c02-c → c02-a" in out


def test_non_frontier_topic_needs_a_valid_in_edge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(
        skeleton(tmp_path, topic("c02-a") + topic("c02-b", prereqs="[c02-ghost]")), capsys=capsys
    )

    assert code == 1
    assert "c02-b" in out and "入边" in out and "初始前沿" in out


def test_topic_behind_a_cycle_is_unreachable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    topics = (
        topic("c02-a", prereqs="[c02-b]")
        + topic("c02-b", prereqs="[c02-a]")
        + topic("c02-c", prereqs="[c02-a]")
    )
    code, out = run(skeleton(tmp_path, topics), capsys=capsys)

    assert code == 1
    assert "c02-c" in out and "不可达" in out
    assert "c02-b" not in out.split("不可达")[0].splitlines()[-1]  # 环上的主题只在环的错误里报一次


def test_prerequisite_lists_per_field(
    sample_skeleton: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(sample_skeleton, "--prerequisites", capsys=capsys)

    assert code == 0
    assert "## c14 概率论基础（主干）" in out
    assert "- 概率空间、公理化体系与组合概型 ←（初始前沿）" in out
    assert (
        "- 连续型随机变量与密度函数 ← 概率空间、公理化体系与组合概型；导数、微分与求导法则（c02）"
        in out
    )
    assert "## b06 最优化方法与凸优化（分支）" in out
    assert out.index("## c02") < out.index("## c04") < out.index("## c14") < out.index("## b06")


def test_prerequisite_lists_still_print_for_an_invalid_fragment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """生成阶段的领域片段常有跨领域前置还没落地，清单照样要出，缺失的前置标出来。"""
    code, out = run(skeleton(tmp_path, topic("c02-b", prereqs="[c04-x]")), "-p", capsys=capsys)

    assert code == 1
    assert "- 主题 c02-b ← c04-x（不存在）" in out


def test_unreadable_or_malformed_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path / "nope.yaml", capsys=capsys)[0] == 2
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: [1\n", encoding="utf-8")
    assert run(bad, capsys=capsys)[0] == 2


def test_runs_as_a_standalone_command(sample_skeleton: Path) -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "theroadnottaken.skeleton", str(sample_skeleton)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "通过" in proc.stdout
