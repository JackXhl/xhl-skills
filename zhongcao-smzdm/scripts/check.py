#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hard-fail lexical checks for zhongcao-smzdm drafts."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HARD = [
    (r"打了码|打码|马赛克", "制作痕迹（打码/马赛克）"),
    (r"图上看不清|这张图|图上这条", "制作痕迹（审图）"),
    (r"绝对值得收藏", "绝对值得收藏"),
    (r"真正全面", "真正全面"),
    (r"i导航|idaohang", "范文产品名"),
    (r"不是[^。]{0,20}而是", "翻案腔：不是……而是"),
    (r"并非[^。]{0,20}而是", "翻案腔：并非……而是"),
    (r"与其说[^。]{0,20}不如说", "翻案腔：与其说……不如说"),
    (r"你以为[^。]{0,20}其实", "翻案腔：你以为……其实"),
    (r"[—–]|——", "破折号"),
]

FREQ_CAP = {
    "神器": 1,
    "安利": 1,
    "亲测": 1,
}

WARN = [
    (r"无水印|去水印", "无水印/去水印：须事实卡允许"),
    (r"100\s*\+|100\s*个平台|一百[多＋+]?个平台", "100+ 平台：须事实卡允许"),
    (r"扒主页下视频|批量下载全站|扒号下视频", "扒主页下视频：须事实卡允许"),
    (r"1080P|1080p", "写了具体清晰度，必须能在当前截图上指出来"),
    (r"一句话总结：|核心是：|总而言之：", "提示性冒号"),
    (r"老铁|咱就是说|泡杯茶", "表演口语"),
    (r"值得注意的是|从某种意义上说|说白了|说穿了", "洞察路标"),
]


def count(pat: str, text: str) -> list[int]:
    return [m.start() for m in re.finditer(pat, text)]


def line_no(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check.py <draft.md>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    body = text
    # 小标题「适合人群」不算口癖次数
    freq_text = re.sub(r"^#+\s*(?:\d+\.\s*)?适合人群\s*$", "", body, flags=re.M)

    failed = False
    for pat, label in HARD:
        hits = count(pat, body)
        if hits:
            failed = True
            where = ", ".join(f"L{line_no(body, i)}" for i in hits[:8])
            print(f"FAIL {label} @ {where}")

    for word, cap in FREQ_CAP.items():
        n = freq_text.count(word)
        if n > cap:
            failed = True
            print(f"FAIL 「{word}」出现 {n} 次，上限 {cap}")

    for pat, label in WARN:
        hits = count(pat, body)
        if hits:
            where = ", ".join(f"L{line_no(body, i)}" for i in hits[:8])
            print(f"WARN {label} @ {where}", file=sys.stderr)

    if "http://" not in body and "https://" not in body:
        print("WARN 正文里没有网址。什么值得买/知乎长文通常要放入口", file=sys.stderr)

    if failed:
        print("check failed")
        return 1
    print("check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
