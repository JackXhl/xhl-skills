#!/usr/bin/env python3
"""scaffold_plugin.py - 生成符合 WordPress 规范的插件骨架。

用法:
    python scaffold_plugin.py --name "My Plugin" [--path D:/wp-content/plugins]
        [--slug my-plugin] [--author "Your Name"] [--author-uri https://example.com]
        [--with-settings] [--with-rest] [--with-blocks] [--with-ai]

生成内容:
    {slug}/{slug}.php          主文件（完整 header + ABSPATH 守卫 + 引导）
    {slug}/src/autoload.php     PSR-4 自动加载
    {slug}/src/Plugin.php       主类（子模块引导）
    {slug}/src/Activator.php    激活逻辑
    {slug}/src/Deactivator.php  停用逻辑
    {slug}/uninstall.php        卸载清理（WP_UNINSTALL_PLUGIN 守卫）
    {slug}/readme.txt           wordpress.org 发布模板
    {slug}/languages/           翻译目录
  可选: 设置页 / REST 路由 / 块桩 / AI Client+Connector+Ability 桩
"""

from __future__ import annotations

import argparse
import hashlib
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


HEADER = """<?php
/**
 * Plugin Name:       {name}
 * Plugin URI:        {plugin_uri}
 * Description:       {description}
 * Version:           1.0.0
 * Requires at least: 7.0
 * Requires PHP:      8.1
 * Author:            {author}
 * Author URI:        {author_uri}
 * License:           GPL v2 or later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       {slug}
 * Domain Path:       /languages
 *
 * @package {namespace}
 */

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

define( '{const_prefix}_VERSION', '1.0.0' );
define( '{const_prefix}_FILE', __FILE__ );
define( '{const_prefix}_DIR', plugin_dir_path( __FILE__ ) );
define( '{const_prefix}_URL', plugin_dir_url( __FILE__ ) );

require_once {const_prefix}_DIR . 'src/autoload.php';

register_activation_hook( __FILE__, array( {namespace}\\Activator::class, 'activate' ) );
register_deactivation_hook( __FILE__, array( {namespace}\\Deactivator::class, 'deactivate' ) );

add_action( 'plugins_loaded', array( {namespace}\\Plugin::class, 'init' ) );
"""

AUTOLOAD = """<?php
/**
 * PSR-4 autoloader for {name}
 *
 * @package {namespace}
 */

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

spl_autoload_register( function ( string $class ): void {{
    $prefix = '{namespace}\\\\';
    if ( strpos( $class, $prefix ) !== 0 ) {{
        return;
    }}
    $relative = substr( $class, strlen( $prefix ) );
    $file = {const_prefix}_DIR . 'src/' . str_replace( '\\\\', '/', $relative ) . '.php';
    if ( file_exists( $file ) ) {{
        require_once $file;
    }}
}} );
"""

PLUGIN_CLASS = """<?php
/**
 * Main plugin class
 *
 * @package {namespace}
 */

namespace {namespace};

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class Plugin {{

    public static function init(): void {{
        load_plugin_textdomain( '{slug}', false, dirname( plugin_basename( __FILE__ ), 2 ) . '/languages' );
{submodule_calls}    }}
}}
"""

ACTIVATOR = """<?php
/**
 * Activation logic
 *
 * @package {namespace}
 */

namespace {namespace};

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class Activator {{

    public static function activate(): void {{
        if ( version_compare( get_bloginfo( 'version' ), '7.0', '<' ) ) {{
            deactivate_plugins( plugin_basename( {const_prefix}_FILE ) );
            wp_die( esc_html__( '{name_lit} 需要 WordPress 7.0 或更高版本。', '{slug}' ), '插件激活失败', array( 'back_link' => true ) );
        }}
        add_option( '{slug}_version', {const_prefix}_VERSION );
        flush_rewrite_rules();
    }}
}}
"""

DEACTIVATOR = """<?php
/**
 * Deactivation logic
 *
 * @package {namespace}
 */

namespace {namespace};

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class Deactivator {{

    public static function deactivate(): void {{
        // 仅在你确实调度过定时任务时保留这两行；否则删除。
        wp_clear_scheduled_hook( '{slug}_cron_event' );
        flush_rewrite_rules();
    }}
}}
"""

