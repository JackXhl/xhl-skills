#!/usr/bin/env python3
"""Stop a server-promo draft that narrates the capture or cites a missing image."""

import re
import sys
from pathlib import Path

BANNED = (
    "截图时",
    "这张图",
    "按钮是",
    "我打开",
    "添加提醒",
    "你是不是也遇到过",
    "今天把资格领上",
    "试用入口",
    "机器回头再开",
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python check_article.py <draft.md>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    failed = False
    for lineno, line in enumerate(text.splitlines(), 1):
        for word in BANNED:
            if word in line:
                print(f"{path}:{lineno}: 制作过程或禁句: {word}")
                failed = True
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        src = match.group(1).split()[0].strip("<>")
        if src.startswith(("http://", "https://")):
            continue
        image = (path.parent / src).resolve()
        if not image.is_file():
            print(f"{path}: 图片不存在: {src}")
            failed = True
    if failed:
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
