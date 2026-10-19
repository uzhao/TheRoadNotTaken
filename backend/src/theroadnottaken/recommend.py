"""推荐：从骨架与掌握状态算出唯一一张推荐卡（规格「推荐」一节，工单 013）。

纯函数，只读后端写的状态，无随机，每次请求重算：
- 候选 = 全部直接前置均已掌握的「未学 / 学习中」主题 + 所有「声称掌握」主题；
  分支领域的主题仅当该领域「纳入推荐」时参与；「暂不学」不在候选中，
  只在其余候选耗尽时按同样的前置规则回归，并标「之前暂不学」。
- 字典序取第一个：待验证 > 学习中 > 主干 > 与最近一次状态变化的主题同领域 > 直接后继多 > id 升序。
  「最近一次状态变化」指开始学习或验证通过，即状态为学习中或已掌握的条目里 `updated_at` 最新者。
- 理由取决出胜负的那一级（与第二名比较）；只有一个候选或比到 id 才分出时，
  改用推荐主题自身最靠前的一条长处。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from theroadnottaken.skeleton import Skeleton, Topic
from theroadnottaken.state import State

Kind = Literal["learn", "verify"]

EMPTY_HINT = "当前没有可学的主题。可以在左侧开启分支领域的「纳入推荐」，或在看板上自选主题。"


@dataclass(frozen=True)
class Recommendation:
    topic: Topic
    kind: Kind
    reason: str
    was_deferred: bool


def recommend(skeleton: Skeleton, state: State) -> Recommendation | None:
    """唯一推荐；没有任何候选（含暂不学回归）时返回 None。"""
    fields = {f.id: f for f in skeleton.fields}
    included = set(state.included_branches)
    successors: dict[str, int] = {t.id: 0 for t in skeleton.topics}
    for t in skeleton.topics:
        for p in t.prerequisites:
            successors[p] += 1

    def eligible(t: Topic) -> bool:
        f = fields[t.field]
        return f.kind == "core" or f.id in included

    def unlocked(t: Topic) -> bool:
        return all(state.status_of(p) == "mastered" for p in t.prerequisites)

    pool = [t for t in skeleton.topics if eligible(t)]
    candidates = [
        t
        for t in pool
        if state.status_of(t.id) == "claimed"
        or (state.status_of(t.id) in ("unlearned", "learning") and unlocked(t))
    ]
    was_deferred = False
    if not candidates:
        candidates = [t for t in pool if state.status_of(t.id) == "deferred" and unlocked(t)]
        was_deferred = True
    if not candidates:
        return None

    recent = _recent_field(skeleton, state)
    levels: list[tuple[Callable[[Topic], object], Callable[[Topic], str | None]]] = [
        (
            lambda t: state.status_of(t.id) != "claimed",
            lambda t: "你声称掌握，先验证" if state.status_of(t.id) == "claimed" else None,
        ),
        (
            lambda t: state.status_of(t.id) != "learning",
            lambda t: "上次没学完" if state.status_of(t.id) == "learning" else None,
        ),
        (
            lambda t: fields[t.field].kind != "core",
            lambda t: "主干优先于分支" if fields[t.field].kind == "core" else None,
        ),
        (
            lambda t: t.field != recent,
            lambda t: f"接着「{fields[t.field].name}」往下" if t.field == recent else None,
        ),
        (
            lambda t: -successors[t.id],
            lambda t: f"它解锁 {successors[t.id]} 个主题" if successors[t.id] else None,
        ),
        (lambda t: t.id, lambda t: None),
    ]

    ranked = sorted(candidates, key=lambda t: tuple(key(t) for key, _ in levels))
    best = ranked[0]
    reason = None
    if len(ranked) > 1:
        runner_up = ranked[1]
        decisive = next(i for i, (key, _) in enumerate(levels) if key(best) != key(runner_up))
        reason = levels[decisive][1](best)
    if reason is None:
        # 主干是常态，单独作为理由没有信息量；只在与分支比出胜负时才说
        strengths = (say(best) for i, (_, say) in enumerate(levels) if i != 2)
        reason = next((s for s in strengths if s), "前置都已掌握，可以开始")

    kind: Kind = "verify" if state.status_of(best.id) == "claimed" else "learn"
    return Recommendation(topic=best, kind=kind, reason=reason, was_deferred=was_deferred)


def _recent_field(skeleton: Skeleton, state: State) -> str | None:
    """最近一次开始学习或验证通过的主题所在领域；同一时刻按 id 取大者以保持确定。"""
    field_of = {t.id: t.field for t in skeleton.topics}
    touched = [
        (entry.updated_at, tid)
        for tid, entry in state.topics.items()
        if tid in field_of and entry.status in ("learning", "mastered")
    ]
    if not touched:
        return None
    return field_of[max(touched)[1]]