UNINSTALL = """<?php
/**
 * Uninstall cleanup
 *
 * @package {namespace}
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {{
    exit;
}}

// 单站点
delete_option( '{slug}_version' );
delete_option( '{slug}_option' );

// 多站点循环（按需启用）
// $sites = get_sites( array( 'fields' => 'ids' ) );
// foreach ( $sites as $site_id ) {{
//     switch_to_blog( $site_id );
//     delete_option( '{slug}_version' );
//     delete_option( '{slug}_option' );
//     restore_current_blog();
// }}
"""

SETTINGS_CLASS = """<?php
/**
 * Settings page (Settings API)
 *
 * @package {namespace}\\Admin
 */

namespace {namespace}\\Admin;

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class SettingsPage {{

    public static function init(): void {{
        add_action( 'admin_menu', array( self::class, 'add_menu' ) );
        add_action( 'admin_init', array( self::class, 'register' ) );
    }}

    public static function add_menu(): void {{
        add_options_page( __( '{name_lit}', '{slug}' ), __( '{name_lit}', '{slug}' ), 'manage_options', '{slug}', array( self::class, 'render' ) );
    }}

    public static function register(): void {{
        register_setting( '{slug}_group', '{slug}_option', array(
            'type'              => 'array',
            'default'           => array(),
            'sanitize_callback' => array( self::class, 'sanitize' ),
        ) );
        add_settings_section( '{slug}_main', __( '设置', '{slug}' ), '__return_false', '{slug}' );
        add_settings_field( '{slug}_api_key', __( 'API Key', '{slug}' ), array( self::class, 'field_api_key' ), '{slug}', '{slug}_main' );
    }}

    /**
     * 净化设置值：只保留已知键，逐值净化。
     *
     * @param mixed $input 提交的原始值（可能是数组，也可能是标量）。
     * @return array
     */
    public static function sanitize( $input ): array {{
        if ( ! is_array( $input ) ) {{
            return array();
        }}
        return array(
            'api_key' => isset( $input['api_key'] ) ? sanitize_text_field( $input['api_key'] ) : '',
        );
    }}

    public static function field_api_key(): void {{
        $option = get_option( '{slug}_option', array() );
        $value  = is_array( $option ) && isset( $option['api_key'] ) ? $option['api_key'] : '';
        printf(
            '<input type="password" class="regular-text" name="%1$s[api_key]" value="%2$s" />',
            esc_attr( '{slug}_option' ),
            esc_attr( $value )
        );
    }}

    public static function render(): void {{
        if ( ! current_user_can( 'manage_options' ) ) {{
            return;
        }}
        ?>
        <div class="wrap">
            <h1><?php echo esc_html( get_admin_page_title() ); ?></h1>
            <form method="post" action="options.php">
                <?php settings_fields( '{slug}_group' ); ?>
                <?php do_settings_sections( '{slug}' ); ?>
                <?php submit_button(); ?>
            </form>
        </div>
        <?php
    }}
}}
"""

REST_CLASS = """<?php
/**
 * REST routes
 *
 * @package {namespace}\\Api
 */

namespace {namespace}\\Api;

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class RestRoutes {{

    public static function init(): void {{
        add_action( 'rest_api_init', array( self::class, 'register_routes' ) );
    }}

    public static function register_routes(): void {{
        register_rest_route( '{slug}/v1', '/items', array(
            array(
                'methods'             => 'GET',
                'callback'            => array( self::class, 'get_items' ),
                // 默认要求登录并具备 read 能力。
                // 若接口确实返回任何人都可见的公开数据，可改用 WordPress 的公开权限回调常量；
                // 但切勿用它保护敏感数据。
                'permission_callback' => array( self::class, 'can_read_items' ),
                'args'                => array(
                    'per_page' => array(
                        'type'              => 'integer',
                        'default'           => 10,
                        'sanitize_callback' => 'absint',
                        'validate_callback' => static fn ( $v ): bool => $v > 0 && $v <= 100,
                    ),
                ),
            ),
        ) );
    }}

    public static function can_read_items(): bool {{
        return current_user_can( 'read' );
    }}

    public static function get_items( \\WP_REST_Request $request ): \\WP_REST_Response {{
        return rest_ensure_response( array() );
    }}
}}
"""

