"""骨架：读取、校验与每领域前置清单。

独立命令 `theroadnottaken-skeleton PATH [--prerequisites]`：校验一份骨架 YAML，输出通过或
带定位（行号与主题 / 领域 id）的错误列表；`--prerequisites` 另输出每领域的 markdown 前置清单
（主题名 → 直接前置名），供作者在生成与审核骨架时逐领域检查。
退出码：0 通过、1 校验失败、2 文件无法读取或解析。

骨架结构按规格 017「骨架」一节：顶层 `version`、`fields`、`topics`、`retired`。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML, YAMLError

FIELD_KINDS = ("core", "branch")
CONCEPTS_MIN, CONCEPTS_MAX = 3, 5


class SkeletonLoadError(Exception):
    """文件不存在、不是 YAML 或顶层结构不对，无法进入逐条校验。"""


@dataclass(frozen=True)
class Field:
    id: str
    name: str
    kind: str
    order: int
    line: int | None = None


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


@dataclass(frozen=True)
class Retired:
    id: str
    successors: tuple[str, ...] = ()
    line: int | None = None


@dataclass(frozen=True)
class Skeleton:
    version: object
    fields: tuple[Field, ...]
    topics: tuple[Topic, ...]
    retired: tuple[Retired, ...]
    structure_errors: tuple[str, ...] = field(default_factory=tuple)
    """结构层面的错误（缺字段、类型不对）；带这类错误的条目仍尽量保留以便其它规则继续报告。"""


# ---------------------------------------------------------------- 读取


def load_skeleton(path: Path) -> Skeleton:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkeletonLoadError(f"无法读取 {path}：{exc.strerror}") from exc
    try:
        doc = YAML(typ="rt").load(text)
    except YAMLError as exc:
        raise SkeletonLoadError(f"{path} 不是合法的 YAML：{exc}") from exc
    if not isinstance(doc, dict):
        raise SkeletonLoadError(f"{path} 顶层必须是映射（含 version / fields / topics / retired）")
    return _parse(doc)


def _parse(doc: dict) -> Skeleton:
    errors: list[str] = []
    fields = [
        f
        for f in (
            _parse_field(item, i, errors) for i, item in enumerate(_list(doc, "fields", errors))
        )
        if f is not None
    ]
    topics = [
        t
        for t in (
            _parse_topic(item, i, errors) for i, item in enumerate(_list(doc, "topics", errors))
        )
        if t is not None
    ]
    retired = [
        r
        for r in (
            _parse_retired(item, i, errors) for i, item in enumerate(_list(doc, "retired", errors))
        )
        if r is not None
    ]
    return Skeleton(doc.get("version"), tuple(fields), tuple(topics), tuple(retired), tuple(errors))


def _list(doc: dict, key: str, errors: list[str]) -> list:
    value = doc.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"顶层 {key} 必须是列表")
        return []
    return value


def _line(node: object) -> int | None:
    lc = getattr(node, "lc", None)
    return None if lc is None else lc.line + 1


def _parse_field(item: object, index: int, errors: list[str]) -> Field | None:
    where = f"fields[{index}]"
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        errors.append(f"{where}：每个领域必须是带字符串 id 的映射")
        return None
    fid = item["id"]
    where = _at(_line(item), f"领域 {fid}")
    kind = item.get("kind")
    if kind not in FIELD_KINDS:
        errors.append(f"{where}：kind 必须是 core 或 branch，当前为 {kind!r}")
    name = item.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{where}：缺少 name")
    order = item.get("order")
    if not isinstance(order, int) or isinstance(order, bool):
        errors.append(f"{where}：order 必须是整数")
    return Field(
        fid, str(name or ""), str(kind or ""), order if isinstance(order, int) else 0, _line(item)
    )


def _parse_topic(item: object, index: int, errors: list[str]) -> Topic | None:
    where = f"topics[{index}]"
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        errors.append(f"{where}：每个主题必须是带字符串 id 的映射")
        return None
    tid = item["id"]
    where = _at(_line(item), f"主题 {tid}")
    name = item.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{where}：缺少 name")
    field_id = item.get("field")
    if not isinstance(field_id, str) or not field_id:
        errors.append(f"{where}：缺少 field")
    concepts = _str_list(item, "concepts", where, errors, required=True)
    prerequisites = _str_list(item, "prerequisites", where, errors, required=True)
    history = item.get("history")
    if history is not None and not isinstance(history, str):
        errors.append(f"{where}：history 必须是字符串")
    references = _str_list(item, "references", where, errors, required=False)
    aliases = _str_list(item, "aliases", where, errors, required=False)
    return Topic(
        tid,
        str(name or ""),
        str(field_id or ""),
        concepts,
        prerequisites,
        str(history or ""),
        references,
        aliases,
        _line(item),
    )


def _parse_retired(item: object, index: int, errors: list[str]) -> Retired | None:
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        errors.append(f"retired[{index}]：每条退役记录必须是带字符串 id 的映射")
        return None
    where = _at(_line(item), f"退役主题 {item['id']}")
    successors = _str_list(item, "successors", where, errors, required=False)
    return Retired(item["id"], successors, _line(item))


def _str_list(
    item: dict, key: str, where: str, errors: list[str], *, required: bool
) -> tuple[str, ...]:
    value = item.get(key)
    if value is None:
        if required:
            errors.append(f"{where}：缺少 {key}（没有则写 []）")
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{where}：{key} 必须是字符串列表")
        return ()
    return tuple(value)


def _at(line: int | None, what: str) -> str:
    return what if line is None else f"第 {line} 行 {what}"


# ---------------------------------------------------------------- 校验


def validate(skeleton: Skeleton) -> list[str]:
    """返回错误列表（空表示通过）。每条错误都带主题或领域 id，能定位则带行号。"""
    errors = list(skeleton.structure_errors)
    v = skeleton.version
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        errors.append(f"version 必须是正整数，当前为 {v!r}")

    retired = {r.id: r for r in skeleton.retired}
    fields = {f.id: f for f in skeleton.fields}
    topics: dict[str, Topic] = {}
    for t in skeleton.topics:
        where = _at(t.line, f"主题 {t.id}")
        if t.id in topics:
            errors.append(f"{where}：id 重复")
        topics.setdefault(t.id, t)
        if t.id in retired:
            errors.append(f"{where}：id 与退役主题重复（退役 id 永不复用）")

    for t in skeleton.topics:
        where = _at(t.line, f"主题 {t.id}")
        if t.field not in fields:
            errors.append(f"{where}：领域 {t.field} 未定义")
        if not CONCEPTS_MIN <= len(t.concepts) <= CONCEPTS_MAX:
            errors.append(f"{where}：概念必须 3–5 个，当前 {len(t.concepts)} 个")
        for p in t.prerequisites:
            if p in topics:
                continue
            if p in retired:
                successors = "、".join(retired[p].successors) or "无"
                errors.append(f"{where}：前置 {p} 已退役（后继：{successors}）")
            else:
                errors.append(f"{where}：前置 {p} 不存在")
        valid = [p for p in t.prerequisites if p in topics]
        if t.prerequisites and not valid:
            errors.append(f"{where}：不是初始前沿（前置非空），却没有一条有效入边")
        if t.field in fields and fields[t.field].kind == "core":
            for p in valid:
                pf = topics[p].field
                if pf in fields and fields[pf].kind == "branch":
                    errors.append(f"{where}：主干主题的前置只能是主干主题，{p} 属于分支领域 {pf}")

    graph = {t.id: [p for p in t.prerequisites if p in topics] for t in topics.values()}
    cycles = _find_cycles(graph)
    for cycle in cycles:
        first = topics[cycle[0]]
        chain = " → ".join([*cycle, cycle[0]])
        errors.append(f"{_at(first.line, f'主题 {cycle[0]}')}：前置成环：{chain}")

    reachable = _reachable_from_frontier(graph)
    on_cycle = {tid for cycle in cycles for tid in cycle}
    for t in topics.values():
        if t.id in reachable or t.id in on_cycle or len(graph[t.id]) < len(t.prerequisites):
            continue
        errors.append(f"{_at(t.line, f'主题 {t.id}')}：从初始前沿不可达（前置链上有环或缺失）")
    return errors


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """沿前置边做深度优先遍历，每个环按首次发现的顺序返回一次。"""
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        color[node] = GREY
        stack.append(node)
        for p in graph[node]:
            if color[p] == GREY:
                cycles.append(_rotate(stack[stack.index(p) :]))
            elif color[p] == WHITE:
                visit(p)
        stack.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            visit(node)
    return cycles


def _rotate(cycle: list[str]) -> list[str]:
    """把环写成从字典序最小的 id 出发的学习顺序链（stack 里是「主题 → 其前置」，要反过来）。"""
    order = list(reversed(cycle))
    start = order.index(min(order))
    return order[start:] + order[:start]


def _reachable_from_frontier(graph: dict[str, list[str]]) -> set[str]:
    """一个主题可达，当且仅当它的全部前置都可达；初始前沿（无前置）天然可达。"""
    reachable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for tid, prereqs in graph.items():
            if tid not in reachable and all(p in reachable for p in prereqs):
                reachable.add(tid)
                changed = True
    return reachable


# ---------------------------------------------------------------- 前置清单


def prerequisite_lists(skeleton: Skeleton) -> str:
    """每领域一节 markdown：`- 主题名 ← 直接前置名；…`，跨领域前置附领域 id，缺失的标出。"""
    topics = {t.id: t for t in skeleton.topics}
    kind_name = {"core": "主干", "branch": "分支"}
    sections: list[str] = []
    for f in sorted(skeleton.fields, key=lambda f: (f.kind != "core", f.order, f.id)):
        lines = [f"## {f.id} {f.name}（{kind_name.get(f.kind, f.kind)}）", ""]
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
    parser = argparse.ArgumentParser(
        prog="theroadnottaken-skeleton", description=__doc__.split("\n\n")[1]
    )
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
