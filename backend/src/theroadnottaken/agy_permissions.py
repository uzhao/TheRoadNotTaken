"""agy 全局 settings 的 allow 规则校验与追加（research/agy-print-mode.md 第九节）。

print 模式下需要确认的工具会被自动拒绝；后端不用 `--dangerously-skip-permissions`，
而要求全局 settings 的 `permissions.allow` 含下列规则。只追加缺失项，不改动其它任何键。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from theroadnottaken.files import write_json_atomic

DEFAULT_SETTINGS = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
REQUIRED_RULES = ["command(python3)", "command(python3 *)", "command(mkdir)", "write_file(*)"]


class SettingsError(Exception):
    """settings 文件存在但无法安全解析；此时绝不覆盖它。"""


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SettingsError(f"{path} 不是合法的 JSON：{exc}") from exc
    if not isinstance(settings, dict):
        raise SettingsError(f"{path} 顶层不是对象")
    permissions = settings.get("permissions", {})
    if not isinstance(permissions, dict) or not isinstance(permissions.get("allow", []), list):
        raise SettingsError(f"{path} 的 permissions.allow 不是列表")
    return settings


def _missing(settings: dict[str, Any]) -> list[str]:
    allow = settings.get("permissions", {}).get("allow", [])
    return [rule for rule in REQUIRED_RULES if rule not in allow]


def status(path: Path) -> dict[str, Any]:
    """供顶栏横幅使用：缺哪些规则、要追加的 JSON 片段、解析错误（若有）。"""
    try:
        missing, error = _missing(_load(path)), None
    except SettingsError as exc:
        missing, error = list(REQUIRED_RULES), str(exc)
    snippet = json.dumps({"permissions": {"allow": missing}}, ensure_ascii=False, indent=2)
    return {
        "ok": not missing and error is None,
        "missing": missing,
        "settings_path": str(path),
        "snippet": snippet,
        "error": error,
    }


def add_missing_rules(path: Path) -> None:
    """把缺失的规则追加到 `permissions.allow` 末尾；文件不存在则新建。"""
    settings = _load(path)
    missing = _missing(settings)
    if not missing:
        return
    settings.setdefault("permissions", {}).setdefault("allow", []).extend(missing)
    write_json_atomic(path, settings)