AI_CLASS = """<?php
/**
 * AI features: Abilities API + AI Client（WP 7.0+，带特性探测）
 *
 * @package {namespace}\\Ai
 */

namespace {namespace}\\Ai;

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class AiFeatures {{

    public static function init(): void {{
        // Abilities API 自 WP 6.9 引入；AI Client 自 WP 7.0 引入，故分开探测。
        if ( ! function_exists( 'wp_register_ability' ) ) {{
            return;
        }}
        // 分类必须先于 ability 注册（否则 wp_register_ability() 会 _doing_it_wrong 并返回 null）。
        add_action( 'wp_abilities_api_categories_init', array( self::class, 'register_category' ) );
        add_action( 'wp_abilities_api_init', array( self::class, 'register_ability' ) );
    }}

    public static function register_category(): void {{
        if ( ! function_exists( 'wp_register_ability_category' ) ) {{
            return;
        }}
        wp_register_ability_category( '{slug}', array(
            'label'       => __( '{name_lit}', '{slug}' ),
            'description' => __( 'Abilities provided by {name_lit}.', '{slug}' ),
        ) );
    }}

    public static function register_ability(): void {{
        if ( ! function_exists( 'wp_register_ability' ) ) {{
            return;
        }}
        wp_register_ability( '{slug}/summarize-post', array(
            'label'               => __( 'Summarize post', '{slug}' ),
            'description'         => __( 'Generates a short summary of the given post content.', '{slug}' ),
            'category'            => '{slug}',
            'input_schema'        => array(
                'type'        => 'string',
                'description' => __( 'The post content to summarize.', '{slug}' ),
                'minLength'   => 1,
                'required'    => true,
            ),
            'output_schema'       => array(
                'type' => 'string',
            ),
            'execute_callback'    => array( self::class, 'summarize' ),
            'permission_callback' => static function (): bool {{
                return current_user_can( 'edit_posts' );
            }},
            // public 只表示"可被发现"，不代表"可执行"；执行仍走 permission_callback。
            'meta'                => array(
                'annotations' => array(
                    // 注意：readonly=true 会让官方 REST 控制器强制要求 GET 方法，
                    // 而 GET 的 input 走 URL 查询参数——长正文会被服务器截断。
                    // 摘要生成既非只读语义也非幂等，故这里不标 readonly，
                    // 让官方回落到 POST（input 放 JSON body）。
                    'readonly'    => false,
                    'destructive' => false,
                    'idempotent'  => false,
                ),
                'public'      => false,
            ),
        ) );
    }}

    /**
     * 生成摘要。
     *
     * @param string $input 待摘要的正文。
     * @return string|\\WP_Error
     */
    public static function summarize( string $input ) {{
        // AI Client 需要 WP 7.0+；旧站优雅降级，不产生 Fatal。
        if ( ! function_exists( 'wp_ai_client_prompt' ) ) {{
            return new \\WP_Error(
                'wp_ai_client_unavailable',
                __( '当前站点未启用 WordPress AI Client。', '{slug}' )
            );
        }}

        // generate_text() 返回 string|WP_Error。
        $text = wp_ai_client_prompt( $input )
            ->using_temperature( 0.3 )
            ->generate_text();

        if ( is_wp_error( $text ) ) {{
            return $text;
        }}

        return wp_kses_post( $text );
    }}
}}
"""

BLOCK_JSON = """{{
    "$schema": "https://schemas.wp.org/trunk/block.json",
    "apiVersion": 3,
    "name": "{slug}/example-block",
    "version": "1.0.0",
    "title": "Example Block",
    "category": "widgets",
    "icon": "smiley",
    "description": "An example block.",
    "textdomain": "{slug}",
    "supports": {{ "html": false }},
    "attributes": {{ "message": {{ "type": "string", "default": "" }} }},
    "example": {{ "attributes": {{ "message": "Hello" }} }},
    "editorScript": "file:./index.js",
    "style": "file:./style-index.css"
}}
"""

