#!/usr/bin/env python3
"""wp_security_scan.py - WordPress 插件静态安全扫描器。

用法:
    python wp_security_scan.py <插件目录> [--json] [--quiet]

检查项（分级 HIGH / MEDIUM / LOW / INFO）:
    HIGH   危险函数（eval/exec/命令执行）、混淆特征、对象注入、
           变量劫持、SQL 注入（含两段式拼接）、LFI/RFI、用户输入作回调
    MEDIUM 缺失 ABSPATH 守卫、缺失 nonce、缺失 capability、
           nopriv（未登录可达）Ajax 端点、REST 权限宽松、
           请求数据行内无 sanitize、外联域名、隐藏/可执行文件
    LOW    短标签、phpinfo、@ 静默错误、短代码未转义
    INFO   文件清单、大小、外部 URL 去重列表

污点传播（v2）：先收集"由超全局赋值的变量"，再判断这些变量是否流入
危险汇聚点（$wpdb->* / include / call_user_func / unserialize / 文件写入）。
这样才能覆盖两段式写法，例如：
    $id  = $_GET['id'];
    $sql = "SELECT ... WHERE id = " . $id;
    $wpdb->get_results( $sql );          // 直接拼接写法扫描不到，本版可捕获

只读扫描，不修改任何文件。退出码: 0=无 HIGH, 1=存在 HIGH, 2=参数/路径错误。
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


# (severity, 类别, 正则, 说明)
PATTERNS: list[tuple[str, str, str, str]] = [
    # ---- 代码/命令执行 ----
    ("HIGH", "rce", r"\beval\s*\(", "eval() 代码执行"),
    ("HIGH", "rce", r"\bassert\s*\(", "assert() 可用于代码执行"),
    ("HIGH", "rce", r"\bcreate_function\s*\(", "create_function() 已废弃且危险"),
    ("HIGH", "rce", r"preg_replace\s*\(\s*(['\"]).*?/[a-zA-Z]*e[a-zA-Z]*\1", "preg_replace /e 修饰符"),
    ("HIGH", "rce", r"\b(exec|shell_exec|system|passthru|proc_open|popen)\s*\(", "系统命令执行"),
    ("HIGH", "rce", r"\bcall_user_func(?:_array)?\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)", "用户输入直接作回调"),
    # ---- 混淆 / 隐藏 ----
    # base64_decode 单独出现属正常用途（解码 JWT/二进制/数据 URI），
    # 仅当解码结果直接进入执行函数时才判 HIGH——避免对正常插件刷屏。
    ("HIGH", "obfuscation", r"\b(eval|assert|system|exec|shell_exec|passthru|proc_open|popen)\s*\(\s*[^)]{0,120}base64_decode\s*\(", "base64_decode 结果直接进入执行函数"),
    ("MEDIUM", "obfuscation", r"\bbase64_decode\s*\(", "base64_decode 使用（确认解码内容是否被执行）"),
    ("HIGH", "obfuscation", r"\b(gzinflate|gzuncompress|str_rot13)\s*\(", "压缩/旋转混淆"),
    ("HIGH", "obfuscation", r"chr\s*\(\s*\d+\s*\)\s*\.\s*chr\s*\(\s*\d+\s*\)\s*\.\s*chr\s*\(\s*\d+\s*\)", "chr() 链拼接（常见混淆）"),
    ("MEDIUM", "obfuscation", r"['\"][A-Za-z0-9+/]{200,}={0,2}['\"]", "超长 base64 样字符串"),
    # ---- 文件风险 ----
    # move_uploaded_file 是 WordPress 上传的标准落盘方式（wp_handle_upload 内部即用它），
    # 本身不是漏洞；风险在于是否配合 wp_check_filetype_and_ext / wp_handle_upload 校验。
    ("MEDIUM", "file", r"\bmove_uploaded_file\s*\(", "上传文件落盘（确认已用 wp_handle_upload / wp_check_filetype_and_ext 校验类型与扩展名）"),
    ("MEDIUM", "file", r"\bfile_put_contents\s*\([^)]*\$_(GET|POST|REQUEST|COOKIE)", "文件写入且路径含用户输入"),
    ("LOW", "file", r"\bfile_put_contents\s*\(", "文件写入（确认路径不可被用户控制）"),
    ("MEDIUM", "file", r"\b(include|require)(_once)?\s*\(?\s*\$_(GET|POST|REQUEST|COOKIE)", "用户输入直接作包含路径（LFI/RFI）"),
    ("MEDIUM", "file", r"\bf?open\s*\(.*['\"]w", "写模式打开文件"),
    # ---- 变量劫持 / 反序列化 ----
    ("HIGH", "hijack", r"\bextract\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)", "extract 用户输入"),
    ("HIGH", "hijack", r"\bunserialize\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)", "反序列化用户输入"),
    ("MEDIUM", "hijack", r"\$\$\w+", "可变变量（$$var）"),
    # parse_str 只有在不带第二参数时才会覆盖当前作用域变量（WP 官方口径）
    ("MEDIUM", "hijack", r"\bparse_str\s*\(\s*\$?\w+\s*\)", "parse_str 未使用第二参数（会创建/覆盖局部变量）"),
    # ---- REST 权限 ----
    ("MEDIUM", "rest", r"['\"]permission_callback['\"]\s*=>\s*['\"]__return_true['\"]", "REST permission_callback 为 __return_true（确认确为公开数据）"),
    # ---- 信息泄露 ----
    ("LOW", "info", r"\bphpinfo\s*\(", "phpinfo()"),
    ("LOW", "info", r"@\$\w+->\w+\(", "@ 静默错误抑制（不一定是问题，仅提示）"),
    # ---- 短标签 ----
    ("LOW", "compat", r"<\?=\s", "短 echo 标签 <?= （可移植性提示）"),
]

SUPER_GLOBAL_RE = re.compile(r"\$_(GET|POST|REQUEST|COOKIE|FILES)\s*\[")
SUPER_GLOBAL_BARE_RE = re.compile(r"\$_(GET|POST|REQUEST|COOKIE|FILES)\b")
SANITIZE_HINT_RE = re.compile(
    r"sanitize_\w+|absint|intval|wp_kses|esc_url_raw|esc_attr|esc_html|wp_unslash|\(int\)|filter_var|rest_sanitize"
)
ABSPATH_RE = re.compile(r"defined\s*\(\s*['\"]ABSPATH['\"]\s*\)")
URL_RE = re.compile(r"https?://[^\s'\"<>)]+")
AJAX_HOOK_RE = re.compile(r"add_action\s*\(\s*['\"]wp_ajax_")
AJAX_NOPRIV_RE = re.compile(r"add_action\s*\(\s*['\"]wp_ajax_nopriv_")
REST_ROUTE_RE = re.compile(r"\bregister_rest_route\s*\(")
NONCE_RE = re.compile(r"check_ajax_referer|check_admin_referer|wp_verify_nonce")
CAPABILITY_RE = re.compile(r"current_user_can|wp_doing_ajax|manage_options|edit_posts|edit_others_posts|\bedit_")
IGNORE_DIRS = {".git", "node_modules", "vendor", ".wordpress-org", "languages"}
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ttf", ".zip", ".pot", ".po", ".mo"}

# 污点来源：这些超全局的值视为不可信
TAINT_SOURCES = ("GET", "POST", "REQUEST", "COOKIE", "FILES")
# 危险汇聚点（污点变量流入即报告）
WPDB_SINK_RE = re.compile(r"\$wpdb->(?:query|get_results|get_row|get_var|get_col|get_results_async)\s*\(")
WPDB_PREPARE_RE = re.compile(r"\$wpdb->prepare\s*\(")
INCLUDE_SINK_RE = re.compile(r"\b(?:include|require)(?:_once)?\s*\(?\s*\$")
CALLBACK_SINK_RE = re.compile(r"\bcall_user_func(?:_array)?\s*\(\s*\$")
UNSERIALIZE_SINK_RE = re.compile(r"\bunserialize\s*\(\s*\$")
WRITE_SINK_RE = re.compile(r"\b(?:file_put_contents|fopen|fwrite)\s*\(\s*\$")
ASSIGN_RE = re.compile(r"\$(\w+)\s*=\s*([^;]{0,400});")
VAR_RE_CACHE: dict[str, re.Pattern[str]] = {}


def iter_code_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.splitext(name)[1].lower() in SKIP_EXTENSIONS:
                continue
            yield path


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def split_top_args(argtext: str) -> list[str]:
    """按顶层逗号切分实参列表（忽略括号/引号内的逗号）。"""
    args: list[str] = []
    depth = 0
    quote = ""
    buf = []
    for ch in argtext:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    args.append("".join(buf))
    return args


def extract_call_args(text: str, open_paren_idx: int, limit: int = 1500) -> str:
    """从左括号位置提取配对右括号内的实参文本（找不到则截断）。"""
    depth = 0
    quote = ""
    for i in range(open_paren_idx, min(len(text), open_paren_idx + limit)):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren_idx + 1: i]
    return text[open_paren_idx + 1: min(len(text), open_paren_idx + limit)]


def var_re(name: str) -> re.Pattern[str]:
    pat = VAR_RE_CACHE.get(name)
    if pat is None:
        pat = re.compile(r"\$" + re.escape(name) + r"\b")
        VAR_RE_CACHE[name] = pat
    return pat


def find_open_paren(text: str, match_end: int) -> int | None:
    """从正则匹配结束位置向前找到本调用的左括号下标。

    正则里若已把 "(" 消费掉（如 `unserialize\\s*\\(\\s*\\$`），匹配结束位置已在
    括号之后，直接回退查找会越界或找不到。这里在 match_end 之前的有限窗口内
    反向寻找最近的 "("，找不到则返回 None（跳过该处，不抛异常）。
    """
    window = text[max(0, match_end - 120): match_end]
    idx = window.rfind("(")
    if idx == -1:
        return None
    return max(0, match_end - 120) + idx


def collect_tainted_vars(text: str) -> set[str]:
    """收集由超全局赋值的变量名（含一次传递赋值）。"""
    tainted: set[str] = set()
    assignments: list[tuple[str, str]] = []
    for m in ASSIGN_RE.finditer(text):
        assignments.append((m.group(1), m.group(2)))

    # 第一轮：直接来自超全局
    for var, rhs in assignments:
        if SUPER_GLOBAL_BARE_RE.search(rhs):
            tainted.add(var)

    # 第二轮：来自已被污染的变量（最多传递 3 层，足够覆盖常见写法）
    for _ in range(3):
        grown = False
        for var, rhs in assignments:
            if var in tainted:
                continue
            for t in list(tainted):
                if var_re(t).search(rhs):
                    tainted.add(var)
                    grown = True
                    break
        if not grown:
            break
    return tainted


def scan_taint_flows(text: str, rel: str, tainted: set[str]) -> list[dict]:
    """检测污点变量流入危险汇聚点。"""
    findings: list[dict] = []
    if not tainted:
        return findings

    def any_tainted(fragment: str) -> list[str]:
        return [t for t in tainted if var_re(t).search(fragment)]

    def taint_source_in(fragment: str) -> bool:
        """片段中是否直接出现超全局（未经中间变量）。"""
        return bool(SUPER_GLOBAL_BARE_RE.search(fragment))

    # ---- SQL：$wpdb->* 直接接收污点变量或超全局 ----
    for m in WPDB_SINK_RE.finditer(text):
        open_idx = find_open_paren(text, m.end())
        if open_idx is None:
            continue
        args = split_top_args(extract_call_args(text, open_idx))
        if not args:
            continue
        hit = any_tainted(args[0])
        # 外层调用若已用 prepare() 包裹，则参数是已转义的——不重复报告
        # （prepare 的格式串插值问题由下面的 WPDB_PREPARE_RE 分支单独覆盖）。
        outer_prepare = "prepare" in args[0]
        if hit and not outer_prepare:
            findings.append({
                "severity": "HIGH", "category": "sql", "file": rel,
                "line": line_of(text, m.start()),
                "detail": f"SQL 语句拼接用户输入变量 ${hit[0]}（应改用 $wpdb->prepare）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })
        elif taint_source_in(args[0]) and not outer_prepare:
            findings.append({
                "severity": "HIGH", "category": "sql", "file": rel,
                "line": line_of(text, m.start()),
                "detail": "SQL 语句直接拼接超全局输入（应改用 $wpdb->prepare）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })

    # ---- SQL：prepare() 的格式串里插值了污点变量（prepare 只转义 %s 占位符，
    #      直接插值进格式串等同于拼接，prepare 救不了）----
    for m in WPDB_PREPARE_RE.finditer(text):
        open_idx = find_open_paren(text, m.end())
        if open_idx is None:
            continue
        args = split_top_args(extract_call_args(text, open_idx))
        if not args:
            continue
        fmt_hit = any_tainted(args[0])
        if fmt_hit:
            findings.append({
                "severity": "HIGH", "category": "sql", "file": rel,
                "line": line_of(text, m.start()),
                "detail": f"$wpdb->prepare() 的格式串中插入了用户输入变量 ${fmt_hit[0]}（须改用 %s 占位符传参）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })

    # ---- LFI/RFI：污点变量作包含路径 ----
    for m in INCLUDE_SINK_RE.finditer(text):
        frag = text[m.start(): m.start() + 200]
        hit = any_tainted(frag)
        if hit:
            findings.append({
                "severity": "HIGH", "category": "file", "file": rel,
                "line": line_of(text, m.start()),
                "detail": f"用户输入变量 ${hit[0]} 作包含路径（LFI/RFI）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })

    # ---- 用户输入作回调（间接）----
    for m in CALLBACK_SINK_RE.finditer(text):
        frag = text[m.start(): m.start() + 200]
        hit = any_tainted(frag)
        if hit:
            findings.append({
                "severity": "HIGH", "category": "rce", "file": rel,
                "line": line_of(text, m.start()),
                "detail": f"用户输入变量 ${hit[0]} 作回调（可导致任意函数调用）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })

    # ---- 反序列化：污点变量或任意非字面量（对象注入）----
    for m in UNSERIALIZE_SINK_RE.finditer(text):
        open_idx = find_open_paren(text, m.end())
        if open_idx is None:
            continue
        arg = extract_call_args(text, open_idx, limit=200).strip()
        hit = any_tainted(arg)
        if hit:
            findings.append({
                "severity": "HIGH", "category": "hijack", "file": rel,
                "line": line_of(text, m.start()),
                "detail": f"反序列化用户输入变量 ${hit[0]}（PHP 对象注入）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })
        elif arg and not arg.startswith(("'", '"')):
            findings.append({
                "severity": "MEDIUM", "category": "hijack", "file": rel,
                "line": line_of(text, m.start()),
                "detail": "unserialize() 反序列化非常量数据（PHP 对象注入风险，确认数据来源可信）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })

    # ---- 文件写入：路径含污点变量（路径穿越）----
    for m in WRITE_SINK_RE.finditer(text):
        open_idx = find_open_paren(text, m.end())
        if open_idx is None:
            continue
        args = split_top_args(extract_call_args(text, open_idx))
        if not args:
            continue
        hit = any_tainted(args[0])
        if hit:
            findings.append({
                "severity": "MEDIUM", "category": "file", "file": rel,
                "line": line_of(text, m.start()),
                "detail": f"文件写入路径含用户输入变量 ${hit[0]}（路径穿越）",
                "code": text.splitlines()[line_of(text, m.start()) - 1].strip()[:120],
            })

    return findings


def scan(root: str) -> list[dict]:
    findings: list[dict] = []
    all_urls: set[str] = set()
    files = list(iter_code_files(root))

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
            if AJAX_HOOK_RE.search(text) and not NONCE_RE.search(text):
                findings.append({"severity": "MEDIUM", "category": "ajax-nonce", "file": rel, "line": 1,
                                 "detail": "注册了 wp_ajax_ 处理器但文件内未见 nonce 校验（check_ajax_referer / wp_verify_nonce）"})
            if AJAX_HOOK_RE.search(text) and not CAPABILITY_RE.search(text):
                findings.append({"severity": "MEDIUM", "category": "ajax-capability", "file": rel, "line": 1,
                                 "detail": "注册了 wp_ajax_ 处理器但文件内未见 capability 校验（current_user_can）——仅验 nonce 不足以防越权"})
            if AJAX_NOPRIV_RE.search(text):
                findings.append({"severity": "MEDIUM", "category": "ajax-nopriv", "file": rel, "line": 1,
                                 "detail": "注册了 wp_ajax_nopriv_ 处理器（未登录用户可达），确认输入校验与限流到位"})
            if REST_ROUTE_RE.search(text) and "permission_callback" not in text:
                findings.append({"severity": "MEDIUM", "category": "rest", "file": rel, "line": 1,
                                 "detail": "注册 REST 路由但未见 permission_callback（WP 6.5+ 该参数必填，缺失会导致 _doing_it_wrong）"})
            if re.search(r"<\?php", text) is None and "<?" in text:
                findings.append({"severity": "LOW", "category": "compat", "file": rel, "line": 1,
                                 "detail": "疑似短开标签 <?"})

            lines = text.splitlines()
            for severity, category, pattern, desc in PATTERNS:
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    # SQL 类：同一调用内若使用 prepare() 则为安全写法，不报
                    if category == "sql":
                        seg = text[m.start(): m.start() + 400]
                        if "prepare" in seg:
                            continue
                    ln = line_of(text, m.start())
                    line_text = lines[ln - 1].strip()[:120] if ln <= len(lines) else ""
                    # 注释行降级提示
                    if line_text.lstrip().startswith(("*", "//", "#", "/*")):
                        sev = "INFO" if severity == "HIGH" else severity
                    else:
                        sev = severity
                    findings.append({"severity": sev, "category": category, "file": rel, "line": ln,
                                     "detail": desc, "code": line_text})

            # 污点传播：超全局 -> 变量 -> 危险汇聚点
            tainted = collect_tainted_vars(text)
            findings.extend(scan_taint_flows(text, rel, tainted))

            # 超全局使用点：同行/上下文中无净化提示时记 MEDIUM
            for m in SUPER_GLOBAL_RE.finditer(text):
                ln = line_of(text, m.start())
                ctx = "\n".join(lines[max(0, ln - 2): ln + 2])
                if not SANITIZE_HINT_RE.search(ctx):
                    snippet = lines[ln - 1].strip()[:120] if ln <= len(lines) else ""
                    findings.append({"severity": "MEDIUM", "category": "input", "file": rel, "line": ln,
                                     "detail": "超全局变量使用点附近未见 sanitize/转义（需人工确认）", "code": snippet})

            # 短代码属性直接输出且未转义
            if "add_shortcode" in text:
                for i, line_text in enumerate(lines, start=1):
                    if "$atts[" in line_text and re.search(r"(echo|return|printf)", line_text):
                        if not re.search(r"esc_html|esc_attr|wp_kses|sanitize_|absint|intval", line_text):
                            findings.append({"severity": "LOW", "category": "xss", "file": rel, "line": i,
                                             "detail": "短代码属性未转义即输出（存储型 XSS 风险）", "code": line_text.strip()[:120]})

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
    ensure_utf8_stdout()
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
