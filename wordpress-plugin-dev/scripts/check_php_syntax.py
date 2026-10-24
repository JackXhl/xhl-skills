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
import glob
import os
import shutil
import subprocess
import sys


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

CANDIDATES = ["php", "php8", "php8.4", "php8.3", "php8.2", "php8.1", "php.exe"]

# 常见安装位置（含未加入 PATH 的解压版 / XAMPP / WAMP / Scoop）
COMMON_GLOBS = [
    r"C:\php\php.exe",
    r"C:\tools\php\php.exe",
    r"C:\Program Files\PHP\php.exe",
    r"C:\Program Files\php\php.exe",
    r"C:\xampp\php\php.exe",
    r"C:\laragon\bin\php\php.exe",
    r"C:\wamp64\bin\php\php.exe",
    r"C:\wamp\bin\php\php.exe",
    r"D:\php\php.exe",
    r"D:\tool\php\php.exe",
    r"D:\tool\php\php-*\php.exe",
    r"C:\Users\*\AppData\Local\Temp\php\php.exe",
    r"C:\Users\*\scoop\apps\php\current\php.exe",
]


def find_php() -> str | None:
    """定位 PHP CLI：PHP_BIN 环境变量 → PATH → 常见安装位置。

    只查 PATH 会漏掉"已安装但未加入 PATH"的 PHP，导致语法检查被静默跳过、
    用户以为通过了。顺序与 self_test.py 保持一致。

    设 `WP_DEV_NO_PHP_SEARCH=1` 可关闭 PATH 之外的兜底扫描（仅供测试
    构造"无 PHP"环境使用）。
    """
    env = os.environ.get("PHP_BIN", "").strip()
    if env:
        if os.path.isfile(env):
            return env
        found = shutil.which(env)
        if found:
            return found

    for name in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path

    if os.environ.get("WP_DEV_NO_PHP_SEARCH", "").strip() in ("1", "true", "yes"):
        return None

    for pattern in COMMON_GLOBS:
        try:
            for cand in sorted(glob.glob(pattern), reverse=True):
                if os.path.isfile(cand):
                    return cand
        except (OSError, ValueError):
            continue
    return None


def main() -> int:
    ensure_utf8_stdout()
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
