"""种子骨架生成工具：把调研报告的 22 领域 209 主题清单变成通过校验的种子骨架。

独立命令 `theroadnottaken-seed <子命令>`，供作者在本机配合真实 agy 逐领域生成并审核（工单 020）：

- `extract`：从调研报告 `research/curriculum-references.md` 提取领域、主题清单、概念提示、领域间
  先修关系与历史素材来源，写成 `seed/gen/input.yaml`（生成的唯一输入，勿手改）。
- `prompt FIELD`：渲染某领域的 prompt 与 JSON schema 到 `seed/gen/work/FIELD/`，打印 agy 命令行。
- `run FIELD`：调用 agy（`--json-schema`）产出该领域的主题 id、概念、领域内前置与历史动机索引，
  本地校验后写成可单独校验、可手改的骨架片段 `seed/gen/fields/FIELD.yaml`，并打印前置清单。
- `cross FIELD`：再调用一次 agy，为该领域补跨领域直接前置（候选限于课程体系中的直接先修领域），
  写回片段并打印带领域标注的前置清单。
- `merge`：把全部片段拼成 `seed/skeleton.yaml`，跑 019 的校验，可同时输出每领域前置清单。

agent 结构化输出按规格用 pydantic 建模，`--json-schema` 的 schema 直接由模型导出，解析时忽略
`toolAction` / `toolSummary` 等 schema 外字段；`status` 为 SUCCESS 但无 `structured_output`
视为失败。
退出码：0 成功、1 校验或 agy 失败、2 输入文件无法读取。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from string import Template

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from theroadnottaken.skeleton import (
    Skeleton,
    SkeletonLoadError,
    load_skeleton,
    prerequisite_lists,
)
from theroadnottaken.skeleton import main as skeleton_main

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESEARCH = REPO_ROOT / "research" / "curriculum-references.md"
DEFAULT_GEN_DIR = REPO_ROOT / "seed" / "gen"
DEFAULT_SKELETON = REPO_ROOT / "seed" / "skeleton.yaml"

FIELD_KIND_BY_LETTER = {"c": "core", "b": "branch"}
KIND_NAMES = {"core": "主干", "branch": "分支"}
FIELD_PROMPT_TEMPLATE = "seed-field.v1.md"
CROSS_PROMPT_TEMPLATE = "seed-cross.v1.md"
SLUG_PATTERN = r"^[cb][0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$"
DEFAULT_EFFORT = "high"
DEFAULT_TIMEOUT_SECONDS = 600


class SeedError(Exception):
    """输入文件缺失或无法解析，无法继续。"""


class AgyFailure(Exception):
    """agy 调用失败或其输出不可用（退出码非 0、非 JSON、无 structured_output、不符合 schema）。"""


# ---------------------------------------------------------------- extract：解析调研报告

_FIELD_HEADING = re.compile(r"^##### ([CB])(\d{2})\. (.+?)（(\d+) 个主题）\s*$")
_TOPIC_LINE = re.compile(r"^\d+\. \*\*(.+?)\*\*（(.+)）\s*$")
_FIELD_EDGE = re.compile(r'^\s*([CB]\d{2}) (?:-->|-\.->\|"([^"]*)"\|) ([CB]\d{2})\s*$')
_HISTORY_ROW = re.compile(r"^\| \*\*([CB]\d{2})\. .+?\*\* \| (.+?) \| (.+?) \|\s*$")
_HISTORY_SECTION = "知识网领域与《古今数学思想》及补充历史素材的总映射"
_TOPIC_SECTION_END = "## 二、"


def extract_input(research: Path) -> CommentedMap:
    """把调研报告解析成生成输入：领域（含先修领域与历史素材来源）与各领域的主题清单。"""
    try:
        lines = research.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise SeedError(f"无法读取调研报告 {research}：{exc}") from exc

    fields = _extract_fields_and_topics(lines)
    if not fields:
        raise SeedError(f"{research} 里没有找到「##### C01. …（N 个主题）」形式的领域清单")
    by_id = {f["id"]: f for f in fields}
    for upstream, note, downstream in _extract_field_edges(lines):
        field = by_id[downstream]
        field["upstream"].append(upstream)
        if note:
            field["upstream_notes"].append(f"{upstream}：{note}（进阶 / 局部主题前置）")
    for fid, kline, supplement in _extract_history_rows(lines):
        by_id[fid]["history_sources"] = CommentedMap(kline=kline, supplement=supplement)

    doc = CommentedMap()
    doc.yaml_set_start_comment(
        "由 theroadnottaken-seed extract 从调研报告提取的生成输入；"
        "勿手改，改调研报告后重新 extract。"
    )
    doc["source"] = (
        str(research.relative_to(REPO_ROOT))
        if research.is_relative_to(REPO_ROOT)
        else str(research)
    )
    doc["fields"] = CommentedSeq(fields)
    return doc


def _extract_fields_and_topics(lines: list[str]) -> list[CommentedMap]:
    fields: list[CommentedMap] = []
    current: CommentedMap | None = None
    for line in lines:
        if line.startswith(_TOPIC_SECTION_END):
            break
        heading = _FIELD_HEADING.match(line)
        if heading:
            letter, number, name, _count = heading.groups()
            current = CommentedMap()
            current["id"] = f"{letter.lower()}{number}"
            current["name"] = name
            current["kind"] = FIELD_KIND_BY_LETTER[letter.lower()]
            current["order"] = int(number)
            current["upstream"] = _flow([])
            current["upstream_notes"] = []
            current["history_sources"] = CommentedMap(kline="", supplement="")
            current["topics"] = []
            fields.append(current)
            continue
        topic = _TOPIC_LINE.match(line)
        if topic and current is not None:
            name, hints = topic.groups()
            entry = CommentedMap()
            entry["name"] = name
            entry["concept_hints"] = _flow([h.strip() for h in hints.split("、") if h.strip()])
            current["topics"].append(entry)
    return fields


def _extract_field_edges(lines: list[str]) -> list[tuple[str, str | None, str]]:
    edges = []
    for line in lines:
        m = _FIELD_EDGE.match(line)
        if m:
            upstream, note, downstream = m.groups()
            edges.append((upstream.lower(), note, downstream.lower()))
    return edges


def _extract_history_rows(lines: list[str]) -> list[tuple[str, str, str]]:
    rows = []
    in_section = False
    for line in lines:
        if _HISTORY_SECTION in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        m = _HISTORY_ROW.match(line) if in_section else None
        if m:
            fid, kline, supplement = m.groups()
            rows.append((fid.lower(), _clean_cell(kline), _clean_cell(supplement)))
    return rows


def _clean_cell(cell: str) -> str:
    return cell.replace("<br>", "\n").replace("**", "").strip()


def _flow(items: list[str]) -> CommentedSeq:
    seq = CommentedSeq(items)
    seq.fa.set_flow_style()
    return seq


# ---------------------------------------------------------------- agent 结构化输出模型

_IGNORE_EXTRA = ConfigDict(
    extra="ignore"
)  # agy 会在 structured_output 里混入 toolAction / toolSummary


class TopicDraft(BaseModel):
    """领域内一轮：一个主题的 id、名称、概念、领域内直接前置与历史动机索引。"""

    model_config = _IGNORE_EXTRA
    index: int = Field(ge=1, description="主题在输入清单中的序号，从 1 起")
    id: str = Field(pattern=SLUG_PATTERN, description="稳定 slug，前缀为领域 id")
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(min_length=3, max_length=5)
    prerequisites: list[str] = Field(description="本领域内直接前置的 id")
    history: str = Field(min_length=1, description="历史动机索引，如 Kline Ch.17")


class FieldDraft(BaseModel):
    model_config = _IGNORE_EXTRA
    topics: list[TopicDraft]


class CrossEdges(BaseModel):
    """跨领域一轮：一个主题需要补充的跨领域直接前置。"""

    model_config = _IGNORE_EXTRA
    topic: str = Field(description="本领域主题的 id")
    prerequisites: list[str] = Field(min_length=1, max_length=3, description="其它领域主题的 id")


class CrossDraft(BaseModel):
    model_config = _IGNORE_EXTRA
    edges: list[CrossEdges]


def schema_json(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 生成输入与 prompt


def load_input(gen_dir: Path) -> dict:
    path = gen_dir / "input.yaml"
    try:
        doc = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise SeedError(f"无法读取生成输入 {path}（先运行 extract）：{exc}") from exc
    except YAMLError as exc:
        raise SeedError(f"{path} 不是合法的 YAML：{exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("fields"), list):
        raise SeedError(f"{path} 顶层必须有 fields 列表")
    return doc


def pick_field(doc: dict, field_id: str) -> dict:
    by_id = {f["id"]: f for f in doc["fields"]}
    if field_id not in by_id:
        raise SeedError(f"领域 {field_id} 不在生成输入里；可用领域：{'、'.join(by_id)}")
    return by_id[field_id]


def _template(name: str) -> Template:
    text = resources.files("theroadnottaken").joinpath("prompts", name).read_text(encoding="utf-8")
    return Template(text)


def render_field_prompt(field: dict) -> str:
    """领域内一轮的 prompt：主题清单带概念提示，历史素材来源，再加输出要求。"""
    topics_block = "\n".join(
        f"{i}. {t['name']}\n   概念提示：{'、'.join(t['concept_hints'])}"
        for i, t in enumerate(field["topics"], start=1)
    )
    sources = field.get("history_sources") or {}
    history_block = "\n".join(
        f"- {label}：{text}"
        for label, text in (
            ("《古今数学思想》（Kline）", sources.get("kline") or "未覆盖"),
            ("补充文献", sources.get("supplement") or "—"),
        )
    )
    return _template(FIELD_PROMPT_TEMPLATE).substitute(
        field_id=field["id"],
        field_name=field["name"],
        kind_name=KIND_NAMES[field["kind"]],
        count=len(field["topics"]),
        topics_block=topics_block,
        history_block=history_block,
    )


def agy_command(
    schema_path: Path, prompt_path: Path, effort: str, extra: Sequence[str]
) -> list[str]:
    """agy print 模式：参数放在 --print 之前，prompt 是 --print= 的值（规格「agent 调用」节）。"""
    return [
        "agy",
        "--output-format",
        "json",
        f"--json-schema={schema_path}",
        "--disable-slash-commands",
        f"--effort={effort}",
        *extra,
        f"--print={prompt_path.read_text(encoding='utf-8')}",
    ]


def _shell_hint(command: list[str], prompt_path: Path) -> str:
    """给作者看的等价命令行：prompt 太长，用 $(cat …) 代替正文。"""
    shown = [*command[:-1], f'--print="$(cat {shlex.quote(str(prompt_path))})"']
    return " ".join(shlex.quote(c) if c != shown[-1] else c for c in shown)


# ---------------------------------------------------------------- 调用 agy


def call_agy(command: list[str], raw_path: Path, timeout: float) -> dict:
    """运行 agy print 模式，原始 stdout 存到 raw_path，返回 structured_output。

    退出码非 0 时带出 stderr 里的 `AGY_ERROR:` 行；`status` 为 SUCCESS 但无 `structured_output`
    视为失败（schema 未被满足），把模型的解释文字带给作者。自备硬超时并杀掉整个进程组。
    """
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise AgyFailure("找不到 agy 可执行文件（不在 PATH 上）") from exc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        raise AgyFailure(f"agy 超过 {timeout:g} 秒未返回，已终止") from exc
    raw_path.write_text(stdout, encoding="utf-8")

    if proc.returncode != 0:
        error_line = next(
            (line for line in stderr.splitlines() if line.startswith("AGY_ERROR:")),
            stderr.strip()[-500:] or "（stderr 为空）",
        )
        raise AgyFailure(f"agy 退出码 {proc.returncode}：{error_line}")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AgyFailure(f"agy 输出不是 JSON（原始输出见 {raw_path}）") from exc
    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        status = payload.get("status") if isinstance(payload, dict) else None
        error = payload.get("error", "") if isinstance(payload, dict) else ""
        raise AgyFailure(f"agy 返回 status={status!r}：{error}（原始输出见 {raw_path}）")
    structured = payload.get("structured_output")
    if not isinstance(structured, dict):
        response = str(payload.get("response", "")).strip()[:800]
        raise AgyFailure(
            "agy 返回 SUCCESS 但没有 structured_output（schema 未被满足）。模型回复：\n" + response
        )
    return structured


def parse_draft[T: BaseModel](model: type[T], structured: dict) -> T:
    try:
        return model.model_validate(structured)
    except ValidationError as exc:
        details = "\n".join(
            f"- {'.'.join(str(p) for p in e['loc'])}：{e['msg']}" for e in exc.errors()
        )
        raise AgyFailure(f"structured_output 不符合 schema：\n{details}") from exc


# ---------------------------------------------------------------- 领域内一轮：本地检查与片段


def check_field_draft(field: dict, draft: FieldDraft) -> list[str]:
    """序号与输入清单一一对应；id 以领域 id 为前缀；这一轮的前置只能是本领域的 id。"""
    fid = field["id"]
    errors: list[str] = []
    expected = set(range(1, len(field["topics"]) + 1))
    got = [t.index for t in draft.topics]
    missing = sorted(expected - set(got))
    extra = sorted(set(got) - expected)
    duplicated = sorted({i for i in got if got.count(i) > 1})
    if missing:
        errors.append(f"主题序号缺失：{missing}（输入清单共 {len(expected)} 个主题）")
    if extra:
        errors.append(f"主题序号超出清单：{extra}（输入清单共 {len(expected)} 个主题）")
    if duplicated:
        errors.append(f"主题序号重复：{duplicated}")
    for t in draft.topics:
        if not t.id.startswith(f"{fid}-"):
            errors.append(f"主题 {t.id}：id 必须以 {fid}- 开头")
        for p in t.prerequisites:
            if not p.startswith(f"{fid}-"):
                errors.append(
                    f"主题 {t.id}：前置 {p} 不是本领域的主题（跨领域前置由 cross 一轮处理）"
                )
    return errors


def fragment_document(field: dict, draft: FieldDraft) -> CommentedMap:
    """一份只含该领域的骨架（version / fields / topics / retired），可单独校验、可手改。"""
    fid = field["id"]
    doc = CommentedMap()
    doc.yaml_set_start_comment(
        f"领域 {fid}「{field['name']}」（{KIND_NAMES[field['kind']]}，{len(draft.topics)} 个主题）"
        f"的骨架片段。由 theroadnottaken-seed run 生成（prompt 模板 {FIELD_PROMPT_TEMPLATE}），"
        "可手改；cross 一轮会补跨领域前置，merge 把全部片段拼成 seed/skeleton.yaml。\n"
        f"单独校验：theroadnottaken-skeleton seed/gen/fields/{fid}.yaml -p"
    )
    doc["version"] = 1
    doc["fields"] = CommentedSeq([_field_entry(field)])
    topics = CommentedSeq()
    for t in sorted(draft.topics, key=lambda t: t.index):
        entry = CommentedMap()
        entry["id"] = t.id
        entry["name"] = t.name
        entry["field"] = fid
        entry["concepts"] = _flow(t.concepts)
        entry["prerequisites"] = _flow(t.prerequisites)
        entry["history"] = t.history
        entry["references"] = _flow([])
        if t.aliases:
            entry["aliases"] = _flow(t.aliases)
        topics.append(entry)
    doc["topics"] = topics
    doc["retired"] = _flow([])
    return doc


def _field_entry(field: dict) -> CommentedMap:
    entry = CommentedMap()
    for key in ("id", "name", "kind", "order"):
        entry[key] = field[key]
    entry.fa.set_flow_style()
    return entry


def fragment_path(gen_dir: Path, field_id: str) -> Path:
    return gen_dir / "fields" / f"{field_id}.yaml"


# ---------------------------------------------------------------- 跨领域一轮


def load_fragment(gen_dir: Path, field_id: str, *, needed_by: str | None = None) -> CommentedMap:
    """读入片段（保留注释与顺序）；缺失时提示先运行 run。"""
    path = fragment_path(gen_dir, field_id)
    if not path.exists():
        why = f"（领域 {needed_by} 的跨领域前置候选）" if needed_by else ""
        raise SeedError(f"缺少片段 {path}{why}；先运行：theroadnottaken-seed run {field_id}")
    try:
        doc = _yaml().load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise SeedError(f"无法读取片段 {path}：{exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("topics"), list):
        raise SeedError(f"片段 {path} 顶层必须有 topics 列表")
    return doc


def render_cross_prompt(
    field: dict, target: CommentedMap, candidates: dict[str, tuple[dict, CommentedMap]]
) -> str:
    """跨领域一轮的 prompt：本领域主题（含领域内前置）＋按先修领域分组的候选主题。"""
    target_block = "\n".join(
        f"- `{t['id']}` {t['name']}\n  概念：{'、'.join(t['concepts'])}\n"
        f"  领域内前置：{'、'.join(t['prerequisites']) or '（无）'}"
        for t in target["topics"]
    )
    sections = []
    for fid, (upstream_field, doc) in candidates.items():
        lines = [f"### {fid} {upstream_field['name']}（{KIND_NAMES[upstream_field['kind']]}）"]
        lines += [f"- `{t['id']}` {t['name']}：{'、'.join(t['concepts'])}" for t in doc["topics"]]
        sections.append("\n".join(lines))
    notes = field.get("upstream_notes") or []
    notes_block = (
        "\n课程体系对其中部分先修关系的说明（只有相应的局部主题才需要这些前置）：\n"
        + "\n".join(f"- {n}" for n in notes)
        + "\n"
        if notes
        else ""
    )
    return _template(CROSS_PROMPT_TEMPLATE).substitute(
        field_id=field["id"],
        field_name=field["name"],
        kind_name=KIND_NAMES[field["kind"]],
        target_block=target_block,
        candidates_block="\n\n".join(sections) or "（无：课程体系中本领域没有先修领域）",
        notes_block=notes_block,
    )


def check_cross_draft(
    field: dict,
    target: CommentedMap,
    candidates: dict[str, tuple[dict, CommentedMap]],
    draft: CrossDraft,
) -> list[str]:
    """主题是本领域的；前置只能是候选领域里存在的 id；同一主题不重复出现。"""
    fid = field["id"]
    target_ids = {t["id"] for t in target["topics"]}
    candidate_ids = {t["id"] for _, doc in candidates.values() for t in doc["topics"]}
    upstream = "、".join(candidates) or "无"
    errors: list[str] = []
    seen: set[str] = set()
    for edge in draft.edges:
        if edge.topic in seen:
            errors.append(f"主题 {edge.topic} 出现了多次")
        seen.add(edge.topic)
        if edge.topic not in target_ids:
            errors.append(f"主题 {edge.topic} 不在领域 {fid} 的片段里")
        for p in edge.prerequisites:
            if p.startswith(f"{fid}-"):
                errors.append(f"主题 {edge.topic}：{p} 是本领域的主题，这一轮只填跨领域前置")
            elif p not in candidate_ids:
                errors.append(f"主题 {edge.topic}：前置 {p} 不在候选领域（{upstream}）的片段里")
    return errors


def apply_cross_edges(target: CommentedMap, field_id: str, draft: CrossDraft) -> None:
    """就地改写：每个主题保留领域内前置、替换全部跨领域前置（重跑不会累积旧边）。"""
    new_edges = {e.topic: e.prerequisites for e in draft.edges}
    for t in target["topics"]:
        in_field = [p for p in t["prerequisites"] if p.startswith(f"{field_id}-")]
        t["prerequisites"] = _flow(in_field + list(new_edges.get(t["id"], [])))


def field_prerequisite_list(gen_dir: Path, field_id: str) -> str:
    """只打印一个领域的前置清单，跨领域前置用全部已有片段解析名称。"""
    skeletons = []
    for path in sorted((gen_dir / "fields").glob("*.yaml")):
        try:
            skeletons.append(load_skeleton(path))
        except SkeletonLoadError as exc:
            raise SeedError(str(exc)) from exc
    target = next(s for s in skeletons if any(f.id == field_id for f in s.fields))
    merged = Skeleton(
        1,
        tuple(f for f in target.fields if f.id == field_id),
        tuple(t for s in skeletons for t in s.topics),
        (),
    )
    return prerequisite_lists(merged)


# ---------------------------------------------------------------- merge


def ordered_fields(doc: dict) -> list[dict]:
    """主干在前、各按 order，与前置清单的领域顺序一致。"""
    return sorted(doc["fields"], key=lambda f: (f["kind"] != "core", f["order"], f["id"]))


def merge_fragments(doc: dict, gen_dir: Path) -> tuple[CommentedMap, list[str]]:
    """把每个领域的片段按顺序拼成一份骨架；返回骨架与缺失片段的领域 id。"""
    fields = ordered_fields(doc)
    missing = [f["id"] for f in fields if not fragment_path(gen_dir, f["id"]).exists()]
    merged = CommentedMap()
    if missing:
        return merged, missing

    merged["version"] = 1
    field_entries, topics = CommentedSeq(), CommentedSeq()
    for field in fields:
        fragment = load_fragment(gen_dir, field["id"])
        own = [
            f
            for f in fragment.get("fields") or []
            if isinstance(f, dict) and f.get("id") == field["id"]
        ]
        field_entries.append(own[0] if own else _field_entry(field))
        first = len(topics)
        for topic in fragment["topics"]:
            if isinstance(topic, CommentedMap):
                topic.fa.set_block_style()  # 主题一律块式，列表字段保持流式
            topics.append(topic)
        if len(topics) > first:
            header = (
                f"---- {field['id']} {field['name']}"
                f"（{KIND_NAMES[field['kind']]}，{len(topics) - first} 个主题）"
            )
            topics.yaml_set_comment_before_after_key(first, before=header, indent=2)
    merged["fields"] = field_entries
    merged["topics"] = topics
    merged["retired"] = _flow([])
    merged.yaml_set_start_comment(
        f"种子骨架 version 1：{len(fields)} 个领域、{len(topics)} 个主题（主干 "
        f"{sum(1 for f in fields if f['kind'] == 'core')} 个领域、分支 "
        f"{sum(1 for f in fields if f['kind'] == 'branch')} 个领域）。\n"
        "由 theroadnottaken-seed merge 从 seed/gen/fields/*.yaml 拼装；首次启动时复制到数据目录，"
        "此后数据目录副本为权威。\n"
        "校验：theroadnottaken-skeleton seed/skeleton.yaml -p"
    )
    return merged, []


# ---------------------------------------------------------------- YAML 读写


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.width = 120
    yaml.allow_unicode = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def write_yaml(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        _yaml().dump(doc, f)


# ---------------------------------------------------------------- 命令行


def cmd_extract(args: argparse.Namespace) -> int:
    doc = extract_input(args.research)
    write_yaml(args.output, doc)
    topics = sum(len(f["topics"]) for f in doc["fields"])
    print(f"已提取 {len(doc['fields'])} 个领域、{topics} 个主题 → {args.output}")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    field = pick_field(load_input(args.gen_dir), args.field)
    work = args.gen_dir / "work" / field["id"]
    work.mkdir(parents=True, exist_ok=True)
    prompt_path, schema_path = work / "prompt.md", work / "schema.json"
    prompt_path.write_text(render_field_prompt(field), encoding="utf-8")
    schema_path.write_text(schema_json(FieldDraft), encoding="utf-8")
    command = agy_command(schema_path, prompt_path, args.effort, args.agy_args)
    print(f"已写入 {prompt_path} 与 {schema_path}（模板 {FIELD_PROMPT_TEMPLATE}）")
    print("手动运行：")
    print("  " + _shell_hint(command, prompt_path))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    field = pick_field(load_input(args.gen_dir), args.field)
    fid = field["id"]
    target = fragment_path(args.gen_dir, fid)
    if target.exists() and not args.force:
        print(f"{target} 已存在（可能已手改）；要重新生成请加 --force")
        return 1

    work = args.gen_dir / "work" / fid
    work.mkdir(parents=True, exist_ok=True)
    prompt_path, schema_path = work / "prompt.md", work / "schema.json"
    prompt_path.write_text(render_field_prompt(field), encoding="utf-8")
    schema_path.write_text(schema_json(FieldDraft), encoding="utf-8")
    command = agy_command(schema_path, prompt_path, args.effort, args.agy_args)
    print(f"调用 agy 生成领域 {fid}「{field['name']}」（{len(field['topics'])} 个主题）…")
    try:
        structured = call_agy(command, work / "agy.json", args.timeout)
        draft = parse_draft(FieldDraft, structured)
    except AgyFailure as exc:
        print(f"生成失败：{exc}")
        return 1

    errors = check_field_draft(field, draft)
    if errors:
        print(
            f"agy 输出不合要求（{len(errors)} 个问题，片段未写入；"
            f"原始输出见 {work / 'agy.json'}）："
        )
        for e in errors:
            print(f"- {e}")
        return 1

    write_yaml(target, fragment_document(field, draft))
    print(f"已写入 {target}，校验：")
    return skeleton_main([str(target), "--prerequisites"])


def cmd_cross(args: argparse.Namespace) -> int:
    doc = load_input(args.gen_dir)
    field = pick_field(doc, args.field)
    fid = field["id"]
    target = load_fragment(args.gen_dir, fid)
    candidates = {
        up: (pick_field(doc, up), load_fragment(args.gen_dir, up, needed_by=fid))
        for up in field.get("upstream") or []
    }

    work = args.gen_dir / "work" / fid
    work.mkdir(parents=True, exist_ok=True)
    prompt_path, schema_path = work / "cross-prompt.md", work / "cross-schema.json"
    prompt_path.write_text(render_cross_prompt(field, target, candidates), encoding="utf-8")
    schema_path.write_text(schema_json(CrossDraft), encoding="utf-8")
    command = agy_command(schema_path, prompt_path, args.effort, args.agy_args)
    print(
        f"调用 agy 为领域 {fid}「{field['name']}」补跨领域前置"
        f"（候选领域：{'、'.join(candidates) or '无'}）…"
    )
    try:
        structured = call_agy(command, work / "cross-agy.json", args.timeout)
        draft = parse_draft(CrossDraft, structured)
    except AgyFailure as exc:
        print(f"生成失败：{exc}")
        return 1

    errors = check_cross_draft(field, target, candidates, draft)
    if errors:
        print(
            f"agy 输出不合要求（{len(errors)} 个问题，片段未改动；"
            f"原始输出见 {work / 'cross-agy.json'}）："
        )
        for e in errors:
            print(f"- {e}")
        return 1

    apply_cross_edges(target, fid, draft)
    path = fragment_path(args.gen_dir, fid)
    write_yaml(path, target)
    print(f"已写回 {path}：{len(draft.edges)} 个主题新增跨领域前置。前置清单：")
    print()
    print(field_prerequisite_list(args.gen_dir, fid), end="")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    doc = load_input(args.gen_dir)
    merged, missing = merge_fragments(doc, args.gen_dir)
    if missing:
        print(f"缺少 {len(missing)} 个领域的片段，未拼装：{'、'.join(missing)}")
        for fid in missing:
            print(f"- theroadnottaken-seed run {fid}")
        return 1
    write_yaml(args.output, merged)
    print(f"已拼装 {args.output}，校验：")
    flags = ["--prerequisites"] if args.prerequisites else []
    return skeleton_main([str(args.output), *flags])


def _add_agy_options(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--gen-dir", type=Path, default=DEFAULT_GEN_DIR, help="生成目录（含 input.yaml）"
    )
    p.add_argument(
        "--effort", default=DEFAULT_EFFORT, help=f"agy --effort（缺省 {DEFAULT_EFFORT}）"
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"agy 硬超时秒数（缺省 {DEFAULT_TIMEOUT_SECONDS}）",
    )
    p.epilog = "`--` 之后的参数原样传给 agy（放在 --print 之前）。"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="theroadnottaken-seed", description=__doc__.split("\n\n")[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract", help="从调研报告提取生成输入 input.yaml")
    p.add_argument("--research", type=Path, default=DEFAULT_RESEARCH, help="调研报告 markdown")
    p.add_argument("--output", type=Path, default=DEFAULT_GEN_DIR / "input.yaml")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("prompt", help="渲染某领域的 prompt 与 JSON schema，打印 agy 命令行")
    p.add_argument("field", help="领域 id，如 c04")
    _add_agy_options(p)
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser(
        "run", help="调用 agy 产出某领域的主题、概念、领域内前置与历史索引，写成片段"
    )
    p.add_argument("field", help="领域 id，如 c04")
    p.add_argument("--force", action="store_true", help="覆盖已存在的片段")
    _add_agy_options(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("cross", help="调用 agy 为某领域补跨领域直接前置，写回片段")
    p.add_argument("field", help="领域 id，如 b06")
    _add_agy_options(p)
    p.set_defaults(func=cmd_cross)

    p = sub.add_parser("merge", help="把全部片段拼成种子骨架并校验")
    p.add_argument(
        "--gen-dir", type=Path, default=DEFAULT_GEN_DIR, help="生成目录（含 input.yaml）"
    )
    p.add_argument("--output", type=Path, default=DEFAULT_SKELETON, help="种子骨架输出路径")
    p.add_argument(
        "-p", "--prerequisites", action="store_true", help="同时输出每领域的 markdown 前置清单"
    )
    p.set_defaults(func=cmd_merge)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    agy_args: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, agy_args = argv[:split], argv[split + 1 :]
    args = build_parser().parse_args(argv)
    args.agy_args = agy_args
    try:
        return args.func(args)
    except SeedError as exc:
        print(exc)
        return 2


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
