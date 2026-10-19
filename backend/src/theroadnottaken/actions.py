"""学习者对掌握状态的直接操作：我已掌握、其实没学过、暂不学、恢复推荐（规格用户故事 16、17、46）。

每个操作只改目标主题的 `status` 与 `updated_at`，薄弱点与验证记录原样保留；
只允许从规定的状态出发，其它情况拒绝（例如已掌握的主题不能「暂不学」）。
开始学习与验证会改状态，但它们随讲义与验证流程实现，不在这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from theroadnottaken.skeleton import Topic
from theroadnottaken.state import State, Status, TopicState

Action = Literal["claim", "unclaim", "defer", "restore"]


@dataclass(frozen=True)
class Transition:
    label: str  # 提交信息与界面上的动作名
    allowed_from: tuple[Status, ...]
    to: Status


TRANSITIONS: dict[Action, Transition] = {
    "claim": Transition("我已掌握", ("unlearned", "learning", "deferred"), "claimed"),
    "unclaim": Transition("其实没学过", ("claimed",), "unlearned"),
    "defer": Transition("暂不学", ("unlearned", "learning"), "deferred"),
    "restore": Transition("恢复推荐", ("deferred",), "unlearned"),
}

STATUS_NAMES: dict[Status, str] = {
    "unlearned": "未学",
    "learning": "学习中",
    "deferred": "暂不学",
    "claimed": "声称掌握",
    "mastered": "已掌握",
}


class TransitionError(Exception):
    """当前状态不允许该操作。"""


def apply(
    state: State, topic: Topic, action: Action, now: datetime | None = None
) -> tuple[State, str]:
    """返回新状态与人可读的提交信息；不允许时抛 `TransitionError`。"""
    t = TRANSITIONS[action]
    current = state.status_of(topic.id)
    if current not in t.allowed_from:
        allowed = "、".join(STATUS_NAMES[s] for s in t.allowed_from)
        raise TransitionError(
            f"「{topic.name}」当前为{STATUS_NAMES[current]}，「{t.label}」只适用于{allowed}的主题"
        )
    old = state.topics.get(topic.id)
    entry = TopicState(
        status=t.to,
        weak_points=list(old.weak_points) if old else [],
        verifications=list(old.verifications) if old else [],
        updated_at=now or datetime.now(UTC),
    )
    new = state.model_copy(update={"topics": {**state.topics, topic.id: entry}})
    message = f"{t.label}：{topic.name}（{topic.id}）{STATUS_NAMES[current]} → {STATUS_NAMES[t.to]}"
    return new, message
