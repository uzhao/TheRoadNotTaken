"""骨架：读取、校验与每领域前置清单。

独立命令 `theroadnottaken-skeleton PATH [--prerequisites]`：校验一份骨架 YAML，输出通过或
带定位（行号与主题 / 领域 id）的错误列表；`--prerequisites` 另输出每领域的 markdown 前置清单
（主题名 → 直接前置名），供作者在生成与审核骨架时逐领域检查。
退出码：0 通过、1 校验失败、2 文件无法读取或解析。

骨架结构按规格 017「骨架」一节：顶层 `version`、`fields`、`topics`、`retired`。结构层面的检查
（缺键、类型）与图规则都在这里手写，而不用 pydantic：错误要用中文、带行号、并且一次列出全部，
而 pydantic 对结构错误是整体拒绝、消息为英文（pydantic 按规格用于状态文件与 agent 结构化输出）。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML, YAMLError

FIELD_KINDS = ("core", "branch")
KIND_NAMES = {"core": "主干", "branch": "分支"}
CONCEPTS_MIN, CONCEPTS_MAX = 3, 5
TOP_LEVEL_LISTS = ("fields", "topics", "retired")
CLI_DESCRIPTION = "校验一份骨架 YAML：输出通过或带行号与 id 的错误列表，-p 另输出每领域的前置清单。"


class SkeletonLoadError(Exception):
    """文件不存在、不是 YAML 或顶层结构不对，无法进入逐条校验。"""


@dataclass(frozen=True)
class Field:
    id: str
    name: str
    kind: str
    order: int
    line: int | None = None

    @property
    def where(self) -> str:
        return _located(self.line, f"领域 {self.id}")


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    field: str
    concepts: tuple[str, ...]
    prerequisites: tuple[str, ...]
    history: str
    references: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    line: int | None = None

    @property
    def where(self) -> str:
        return _located(self.line, f"主题 {self.id}")


@dataclass(frozen=True)
class Retired:
    id: str
    successors: tuple[str, ...] = ()
    line: int | None = None

    @property
    def where(self) -> str:
        return _located(self.line, f"退役主题 {self.id}")


@dataclass(frozen=True)
class Skeleton:
    version: object
    fields: tuple[Field, ...]
    topics: tuple[Topic, ...]
    retired: tuple[Retired, ...]
    structure_errors: tuple[str, ...] = ()
    """结构层面的错误（缺键、类型不对）；带这类错误的条目仍尽量保留，让图规则继续报告。"""


def _located(line: int | None, what: str) -> str:
    return what if line is None else f"第 {line} 行 {what}"


# ---------------------------------------------------------------- 读取


def load_skeleton(path: Path) -> Skeleton:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) else "不是 UTF-8 文本"
        raise SkeletonLoadError(f"无法读取 {path}：{reason}") from exc
    try:
        doc = YAML(typ="rt").load(text)
    except YAMLError as exc:
        raise SkeletonLoadError(f"{path} 不是合法的 YAML：{exc}") from exc
    if not isinstance(doc, dict):
        raise SkeletonLoadError(f"{path} 顶层必须是映射（含 version / fields / topics / retired）")
    return _parse(doc)


def _parse(doc: dict) -> Skeleton:
    errors: list[str] = []
    fields = _parse_list(doc, "fields", _parse_field, errors)
    topics = _parse_list(doc, "topics", _parse_topic, errors)
    retired = _parse_list(doc, "retired", _parse_retired, errors)
    return Skeleton(doc.get("version"), fields, topics, retired, tuple(errors))


def _parse_list[T](
    doc: dict,
    key: str,
    parse_item: Callable[[dict, list[str]], T],
    errors: list[str],
) -> tuple[T, ...]:
    """读顶层列表；每项必须是带非空字符串 id 的映射，否则记错并跳过该项。"""
    value = doc.get(key)
    if value is None:
        errors.append(f"顶层缺少 {key}（没有则写 []）")
        return ()
    if not isinstance(value, list):
        errors.append(f"顶层 {key} 必须是列表")
        return ()
    items: list[T] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            errors.append(f"{key}[{index}]：每项必须是带非空字符串 id 的映射")
            continue
        items.append(parse_item(item, errors))
    return tuple(items)


def _line(node: object) -> int | None:
    lc = getattr(node, "lc", None)
    return None if lc is None else lc.line + 1


def _parse_field(item: dict, errors: list[str]) -> Field:
    field = Field(
        item["id"],
        _required_str(item, "name"),
        _required_str(item, "kind"),
        _required_int(item, "order"),
        _line(item),
    )
    _check_str(item, "name", field.where, errors)
    if item.get("kind") not in FIELD_KINDS:
        errors.append(f"{field.where}：kind 必须是 core 或 branch，当前为 {item.get('kind')!r}")
    if not _is_int(item.get("order")):
        errors.append(f"{field.where}：order 必须是整数")
    return field


def _parse_topic(item: dict, errors: list[str]) -> Topic:
    topic = Topic(
        item["id"],
        _required_str(item, "name"),
        _required_str(item, "field"),
        _str_list(item, "concepts"),
        _str_list(item, "prerequisites"),
        _required_str(item, "history"),
        _str_list(item, "references"),
        _str_list(item, "aliases"),
        _line(item),
    )
    for key in ("name", "field", "history"):
        _check_str(item, key, topic.where, errors)
    for key in ("concepts", "prerequisites", "references"):
        _check_str_list(item, key, topic.where, errors, required=True)
    _check_str_list(item, "aliases", topic.where, errors, required=False)
    return topic


def _parse_retired(item: dict, errors: list[str]) -> Retired:
    retired = Retired(item["id"], _str_list(item, "successors"), _line(item))
    _check_str_list(item, "successors", retired.where, errors, required=False)
    return retired


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _required_str(item: dict, key: str) -> str:
    value = item.get(key)
    return value if isinstance(value, str) else ""


def _required_int(item: dict, key: str) -> int:
    value = item.get(key)
    return value if _is_int(value) else 0


def _str_list(item: dict, key: str) -> tuple[str, ...]:
    value = item.get(key)
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(value)
    return ()


def _check_str(item: dict, key: str, where: str, errors: list[str]) -> None:
    if not isinstance(item.get(key), str):
        errors.append(f"{where}：缺少 {key}（必须是字符串）")


def _check_str_list(item: dict, key: str, where: str, errors: list[str], *, required: bool) -> None:
    value = item.get(key)
    if value is None:
        if required:
            errors.append(f"{where}：缺少 {key}（没有则写 []）")
    elif not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{where}：{key} 必须是字符串列表")


# ---------------------------------------------------------------- 校验


def validate(skeleton: Skeleton) -> list[str]:
    """返回错误列表（空表示通过）。每条错误都带主题或领域 id，能定位则带行号。"""
    errors = list(skeleton.structure_errors)
    if not _is_int(skeleton.version) or skeleton.version < 1:  # type: ignore[operator]
        errors.append(f"version 必须是正整数，当前为 {skeleton.version!r}")

    fields = _unique_by_id(skeleton.fields, errors)
    retired = _unique_by_id(skeleton.retired, errors)
    topics = _unique_by_id(skeleton.topics, errors)
    for t in topics.values():
        if t.id in retired:
            errors.append(f"{t.where}：id 与退役主题重复（退役 id 永不复用）")
    for r in retired.values():
        for s in r.successors:
            if s not in topics:
                errors.append(f"{r.where}：后继 {s} 不存在")

    for t in topics.values():
        if t.field and t.field not in fields:
            errors.append(f"{t.where}：领域 {t.field} 未定义")
        if not CONCEPTS_MIN <= len(t.concepts) <= CONCEPTS_MAX:
            errors.append(f"{t.where}：概念必须 3–5 个，当前 {len(t.concepts)} 个")
        errors.extend(_prerequisite_errors(t, topics, fields, retired))

    errors.extend(_connectivity_errors(topics))
    return errors


def _unique_by_id[T: Field | Topic | Retired](
    items: Sequence[T], errors: list[str]
) -> dict[str, T]:
    by_id: dict[str, T] = {}
    for item in items:
        if item.id in by_id:
            errors.append(f"{item.where}：id 重复")
        else:
            by_id[item.id] = item
    return by_id


def _prerequisite_errors(
    t: Topic, topics: dict[str, Topic], fields: dict[str, Field], retired: dict[str, Retired]
) -> list[str]:
    """前置存在、不重复；主干主题的前置只能是主干；非初始前沿至少一条有效入边。"""
    errors: list[str] = []
    seen: set[str] = set()
    for p in t.prerequisites:
        if p in seen:
            errors.append(f"{t.where}：前置 {p} 重复")
        seen.add(p)
        if p in topics:
            continue
        if p in retired:
            successors = "、".join(retired[p].successors) or "无"
            errors.append(f"{t.where}：前置 {p} 已退役（后继：{successors}）")
        else:
            errors.append(f"{t.where}：前置 {p} 不存在")
    valid = [p for p in t.prerequisites if p in topics]
    if t.prerequisites and not valid:
        errors.append(f"{t.where}：不是初始前沿（前置非空），却没有一条有效入边")
    if t.field in fields and fields[t.field].kind == "core":
        for p in valid:
            pf = topics[p].field
            if pf in fields and fields[pf].kind == "branch":
                errors.append(f"{t.where}：主干主题的前置只能是主干主题，{p} 属于分支领域 {pf}")
    return errors


def _connectivity_errors(topics: dict[str, Topic]) -> list[str]:
    """无环；所有主题从初始前沿可达。

    环上的主题只在环的错误里出现；前置缺失的主题已由「前置存在」报告；两者下游被挡住的主题
    才报「不可达」，让作者看到上游问题的影响范围。
    """
    graph = {t.id: [p for p in t.prerequisites if p in topics] for t in topics.values()}
    cycles = _find_cycles(graph)
    errors = [
        f"{topics[cycle[0]].where}：前置成环：{' → '.join([*cycle, cycle[0]])}" for cycle in cycles
    ]
    on_cycle = {tid for cycle in cycles for tid in cycle}
    has_missing = {t.id for t in topics.values() if len(graph[t.id]) < len(t.prerequisites)}
    reachable = _reachable_from_frontier(graph, blocked=has_missing)
    for t in topics.values():
        if t.id not in reachable and t.id not in on_cycle and t.id not in has_missing:
            errors.append(f"{t.where}：从初始前沿不可达（前置链上有环或缺失）")
    return errors


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """沿前置边做深度优先遍历，每个环按首次发现的顺序返回一次。"""
    white, grey, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        color[node] = grey
        stack.append(node)
        for p in graph[node]:
            if color[p] == grey:
                cycles.append(_learning_order(stack[stack.index(p) :]))
            elif color[p] == white:
                visit(p)
        stack.pop()
        color[node] = black

    for node in graph:
        if color[node] == white:
            visit(node)
    return cycles


def _learning_order(cycle: list[str]) -> list[str]:
    """把环写成从字典序最小的 id 出发的学习顺序链（stack 里是「主题 → 其前置」，要反过来）。"""
    order = list(reversed(cycle))
    start = order.index(min(order))
    return order[start:] + order[:start]


def _reachable_from_frontier(graph: dict[str, list[str]], *, blocked: set[str]) -> set[str]:
    """一个主题可达，当且仅当它的全部前置都可达；初始前沿（无前置）天然可达；`blocked` 永不可达。"""
    reachable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for tid, prereqs in graph.items():
            if tid in reachable or tid in blocked:
                continue
            if all(p in reachable for p in prereqs):
                reachable.add(tid)
                changed = True
    return reachable


# ---------------------------------------------------------------- 前置清单


def prerequisite_lists(skeleton: Skeleton) -> str:
    """每领域一节 markdown：`- 主题名 ← 直接前置名；…`，跨领域前置附领域 id，缺失的标出。"""
    topics = {t.id: t for t in skeleton.topics}
    sections: list[str] = []
    for f in sorted(skeleton.fields, key=lambda f: (f.kind != "core", f.order, f.id)):
        lines = [f"## {f.id} {f.name}（{KIND_NAMES.get(f.kind, f.kind)}）", ""]
        for t in skeleton.topics:
            if t.field != f.id:
                continue
            if not t.prerequisites:
                lines.append(f"- {t.name} ←（初始前沿）")
                continue
            names = []
            for p in t.prerequisites:
                if p not in topics:
                    names.append(f"{p}（不存在）")
                elif topics[p].field == t.field:
                    names.append(topics[p].name)
                else:
                    names.append(f"{topics[p].name}（{topics[p].field}）")
            lines.append(f"- {t.name} ← {'；'.join(names)}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------- 命令行


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="theroadnottaken-skeleton", description=CLI_DESCRIPTION)
    parser.add_argument("path", type=Path, help="骨架 YAML 文件")
    parser.add_argument(
        "-p", "--prerequisites", action="store_true", help="输出每领域的 markdown 前置清单"
    )
    args = parser.parse_args(argv)

    try:
        skeleton = load_skeleton(args.path)
    except SkeletonLoadError as exc:
        print(exc)
        return 2

    errors = validate(skeleton)
    if errors:
        print(f"校验失败：{len(errors)} 个错误")
        for e in errors:
            print(f"- {e}")
    else:
        print(f"通过：{len(skeleton.fields)} 个领域、{len(skeleton.topics)} 个主题")
    if args.prerequisites:
        print()
        print(prerequisite_lists(skeleton), end="")
    return 1 if errors else 0


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
