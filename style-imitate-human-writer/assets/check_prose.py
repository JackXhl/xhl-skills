#!/usr/bin/env python3
"""
check_prose.py：AI腔文本静态扫描器
配套 style-imitate-human-writer skill，扫描文本，标记黑名单AI句式、词汇
MIT License
"""
import re
import sys

BLACKLIST = [
    r"值得一提的是",
    r"综上所述",
    r"由此可见",
    r"从某种意义上来说",
    r"简言之",
    r"并非.*?而是",
]


def scan_text(text: str):
    lines = text.splitlines()
    findings = []
    for idx, line in enumerate(lines, start=1):
        for pat in BLACKLIST:
            matches = re.findall(pat, line)
            if matches:
                findings.append({
                    "line": idx,
                    "pattern": pat,
                    "content": line.strip()
                })
    return findings


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_prose.py your_article.md")
        return
    filepath = sys.argv[1]
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    res = scan_text(content)
    if not res:
        print("扫描完成，未命中AI黑名单句式")
        return
    print(f"发现 {len(res)} 处命中AI特征词：")
    for item in res:
        print(f"行{item['line']} | 匹配规则：{item['pattern']}")
        print(f"> {item['content']}\n")


if __name__ == "__main__":
    main()
