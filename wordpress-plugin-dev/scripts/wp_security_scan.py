#!/usr/bin/env python3
"""wp_security_scan.py - WordPress 插件静态安全扫描器。

用法:
    python wp_security_scan.py <插件目录> [--json] [--quiet]

检查项（分级 HIGH / MEDIUM / LOW / INFO）:
    HIGH   危险函数（eval/exec/base64_decode 执行等）、混淆特征、
           未净化超全局直接进入敏感函数、缺失 ABSPATH 守卫
    MEDIUM 请求数据行内无 sanitize、外联域名清单、隐藏/可执行文件
    LOW    短标签、phpinfo、@ 静默错误
    INFO   文件清单、大小、外部 URL 去重列表

只读扫描，不修改任何文件。退出码: 0=无 HIGH, 1=存在 HIGH。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# (severity, 类别, 正则, 说明)
PATTERNS: list[tuple[str, str, str, str]] = [
    # ---- 代码/命令执行 ----
    ("HIGH", "rce", r"\beval\s*\(", "eval() 代码执行"),
    ("HIGH", "rce", r"\bassert\s*\(", "assert() 可用于代码执行"),
    ("HIGH", "rce", r"\bcreate_function\s*\(", "create_function() 已废弃且危险"),
    ("HIGH", "rce", r"preg_replace\s*\(\s*(['\"]).*?/[a-zA-Z]*e[a-zA-Z]*\1", "preg_replace /e 修饰符"),
    ("HIGH", "rce", r"\b(exec|shell_exec|system|passthru|proc_open|popen)\s*\(", "系统命令执行"),
    ("HIGH", "rce", r"\bcall_user_func(?:_array)?\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)", "用户输入作回调"),
    # ---- 混淆 / 隐藏 ----
    ("HIGH", "obfuscation", r"\bbase64_decode\s*\(", "base64_decode（执行上下文常见）"),
    ("HIGH", "obfuscation", r"\b(gzinflate|gzuncompress|str_rot13)\s*\(", "压缩/旋转混淆"),
    ("HIGH", "obfuscation", r"chr\s*\(\s*\d+\s*\)\s*\.\s*chr\s*\(\s*\d+\s*\)\s*\.\s*chr\s*\(\s*\d+\s*\)", "chr() 链拼接（常见混淆）"),
    ("MEDIUM", "obfuscation", r"['\"][A-Za-z0-9+/]{200,}={0,2}['\"]", "超长 base64 样字符串"),
    # ---- 文件风险 ----
    ("HIGH", "file", r"\bmove_uploaded_file\s*\(", "上传文件落盘（需严格校验）"),
    ("MEDIUM", "file", r"\bfile_put_contents\s*\(", "文件写入"),
    ("MEDIUM", "file", r"\b(include|require)(_once)?\s*\(?\s*\$_(GET|POST|REQUEST|COOKIE)", "用户输入作包含路径"),
    ("MEDIUM", "file", r"\bf?open\s*\(.*['\"]w", "写模式打开文件"),
    # ---- 变量劫持 / 反序列化 ----
    ("HIGH", "hijack", r"\bextract\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)", "extract 用户输入"),
    ("HIGH", "hijack", r"\bunserialize\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)", "反序列化用户输入"),
    ("MEDIUM", "hijack", r"\$\$\w+", "可变变量（$$var）"),
    ("MEDIUM", "hijack", r"\bparse_str\s*\(", "parse_str 变量注入"),
    # ---- 信息泄露 ----
    ("LOW", "info", r"\bphpinfo\s*\(", "phpinfo()"),
    ("LOW", "info", r"@\$\w+->\w+\(", "@ 静默错误抑制（不一定是问题，仅提示）"),
    # ---- 短标签 ----
    ("LOW", "compat", r"<\?=\s", "短 echo 标签 <?= （可移植性提示）"),
]

SUPER_GLOBAL_RE = re.compile(r"\$_(GET|POST|REQUEST|COOKIE|FILES)\s*\[")
SANITIZE_HINT_RE = re.compile(
    r"sanitize_\w+|absint|intval|wp_kses|esc_url_raw|esc_attr|esc_html|wp_unslash|\(int\)|filter_var|rest_sanitize"
)
ABSPATH_RE = re.compile(r"defined\s*\(\s*['\"]ABSPATH['\"]\s*\)")
URL_RE = re.compile(r"https?://[^\s'\"<>)]+")
IGNORE_DIRS = {".git", "node_modules", "vendor", ".wordpress-org", "languages"}
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ttf", ".zip", ".pot", ".po", ".mo"}


def iter_php_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.splitext(name)[1].lower() in SKIP_EXTENSIONS:
                continue
            yield path


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def scan(root: str) -> list[dict]:
    findings: list[dict] = []
    all_urls: set[str] = set()
    files = list(iter_php_files(root))

    for path in files:
        rel = os.path.relpath(path, root)
        ext = os.path.splitext(path)[1].lower()
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            findings.append({"severity": "INFO", "category": "io", "file": rel, "line": 0, "detail": f"无法读取: {exc}"})
            continue

        for m in URL_RE.finditer(text):
            all_urls.add(m.group(0).rstrip(".,;"))

        if ext == ".php":
            is_uninstall = os.path.basename(path) == "uninstall.php"
            if not ABSPATH_RE.search(text) and not (is_uninstall and "WP_UNINSTALL_PLUGIN" in text):
                guard = "WP_UNINSTALL_PLUGIN" if is_uninstall else "ABSPATH"
                findings.append({"severity": "MEDIUM", "category": "abspath", "file": rel, "line": 1,
                                 "detail": f"缺少直接访问守卫（应有 if ( ! defined( '{guard}' ) ) exit;）"})
            if re.search(r"<\?php", text) is None and "<?" in text:
                findings.append({"severity": "LOW", "category": "compat", "file": rel, "line": 1,
                                 "detail": "疑似短开标签 <?"})

            for severity, category, pattern, desc in PATTERNS:
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    ln = line_of(text, m.start())
                    line_text = text.splitlines()[ln - 1].strip()[:120] if ln <= len(text.splitlines()) else ""
                    # 注释行降级提示
                    if line_text.lstrip().startswith(("*", "//", "#", "/*")):
                        sev = "INFO" if severity == "HIGH" else severity
                    else:
                        sev = severity
                    findings.append({"severity": sev, "category": category, "file": rel, "line": ln,
                                     "detail": desc, "code": line_text})

            # 超全局使用点：同行/上下文中无净化提示时记 MEDIUM
            for m in SUPER_GLOBAL_RE.finditer(text):
                ln = line_of(text, m.start())
                lines = text.splitlines()
                ctx = "\n".join(lines[max(0, ln - 2): ln + 2])
                if not SANITIZE_HINT_RE.search(ctx):
                    snippet = lines[ln - 1].strip()[:120] if ln <= len(lines) else ""
                    findings.append({"severity": "MEDIUM", "category": "input", "file": rel, "line": ln,
                                     "detail": "超全局变量使用点附近未见 sanitize/转义（需人工确认）", "code": snippet})

        elif ext in {".js", ".html", ".htm"}:
            for pat, desc in [
                (r"\beval\s*\(", "JS eval()"),
                (r"document\.write\s*\(", "document.write"),
                (r"new\s+Function\s*\(", "new Function()"),
                (r"innerHTML\s*=", "innerHTML 赋值（XSS 风险点）"),
            ]:
                for m in re.finditer(pat, text):
                    ln = line_of(text, m.start())
                    findings.append({"severity": "MEDIUM", "category": "frontend", "file": rel, "line": ln,
                                     "detail": desc, "code": text.splitlines()[ln - 1].strip()[:120]})

    for path in files:
        rel = os.path.relpath(path, root)
        name = os.path.basename(path)
        if name.startswith(".") and name not in {".editorconfig", ".gitignore"}:
            findings.append({"severity": "MEDIUM", "category": "hidden", "file": rel, "line": 0,
                             "detail": "隐藏文件（确认是否有意）"})
        if os.path.splitext(name)[1].lower() in {".exe", ".dll", ".sh", ".bat", ".ps1", ".bin"}:
            findings.append({"severity": "HIGH", "category": "binary", "file": rel, "line": 0,
                             "detail": "插件目录含可执行/脚本文件（极罕见，需解释）"})

    for url in sorted(all_urls):
        findings.append({"severity": "INFO", "category": "url", "file": "-", "line": 0, "detail": url})

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["file"], f["line"]))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="WordPress 插件静态安全扫描")
    ap.add_argument("root", help="插件目录")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiet", action="store_true", help="仅输出统计")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"错误: 目录不存在 {args.root}", file=sys.stderr)
        return 2

    findings = scan(args.root)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("HIGH", "MEDIUM", "LOW", "INFO")}

    if args.json:
        print(json.dumps({"summary": counts, "findings": findings}, ensure_ascii=False, indent=2))
    elif args.quiet:
        print(f"HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']} INFO={counts['INFO']}")
    else:
        print(f"扫描目标: {os.path.abspath(args.root)}")
        print(f"结论: HIGH={counts['HIGH']}  MEDIUM={counts['MEDIUM']}  LOW={counts['LOW']}  INFO={counts['INFO']}\n")
        for f in findings:
            if f["severity"] == "INFO" and f["category"] == "url":
                continue
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            print(f"[{f['severity']:6}] {loc}  ({f['category']}) {f['detail']}")
            if f.get("code"):
                print(f"         | {f['code']}")
        urls = [f["detail"] for f in findings if f["category"] == "url"]
        if urls:
            print("\n外联域名清单（INFO，供人工核对）:")
            for u in urls:
                print(f"  - {u}")
        print("\n提示: HIGH 需逐一排除；MEDIUM 需人工确认上下文；本工具为静态启发式，不能替代人工审查。")

    return 1 if counts["HIGH"] else 0


if __name__ == "__main__":
    sys.exit(main())
