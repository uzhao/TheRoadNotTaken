"""讲义：拼 prompt、跑 agy、搬运校验与一次重试、搬入数据目录（规格「讲义、追问与插图」）。

- prompt 由带版本号的模板拼装（`prompts/lecture.v1.md`）：画像、主题定义、前置名、薄弱点、
  历史动机索引、插图契约、提议规则与输出格式。agy 的最终回复就是讲义 markdown。
- 每个任务目录放一份统一的 `matplotlibrc`，agy 在任务目录里跑脚本时 matplotlib 自动读取它。
- 搬运校验（`check`）不过时在同一会话重试一次，prompt 列出错误并给出「修图或删引用」两个出口；
  再不过任务失败、目录保留，状态不动。通过后整目录替换 `lectures/<主题id>/`（追问记录保留），
  写 `meta.json` 并提交 git，任务目录由运行器删除。
- 缓存：`lectures/<主题id>/lecture.md` 存在即命中，不启动 agy。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path, PurePosixPath
from string import Template
from typing import Any

from theroadnottaken import agy
from theroadnottaken.datadir import DataDir
from theroadnottaken.jobs import Job, JobRunner, JobSpec, Reject, Retry, Verdict
from theroadnottaken.skeleton import Topic
from theroadnottaken.state import State

log = logging.getLogger(__name__)

LECTURES_DIR = "lectures"
LECTURE_FILE = "lecture.md"
META_FILE = "meta.json"
FIGURES_DIR = "figures"
FOLLOWUPS_FILE = "followups.jsonl"

TEMPLATE = "lecture.v1"
FIX_TEMPLATE = "lecture-fix.v1"
EFFORT: agy.Effort = "high"
TIMEOUT = 600.0  # 讲义硬超时 10 分钟
MAX_FIGURES = 4
MAX_FIGURE_BYTES = 500 * 1024
FIGURE_SUFFIXES = (".svg", ".png")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CJK_FONT = "Noto Sans CJK"

# 后端统一的绘图环境（规格：Noto Sans CJK、SVG 文字不转路径、固定画布与 dpi、mathtext、不用 TeX）
MATPLOTLIBRC = f"""\
# 由 TheRoadNotTaken 后端放入每个生成任务目录；agent 不要修改。
font.family: sans-serif
font.sans-serif: {CJK_FONT} SC, {CJK_FONT} JP, DejaVu Sans
axes.unicode_minus: False
text.usetex: False
mathtext.fontset: dejavusans
svg.fonttype: none
figure.figsize: 6.4, 4.0
figure.dpi: 100
savefig.dpi: 150
savefig.format: svg
savefig.bbox: tight
figure.facecolor: white
axes.facecolor: white
savefig.facecolor: white
"""

# 行内插图 `![图注](路径 可选标题)`：取括号里的第一个词作路径，标题写法不论（"…"、'…'、(…)）；
# 图注里允许一层方括号（如区间 [a,b]）
IMAGE_RE = re.compile(r"!\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^)]*)\)")
# 引用式插图 `![图注][标签]`：路径不在原处，不允许
REF_IMAGE_RE = re.compile(r"!\[(?:[^\[\]]|\[[^\]]*\])*\]\[")
FIGURE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def definition_hash(topic: Topic) -> str:
    """主题定义（名称 + 概念提纲 + 前置）的哈希，用于判定讲义是否过时（029）。"""
    payload = {
        "name": topic.name,
        "concepts": list(topic.concepts),
        "prerequisites": list(topic.prerequisites),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def _template(name: str) -> Template:
    path = resources.files("theroadnottaken").joinpath("prompts", f"{name}.md")
    return Template(path.read_text(encoding="utf-8"))


def render_prompt(store: DataDir, topic: Topic, weak_points: list[str]) -> str:
    sk = store.skeleton
    field_name = next(f.name for f in sk.fields if f.id == topic.field)
    names = {t.id: t.name for t in sk.topics}
    prerequisites = "、".join(names[p] for p in topic.prerequisites) or "无（只需高中数学）"
    weak = (
        "学习者在验证中暴露出以下薄弱点，正文与例题要重点覆盖：\n"
        + "\n".join(f"- {w}" for w in weak_points)
        if weak_points
        else "暂无。"
    )
    return _template(TEMPLATE).substitute(
        topic_name=topic.name,
        topic_id=topic.id,
        field_name=field_name,
        concepts_block="\n".join(f"  {i}. {c}" for i, c in enumerate(topic.concepts, start=1)),
        prerequisites=prerequisites,
        history=topic.history or "（无）",
        weak_points_block=weak,
        **_figure_limits(),
    )


def render_fix_prompt(topic: Topic, errors: list[str]) -> str:
    return _template(FIX_TEMPLATE).substitute(
        topic_name=topic.name,
        errors_block="\n".join(f"- {e}" for e in errors),
        **_figure_limits(),
    )


def _figure_limits() -> dict[str, int]:
    return {"max_figures": MAX_FIGURES, "max_figure_kb": MAX_FIGURE_BYTES // 1024}


# ---- 搬运校验 ----


@dataclass(frozen=True)
class Checked:
    """校验结果：错误列表，以及通过时要搬运的插图文件名（`figures/` 下）。"""

    errors: list[str]
    figures: list[str] = field(default_factory=list)


def check(job_dir: Path, response: str) -> Checked:
    """按规格的搬运校验检查一次产出；`response` 是 agy 的最终回复（讲义正文）。"""
    errors: list[str] = []
    if not response.strip():
        return Checked(["讲义为空：最终回复必须是讲义 markdown"])
    if not response.lstrip().startswith("# "):
        errors.append("讲义必须以一级标题开头（第一行写「# 主题名」），不要有前言")
    if REF_IMAGE_RE.search(response):
        errors.append("插图只能用行内写法 ![图注](figures/<名>.svg)，不能用引用式 ![图注][标签]")

    figures: list[str] = []
    for caption, destination in IMAGE_RE.findall(response):
        target = (destination.split() or [""])[0].removeprefix("<").removesuffix(">")
        name = _figure_name(target, errors)
        if name is None:
            continue
        if not caption.strip():
            errors.append(f"插图 {target} 缺少图注：![…] 里要写一句中文图注")
        if name not in figures:
            figures.append(name)
    if len(figures) > MAX_FIGURES:
        errors.append(f"插图过多：引用了 {len(figures)} 张，至多 {MAX_FIGURES} 张")
    for name in figures:
        _check_figure_file(job_dir / FIGURES_DIR / name, f"{FIGURES_DIR}/{name}", errors)
    return Checked(errors, figures if not errors else [])


def _figure_name(target: str, errors: list[str]) -> str | None:
    """`figures/<名>.svg|png` → `<名>.svg|png`；路径不合规时记错误并返回 None。"""
    path = PurePosixPath(target)
    if not target or path.is_absolute() or "\\" in target or ".." in path.parts:
        errors.append(f"插图路径 {target or '（空）'} 不合规：只能是相对路径，不能含 ..")
        return None
    if (
        len(path.parts) != 2
        or path.parts[0] != FIGURES_DIR
        or path.suffix not in FIGURE_SUFFIXES
        or not FIGURE_NAME_RE.match(path.name)
    ):
        errors.append(f"插图路径 {target} 不合规：必须是 figures/<名>.svg 或 figures/<名>.png")
        return None
    return path.name


def _check_figure_file(path: Path, shown: str, errors: list[str]) -> None:
    if path.is_symlink() or not path.is_file():
        errors.append(f"插图 {shown} 不存在：脚本没有执行成功，或文件名与引用不一致")
        return
    size = path.stat().st_size
    if size > MAX_FIGURE_BYTES:
        errors.append(
            f"插图 {shown} 过大：{size // 1024} KB，每张至多 {MAX_FIGURE_BYTES // 1024} KB"
        )
        return
    if path.suffix == ".png":
        if not path.read_bytes().startswith(PNG_SIGNATURE):
            errors.append(f"插图 {shown} 不是合法的 PNG 文件")
        return
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        errors.append(f"插图 {shown} 不是合法的 SVG：XML 无法解析（{exc}）")
        return
    if root.tag.rsplit("}", 1)[-1] != "svg":
        errors.append(f"插图 {shown} 不是合法的 SVG：根元素不是 <svg>")


# ---- 搬入数据目录 ----


def install(
    store: DataDir,
    topic: Topic,
    job_dir: Path,
    response: str,
    figures: list[str],
    meta: dict[str, Any],
) -> None:
    """把通过校验的产出整目录替换进 `lectures/<主题id>/` 并提交 git；追问记录保留。

    只搬讲义、被引用的插图与同名 `.py` 脚本，其余文件丢弃。
    """
    lectures = store.root / LECTURES_DIR
    target = lectures / topic.id
    staging = lectures / f".{topic.id}.new"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        (staging / FIGURES_DIR).mkdir(parents=True)
        (staging / LECTURE_FILE).write_text(response, encoding="utf-8")
        for name in figures:
            src = job_dir / FIGURES_DIR / name
            shutil.copyfile(src, staging / FIGURES_DIR / name)
            script = src.with_suffix(".py")
            if script.is_file() and not script.is_symlink():
                shutil.copyfile(script, staging / FIGURES_DIR / script.name)
        (staging / META_FILE).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if (target / FOLLOWUPS_FILE).exists():
            shutil.copyfile(target / FOLLOWUPS_FILE, staging / FOLLOWUPS_FILE)
        store.replace_dir(target, staging, message=f"生成讲义：{topic.name}（{topic.id}）")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# ---- 学习页的服务 ----


class Lectures:
    """开始学习与讲义缓存；同一主题同时至多一个讲义任务。"""

    def __init__(self, store: DataDir, jobs: JobRunner) -> None:
        self.store = store
        self.jobs = jobs
        self._running: dict[str, Job] = {}

    def lecture_dir(self, topic_id: str) -> Path:
        return self.store.root / LECTURES_DIR / topic_id

    def cached(self, topic_id: str) -> dict[str, Any] | None:
        d = self.lecture_dir(topic_id)
        if not (d / LECTURE_FILE).is_file():
            return None
        return {
            "markdown": (d / LECTURE_FILE).read_text(encoding="utf-8"),
            "meta": json.loads((d / META_FILE).read_text(encoding="utf-8")),
        }

    def figure(self, topic_id: str, name: str) -> Path | None:
        """插图文件：先找缓存的讲义，再找在跑的讲义任务（画好即可显示）；越界或不存在为 None。"""
        if not FIGURE_NAME_RE.match(name) or PurePosixPath(name).suffix not in FIGURE_SUFFIXES:
            return None
        job = self.running(topic_id)
        dirs = [self.lecture_dir(topic_id), *([job.dir] if job else [])]
        for d in dirs:
            figures = (d / FIGURES_DIR).resolve()
            path = (figures / name).resolve()
            if path.parent == figures and path.is_file():
                return path
        return None

    def running(self, topic_id: str) -> Job | None:
        job = self._running.get(topic_id)
        return job if job is not None and not job.finished else None

    def generate(self, topic: Topic, state: State) -> Job:
        """提交讲义任务（已有在跑的就返回它）。须在事件循环内调用。"""
        job = self.running(topic.id)
        if job is not None:
            return job
        entry = state.topics.get(topic.id)
        weak_points = list(entry.weak_points) if entry else []
        prompt = render_prompt(self.store, topic, weak_points)

        def postprocess(job_dir: Path, data: dict[str, Any], attempt: int) -> Verdict:
            response = data.get("response") or ""
            checked = check(job_dir, response)
            if checked.errors:
                if attempt == 1:
                    return Retry(
                        agy.Invocation(
                            prompt=render_fix_prompt(topic, checked.errors),
                            effort=EFFORT,
                            conversation_id=data.get("conversation_id"),
                        ),
                        checked.errors,
                    )
                return Reject(
                    {
                        "kind": "validation",
                        "message": "讲义两次未通过搬运校验",
                        "errors": checked.errors,
                    }
                )
            meta = {
                "generated_at": datetime.now(UTC).isoformat(),
                "model": None,  # null = agy 全局设置里的默认模型
                "effort": EFFORT,
                "template": TEMPLATE,
                "definition_hash": definition_hash(topic),
                "weak_points": weak_points,
                "regenerations": 0,
                "job_id": job_dir.name,
                "conversation_id": data.get("conversation_id"),
                "attempts": attempt,
            }
            install(self.store, topic, job_dir, response, checked.figures, meta)
            return {"lecture": True}

        spec = JobSpec(
            kind="lecture",
            invocation=agy.Invocation(prompt=prompt, effort=EFFORT),
            timeout=TIMEOUT,
            conversation_topic=topic.id,
            delete_dir_on_success=True,
            postprocess=postprocess,
            files=(("matplotlibrc", MATPLOTLIBRC),),
        )
        job = self.jobs.submit(spec)
        self._running[topic.id] = job
        return job


def check_cjk_font() -> bool:
    """插图要用的中文字体是否已安装；缺了只记警告（图里的中文会变方框）。"""
    try:
        out = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        log.warning("无法运行 fc-list 检查字体；插图需要 %s 字体", CJK_FONT)
        return False
    if CJK_FONT not in out:
        log.warning("未找到 %s 字体，插图中的中文将无法显示", CJK_FONT)
        return False
    return True
