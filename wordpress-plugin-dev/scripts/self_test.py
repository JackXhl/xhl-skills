#!/usr/bin/env python3
"""self_test.py - wordpress-plugin-dev 技能自测（eval-lite）。

用内置夹具对技能的全部脚本做回归验证，任何环境可重复执行：
  1. 脚手架全选项生成 -> 文件齐全 -> php -l 语法全过（需 PHP，无则跳过）
  2. 扫描器对干净产出 -> HIGH=0
  3. 扫描器对恶意夹具 -> exit=1、HIGH>=8、威胁类别全覆盖
     （rce/obfuscation/file/hijack/binary/hidden/abspath/ajax-nonce/rest/input）
  4. check_php_syntax 无 PHP 路径 -> 优雅跳过；有 PHP 路径 -> 正常检查
  5. check_wp_versions -> 退出码恒为 0（离线/在线均不阻塞）

环境说明: 部分 Windows 杀毒软件（如火绒 Hips / Defender）会在文件写入后
约 100ms 内隔离含恶意签名的夹具（实测延迟 <100ms，而 Python 子进程启动
约 200-400ms，子进程方式必被删）。因此恶意夹具采用进程内扫描（微秒级
窗口）；若写入时即被隔离则重试一次，仍被隔离则明确 SKIP（环境限制，
非技能缺陷），其余断言不受影响。CI（无实时防护）环境下全覆盖。

用法: python self_test.py
退出码: 0=全部通过（含跳过）, 1=存在失败项。
依赖: Python 3.8+，无第三方库；PHP CLI 可选（有则启用语法断言）。
"""

from __future__ import annotations

import json
import os
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

EVIL_FILES = {
    "evil-plugin.php": None,  # 内容在 build_evil 中写入
    "noguard.php": None,
    "rce.php": None,
    "obfuscated.php": None,
    "rest.php": None,
    ".env": None,
    "dropper.exe": None,
}

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
    for name in ("php", "php8", "php8.3", "php8.2", "php8.1", "php.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def build_evil(dirpath: Path) -> None:
    (dirpath / "evil-plugin.php").write_text(EVIL_MAIN, encoding="utf-8")
    (dirpath / "noguard.php").write_text(EVIL_NOGUARD, encoding="utf-8")
    (dirpath / "rce.php").write_text(EVIL_RCE, encoding="utf-8")
    (dirpath / "obfuscated.php").write_text(EVIL_OBFUSCATED, encoding="utf-8")
    (dirpath / "rest.php").write_text(EVIL_REST, encoding="utf-8")
    (dirpath / ".env").write_text("SECRET=fixture\n", encoding="utf-8")
    (dirpath / "dropper.exe").write_bytes(b"MZ\x90\x00\x03")


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

        # ---- 测试 2: 扫描器对干净产出 ----
        proc = run(SCANNER, str(plugin_dir), "--json")
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = {"summary": {"HIGH": -1}}
        check("干净产出 HIGH=0", data["summary"]["HIGH"] == 0 and proc.returncode == 0,
              json.dumps(data["summary"], ensure_ascii=False))

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
                "hidden", "abspath", "ajax-nonce", "rest", "input"}
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

        # ---- 测试 4: check_php_syntax 无 PHP 路径 ----
        env_nophp = dict(os.environ)
        env_nophp["PATH"] = str(tmp / "no-such-bin-dir")
        proc = subprocess.run([sys.executable, str(SYNTAX_CHECK), str(plugin_dir)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env_nophp)
        check("无 PHP 时语法检查优雅跳过",
              proc.returncode == 0 and "跳过" in proc.stdout,
              proc.stdout.strip().splitlines()[0][:60] if proc.stdout.strip() else "无输出")

        # ---- 测试 5: check_php_syntax 有 PHP 路径 ----
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

        # ---- 测试 6: 版本保鲜不阻塞 ----
        proc = run(VERSION_CHECK)
        check("版本保鲜检查退出码恒为 0", proc.returncode == 0,
              proc.stdout.strip().splitlines()[0][:60] if proc.stdout.strip() else "")

    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n总计 {len(RESULTS)} 项: 通过 {len(RESULTS) - len(failed)}, 失败 {len(failed)}, 跳过 {len(SKIPS)}")
    if failed:
        for name in failed:
            print(f"  - {name}")
        return 1
    print("OK: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