BLOCK_PHP = """<?php
/**
 * Block registration
 *
 * @package {namespace}\\Blocks
 */

namespace {namespace}\\Blocks;

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

class ExampleBlock {{

    public static function init(): void {{
        // register_block_type() 必须在 init 阶段执行。
        add_action( 'init', array( self::class, 'register' ) );
    }}

    public static function register(): void {{
        register_block_type( {const_prefix}_DIR . 'blocks/example-block' );
    }}
}}
"""

README_TXT = """=== {name} ===
Contributors: {author_slug}
Tags: custom
Requires at least: 7.0
Tested up to: 7.1
Requires PHP: 8.1
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

{description}

== Description ==

TODO: 详细说明。

== Installation ==

1. 上传插件到 `wp-content/plugins/` 或在后台插件页搜索
2. 激活

== Changelog ==

= 1.0.0 =
* 首次发布

<!--
说明：
- `Requires at least` / `Requires PHP` 以**插件主 PHP 文件的头部**为准
  （自 WP 5.8 起 readme.txt 里的这两个字段不再被核心解析，仅作人工参考）。
- `Tested up to` 只填主版本号（如 7.1，不要写 7.1.3）。
- `Stable tag` 填插件自身的版本号，不是 WP 版本号。
-->
"""


def slugify(text: str, explicit: str | None = None) -> str:
    """生成插件目录名 / Text Domain。

    优先使用 --slug 显式值；否则从插件名提取 ASCII 部分。
    纯非 ASCII 名称（如纯中文名）会退化为同一 slug 导致目录冲突，
    此时用名称哈希生成稳定且唯一的 slug。
    """
    source = explicit if explicit else text
    s = re.sub(r"[^a-zA-Z0-9]+", "-", source.lower()).strip("-")
    if not s:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        s = f"my-plugin-{digest}"
    return s


def to_namespace(slug: str) -> str:
    """从 slug 生成 PHP 命名空间。

    PHP 命名空间每一段都不能以数字开头（namespace 2026Tools 是语法错误），
    因此以数字开头的段加 "Plugin" 前缀（如 "2026-tools" -> Plugin2026Tools）。
    """
    parts = [p.capitalize() for p in slug.split("-") if p]
    parts = [("Plugin" + p) if p[0].isdigit() else p for p in parts]
    return "".join(parts) or "MyPlugin"


def to_const_prefix(slug: str) -> str:
    """从 slug 生成 PHP 常量前缀。

    PHP 标识符不能以数字开头（2026_TOOLS_VERSION 是语法错误），
    因此数字开头时加 PLUGIN_ 前缀。
    """
    cp = re.sub(r"[^A-Z0-9]", "_", slug.upper())
    if cp and cp[0].isdigit():
        cp = "PLUGIN_" + cp
    return cp


