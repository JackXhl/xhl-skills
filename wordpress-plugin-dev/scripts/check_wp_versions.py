#!/usr/bin/env python3
"""check_wp_versions.py - 版本保鲜检查。

用法:
    python check_wp_versions.py

向 api.wordpress.org 查询当前 WordPress 各分支最新版本，
与 SKILL.md 中登记的版本基线（2026-10-24: 7.1.3）比对。
发现新版本时提示更新 skill 的「版本基线」章节。
无网络时静默降级（退出码 0，不阻塞流程）。
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error


def ensure_utf8_stdout() -> None:
    """将标准输出/错误切换到 UTF-8。

    Windows 非中文 locale（如 GitHub Actions 的 en-US runner，管道编码为
    cp1252）下，中文输出会触发 UnicodeEncodeError 直接崩溃；errors=replace
    保证极端字符也不抛异常。Unix 环境本就是 UTF-8，调用无副作用。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

API = "https://api.wordpress.org/core/version-check/1.7/?version=7.1"
SKILL_BASELINE = {"offer": "7.1.3", "next_major": "7.2", "as_of": "2026-10-24"}


def fetch(url: str, timeout: int = 10) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def main() -> int:
    ensure_utf8_stdout()
    data = fetch(API)
    if not data or "offers" not in data:
        print("无法连接 api.wordpress.org（离线或超时），跳过版本保鲜检查。")
        print(f"SKILL.md 当前基线: {SKILL_BASELINE['offer']}（登记于 {SKILL_BASELINE['as_of']}）")
        return 0

    branches: dict[str, str] = {}
    for offer in data["offers"]:
        branches[offer.get("response", "?")] = offer.get("current", "?")

    latest_stable = branches.get("upgrade") or branches.get("latest")
    print("WordPress 官方版本现状:")
    for branch, version in sorted(branches.items()):
        print(f"  {branch:10} -> {version}")

    print(f"\nSKILL.md 基线: {SKILL_BASELINE['offer']}（登记于 {SKILL_BASELINE['as_of']}）")
    if latest_stable and latest_stable != SKILL_BASELINE["offer"]:
        print(f"⚠ 检测到新稳定版 {latest_stable}（基线为 {SKILL_BASELINE['offer']}）。")
        print("  行动: 更新 SKILL.md「版本基线」章节，并复查受影响的 API 说明")
        print("       （弃用/新增函数见 developer.wordpress.org/news 的 What's new for developers）")
        return 0
    print("✓ 基线仍是最新稳定版，无需更新。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
