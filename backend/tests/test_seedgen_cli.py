"""种子骨架生成工具按命令行测试：argv 进、stdout / 退出码 / 文件出；agent 调用走 PATH 上的假 agy。

小输入与片段夹具在 tests/fixtures/seedgen/。
"""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from theroadnottaken.seedgen import main
from theroadnottaken.skeleton import main as skeleton_main

REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH = REPO_ROOT / "research" / "curriculum-references.md"
FIXTURES = Path(__file__).parent / "fixtures" / "seedgen"


def run(*args: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main([str(a) for a in args])
    return code, capsys.readouterr().out


def load(path: Path) -> dict:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- extract


def test_extract_turns_research_into_22_fields_and_209_topics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "input.yaml"

    code, text = run("extract", "--research", RESEARCH, "--output", out, capsys=capsys)

    assert code == 0
    assert "22 个领域" in text and "209 个主题" in text
    doc = load(out)
    fields = {f["id"]: f for f in doc["fields"]}
    assert len(fields) == 22
    assert sum(len(f["topics"]) for f in fields.values()) == 209
    c02 = fields["c02"]
    assert c02["name"] == "单变量微积分与数学分析基础"
    assert (c02["kind"], c02["order"]) == ("core", 2)
    assert c02["upstream"] == ["c01"]
    assert c02["topics"][5]["name"] == "导数、微分与求导法则"
    assert c02["topics"][5]["concept_hints"][1] == "链式法则"
    assert "Ch. 16, 17" in c02["history_sources"]["kline"]
    b01 = fields["b01"]
    assert b01["kind"] == "branch" and b01["order"] == 1
    assert b01["upstream"] == ["c03", "c06", "c10", "c12"]
    assert any("留数" in note for note in b01["upstream_notes"])


# ---------------------------------------------------------------- 小输入：3 个领域、6 个主题


@pytest.fixture
def gen_dir(tmp_path: Path) -> Path:
    d = tmp_path / "gen"
    d.mkdir()
    shutil.copy(FIXTURES / "input.yaml", d / "input.yaml")
    return d


# ---------------------------------------------------------------- prompt


def test_prompt_renders_field_prompt_and_schema(
    gen_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run("prompt", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 0
    prompt = (gen_dir / "work" / "c04" / "prompt.md").read_text(encoding="utf-8")
    assert "线性代数 I：矩阵、方程组与几何直观" in prompt and "主干" in prompt
    assert "1. 线性方程组与 Gauss 消元法" in prompt and "行阶梯形、主元、初等矩阵" in prompt
    assert "`c04-" in prompt and "Stewart 1993" in prompt
    assert "跨领域前置" in prompt  # 这轮只填领域内前置
    schema = (gen_dir / "work" / "c04" / "schema.json").read_text(encoding="utf-8")
    assert '"topics"' in schema and '"minItems": 3' in schema and '"maxItems": 5' in schema
    assert "--json-schema=" in out and "--output-format json" in out and "--print=" in out


def test_prompt_rejects_unknown_field(gen_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run("prompt", "c99", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 2
    assert "c99" in out and "c02" in out  # 列出可用领域


# ---------------------------------------------------------------- 假 agy：回放输出、记录 argv

FAKE_AGY = f"""\
#!{sys.executable}
import json, os, sys, time
with open(os.environ["FAKE_AGY_ARGV"], "w", encoding="utf-8") as f:
    json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd()}}, f, ensure_ascii=False)
time.sleep(float(os.environ.get("FAKE_AGY_SLEEP", "0")))
sys.stdout.write(open(os.environ["FAKE_AGY_STDOUT"], encoding="utf-8").read())
sys.stderr.write(os.environ.get("FAKE_AGY_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_AGY_EXIT", "0")))
"""


class FakeAgy:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        script = bin_dir / "agy"
        script.write_text(FAKE_AGY, encoding="utf-8")
        script.chmod(0o755)
        self.argv_path = tmp_path / "agy-argv.json"
        self.stdout_path = tmp_path / "agy-stdout.json"
        monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("FAKE_AGY_ARGV", str(self.argv_path))
        monkeypatch.setenv("FAKE_AGY_STDOUT", str(self.stdout_path))
        monkeypatch.setenv("FAKE_AGY_SLEEP", "0")
        self.monkeypatch = monkeypatch
        self.reply(structured_output={})

    def reply(self, *, exit_code: int = 0, stderr: str = "", **payload: object) -> None:
        body = {"conversation_id": "conv-1", "status": "SUCCESS", "response": "", **payload}
        self.stdout_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        self.monkeypatch.setenv("FAKE_AGY_EXIT", str(exit_code))
        self.monkeypatch.setenv("FAKE_AGY_STDERR", stderr)

    def raw(self, text: str) -> None:
        self.stdout_path.write_text(text, encoding="utf-8")

    @property
    def argv(self) -> list[str]:
        return json.loads(self.argv_path.read_text(encoding="utf-8"))["argv"]

    @property
    def cwd(self) -> str:
        return json.loads(self.argv_path.read_text(encoding="utf-8"))["cwd"]


@pytest.fixture
def agy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeAgy:
    return FakeAgy(tmp_path, monkeypatch)


def c04_topics(**overrides: object) -> dict:
    """假 agy 对 c04 的合法回复（混入 toolAction 等 schema 外字段）。"""
    draft = {
        "toolAction": "Submitting topics",
        "toolSummary": "2 topics",
        "topics": [
            {
                "index": 1,
                "id": "c04-gauss-elimination",
                "name": "线性方程组与 Gauss 消元法",
                "aliases": [],
                "concepts": ["行阶梯形与主元", "初等矩阵", "分块矩阵"],
                "prerequisites": [],
                "history": "Kline Ch.29",
            },
            {
                "index": 2,
                "id": "c04-eigenvalue-diagonalization",
                "name": "特征值、特征向量与矩阵对角化",
                "aliases": ["eigendecomposition"],
                "concepts": ["特征多项式", "迹与行列式", "几何重数与代数重数", "可对角化判据"],
                "prerequisites": ["c04-gauss-elimination"],
                "history": "Kline Ch.33",
            },
        ],
    }
    draft.update(overrides)
    return draft


# ---------------------------------------------------------------- run


def test_run_writes_a_validated_field_fragment(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(structured_output=c04_topics())

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 0
    fragment = gen_dir / "fields" / "c04.yaml"
    doc = load(fragment)
    assert doc["version"] == 1 and doc["retired"] == []
    assert doc["fields"] == [
        {"id": "c04", "name": "线性代数 I：矩阵、方程组与几何直观", "kind": "core", "order": 4}
    ]
    eig = doc["topics"][1]
    assert eig["id"] == "c04-eigenvalue-diagonalization" and eig["field"] == "c04"
    assert eig["prerequisites"] == ["c04-gauss-elimination"]
    assert eig["history"] == "Kline Ch.33" and eig["references"] == []
    assert eig["aliases"] == ["eigendecomposition"] and "aliases" not in doc["topics"][0]
    assert "toolAction" not in fragment.read_text(encoding="utf-8")
    # 片段自身就是一份通过 019 校验的骨架，并打印了前置清单
    assert skeleton_main([str(fragment)]) == 0
    assert "通过：1 个领域、2 个主题" in out
    assert "- 特征值、特征向量与矩阵对角化 ← 线性方程组与 Gauss 消元法" in out
    assert (gen_dir / "work" / "c04" / "agy.json").exists()


def test_run_calls_agy_in_print_mode_with_schema(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(structured_output=c04_topics())

    run("run", "c04", "--gen-dir", gen_dir, "--effort", "medium", "--", "--foo=bar", capsys=capsys)

    argv = agy.argv
    assert argv[:2] == ["--output-format", "json"]
    assert "--disable-slash-commands" in argv and "--effort=medium" in argv and "--foo=bar" in argv
    schema_arg = next(a for a in argv if a.startswith("--json-schema="))
    assert '"minItems": 3' in Path(schema_arg.removeprefix("--json-schema=")).read_text("utf-8")
    assert argv[-1].startswith("--print=") and "线性方程组与 Gauss 消元法" in argv[-1]
    assert agy.cwd == str(gen_dir / "work" / "c04")  # agent 只在本次调用的工作目录里动


def test_run_rejects_ids_outside_the_field_and_misaligned_indices(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    draft = c04_topics()
    draft["topics"][0]["id"] = "c02-gauss-elimination"
    draft["topics"][1]["index"] = 3
    agy.reply(structured_output=draft)

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "c02-gauss-elimination" in out and "c04-" in out
    assert "序号" in out and "2" in out
    assert not (gen_dir / "fields" / "c04.yaml").exists()


def test_run_rejects_cross_field_prerequisites_in_this_pass(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    draft = c04_topics()
    draft["topics"][1]["prerequisites"] = ["c02-derivative"]
    agy.reply(structured_output=draft)

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "c04-eigenvalue-diagonalization" in out and "c02-derivative" in out and "cross" in out


def test_run_reports_schema_violations_from_agy(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    draft = c04_topics()
    draft["topics"][0]["concepts"] = ["只有一个概念"]
    agy.reply(structured_output=draft)

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "concepts" in out and "schema" in out.lower()


def test_run_surfaces_agy_error_exit_3(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(
        exit_code=3,
        stderr=(
            "error: quota\n"
            'AGY_ERROR: {"short_error":"RESOURCE_EXHAUSTED (code 429)","retryable":true}\n'
        ),
    )

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "退出码 3" in out and "RESOURCE_EXHAUSTED" in out


def test_run_kills_agy_after_the_hard_timeout(
    gen_dir: Path, agy: FakeAgy, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(structured_output=c04_topics())
    monkeypatch.setenv("FAKE_AGY_SLEEP", "5")

    code, out = run("run", "c04", "--gen-dir", gen_dir, "--timeout", "0.3", capsys=capsys)

    assert code == 1
    assert "0.3 秒" in out and "终止" in out
    assert not (gen_dir / "fields" / "c04.yaml").exists()


def test_run_rejects_non_json_output(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.raw("Loading…\n{not json")

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "不是 JSON" in out and "agy.json" in out


def test_run_keeps_a_fragment_that_fails_validation_out_of_fields(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    draft = c04_topics()
    draft["topics"][0]["prerequisites"] = ["c04-eigenvalue-diagonalization"]  # 成环
    agy.reply(structured_output=draft)

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "成环" in out
    assert not (gen_dir / "fields" / "c04.yaml").exists()
    staged = gen_dir / "work" / "c04" / "fragment.yaml"
    assert staged.exists() and str(staged) in out
    # 失败的产出不挡住下一次 run
    agy.reply(structured_output=c04_topics())
    assert run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)[0] == 0


def test_run_treats_success_without_structured_output_as_failure(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(response="我无法同时满足这些约束。")

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "structured_output" in out and "我无法同时满足这些约束" in out


def test_run_does_not_overwrite_an_existing_fragment_without_force(
    gen_dir: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(structured_output=c04_topics())
    fragment = gen_dir / "fields" / "c04.yaml"
    fragment.parent.mkdir()
    fragment.write_text("# 作者改过\n", encoding="utf-8")

    code, out = run("run", "c04", "--gen-dir", gen_dir, capsys=capsys)
    assert code == 1 and "--force" in out
    assert fragment.read_text(encoding="utf-8") == "# 作者改过\n"

    code, _ = run("run", "c04", "--gen-dir", gen_dir, "--force", capsys=capsys)
    assert code == 0 and load(fragment)["topics"]


# ---------------------------------------------------------------- cross


@pytest.fixture
def fragments(gen_dir: Path) -> Path:
    """三份片段（c02、c04、b06），b06 片段里带一条作者注释。"""
    fields = gen_dir / "fields"
    fields.mkdir()
    for name in ("c02.yaml", "c04.yaml", "b06.yaml"):
        shutil.copy(FIXTURES / name, fields / name)
    return fields


def edges(*pairs: tuple[str, list[str]]) -> dict:
    return {
        "toolAction": "Submitting",
        "edges": [{"topic": t, "prerequisites": ps} for t, ps in pairs],
    }


def test_cross_adds_cross_field_prerequisites_and_keeps_author_edits(
    gen_dir: Path, fragments: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(
        structured_output=edges(
            (
                "b06-convex-sets-functions",
                ["c02-derivative-rules", "c04-eigenvalue-diagonalization"],
            ),
            ("b06-gradient-descent", ["c02-mean-value-theorems"]),
        )
    )

    code, out = run("cross", "b06", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 0
    text = (fragments / "b06.yaml").read_text(encoding="utf-8")
    assert "# 作者注：入门主题" in text  # 回写保留作者的注释
    doc = load(fragments / "b06.yaml")
    assert doc["topics"][0]["prerequisites"] == [
        "c02-derivative-rules",
        "c04-eigenvalue-diagonalization",
    ]
    assert doc["topics"][1]["prerequisites"] == [
        "b06-convex-sets-functions",
        "c02-mean-value-theorems",
    ]
    assert (
        "- 凸集与凸函数 ← 导数、微分与求导法则（c02）；特征值、特征向量与矩阵对角化（c04）" in out
    )
    prompt = (gen_dir / "work" / "b06" / "cross-prompt.md").read_text(encoding="utf-8")
    assert "`b06-gradient-descent`" in prompt and "b06-convex-sets-functions" in prompt
    assert "`c02-mean-value-theorems` 微分中值定理" in prompt and "c04-gauss-elimination" in prompt
    assert "c04：矩阵计算" in prompt
    assert '"maxItems": 3' in (gen_dir / "work" / "b06" / "cross-schema.json").read_text("utf-8")


def test_cross_rerun_replaces_old_cross_edges_but_keeps_in_field_ones(
    gen_dir: Path, fragments: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(
        structured_output=edges(
            ("b06-convex-sets-functions", ["c02-derivative-rules"]),
            ("b06-gradient-descent", ["c02-mean-value-theorems"]),
        )
    )
    run("cross", "b06", "--gen-dir", gen_dir, capsys=capsys)
    agy.reply(structured_output=edges(("b06-convex-sets-functions", ["c04-gauss-elimination"])))

    code, _ = run("cross", "b06", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 0
    doc = load(fragments / "b06.yaml")
    assert doc["topics"][0]["prerequisites"] == ["c04-gauss-elimination"]
    assert doc["topics"][1]["prerequisites"] == ["b06-convex-sets-functions"]


def test_cross_rejects_ids_outside_the_candidate_fields(
    gen_dir: Path, fragments: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(
        structured_output=edges(
            ("b06-convex-sets-functions", ["c14-probability-space", "b06-gradient-descent"]),
            ("b06-nonexistent", ["c02-derivative-rules"]),
        )
    )
    before = (fragments / "b06.yaml").read_text(encoding="utf-8")

    code, out = run("cross", "b06", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 1
    assert "c14-probability-space" in out and "c02、c04" in out
    assert "b06-gradient-descent" in out and "本领域" in out
    assert "b06-nonexistent" in out
    assert (fragments / "b06.yaml").read_text(encoding="utf-8") == before


def test_cross_needs_the_upstream_fragments_first(
    gen_dir: Path, fragments: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    (fragments / "c04.yaml").unlink()

    code, out = run("cross", "b06", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 2
    assert "c04" in out and "run c04" in out


def test_cross_upstream_option_overrides_the_candidate_fields(
    gen_dir: Path, fragments: Path, agy: FakeAgy, capsys: pytest.CaptureFixture[str]
) -> None:
    agy.reply(structured_output=edges(("c04-gauss-elimination", ["c02-limits-continuity"])))

    code, out = run("cross", "c04", "--upstream", "c02,b06", "--gen-dir", gen_dir, capsys=capsys)

    assert code == 0
    assert "候选领域：c02）" in out and "忽略分支候选领域 b06" in out  # 主干只拿主干候选
    prompt = (gen_dir / "work" / "c04" / "cross-prompt.md").read_text(encoding="utf-8")
    assert "c02-derivative-rules" in prompt and "b06-convex-sets-functions" not in prompt
    assert load(fragments / "c04.yaml")["topics"][0]["prerequisites"] == ["c02-limits-continuity"]


# ---------------------------------------------------------------- merge


def test_merge_assembles_fragments_into_a_validated_skeleton(
    gen_dir: Path, fragments: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_path = gen_dir.parent / "skeleton.yaml"

    code, out = run("merge", "--gen-dir", gen_dir, "--output", out_path, "-p", capsys=capsys)

    assert code == 0
    assert "通过：3 个领域、7 个主题" in out
    assert "## b06 最优化方法与凸优化（分支）" in out  # -p 的前置清单
    doc = load(out_path)
    assert doc["version"] == 1 and doc["retired"] == []
    assert [f["id"] for f in doc["fields"]] == ["c02", "c04", "b06"]
    assert [t["field"] for t in doc["topics"]] == ["c02"] * 3 + ["c04"] * 2 + ["b06"] * 2
    text = out_path.read_text(encoding="utf-8")
    assert "# ---- c04 线性代数 I：矩阵、方程组与几何直观（主干，2 个主题）" in text
    assert "# 作者注：入门主题" in text  # 片段里的注释带进合并结果
    assert skeleton_main([str(out_path)]) == 0


def test_merge_lists_missing_fragments_and_writes_nothing(
    gen_dir: Path, fragments: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (fragments / "c04.yaml").unlink()
    out_path = gen_dir.parent / "skeleton.yaml"

    code, out = run("merge", "--gen-dir", gen_dir, "--output", out_path, capsys=capsys)

    assert code == 1
    assert "c04" in out and "run c04" in out
    assert not out_path.exists()


def test_merge_reports_validation_errors_across_fields(
    gen_dir: Path, fragments: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    b06 = fragments / "b06.yaml"
    b06.write_text(
        b06.read_text(encoding="utf-8").replace(
            "prerequisites: []   # 作者注：入门主题", "prerequisites: [c04-svd]"
        ),
        encoding="utf-8",
    )
    out_path = gen_dir.parent / "skeleton.yaml"

    code, out = run("merge", "--gen-dir", gen_dir, "--output", out_path, capsys=capsys)

    assert code == 1
    assert "校验失败" in out and "b06-convex-sets-functions" in out and "c04-svd" in out
    assert out_path.exists()  # 仍写出，便于作者在编辑器里定位


def test_merge_refuses_a_topic_filed_under_another_field(
    gen_dir: Path, fragments: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    c04 = fragments / "c04.yaml"
    c04.write_text(
        c04.read_text(encoding="utf-8").replace(
            "field: c04, concepts: [行阶梯形", "field: c02, concepts: [行阶梯形"
        ),
        encoding="utf-8",
    )
    out_path = gen_dir.parent / "skeleton.yaml"

    code, out = run("merge", "--gen-dir", gen_dir, "--output", out_path, capsys=capsys)

    assert code == 1
    assert "c04-gauss-elimination" in out and "'c02'" in out and "未拼装" in out
    assert not out_path.exists()


def test_merge_notes_topic_counts_that_differ_from_the_input(
    gen_dir: Path, fragments: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    b06 = fragments / "b06.yaml"
    b06.write_text(b06.read_text(encoding="utf-8").replace("concept_hints", "x"), encoding="utf-8")
    out_path = gen_dir.parent / "skeleton.yaml"

    code, out = run("merge", "--gen-dir", gen_dir, "--output", out_path, capsys=capsys)

    assert code == 0
    assert "提醒：领域 b06：片段 2 个主题，输入清单 1 个" in out


# ---------------------------------------------------------------- 仓库里的提交物


def test_committed_input_matches_the_research_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """seed/gen/input.yaml 必须是当前调研报告 extract 的结果（改了报告就重新 extract）。"""
    committed = REPO_ROOT / "seed" / "gen" / "input.yaml"
    regenerated = tmp_path / "input.yaml"

    run("extract", "--research", RESEARCH, "--output", regenerated, capsys=capsys)

    assert committed.read_text(encoding="utf-8") == regenerated.read_text(encoding="utf-8")


def test_seed_skeleton_when_present_passes_validation_with_22_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """工单 020 的交付物：作者用真实 agy 生成并审核后提交的 seed/skeleton.yaml。"""
    seed = REPO_ROOT / "seed" / "skeleton.yaml"
    if not seed.exists():
        pytest.skip("seed/skeleton.yaml 尚未生成（工单 020 的人工步骤）")

    code = skeleton_main([str(seed)])
    out = capsys.readouterr().out

    assert code == 0, out
    assert "22 个领域" in out
    assert load(seed)["version"] == 1
    assert len(load(seed)["topics"]) >= 200
