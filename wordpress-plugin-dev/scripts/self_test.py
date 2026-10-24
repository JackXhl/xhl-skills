#!/usr/bin/env python3
"""self_test.py - wordpress-plugin-dev 技能自测（eval-lite）。

用内置夹具对技能的全部脚本做回归验证，任何环境可重复执行：
  1. 脚手架全选项生成 -> 文件齐全 -> php -l 语法全过（需 PHP，无则跳过）
  1b. 无选项基础生成 -> 无残留占位符
  1c. 特殊字符插件名（数字开头/单引号/*/ 注入）-> 生成且语法合法
  1d. CLI 边界（--path 指向文件）-> 优雅报错，不抛栈回溯
  1e. 非 ASCII（中文）插件名 -> 不同名称生成到不同目录（不冲突）
  1f. 子模块引导 -> 直接调用 init()，不在 plugins_loaded 内重复 add_action
  1g. 运行时冒烟（WordPress 存根真正执行钩子）-> autoloader/namespace/钩子/子模块
  1h. 存根对快照陷阱的诊断能力（负向夹具）
  1i. AI 桩注册语义：分类方法先于 ability 方法、两者挂在正确钩子上
  1j. 文档事实准确性 -> 连接器 ID / 零参数签名 / 7.1 过滤器 / REST 端点 / MCP 非核心
  1k. references 全部 PHP 代码块 php -l 通过（片段包入类中校验）
  2. 扫描器对干净产出 -> HIGH=0 且 MEDIUM=0
  3. 扫描器对恶意夹具 -> exit=1、HIGH>=8、威胁类别全覆盖
  4. 扫描器污点传播 -> 两段式 SQL / LFI / 回调 / 反序列化 可捕获
  5. 扫描器误报控制 -> prepare 正确用法不报 HIGH；move_uploaded_file 不判 HIGH
  6. check_php_syntax 无 PHP 路径 -> 优雅跳过；有 PHP 路径 -> 正常检查
  7. check_wp_versions -> 退出码恒为 0（离线/在线均不阻塞）

环境说明: 部分 Windows 杀毒软件（如火绒 Hips / Defender）会在文件写入后
约 100ms 内隔离含恶意签名的夹具（实测延迟 <100ms，而 Python 子进程启动
约 200-400ms，子进程方式必被删）。因此恶意夹具采用进程内扫描（微秒级
窗口）；若写入时即被隔离则重试一次，仍被隔离则明确 SKIP（环境限制，
非技能缺陷），其余断言不受影响。CI（无实时防护）环境下全覆盖。

用法: python self_test.py
退出码: 0=全部通过（含跳过）, 1=存在失败项。
依赖: Python 3.8+，无第三方库；PHP CLI 可选（有则启用语法与运行时断言）。
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SCAFFOLD = SCRIPTS / "scaffold_plugin.py"
SCANNER = SCRIPTS / "wp_security_scan.py"
SYNTAX_CHECK = SCRIPTS / "check_php_syntax.py"
VERSION_CHECK = SCRIPTS / "check_wp_versions.py"
STUB = SCRIPTS / "wp_stub.php"

# ---- 恶意夹具：覆盖扫描器声称的每一类威胁 ----
# 注意: payload 经过"去 malware 化"处理——仍能触发扫描器的全部模式，
# 但不构成可被杀毒软件直接识别的真实攻击签名（避免夹具被实时隔离）。
EVIL_MAIN = """<?php
/**
 * Plugin Name: Evil Fixture
 * Description: 自测夹具，仅含恶意代码样本，禁止用于真实站点
 */
if ( ! defined( 'ABSPATH' ) ) { exit; }