def sanitize_header_value(text: str) -> str:
    """消毒将写入 PHP 文件头注释 / readme.txt 的自由文本。

    去除块注释闭合序列 "*/"（否则可提前闭合注释、注入 PHP 代码）、
    换行（否则会截断 WordPress 插件头部字段）及其余控制字符。
    """
    text = text.replace("*/", "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def to_php_single_quoted(text: str) -> str:
    """将自由文本转为可安全嵌入 PHP 单引号字符串字面量的形式。

    先做头部消毒，再转义反斜杠与单引号（'Bob's Plugin' 不转义会是语法错误）。
    """
    text = sanitize_header_value(text)
    return text.replace("\\", "\\\\").replace("'", "\\'")


def write(path: str, content: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as exc:
        # 权限不足、路径被占用等 I/O 失败：给出可读提示而非 Python 栈回溯
        print(f"错误: 写入文件失败 {path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description="WordPress 插件脚手架")
    ap.add_argument("--name", required=True, help='插件显示名，如 "My Plugin"')
    ap.add_argument("--path", default=".", help="输出父目录（默认当前目录）")
    ap.add_argument("--slug", default=None, help="显式指定目录名/Text Domain（推荐中文名时使用）")
    ap.add_argument("--author", default="Your Name")
    ap.add_argument("--author-uri", default="https://example.com")
    ap.add_argument("--description", default="TODO: 一句话描述插件功能。")
    ap.add_argument("--with-settings", action="store_true")
    ap.add_argument("--with-rest", action="store_true")
    ap.add_argument("--with-blocks", action="store_true")
    ap.add_argument("--with-ai", action="store_true")
    args = ap.parse_args()

    slug = slugify(args.name, args.slug)
    ns = to_namespace(slug)
    cp = to_const_prefix(slug)
    plugin_uri = f"https://example.com/{slug}"

    if os.path.exists(args.path) and not os.path.isdir(args.path):
        print(f"错误: 输出路径不是目录: {args.path}", file=sys.stderr)
        return 2

    base = os.path.join(args.path, slug)
    if os.path.exists(base):
        print(f"错误: 目标已存在 {base}", file=sys.stderr)
        print("  提示: 用 --slug 指定不同的目录名", file=sys.stderr)
        return 2

    ctx = dict(name=sanitize_header_value(args.name),
               name_lit=to_php_single_quoted(args.name),
               slug=slug, namespace=ns, const_prefix=cp,
               author=sanitize_header_value(args.author),
               author_uri=sanitize_header_value(args.author_uri),
               description=sanitize_header_value(args.description),
               plugin_uri=plugin_uri,
               author_slug=slugify(args.author) or "your-wp-username")

    write(os.path.join(base, f"{slug}.php"), HEADER.format(**ctx))
    write(os.path.join(base, "src", "autoload.php"), AUTOLOAD.format(**ctx))
    # 写入时保留 {submodule_calls} 占位符字面量（传 hooks="{hooks}" 是同一个技巧）：
    # 若在此处直接替换成空串，后续就找不到占位符，子模块调用会静默丢失。
    write(os.path.join(base, "src", "Plugin.php"),
          PLUGIN_CLASS.format(submodule_calls="{submodule_calls}", **ctx))
    write(os.path.join(base, "src", "Activator.php"), ACTIVATOR.format(**ctx))
    write(os.path.join(base, "src", "Deactivator.php"), DEACTIVATOR.format(**ctx))
    write(os.path.join(base, "uninstall.php"), UNINSTALL.format(**ctx))
    write(os.path.join(base, "readme.txt"), README_TXT.format(**ctx))
    try:
        os.makedirs(os.path.join(base, "languages"), exist_ok=True)
    except OSError as exc:
        print(f"错误: 创建 languages 目录失败: {exc}", file=sys.stderr)
        return 1

    # 子模块引导。
    #
    # 关键：这些 init 方法必须**直接调用**，不能在 plugins_loaded 回调内部
    # 再 add_action( 'plugins_loaded', ... )。
    # 原因：WordPress 的 WP_Hook 在执行某个优先级的回调时 foreach 遍历的是
    # 该优先级的回调快照；同优先级新注册的回调在本次 do_action 中不会执行。
    # 于是子模块的 init 永远不会被调用——插件能激活，却什么都不做（静默致命）。
    submodule_calls = []
    if args.with_settings:
        write(os.path.join(base, "src", "Admin", "SettingsPage.php"), SETTINGS_CLASS.format(**ctx))
        submodule_calls.append("        Admin\\SettingsPage::init();")
    if args.with_rest:
        write(os.path.join(base, "src", "Api", "RestRoutes.php"), REST_CLASS.format(**ctx))
        submodule_calls.append("        Api\\RestRoutes::init();")
    if args.with_ai:
        write(os.path.join(base, "src", "Ai", "AiFeatures.php"), AI_CLASS.format(**ctx))
        submodule_calls.append("        Ai\\AiFeatures::init();")
    if args.with_blocks:
        write(os.path.join(base, "src", "Blocks", "ExampleBlock.php"), BLOCK_PHP.format(**ctx))
        write(os.path.join(base, "blocks", "example-block", "block.json"), BLOCK_JSON.format(**ctx))
        submodule_calls.append("        Blocks\\ExampleBlock::init();")

    plugin_class_path = os.path.join(base, "src", "Plugin.php")
    with open(plugin_class_path, "r", encoding="utf-8") as fh:
        pc = fh.read()
    pc = pc.replace("{submodule_calls}", "\n".join(submodule_calls))
    write(plugin_class_path, pc)

    print(f"已生成插件骨架: {os.path.abspath(base)}")
    print(f"  slug={slug}  namespace={ns}  常量前缀={cp}_*")
    print("  下一步: 用 scripts/wp_security_scan.py 扫描；补全 readme.txt；跑 Plugin Check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
