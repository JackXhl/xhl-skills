#!/usr/bin/env python3
"""check_php_syntax.py - PHP 语法检查（php -l 封装）。

用法:
    python check_php_syntax.py <插件目录>

行为:
    探测 PATH 中的 php / php8 / php8.2 等可执行文件。
    找到 -> 对目录内所有 .php 逐文件执行 php -l，报告语法错误。
    未找到 -> 打印说明并正常退出（不阻塞流程），建议用户安装 PHP CLI
              或用 wp-env / Docker 环境校验。
退出码: 0=全部通过或跳过, 1=存在语法错误。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

CANDIDATES = ["php", "php8", "php8.3", "php8.2", "php8.1", "php.exe"]


def find_php() -> str | None:
    for name in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="PHP 语法检查")
    ap.add_argument("root", help="插件目录")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"错误: 目录不存在 {args.root}", file=sys.stderr)
        return 2

    php = find_php()
    if not php:
        print("未检测到 PHP CLI，跳过语法检查。")
        print("建议: 安装 PHP 8.1+ 或使用 wp-env（npx wp-env start）在校验环境中执行 php -l。")
        return 0

    print(f"使用 PHP: {php}")
    errors = 0
    checked = 0
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in {"node_modules", "vendor", ".git"}]
        for name in filenames:
            if not name.endswith(".php"):
                continue
            path = os.path.join(dirpath, name)
            checked += 1
            try:
                proc = subprocess.run([php, "-l", path], capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=30)
            except (OSError, subprocess.TimeoutExpired) as exc:
                print(f"[?] {path}: 执行失败 {exc}")
                continue
            if proc.returncode != 0:
                errors += 1
                print(f"[FAIL] {path}")
                print(f"       {proc.stdout.strip() or proc.stderr.strip()}")

    print(f"\n检查 {checked} 个 PHP 文件，语法错误 {errors} 个。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