add_action( 'wp_ajax_evil_action', 'evil_handler' );
function evil_handler() {
    $value = $_POST['field'];
    update_option( 'evil_value', $value );
}
"""

EVIL_NOGUARD = """<?php
// 无 ABSPATH 守卫 + 命令执行
system( $_GET['cmd'] );
"""

EVIL_RCE = """<?php
if ( ! defined( 'ABSPATH' ) ) { exit; }
eval( $code );
system( $cmd );
assert( $expr );
"""

EVIL_OBFUSCATED = """<?php
if ( ! defined( 'ABSPATH' ) ) { exit; }
$p = gzinflate( base64_decode( 'dGVzdA==' ) );
$q = chr( 72 ) . chr( 105 ) . chr( 33 );
move_uploaded_file( $tmp, $dest );
file_put_contents( '/tmp/log.txt', $data );
extract( $_GET );
unserialize( $_COOKIE['data'] );
"""

EVIL_REST = """<?php
if ( ! defined( 'ABSPATH' ) ) { exit; }
add_action( 'rest_api_init', function () {
    register_rest_route( 'evil/v1', '/data', array(
        'methods'             => 'GET',
        'callback'            => function () { return array(); },
        'permission_callback' => '__return_true',
    ) );
} );
"""

EVIL_SQL = """<?php
if ( ! defined( 'ABSPATH' ) ) { exit; }
global $wpdb;
$rows = $wpdb->get_results( "SELECT * FROM {$wpdb->prefix}posts WHERE id = " . $_GET['id'] );
"""

EVIL_FILES = {
    "evil-plugin.php": None,  # 内容在 build_evil 中写入
    "noguard.php": None,
    "rce.php": None,
    "obfuscated.php": None,
    "rest.php": None,
    "sql.php": None,
    ".env": None,
    "dropper.exe": None,
}

# ---- 污点传播夹具：两段式写法（直接拼接正则扫不到）----
EVIL_TAINT = """<?php
if ( ! defined( 'ABSPATH' ) ) { exit; }
global $wpdb;
$id  = $_GET['id'];
$sql = "SELECT * FROM {$wpdb->posts} WHERE ID = " . $id;
$rows = $wpdb->get_results( $sql );
$tpl = $_GET['tpl'];
include( $tpl );
$cb = $_REQUEST['cb'];
call_user_func( $cb );
$blob = $_COOKIE['blob'];
$obj = unserialize( $blob );
"""

RESULTS: list[tuple[str, bool, str]] = []
SKIPS: list[str] = []


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


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""))


def skip(name: str, reason: str = "") -> None:
    SKIPS.append(name)
    print(f"[SKIP] {name}" + (f" -- {reason}" if reason else ""))


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    # encoding=utf-8: 子进程输出含中文，不能用 locale 编码（en-US Windows 为 cp1252）
    return subprocess.run([sys.executable, str(script), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def find_php() -> str | None:
    """定位 PHP CLI。

    依次尝试：PHP_BIN 环境变量 → PATH 上的常见名字 → 常见安装位置。
    只查 PATH 会漏掉"已安装但未加入 PATH"的 PHP（如解压版放在
    AppData\\Temp 或自定义目录），导致所有 php -l 断言被静默跳过。
    """
    env = os.environ.get("PHP_BIN", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return str(p)
        found = shutil.which(env)
        if found:
            return found

    for name in ("php", "php8", "php8.4", "php8.3", "php8.2", "php8.1", "php.exe"):
        path = shutil.which(name)
        if path:
            return path

    # 兜底扫描可被显式关闭（供测试构造"无 PHP"环境）
    if os.environ.get("WP_DEV_NO_PHP_SEARCH", "").strip() in ("1", "true", "yes"):
        return None

    # 常见安装位置（含未加入 PATH 的解压版）
    globs = [
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
    for pattern in globs:
        try:
            for cand in sorted(glob.glob(pattern), reverse=True):
                if os.path.isfile(cand):
                    return cand
        except (OSError, ValueError):
            continue
    return None


def build_evil(dirpath: Path) -> None:
    (dirpath / "evil-plugin.php").write_text(EVIL_MAIN, encoding="utf-8")
    (dirpath / "noguard.php").write_text(EVIL_NOGUARD, encoding="utf-8")
    (dirpath / "rce.php").write_text(EVIL_RCE, encoding="utf-8")
    (dirpath / "obfuscated.php").write_text(EVIL_OBFUSCATED, encoding="utf-8")
    (dirpath / "rest.php").write_text(EVIL_REST, encoding="utf-8")
    (dirpath / "sql.php").write_text(EVIL_SQL, encoding="utf-8")
    (dirpath / ".env").write_text("SECRET=fixture\n", encoding="utf-8")
    (dirpath / "dropper.exe").write_bytes(b"MZ\x90\x00\x03")


def build_ai_fixture(dirpath: Path, namespace: str, const: str, slug: str,
                     init_body: str) -> None:
    """构造一个"故意写错的 AI 模块"夹具。

    init_body 决定 AiFeatures::init() 里注册了哪些钩子，用来模拟两类
    静默致命错误：
      ① 分类从未注册 -> wp_register_ability() 抛错，ability 凭空消失；
      ② 分类注册到错误的钩子 -> wp_register_ability_category() 抛错。
    这两类错误都不会让插件 fatal，只会悄悄少一个 ability。
    """
    (dirpath / "src" / "Ai").mkdir(parents=True, exist_ok=True)
    (dirpath / "src" / "autoload.php").write_text(
        "<?php\nif ( ! defined( 'ABSPATH' ) ) { exit; }\n"
        "spl_autoload_register( function ( string $class ): void {\n"
        f"    $prefix = '{namespace}\\\\';\n"
        "    if ( strpos( $class, $prefix ) !== 0 ) { return; }\n"
        f"    $file = {const}_PLUGIN_DIR . 'src/' . str_replace( '\\\\', '/', "
        "substr( $class, strlen( $prefix ) ) ) . '.php';\n"
        "    if ( file_exists( $file ) ) { require_once $file; }\n"
        "} );\n",
        encoding="utf-8")
    (dirpath / f"{slug}.php").write_text(
        "<?php\n/**\n * Plugin Name: AI Fixture\n */\n"
        "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
        f"define( '{const}_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );\n"
        f"require_once {const}_PLUGIN_DIR . 'src/autoload.php';\n"
        f"add_action( 'plugins_loaded', array( {namespace}\\Plugin::class, 'init' ) );\n",
        encoding="utf-8")
    (dirpath / "src" / "Plugin.php").write_text(
        "<?php\nnamespace " + namespace + ";\n"
        "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
        "class Plugin {\n    public static function init(): void {\n"
        "        Ai\\AiFeatures::init();\n    }\n}\n",
        encoding="utf-8")
    (dirpath / "src" / "Ai" / "AiFeatures.php").write_text(
        "<?php\nnamespace " + namespace + "\\Ai;\n"
        "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
        "class AiFeatures {\n"
        "    public static function init(): void {\n" + init_body + "    }\n"
        "    public static function register_category(): void {\n"
        "        if ( ! function_exists( 'wp_register_ability_category' ) ) { return; }\n"
        f"        wp_register_ability_category( '{slug}', array(\n"
        f"            'label' => __( 'Fixture Category', '{slug}' ),\n"
        f"            'description' => __( 'Fixture category.', '{slug}' ),\n"
        "        ) );\n"
        "    }\n"
        "    public static function register_ability(): void {\n"
        "        if ( ! function_exists( 'wp_register_ability' ) ) { return; }\n"
        f"        wp_register_ability( '{slug}/do-thing', array(\n"
        f"            'label' => __( 'Do Thing', '{slug}' ),\n"
        f"            'description' => __( 'Fixture ability.', '{slug}' ),\n"
        f"            'category' => '{slug}',\n"
        "            'execute_callback' => array( self::class, 'do_thing' ),\n"
        "            'permission_callback' => '__return_true',\n"
        "        ) );\n"
        "    }\n"
        "    public static function do_thing( string $input = '' ) { return $input; }\n"
        "}\n",
        encoding="utf-8")


def scan_json(root: Path) -> tuple[dict, list[dict]]:
    proc = run(SCANNER, str(root), "--json")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"summary": {"HIGH": -1, "MEDIUM": -1, "LOW": -1, "INFO": -1}}, []
    return data.get("summary", {}), data.get("findings", [])


def main() -> int:
    ensure_utf8_stdout()
    php = find_php()

    with tempfile.TemporaryDirectory(prefix="wp-skill-selftest-") as tmpdir:
        tmp = Path(tmpdir)

        # ---- 测试 1: 脚手架全选项生成 ----
        clean = tmp / "clean"
        proc = run(SCAFFOLD, "--name", "Self Test Plugin", "--path", str(clean),
                   "--with-settings", "--with-rest", "--with-blocks", "--with-ai")
        plugin_dir = clean / "self-test-plugin"
        check("脚手架全选项生成成功",
              proc.returncode == 0 and (plugin_dir / "self-test-plugin.php").is_file(),
              proc.stderr.strip()[-100:] if proc.returncode else "")

        php_files = sorted(plugin_dir.rglob("*.php"))
        check("脚手架产出 10 个 PHP 文件", len(php_files) == 10, f"实际 {len(php_files)} 个")

        if php:
            bad = [f.name for f in php_files
                   if subprocess.run([php, "-l", str(f)], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace").returncode != 0]
            check("脚手架产出 php -l 全部通过", not bad,
                  f"语法失败: {bad}" if bad else f"{len(php_files)} 个文件全部通过")
        else:
            skip("脚手架产出 php -l 全部通过", "未检测到 PHP CLI（安装 PHP 8.1+ 后启用）")

        # ---- 测试 1b: 无选项基础生成（占位符不得残留）----
        basic = tmp / "basic"
        proc = run(SCAFFOLD, "--name", "Plain Basic Plugin", "--path", str(basic))
        basic_dir = basic / "plain-basic-plugin"
        check("无选项基础生成成功",
              proc.returncode == 0 and (basic_dir / "plain-basic-plugin.php").is_file(),
              proc.stderr.strip()[-100:] if proc.returncode else "")
        plugin_class = basic_dir / "src" / "Plugin.php"
        if plugin_class.is_file():
            body = plugin_class.read_text(encoding="utf-8")
            check("无选项生成无占位符残留",
                  "{hooks}" not in body and "{submodule_calls}" not in body)
        else:
            check("无选项生成无占位符残留", False, "Plugin.php 未生成")

        # ---- 测试 1c: 特殊字符插件名（边界输入）----
        # 覆盖实战发现的三类致命场景：数字开头（namespace/常量非法）、
        # 单引号（断裂 PHP 字符串字面量）、*/（提前闭合头部注释注入代码）。
        edge = tmp / "edge"
        edge_names = [
            ("2026 Tools", "2026-tools"),
            ("Bob's Plugin", "bob-s-plugin"),
            ("Evil */ system('x'); /*", "evil-system-x"),
        ]
        gen_ok, lint_bad = True, []
        for name, slug in edge_names:
            proc = run(SCAFFOLD, "--name", name, "--path", str(edge), "--with-settings")
            d = edge / slug
            if proc.returncode != 0 or not (d / f"{slug}.php").is_file():
                gen_ok = False
                lint_bad.append(f"{slug}: 生成失败")
                continue
            if php:
                for f in sorted(d.rglob("*.php")):
                    r = subprocess.run([php, "-l", str(f)], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace")
                    if r.returncode != 0:
                        lint_bad.append(f"{slug}/{f.name}: {r.stderr.strip()[:60]}")
        check("特殊字符插件名生成成功", gen_ok and not lint_bad[:1],
              "; ".join(lint_bad[:2]) if lint_bad else "3 组边界输入全部生成成功")
        if php:
            check("特殊字符插件名 php -l 全部通过", not lint_bad,
                  "; ".join(lint_bad[:2]) if lint_bad else "3 组边界输入语法全部合法")
        else:
            skip("特殊字符插件名 php -l 全部通过", "未检测到 PHP CLI")

        # ---- 测试 1d: CLI 边界（--path 指向文件应优雅报错，非栈回溯）----
        not_a_dir = tmp / "not-a-dir"
        not_a_dir.write_text("x", encoding="utf-8")
        proc = run(SCAFFOLD, "--name", "File Path Plugin", "--path", str(not_a_dir))
        check("--path 指向文件时优雅报错",
              proc.returncode == 2 and "Traceback" not in proc.stderr
              and "不是目录" in proc.stderr,
              (proc.stderr.strip().splitlines() or ["无输出"])[-1][:60])

        # ---- 测试 1e: 非 ASCII（中文）插件名不得 slug 冲突 ----
        cn = tmp / "cn"
        cn.mkdir()
        cn_slugs = []
        cn_ok = True
        for nm in ["我的测试插件", "另一个插件"]:
            proc = run(SCAFFOLD, "--name", nm, "--path", str(cn))
            if proc.returncode != 0:
                cn_ok = False
                break
            m = re.search(r"slug=(\S+)", proc.stdout)
            cn_slugs.append(m.group(1) if m else "?")
        check("中文插件名生成成功且互不冲突",
              cn_ok and len(set(cn_slugs)) == 2,
              f"slugs={cn_slugs}")

        # ---- 测试 1f: 子模块引导方式（不得在 plugins_loaded 内重复 add_action）----
        pc_body = plugin_class.read_text(encoding="utf-8") if plugin_class.is_file() else ""
        if plugin_dir.is_dir():
            pc_body = (plugin_dir / "src" / "Plugin.php").read_text(encoding="utf-8")
        check("子模块用直接调用引导（不在 plugins_loaded 内 add_action）",
              "add_action( 'plugins_loaded'" not in pc_body
              and all(f"{ns}::init();" in pc_body for ns in
                      ["Admin\\SettingsPage", "Api\\RestRoutes", "Ai\\AiFeatures", "Blocks\\ExampleBlock"]),
              "四个子模块均由 Plugin::init() 直接调用")

        # ---- 测试 1f2: AI 桩的 Abilities API 注册顺序与钩子归属 ----
        # 必须按"方法定义顺序"判定，而不是按字符串首次出现位置：
        # wp_register_ability_category( 是 wp_register_ability( 的前缀，
        # 且注释里常出现这两个词，直接比位置会得出完全错误的结论。
        ai_file = plugin_dir / "src" / "Ai" / "AiFeatures.php"
        if ai_file.is_file():
            ai_src = ai_file.read_text(encoding="utf-8")
            # 去掉行注释与块注释，避免注释干扰定位
            ai_code = re.sub(r"/\*.*?\*/", "", ai_src, flags=re.S)
            ai_code = re.sub(r"//[^\n]*", "", ai_code)
            cat_def = ai_code.find("function register_category")
            ab_def = ai_code.find("function register_ability")
            cat_hook = "wp_abilities_api_categories_init" in ai_code
            ab_hook = "wp_abilities_api_init" in ai_code
            # 分类注册必须挂在 categories_init，ability 注册必须挂在 api_init
            cat_on_right_hook = bool(re.search(
                r"add_action\(\s*'wp_abilities_api_categories_init'\s*,\s*array\([^)]*'register_category'",
                ai_code))
            ab_on_right_hook = bool(re.search(
                r"add_action\(\s*'wp_abilities_api_init'\s*,\s*array\([^)]*'register_ability'",
                ai_code))
            check("AI 桩：分类注册方法先于 ability 注册方法定义",
                  cat_def != -1 and ab_def != -1 and cat_def < ab_def,
                  f"register_category@{cat_def} register_ability@{ab_def}")
            check("AI 桩：分类与 ability 分别挂在正确的初始化钩子上",
                  cat_hook and ab_hook and cat_on_right_hook and ab_on_right_hook,
                  "categories_init / api_init 归属正确"
                  if (cat_hook and ab_hook and cat_on_right_hook and ab_on_right_hook)
                  else "钩子归属错误")
        else:
            check("AI 桩：分类注册方法先于 ability 注册方法定义", False, "AiFeatures.php 未生成")
            check("AI 桩：分类与 ability 分别挂在正确的初始化钩子上", False, "AiFeatures.php 未生成")

        # ---- 测试 1g: 运行时冒烟（WordPress 存根真正执行钩子）----
        if php:
            r = subprocess.run([php, str(STUB), str(plugin_dir / "self-test-plugin.php")],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            out = r.stdout
            m = re.search(r"钩子注册数:\s*(\d+)", out)
            hook_count = int(m.group(1)) if m else 0
            fired = re.search(r"实际触发的钩子: (.*)", out)
            fired_tags = fired.group(1).strip() if fired else ""
            check("运行时冒烟通过（autoloader/namespace/钩子）",
                  r.returncode == 0 and hook_count >= 7 and "FAIL" not in out,
                  f"钩子 {hook_count} 个" if hook_count else
                  (out.strip().splitlines() or ["无输出"])[-1][:70])
            # 关键回归：plugins_loaded 必须真的被触发，且子模块钩子必须被触发。
            # 若插件在 plugins_loaded 回调内再次 add_action('plugins_loaded')，
            # WP_Hook 的快照语义会让子模块 init 永不执行——这正是被掩盖的致命缺陷。
            check("plugins_loaded 钩子被真实执行",
                  "plugins_loaded" in fired_tags, fired_tags[:90])
            check("子模块钩子被真实执行（init/rest_api_init/admin_*）",
                  any(t in fired_tags for t in ("init", "rest_api_init", "admin_init", "admin_menu")),
                  fired_tags[:90])
            check("abilities 分类与 ability 注册路径被真实执行",
                  "wp_abilities_api_categories_init" in fired_tags
                  and "wp_abilities_api_init" in fired_tags,
                  fired_tags[:120])

            # ---- 测试 1h: 存根必须能诊断出"快照陷阱"致命模式 ----
            # 在 plugins_loaded 回调内部再 add_action('plugins_loaded', ...) 时，
            # WP_Hook 的快照语义使子模块 init 永不执行。存根必须能识别并报 FAIL，
            # 否则这个缺陷会继续被"只统计注册数"的存根掩盖。
            trap = tmp / "trap-plugin"
            (trap / "src" / "Api").mkdir(parents=True)
            (trap / "src" / "autoload.php").write_text(
                "<?php\nif ( ! defined( 'ABSPATH' ) ) { exit; }\n"
                "spl_autoload_register( function ( string $class ): void {\n"
                "    $prefix = 'TrapPlugin\\\\';\n"
                "    if ( strpos( $class, $prefix ) !== 0 ) { return; }\n"
                "    $file = TRAP_PLUGIN_DIR . 'src/' . str_replace( '\\\\', '/', "
                "substr( $class, strlen( $prefix ) ) ) . '.php';\n"
                "    if ( file_exists( $file ) ) { require_once $file; }\n"
                "} );\n",
                encoding="utf-8")
            (trap / "trap-plugin.php").write_text(
                "<?php\n/**\n * Plugin Name: Trap Plugin\n */\n"
                "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
                "define( 'TRAP_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );\n"
                "require_once TRAP_PLUGIN_DIR . 'src/autoload.php';\n"
                "add_action( 'plugins_loaded', array( TrapPlugin\\Plugin::class, 'init' ) );\n",
                encoding="utf-8")
            (trap / "src" / "Plugin.php").write_text(
                "<?php\nnamespace TrapPlugin;\n"
                "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
                "class Plugin {\n    public static function init(): void {\n"
                "        add_action( 'plugins_loaded', array( Api\\RestRoutes::class, 'init' ) );\n"
                "    }\n}\n",
                encoding="utf-8")
            (trap / "src" / "Api" / "RestRoutes.php").write_text(
                "<?php\nnamespace TrapPlugin\\Api;\n"
                "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
                "class RestRoutes {\n    public static function init(): void {\n"
                "        add_action( 'rest_api_init', array( self::class, 'register_routes' ) );\n"
                "    }\n"
                "    public static function register_routes(): void {\n"
                "        register_rest_route( 'trap/v1', '/x', array( 'methods' => 'GET', "
                "'callback' => '__return_true' ) );\n    }\n}\n",
                encoding="utf-8")
            r2 = subprocess.run([php, str(STUB), str(trap / "trap-plugin.php")],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
            check("存根能诊断出 plugins_loaded 快照陷阱（子模块永不执行）",
                  r2.returncode == 1 and "快照" in r2.stdout,
                  (r2.stdout.strip().splitlines() or ["无输出"])[-1][:80])

            # ---- 测试 1i: 存根必须能诊断出 ability 注册的两类静默致命错误 ----
            # ① 分类从未注册：wp_register_ability() 抛错，ability 凭空消失；
            # ② 分类注册到错误的钩子：wp_register_ability_category() 抛错。
            # 两者都不会让插件 fatal，只是安静地少一个 ability，必须由存根拦下。
            ai_cases = [
                ("ai-missing-cat", "AiMissingCatPlugin", "AIMISSINGCAT",
                 "ai-missing-cat",
                 "        add_action( 'wp_abilities_api_init', "
                 "array( self::class, 'register_ability' ) );\n",
                 "分类未注册"),
                ("ai-wrong-hook", "AiWrongHookPlugin", "AIWRONGHOOK",
                 "ai-wrong-hook",
                 "        add_action( 'wp_abilities_api_init', "
                 "array( self::class, 'register_category' ) );\n"
                 "        add_action( 'wp_abilities_api_init', "
                 "array( self::class, 'register_ability' ) );\n",
                 "wp_abilities_api_categories_init"),
            ]
            ai_ok = True
            ai_detail = []
            for dirname, ns, const, slug, init_body, expect in ai_cases:
                d = tmp / dirname
                build_ai_fixture(d, ns, const, slug, init_body)
                r3 = subprocess.run([php, str(STUB), str(d / f"{slug}.php")],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace")
                if not (r3.returncode == 1 and expect in r3.stdout):
                    ai_ok = False
                    ai_detail.append(
                        f"{dirname}: exit={r3.returncode} 期望含 {expect!r}")
            check("存根能诊断出 ability 分类未注册 / 注册钩子错误", ai_ok,
                  "; ".join(ai_detail) if ai_detail else "两类错误均被拦下")

            # ---- 测试 1i2: 存根必须能诊断出连接器注册错误 ----
            # 官方 WP_Connector_Registry::register() 对重复 ID / 非法 ID /
            # 非法认证方式都会 _doing_it_wrong 并返回 null。存根必须拦下，
            # 否则插件会以为自己注册成功了。
            conn_dir = tmp / "conn-plugin"
            (conn_dir / "src").mkdir(parents=True)
            (conn_dir / "src" / "autoload.php").write_text(
                "<?php\nif ( ! defined( 'ABSPATH' ) ) { exit; }\n", encoding="utf-8")
            (conn_dir / "conn-plugin.php").write_text(
                "<?php\n/**\n * Plugin Name: Conn Fixture\n */\n"
                "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
                "define( 'CONN_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );\n"
                "add_action( 'wp_connectors_init', function ( $registry ) {\n"
                "    $registry->register( 'dup_connector', array(\n"
                "        'name' => __( 'Dup', 'conn-fixture' ),\n"
                "        'type' => 'content_sync',\n"
                "        'authentication' => array( 'method' => 'api_key' ),\n"
                "    ) );\n"
                "    // 重复 ID：官方会 _doing_it_wrong 并返回 null\n"
                "    $registry->register( 'dup_connector', array(\n"
                "        'name' => __( 'Dup Again', 'conn-fixture' ),\n"
                "        'type' => 'content_sync',\n"
                "        'authentication' => array( 'method' => 'api_key' ),\n"
                "    ) );\n"
                "} );\n",
                encoding="utf-8")
            r4 = subprocess.run([php, str(STUB), str(conn_dir / "conn-plugin.php")],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
            check("存根能诊断出连接器重复注册",
                  r4.returncode == 1 and "重复注册" in r4.stdout,
                  (r4.stdout.strip().splitlines() or ["无输出"])[-1][:80])
        else:
            skip("运行时冒烟通过（autoloader/namespace/钩子）", "未检测到 PHP CLI")
            skip("plugins_loaded 钩子被真实执行", "未检测到 PHP CLI")
            skip("子模块钩子被真实执行（init/rest_api_init/admin_*）", "未检测到 PHP CLI")
            skip("abilities 分类与 ability 注册路径被真实执行", "未检测到 PHP CLI")
            skip("存根能诊断出 plugins_loaded 快照陷阱（子模块永不执行）", "未检测到 PHP CLI")
            skip("存根能诊断出 ability 分类未注册 / 注册钩子错误", "未检测到 PHP CLI")
            skip("存根能诊断出连接器重复注册", "未检测到 PHP CLI")

        # ---- 测试 1j: 文档事实准确性（对照官方文档核实过的硬事实）----
        #
        # 背景：第 8 轮审查发现参考文档里存在多处与官方不符的表述
        # （连接器 ID 写成 core/openai、声称 wp_get_connector() 返回 base_url、
        #  wp_supports_ai() 被当成带 feature 参数等）。
        # 这类错误不会让任何测试失败——文档照常渲染、代码照常生成——
        # 所以必须用显式断言把"已核实的事实"钉住，防止回退。
        ai_ref = (SCRIPTS.parent / "references" / "ai-client-connectors-abilities.md")
        skill_md = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
        if ai_ref.is_file():
            ai_text = ai_ref.read_text(encoding="utf-8")
            # 1) 内置连接器 ID 官方为 anthropic / google / openai（无任何前缀）。
            #    "core/openai" 这类写法会让插件查不到连接器。
            check("文档载明内置连接器 ID（anthropic/google/openai，无前缀）",
                  all(f"`{cid}`" in ai_text for cid in ("anthropic", "google", "openai"))
                  and not re.search(r"core/(?:openai|claude|gemini|anthropic|google)", ai_text),
                  "core/ 前缀写法已清除")
            # 2) wp_get_connector() 只返回元数据，没有 base_url / 明文密钥
            check("文档未声称 wp_get_connector() 返回 base_url",
                  "base_url（已解密）" not in ai_text and "返回凭证与 base_url" not in ai_text,
                  "")
            # 3) wp_supports_ai() 是零参数函数
            check("文档载明 wp_supports_ai() 为零参数",
                  "零参数" in ai_text, "")
            # 4) WP 7.1 新增的 4 个执行生命周期过滤器
            missing_filters = [f for f in ("wp_pre_execute_ability", "wp_ability_normalize_input",
                                            "wp_ability_permission_result", "wp_ability_execute_result")
                               if f not in ai_text]
            check("文档载明 WP 7.1 新增的 4 个执行生命周期过滤器",
                  not missing_filters, f"缺: {missing_filters}")
            # 5) Abilities REST 端点 + HTTP 方法由 annotations 决定
            check("文档载明 Abilities REST 端点与 annotations 决定的 HTTP 方法",
                  "wp-abilities/v1" in ai_text and "readonly" in ai_text
                  and "DELETE" in ai_text and "POST" in ai_text, "")
            # 6) MCP Adapter 是独立包，不在核心里
            check("文档载明 MCP Adapter 为独立包（非核心）",
                  "mcp-adapter" in ai_text and "独立包" in ai_text, "")
            # 7) 连接器认证方式三种取值 + 常量/环境变量来源 + plugin 子键
            check("文档载明连接器认证三种取值与 constant_name/env_var_name/plugin 子键",
                  "application_password" in ai_text and "constant_name" in ai_text
                  and "env_var_name" in ai_text and "is_active" in ai_text, "")
            # 8) ai_provider + AI 被禁用时 register 静默返回 null
            check("文档载明 ai_provider 在 AI 禁用时静默返回 null",
                  "静默返回" in ai_text and "ai_provider" in ai_text, "")
            # 9) SKILL.md 的版本事实与"MCP 非核心"表述
            check("SKILL.md 载明 7.1.3 为安全版本且 MCP Adapter 非核心",
                  "7.1.3" in skill_md and "安全版本" in skill_md and "独立包" in skill_md, "")
        else:
            check("文档载明内置连接器 ID（anthropic/google/openai，无前缀）",
                  False, "ai-client-connectors-abilities.md 不存在")

        # ---- 测试 1k: references 全部 PHP 代码块语法合法 ----
        # 文档里的代码块会被读者直接复制走，语法错误等于制造 bug。
        # 方法体片段（只有方法、没有类包装）包进类里再校验。
        if php:
            refs_dir = SCRIPTS.parent / "references"
            ref_fail = []
            ref_count = 0
            for md in sorted(refs_dir.glob("*.md")):
                md_text = md.read_text(encoding="utf-8")
                for idx, code in enumerate(re.findall(r"```php\n(.*?)```", md_text, re.S), 1):
                    ref_count += 1
                    body = code.strip()
                    if not body:
                        continue
                    src = body if body.startswith("<?php") else "<?php\n" + body
                    if not re.search(r"^\s*(class|interface|trait|enum)\s+\w", body, flags=re.M) \
                            and re.search(r"^\s*(public|private|protected|static|function)\b", body, flags=re.M):
                        src = "<?php\nclass __Fragment {\n" + body + "\n}\n"
                    frag = tmp / f"ref_{md.stem}_{idx}.php"
                    frag.write_text(src, encoding="utf-8")
                    rr = subprocess.run([php, "-l", str(frag)], capture_output=True, text=True,
                                        encoding="utf-8", errors="replace")
                    if rr.returncode != 0:
                        ref_fail.append(f"{md.name}#{idx}")
            check("references 全部 PHP 代码块 php -l 通过",
                  not ref_fail and ref_count > 0,
                  f"失败: {ref_fail[:3]}" if ref_fail else f"{ref_count} 块全部通过")
        else:
            skip("references 全部 PHP 代码块 php -l 通过", "未检测到 PHP CLI")

        # ---- 测试 1l: 全部文件编码完整（无替换字符 / 非 UTF-8）----
        # 中文注释在批量编辑时可能被截断成 U+FFFD 替换字符，
        # 肉眼很难发现，但会污染交付物。用显式扫描兜住。
        enc_bad = []
        for f in sorted(SCRIPTS.parent.rglob("*")):
            if f.is_dir() or "__pycache__" in f.parts or f.suffix == ".pyc":
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                enc_bad.append(f"{f.relative_to(SCRIPTS.parent)}: 非 UTF-8")
                continue
            for ln, line in enumerate(text.splitlines(), 1):
                if "\ufffd" in line:
                    enc_bad.append(
                        f"{f.relative_to(SCRIPTS.parent)}:{ln} 含替换字符")
                    break
        check("全部文件编码完整（无 U+FFFD 替换字符）",
              not enc_bad, "; ".join(enc_bad[:3]) if enc_bad else "无损坏字符")

        # ---- 测试 1m: 第 9 轮事实核对守卫（对照官方参考页 + WP 7.1 核心源码）----
        #
        # 背景：第 9 轮审查把参考文档的密集 API 表格逐条比对官方参考页与
        # WP 7.1 核心源码，发现 10 处硬错误（参数位置、版本号、行为描述
        # 与官方不符）与 9 处关键遗漏。这类错误同样不会让任何测试失败，
        # 必须用显式断言钉死。
        hooks_ref = (SCRIPTS.parent / "references" / "hooks-and-core-apis.md")
        guten_ref = (SCRIPTS.parent / "references" / "gutenberg-and-frontend.md")
        sec_ref = (SCRIPTS.parent / "references" / "security-checklist.md")
        fund_ref = (SCRIPTS.parent / "references" / "plugin-fundamentals.md")
        rel_ref = (SCRIPTS.parent / "references" / "release-and-quality.md")

        if all(p.is_file() for p in (hooks_ref, guten_ref, sec_ref, fund_ref, rel_ref)):
            hooks_text = hooks_ref.read_text(encoding="utf-8")
            guten_text = guten_ref.read_text(encoding="utf-8")
            sec_text = sec_ref.read_text(encoding="utf-8")
            fund_text = fund_ref.read_text(encoding="utf-8")
            rel_text = rel_ref.read_text(encoding="utf-8")

            # 1) add_submenu_page 的 capability 在第 4 位，不是第 3 位。
            #    官方签名：add_submenu_page( $parent_slug, $page_title, $menu_title, $capability, ... )
            check("文档区分 add_submenu_page（capability 第4位）与 add_menu_page/add_options_page（第3位）",
                  "第 4" in hooks_text and "第 3" in hooks_text
                  and "add_submenu_page" in hooks_text,
                  "三个菜单函数的 capability 参数位置必须分别说明")

            # 2) dbDelta 的 "PRIMARY KEY 必须两个空格" 是误解——
            #    官方正则 PRIMARY\s+KEY|(?:UNIQUE|FULLTEXT|SPATIAL)\s+(?:KEY|INDEX)|KEY|INDEX
            check("文档未声称 dbDelta 的 PRIMARY KEY 需要两个空格",
                  "双空格格式要求" not in hooks_text
                  and ("一个空格即可" in hooks_text or "一个空格" in hooks_text),
                  "dbDelta 硬性要求是每字段单独一行")

            # 3) register_rest_route 的 permission_callback 自 WP 5.5 起必填（不是 6.5+）
            check("文档载明 permission_callback 自 WP 5.5 起必填",
                  "5.5" in hooks_text and "6.5+" not in
                  re.search(r"permission_callback[^\n]*", hooks_text).group(0)
                  if re.search(r"permission_callback[^\n]*", hooks_text) else False,
                  "官方源码 @since 5.5.0")
            check("安全清单未把 permission_callback 必填版本写成 6.5+",
                  "WP 6.5+ 必填" not in sec_text and "5.5" in sec_text, "")

            # 4) register_setting() 没有 permission_callback 参数
            check("文档载明 register_setting 无 permission_callback 参数",
                  "register_setting" in hooks_text and "没有" in hooks_text
                  and "permission_callback" in hooks_text, "")

            # 5) register_meta 的权限回调键名是 auth_callback，不是 permission_callback
            check("文档载明 register_meta 用 auth_callback 而非 permission_callback",
                  "auth_callback" in hooks_text, "")

            # 6) wp_localize_script 不该用于传数据；官方推荐 wp_add_inline_script + wp_json_encode
            check("文档推荐 wp_add_inline_script + wp_json_encode 且劝退 wp_localize_script 传数据",
                  "wp_add_inline_script" in guten_text and "wp_json_encode" in guten_text
                  and "wp_localize_script" in guten_text
                  and "wp_localize_script" in sec_text,
                  "")
            check("文档不再示范用 wp_localize_script 传 ajaxUrl/nonce",
                  "wp_localize_script( 'my-plugin-admin'" not in guten_text
                  and "MyPluginData', array(" not in guten_text,
                  "示例已改为 wp_add_inline_script")

            # 7) wp_unslash 只处理字符串与数组；且要先于 sanitize
            check("文档载明 wp_unslash 先于 sanitize 且只处理字符串/数组",
                  "wp_unslash" in hooks_text and "wp_unslash" in sec_text
                  and ("只对字符串去斜杠" in hooks_text or "只处理字符串" in hooks_text
                       or "只处理字符串与数组" in hooks_text), "")

            # 8) Requires at least / Requires PHP 自 WP 5.3 起从主文件读取（不是 5.5+/5.1+）
            check("文档载明 Requires at least / Requires PHP 自 WP 5.3 起支持",
                  "5.3" in fund_text and "5.5+/5.1+" not in fund_text, "")
            check("文档载明 Requires Plugins 为 WP 6.5+ 且 Update URI 为 WP 5.8+",
                  "6.5+" in fund_text and "5.8+" in fund_text, "")

            # 9) apiVersion 3 对应 WP 6.3+
            check("文档载明 apiVersion 3 对应 WP 6.3+",
                  "6.3" in guten_text and "apiVersion" in guten_text, "")

            # 10) Interactivity API 必须有 data-wp-interactive 激活区
            check("文档载明 Interactivity API 需 data-wp-interactive 声明交互区",
                  "data-wp-interactive" in guten_text, "")

            # 11) Plugin Check 官方名与 CLI 用法
            check("文档载明 Plugin Check (PCP) 的官方名与 WP-CLI 用法",
                  "Plugin Check (PCP)" in rel_text and "wp plugin check" in rel_text, "")

            # 12) 评审时限为 14 个工作日（不是 14 天）
            check("文档载明初审时限为 14 个工作日",
                  "14 个工作日" in rel_text, "")

            # 13) 资产在 SVN 顶层 assets/，文件名即尺寸；SVG 需 PNG 兜底
            check("文档载明资产目录为 SVN 顶层 assets/ 且文件名即尺寸",
                  "banner-772x250" in rel_text and "icon-128x128" in rel_text
                  and "PNG 兜底" in rel_text, "")

            # 14) use_block_editor_for_post 是函数（int|WP_Post -> bool）
            check("文档载明 use_block_editor_for_post 的函数签名与返回值",
                  "use_block_editor_for_post" in guten_text
                  and ("WP_Post" in guten_text or "int" in guten_text), "")

            # 15) 保留的 CPT 名称清单
            check("文档载明 register_post_type 的保留名清单",
                  "wp_template_part" in hooks_text and "nav_menu_item" in hooks_text, "")
        else:
            for label in ("文档区分 add_submenu_page（capability 第4位）与 add_menu_page/add_options_page（第3位）",
                          "文档未声称 dbDelta 的 PRIMARY KEY 需要两个空格",
                          "文档载明 permission_callback 自 WP 5.5 起必填",
                          "安全清单未把 permission_callback 必填版本写成 6.5+",
                          "文档载明 register_setting 无 permission_callback 参数",
                          "文档载明 register_meta 用 auth_callback 而非 permission_callback",
                          "文档推荐 wp_add_inline_script + wp_json_encode 且劝退 wp_localize_script 传数据",
                          "文档不再示范用 wp_localize_script 传 ajaxUrl/nonce",
                          "文档载明 wp_unslash 先于 sanitize 且只处理字符串/数组",
                          "文档载明 Requires at least / Requires PHP 自 WP 5.3 起支持",
                          "文档载明 Requires Plugins 为 WP 6.5+ 且 Update URI 为 WP 5.8+",
                          "文档载明 apiVersion 3 对应 WP 6.3+",
                          "文档载明 Interactivity API 需 data-wp-interactive 声明交互区",
                          "文档载明 Plugin Check (PCP) 的官方名与 WP-CLI 用法",
                          "文档载明初审时限为 14 个工作日",
                          "文档载明资产目录为 SVN 顶层 assets/ 且文件名即尺寸",
                          "文档载明 use_block_editor_for_post 的函数签名与返回值",
                          "文档载明 register_post_type 的保留名清单"):
                check(label, False, "参考文档缺失")

        # ---- 测试 1n: 第 10 轮事实核对守卫（对照 WP 核心源码 + PHP AI Client SDK）----
        #
        # 背景：第 10 轮审查改为直接下载并逐行比对 WP 核心源码文件
        # （wp-includes/ai-client/、abilities-api/、
        #  rest-api/endpoints/class-wp-rest-abilities-v1-*.php、connectors.php）
        # 与 WordPress/php-ai-client SDK，发现 4 处硬错误与 7 处关键遗漏，
        # 其中「7.1 新增 4 个生命周期过滤器」的错误已扩散到 SKILL.md 与
        # README.md。这类错误不会让任何测试失败，必须显式钉死。
        ai_ref = (SCRIPTS.parent / "references" / "ai-client-connectors-abilities.md")
        skill_md = (SCRIPTS.parent / "SKILL.md")
        readme_md = (SCRIPTS.parent / "README.md")

        if all(p.is_file() for p in (ai_ref, skill_md, readme_md)):
            ai_text = ai_ref.read_text(encoding="utf-8")
            skill_text = skill_md.read_text(encoding="utf-8")
            readme_text = readme_md.read_text(encoding="utf-8")
            scaffold_text = (SCRIPTS / "scaffold_plugin.py").read_text(encoding="utf-8")

            # 1) REST run 端点用 DELETE 的判定是 destructive && idempotent 双条件。
            #    官方 WP_REST_Abilities_V1_Run_Controller::validate_request_method()：
            #      if readonly -> GET
            #      elseif destructive && idempotent -> DELETE
            #      else -> POST
            #    只写 destructive: true 会落回 POST，与直觉相反。
            check("文档载明 DELETE 需 destructive 与 idempotent 同时为 true",
                  "idempotent" in ai_text and "同时" in ai_text
                  and "destructive" in ai_text, "")
            check("文档未把 destructive 单独描述为即等于 DELETE",
                  "destructive: true` | **DELETE" not in ai_text,
                  "官方要求 destructive && idempotent 双条件")

            # 2) WP 7.1 新增的执行生命周期过滤器是 6 个，不是 4 个。
            #    官方 WP_Ability 中 7.1 标注的过滤器：
            #      wp_pre_execute_ability / wp_ability_normalize_input /
            #      wp_ability_validate_input / wp_ability_permission_result /
            #      wp_ability_execute_result / wp_ability_validate_output
            for fname in ("wp_pre_execute_ability", "wp_ability_normalize_input",
                          "wp_ability_validate_input", "wp_ability_permission_result",
                          "wp_ability_execute_result", "wp_ability_validate_output"):
                check(f"文档载明 7.1 过滤器 {fname}",
                      fname in ai_text, "官方 WP_Ability 源码 @since 7.1.0")
            check("文档不再声称 7.1 只有 4 个生命周期过滤器",
                  "4 个执行生命周期过滤器" not in ai_text
                  and "4 个生命周期过滤器" not in ai_text, "")
            check("SKILL.md 已把生命周期过滤器数量更正为 6 个",
                  "6 个执行生命周期过滤器" in skill_text
                  and "4 个执行生命周期过滤器" not in skill_text, "")
            check("README.md 已把生命周期过滤器数量更正为 6 个",
                  "6 个" in readme_text and "4 个执行生命周期过滤器" not in readme_text, "")

            # 3) wp_pre_execute_ability 的短路靠哨兵对象：
            #    只有返回值 !== WP_Filter_Sentinel 才算短路。
            check("文档载明 wp_pre_execute_ability 的哨兵短路语义",
                  "哨兵" in ai_text and "wp_pre_execute_ability" in ai_text, "")

            # 4) wp_ability_permission_result 非 bool 非 WP_Error 会被强制转 false
            check("文档载明 permission_result 的非 bool 强制转 false 语义",
                  "强制转为 `false`" in ai_text or "强制转为 false" in ai_text, "")

            # 5) 7.2 起 category 可选（默认 uncategorized）、
            #    permission_callback 可由 required_capabilities 替代
            check("文档载明 7.2 起 category 可选并默认 uncategorized",
                  "uncategorized" in ai_text and "7.2" in ai_text, "")
            check("文档载明 required_capabilities 可替代 permission_callback",
                  "required_capabilities" in ai_text, "")

            # 6) wp_ai_client_embedding() 自 7.2.0 起提供
            check("文档载明 wp_ai_client_embedding 为 7.2 新增",
                  "wp_ai_client_embedding" in ai_text and "7.2" in ai_text, "")

            # 7) REST 层错误码：rest_ability_invalid_method(405)、rest_ability_not_found(404)
            check("文档载明 REST 层 405 错误码 rest_ability_invalid_method",
                  "rest_ability_invalid_method" in ai_text and "405" in ai_text, "")

            # 8) wp_get_abilities() 的 7.2 新参数 has_required_capabilities
            check("文档载明 wp_get_abilities 的 has_required_capabilities 参数",
                  "has_required_capabilities" in ai_text, "")

            # 9) 脚手架的 ability 桩不得设 readonly: true
            #    ——readonly 会让官方 REST 控制器强制 GET，长正文走 URL 会被截断。
            check("脚手架 ability 桩未把 readonly 设为 true",
                  "'readonly'    => true" not in scaffold_text
                  and "'readonly'    => false" in scaffold_text, "")
            check("脚手架 ability 桩标注了 readonly 与 GET 方法的关系",
                  "GET" in scaffold_text and "readonly" in scaffold_text, "")
        else:
            for label in ("文档载明 DELETE 需 destructive 与 idempotent 同时为 true",
                          "文档未把 destructive 单独描述为即等于 DELETE",
                          "文档载明 7.1 过滤器 wp_pre_execute_ability",
                          "文档载明 7.1 过滤器 wp_ability_normalize_input",
                          "文档载明 7.1 过滤器 wp_ability_validate_input",
                          "文档载明 7.1 过滤器 wp_ability_permission_result",
                          "文档载明 7.1 过滤器 wp_ability_execute_result",
                          "文档载明 7.1 过滤器 wp_ability_validate_output",
                          "文档不再声称 7.1 只有 4 个生命周期过滤器",
                          "SKILL.md 已把生命周期过滤器数量更正为 6 个",
                          "README.md 已把生命周期过滤器数量更正为 6 个",
                          "文档载明 wp_pre_execute_ability 的哨兵短路语义",
                          "文档载明 permission_result 的非 bool 强制转 false 语义",
                          "文档载明 7.2 起 category 可选并默认 uncategorized",
                          "文档载明 required_capabilities 可替代 permission_callback",
                          "文档载明 wp_ai_client_embedding 为 7.2 新增",
                          "文档载明 REST 层 405 错误码 rest_ability_invalid_method",
                          "文档载明 wp_get_abilities 的 has_required_capabilities 参数",
                          "脚手架 ability 桩未把 readonly 设为 true",
                          "脚手架 ability 桩标注了 readonly 与 GET 方法的关系"):
                check(label, False, "参考文档或脚本缺失")

        # ---- 测试 2: 扫描器对干净产出 ----
        summary, _ = scan_json(plugin_dir)
        check("干净产出 HIGH=0 且 MEDIUM=0",
              summary.get("HIGH") == 0 and summary.get("MEDIUM") == 0,
              json.dumps(summary, ensure_ascii=False))

        # ---- 测试 3: 扫描器对恶意夹具 ----
        # 恶意签名文件会被实时杀软在 ~100ms 内隔离，Python 子进程启动
        # （~300ms）必输，故恶意夹具走进程内扫描；关键是先完成模块导入
        # （编译耗时不计入窗口），再写夹具、立即扫描，将窗口压到 ~25ms。
        # 写入或扫描过程中仍被隔离则重试一次，持续被隔离则 SKIP。
        evil = tmp / "evil"
        evil.mkdir()
        expected = set(EVIL_FILES)

        def evil_alive() -> set:
            return expected - {p.name for p in evil.iterdir()}

        if str(SCANNER.parent) not in sys.path:
            sys.path.insert(0, str(SCANNER.parent))
        import wp_security_scan as scanner  # 预热导入，压缩写入-扫描窗口

        need = {"rce", "obfuscation", "file", "hijack", "binary",
                "hidden", "abspath", "ajax-nonce", "rest", "input", "sql"}
        result: tuple[dict, set] | None = None
        for attempt in (1, 2):
            build_evil(evil)
            eaten = evil_alive()
            if eaten:
                print(f"[warn] 夹具写入时即被隔离（第 {attempt} 次）: {sorted(eaten)}")
                continue
            findings = scanner.scan(str(evil))
            eaten_mid = evil_alive()
            if eaten_mid:
                print(f"[warn] 扫描过程中夹具被隔离（第 {attempt} 次）: {sorted(eaten_mid)}")
                continue
            counts = {s: sum(1 for f in findings if f["severity"] == s)
                      for s in ("HIGH", "MEDIUM", "LOW", "INFO")}
            categories = {f["category"] for f in findings}
            result = (counts, need - categories)
            break

        if result is None:
            skip("恶意样本进程内扫描 HIGH>=8", "安全软件在写入/扫描窗口内持续隔离夹具")
            skip("恶意样本威胁类别全覆盖", "同上（可在 CI 或无实时防护环境获得完整覆盖）")
            skip("恶意样本 CLI exit=1", "同上")
        else:
            counts, missing = result
            check("恶意样本进程内扫描 HIGH>=8", counts["HIGH"] >= 8,
                  json.dumps(counts, ensure_ascii=False))
            check("恶意样本威胁类别全覆盖", not missing,
                  f"缺失: {sorted(missing)}" if missing else f"{len(need)} 类全部命中")

            # 进程内扫描后文件仍存活 -> 顺带验证 CLI 退出码路径
            if evil_alive():
                skip("恶意样本 CLI exit=1", "夹具在进程内扫描后被隔离，跳过 CLI 复测")
            else:
                proc = run(SCANNER, str(evil), "--json")
                if proc.returncode == 1:
                    check("恶意样本 CLI exit=1", True)
                elif evil_alive():
                    skip("恶意样本 CLI exit=1", "CLI 扫描过程中夹具被隔离")
                else:
                    check("恶意样本 CLI exit=1", False,
                          f"exit={proc.returncode} 且文件未被隔离，疑似真实回归")

        # ---- 测试 4: 污点传播（两段式写法）----
        taint_dir = tmp / "taint"
        taint_dir.mkdir()
        (taint_dir / "taint.php").write_text(EVIL_TAINT, encoding="utf-8")
        summary, findings = scan_json(taint_dir)
        cats = {(f["severity"], f["category"]) for f in findings}
        check("污点传播：两段式 SQL 注入被捕获",
              ("HIGH", "sql") in cats, f"HIGH={summary.get('HIGH')}")
        check("污点传播：LFI/RFI 被捕获", ("HIGH", "file") in cats)
        check("污点传播：用户输入作回调被捕获", ("HIGH", "rce") in cats)
        check("污点传播：对象注入（unserialize）被捕获", ("HIGH", "hijack") in cats)

        # ---- 测试 5: 误报控制 ----
        safe_dir = tmp / "safe"
        safe_dir.mkdir()
        (safe_dir / "safe.php").write_text(
            "<?php\n"
            "if ( ! defined( 'ABSPATH' ) ) { exit; }\n"
            "global $wpdb;\n"
            "$rows = $wpdb->get_results( $wpdb->prepare(\n"
            "    'SELECT * FROM p WHERE t LIKE %s',\n"
            "    '%' . sanitize_text_field( $_GET['q'] ) . '%'\n"
            ") );\n",
            encoding="utf-8")
        summary, _ = scan_json(safe_dir)
        check("误报控制：prepare 正确用法不报 HIGH", summary.get("HIGH") == 0,
              json.dumps(summary, ensure_ascii=False))

        up_dir = tmp / "upload"
        up_dir.mkdir()
        (up_dir / "u.php").write_text(
            "<?php\nif ( ! defined( 'ABSPATH' ) ) { exit; }\n"
            "move_uploaded_file( $tmp, $dest );\n",
            encoding="utf-8")
        summary, findings = scan_json(up_dir)
        mv = [f for f in findings if f["category"] == "file"]
        check("误报控制：move_uploaded_file 不判 HIGH",
              summary.get("HIGH") == 0 and bool(mv),
              f"HIGH={summary.get('HIGH')} 提示级={len(mv)}")

        # ---- 测试 6: check_php_syntax 无 PHP 路径 ----
        # 注意：find_php() 现在会主动探测常见安装位置（如 XAMPP / Temp\\php），
        # 只清空 PATH 已不足以制造"无 PHP"环境——必须同时清掉 PHP_BIN，
        # 并把 HOME/USERPROFILE/TEMP 指向空目录，让 glob 也扫不到任何 php.exe。
        env_nophp = dict(os.environ)
        env_nophp["PATH"] = str(tmp / "no-such-bin-dir")
        env_nophp.pop("PHP_BIN", None)
        env_nophp["WP_DEV_NO_PHP_SEARCH"] = "1"
        fake_home = tmp / "fake-home"
        fake_home.mkdir(exist_ok=True)
        env_nophp["USERPROFILE"] = str(fake_home)
        env_nophp["HOME"] = str(fake_home)
        env_nophp["TEMP"] = str(fake_home)
        env_nophp["TMP"] = str(fake_home)
        env_nophp["LOCALAPPDATA"] = str(fake_home / "AppData" / "Local")
        (fake_home / "AppData" / "Local").mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([sys.executable, str(SYNTAX_CHECK), str(plugin_dir)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env_nophp)
        check("无 PHP 时语法检查优雅跳过",
              proc.returncode == 0 and "跳过" in proc.stdout,
              proc.stdout.strip().splitlines()[0][:60] if proc.stdout.strip() else "无输出")

        # ---- 测试 7: check_php_syntax 有 PHP 路径 ----
        if php:
            env_php = dict(os.environ)
            env_php["PATH"] = str(Path(php).parent) + os.pathsep + env_php.get("PATH", "")
            proc = subprocess.run([sys.executable, str(SYNTAX_CHECK), str(plugin_dir)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env_php)
            check("有 PHP 时语法检查正常执行",
                  proc.returncode == 0 and "语法错误 0 个" in proc.stdout,
                  proc.stdout.strip().splitlines()[-1][:60] if proc.stdout.strip() else "无输出")
        else:
            skip("有 PHP 时语法检查正常执行", "未检测到 PHP CLI")

        # ---- 测试 8: 版本保鲜不阻塞 ----
        proc = run(VERSION_CHECK)
        check("版本保鲜检查退出码恒为 0", proc.returncode == 0,
              proc.stdout.strip().splitlines()[0][:60] if proc.stdout.strip() else "")

    failed = [name for name, ok, _ in RESULTS if not ok]
    total = len(RESULTS) + len(SKIPS)
    print(f"\n总计 {total} 项: 通过 {len(RESULTS) - len(failed)}, 失败 {len(failed)}, 跳过 {len(SKIPS)}")
    if failed:
        for name in failed:
            print(f"  - {name}")
        return 1
    print("OK: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
