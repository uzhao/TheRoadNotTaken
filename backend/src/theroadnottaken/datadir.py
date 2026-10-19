"""数据目录：全部持久数据所在的唯一根目录，一个本地 git 仓库（见 GLOSSARY「数据目录」）。

`open_data_dir` 在启动时做三件事：
1. 初始化缺失的部分——复制种子骨架、建立空的 `state.json` / `conversations.json` /
   `proposals.yaml`、写 `.gitignore`（忽略 `jobs/`）、`git init` 并提交首个 commit。
   已存在的文件一律不碰。
2. 读入并校验骨架（`skeleton.yaml`），不合法抛 `StartupError`，指出位置。
3. 校验状态文件（`state.json`）与会话映射（`conversations.json`），不合法同样抛 `StartupError`。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from theroadnottaken.files import write_json_atomic
from theroadnottaken.skeleton import Skeleton, SkeletonLoadError, load_skeleton, validate
from theroadnottaken.state import State, StateError, load_state, save_state

SKELETON_FILE = "skeleton.yaml"
STATE_FILE = "state.json"
CONVERSATIONS_FILE = "conversations.json"
PROPOSALS_FILE = "proposals.yaml"
GITIGNORE_FILE = ".gitignore"
JOBS_DIR = "jobs"

# 空文件的初始内容：状态与会话映射是空对象，提议清单是空列表。
INITIAL_CONTENT: dict[str, str] = {
    STATE_FILE: "{}\n",
    CONVERSATIONS_FILE: "{}\n",
    PROPOSALS_FILE: "# 主题提议清单（追加式；只有后端写）\n[]\n",
    GITIGNORE_FILE: f"# 生成任务目录是一次性的工作目录，不入库\n{JOBS_DIR}/\n",
}

# 数据目录的提交者身份：与作者的全局 git 配置无关，机器上没配置 git 也能提交。
GIT_IDENTITY = ["-c", "user.name=TheRoadNotTaken", "-c", "user.email=theroadnottaken@localhost"]


class StartupError(Exception):
    """启动失败（骨架或状态文件不合法）。消息已含文件与定位，可直接打印。"""


@dataclass(frozen=True)
class DataDir:
    root: Path
    skeleton: Skeleton
    # 串行化「读—改—写—提交」：请求在线程池里并发执行
    _write_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False
    )

    @property
    def state_path(self) -> Path:
        return self.root / STATE_FILE

    def read_state(self) -> State:
        """每次读文件：状态由后端写入后下一请求立即可见，测试也可直接写文件构造状态。"""
        try:
            return load_state(self.state_path)
        except StateError as exc:
            raise StartupError(f"状态文件不合法：\n{exc}") from exc

    def update_state(self, change: Callable[[State], tuple[State, str] | None]) -> State:
        """读入当前状态，`change` 返回新状态与提交信息；原子写入后提交 git，返回新状态。

        `change` 返回 None 表示无需改动，原样返回当前状态；
        `change` 抛出的异常原样传出，此时文件与仓库都不变。
        """
        with self._write_lock:
            current = self.read_state()
            changed = change(current)
            if changed is None:
                return current
            new, message = changed
            save_state(self.state_path, new)
            _git(self.root, "add", "--", STATE_FILE)
            _commit_if_staged(self.root, message)
            return new

    @property
    def conversations_path(self) -> Path:
        return self.root / CONVERSATIONS_FILE

    def read_conversations(self) -> dict[str, str]:
        """会话映射：主题 id → 当前主题会话 id。"""
        try:
            mapping = json.loads(self.conversations_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise StartupError(
                f"会话映射不是合法的 JSON：{self.conversations_path}：{exc}"
            ) from exc
        if not isinstance(mapping, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
        ):
            raise StartupError(
                f"会话映射应为「主题 id → 会话 id」的对象：{self.conversations_path}"
            )
        return mapping

    def replace_dir(self, target: Path, staging: Path, *, message: str) -> None:
        """用备好的 `staging` 整目录替换数据目录里的 `target`（可不存在），并提交 git。"""
        old = target.with_name(f".{target.name}.old")
        with self._write_lock:
            shutil.rmtree(old, ignore_errors=True)
            if target.exists():
                target.rename(old)
            staging.rename(target)
            shutil.rmtree(old, ignore_errors=True)
            rel = str(target.relative_to(self.root))
            _git(self.root, "add", "--all", "--", rel)
            _commit_if_staged(self.root, message)

    def set_conversation(self, topic: str, conversation_id: str) -> None:
        """记下主题的当前主题会话（覆盖旧 id），原子写入后提交 git。"""
        with self._write_lock:
            mapping = self.read_conversations()
            if mapping.get(topic) == conversation_id:
                return
            mapping[topic] = conversation_id
            write_json_atomic(self.conversations_path, mapping)
            _git(self.root, "add", "--", CONVERSATIONS_FILE)
            _commit_if_staged(self.root, f"记录主题会话：{topic}")


def open_data_dir(root: Path, seed_skeleton: Path) -> DataDir:
    """初始化（如需要）并加载数据目录；骨架或状态不合法时抛 `StartupError`。"""
    initialize(root, seed_skeleton)
    skeleton_path = root / SKELETON_FILE
    try:
        skeleton = load_skeleton(skeleton_path)
    except SkeletonLoadError as exc:
        raise StartupError(f"骨架无法读取，拒绝启动：\n{exc}") from exc
    errors = validate(skeleton)
    if errors:
        listing = "\n".join(f"- {e}" for e in errors)
        raise StartupError(
            f"骨架校验失败，拒绝启动：{skeleton_path}（{len(errors)} 个错误）\n{listing}"
        )
    data_dir = DataDir(root=root, skeleton=skeleton)
    data_dir.read_state()  # 启动时就校验，坏文件不等到第一次请求才发现
    data_dir.read_conversations()
    return data_dir


def initialize(root: Path, seed_skeleton: Path) -> list[str]:
    """补齐缺失的文件与 git 仓库，返回新建文件名列表。已有的文件不覆盖。"""
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    skeleton_path = root / SKELETON_FILE
    if not skeleton_path.exists():
        shutil.copyfile(seed_skeleton, skeleton_path)
        created.append(SKELETON_FILE)
    for name, content in INITIAL_CONTENT.items():
        path = root / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(name)

    fresh_repo = not (root / ".git").exists()
    if fresh_repo:
        # 新仓库：目录里已有的文件一并纳入首个提交
        _git(root, "init", "--quiet")
        _git(root, "add", "--all")
        _commit_if_staged(root, "初始化数据目录")
    elif created:
        # 已有仓库：只提交补齐的文件，学习者未提交的手改留在工作树里
        _git(root, "add", "--", *created)
        _commit_if_staged(root, f"补齐数据目录缺失的文件：{'、'.join(created)}")
    return created


def _commit_if_staged(root: Path, message: str) -> None:
    if _git(root, "diff", "--cached", "--name-only").strip():
        _git(root, "commit", "--quiet", "-m", message)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *GIT_IDENTITY, "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
