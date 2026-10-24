<?php
/**
 * wp-stub.php - 最小 WordPress 运行时存根。
 *
 * 用途：加载脚手架产出的插件并调用 init()，验证
 *  - PSR-4 autoloader 能否正确定位类文件
 *  - namespace 解析是否正确（Admin\ / Api\ / Ai\ / Blocks\ 子命名空间）
 *  - 常量是否在类使用前定义
 *  - 钩子是否按预期注册
 *
 * 仅覆盖生成代码实际调用到的 API；未实现的调用会抛错，便于暴露问题。
 *
 * 用法: php wp_stub.php <plugin_main_file>
 * 输出: 加载结果 + 已注册钩子清单 + PASS/FAIL，失败时退出码 1。
 * 用途: php -l 只能验证语法，本脚本验证运行时（autoloader 定位、
 *       namespace 解析、常量定义时机、钩子注册），二者互补。
 */

if ( ! defined( 'ABSPATH' ) ) {
    define( 'ABSPATH', __DIR__ . '/' );
}

$GLOBALS['wp_stub_hooks'] = array();

function add_action( $tag, $cb, $priority = 10, $args = 1 ) {
    $GLOBALS['wp_stub_hooks'][] = array( $tag, is_array( $cb ) ? ( is_string( $cb[0] ) ? $cb[0] : $cb[0] ) . '::' . $cb[1] : $cb, $priority );
    return true;
}
function add_filter( $tag, $cb, $priority = 10, $args = 1 ) { return add_action( $tag, $cb, $priority, $args ); }
function do_action( $tag ) {}
function register_activation_hook( $file, $cb ) { $GLOBALS['wp_stub_hooks'][] = array( 'activate', $cb, 0 ); }
function register_deactivation_hook( $file, $cb ) { $GLOBALS['wp_stub_hooks'][] = array( 'deactivate', $cb, 0 ); }
function register_uninstall_hook( $file, $cb ) {}
function load_plugin_textdomain( $domain, $abs = false, $path = '' ) { return true; }
function plugin_dir_path( $file ) { return rtrim( dirname( $file ), '/\\' ) . '/'; }
function plugin_dir_url( $file ) { return 'https://example.com/wp-content/plugins/' . basename( dirname( $file ) ) . '/'; }
function plugin_basename( $file ) { return basename( dirname( $file ) ) . '/' . basename( $file ); }
function wp_die( $msg = '', $title = '', $args = array() ) { throw new RuntimeException( 'wp_die: ' . $msg ); }
function deactivate_plugins( $p ) {}
function get_bloginfo( $k = '' ) { return '7.1.3'; }
function add_option( $k, $v = '' ) { return true; }
function get_option( $k, $d = false ) { return $d; }
function update_option( $k, $v ) { return true; }
function delete_option( $k ) { return true; }
function flush_rewrite_rules( $hard = true ) {}
function wp_clear_scheduled_hook( $hook, $args = array() ) {}
function wp_next_scheduled( $hook ) { return false; }
function current_user_can( $cap ) { return true; }
function esc_attr( $t ) { return htmlspecialchars( (string) $t, ENT_QUOTES ); }
function esc_html( $t ) { return htmlspecialchars( (string) $t, ENT_QUOTES ); }
function esc_url( $u ) { return $u; }
function esc_url_raw( $u ) { return $u; }
function esc_html__( $t, $d = null ) { return esc_html( $t ); }
function esc_attr__( $t, $d = null ) { return esc_attr( $t ); }
function __( $t, $d = null ) { return $t; }
function _e( $t, $d = null ) { echo $t; }
function _x( $t, $c, $d = null ) { return $t; }
function __return_false() { return false; }
function __return_true() { return true; }
function __return_empty_array() { return array(); }
function absint( $v ) { return abs( (int) $v ); }
function sanitize_text_field( $v ) { return trim( strip_tags( (string) $v ) ); }
function sanitize_textarea_field( $v ) { return trim( (string) $v ); }
function sanitize_key( $v ) { return strtolower( preg_replace( '/[^a-z0-9_\-]/', '', (string) $v ) ); }
function sanitize_email( $v ) { return filter_var( $v, FILTER_SANITIZE_EMAIL ); }
function sanitize_title( $v ) { return strtolower( trim( preg_replace( '/[^a-z0-9]+/', '-', (string) $v ), '-' ) ); }
function wp_kses_post( $t ) { return $t; }
function wp_kses( $t, $allowed ) { return $t; }
function wp_unslash( $v ) { return is_array( $v ) ? array_map( 'wp_unslash', $v ) : stripslashes( (string) $v ); }
function wp_send_json_success( $d = null ) {}
function wp_send_json_error( $d = null ) {}
function is_wp_error( $t ) { return $t instanceof WP_Error; }
function wp_remote_get( $url, $args = array() ) { return array(); }
function settings_fields( $group ) {}
function do_settings_sections( $page ) {}
function submit_button( $t = null ) {}
function get_admin_page_title() { return 'Title'; }
function add_options_page( $pt, $mt, $cap, $slug, $cb = null ) { return $slug; }
function add_menu_page( $pt, $mt, $cap, $slug, $cb = null ) { return $slug; }
function register_setting( $group, $name, $args = array() ) {}
function add_settings_section( $id, $title, $cb, $page ) {}
function add_settings_field( $id, $title, $cb, $page, $section ) {}
function register_rest_route( $ns, $route, $args = array() ) { return true; }
function rest_ensure_response( $r ) { return $r; }
function register_block_type( $path ) { return true; }
function wp_register_ability( $name, $args = array() ) { return true; }
function wp_supports_ai( $feature = null ) { return true; }
function wp_create_nonce( $action = -1 ) { return 'nonce'; }
function wp_nonce_field( $action = -1, $name = '_wpnonce' ) { return ''; }
function check_admin_referer( $action = -1, $name = '_wpnonce' ) { return 1; }
function check_ajax_referer( $action = -1, $name = false, $die = true ) { return 1; }
function wp_verify_nonce( $n, $a = -1 ) { return 1; }
function admin_url( $p = '' ) { return 'https://example.com/wp-admin/' . $p; }
function wp_enqueue_script() {}
function wp_enqueue_style() {}
function wp_localize_script() {}
function wp_slash( $v ) { return $v; }
function get_post_meta( $id, $k = '', $single = false ) { return $single ? '' : array(); }
function update_post_meta( $id, $k, $v ) { return true; }
function register_meta( $type, $k, $args = array() ) {}
function wp_ai_client_prompt( $prompt, $args = array() ) { return new WpStubAiPrompt( $prompt ); }
function wp_ai_client() { return new WpStubAiClient(); }

class WP_Error {
    public function __construct( $code = '', $msg = '' ) {}
    public function get_error_message() { return 'stub error'; }
}

class WP_REST_Response {
    public $data;
    public function __construct( $data = null ) { $this->data = $data; }
    public function get_data() { return $this->data; }
}

class WP_REST_Request {
    public $params = array();
    public function get_param( $k ) { return isset( $this->params[ $k ] ) ? $this->params[ $k ] : null; }
}

class WpStubAiPrompt {
    private $prompt;
    public function __construct( $prompt ) { $this->prompt = $prompt; }
    public function using_temperature( $t ) { return $this; }
    public function using_max_tokens( $n ) { return $this; }
    public function generate_text() { return 'stub text'; }
    public function generate_text_result() { return new WpStubAiResult( 'stub text' ); }
}

class WpStubAiResult {
    private $text;
    public function __construct( $text ) { $this->text = $text; }
    public function get_text() { return $this->text; }
    public function getTokenUsage() { return array(); }
}

class WpStubAiClient {}

// ---- 执行冒烟测试 ----
$main = isset( $argv[1] ) ? $argv[1] : '';
if ( ! $main || ! is_file( $main ) ) {
    fwrite( STDERR, "用法: php wp-stub.php <plugin_main_file>\n" );
    exit( 2 );
}

$errors = array();
set_error_handler( function ( $no, $str, $file, $line ) use ( &$errors ) {
    $errors[] = "PHP 错误: $str @ $file:$line";
    return true;
} );

try {
    require_once $main;
    echo "[OK] 主文件加载成功（常量与 autoloader 就位）\n";

    // 主文件是全局命名空间，Plugin 类在 src/ 下；
    // 从主文件的 hooks 注册行提取命名空间前缀（如 "Php81Compat\Plugin::class"）
    $ns = null;
    if ( preg_match( '/([A-Za-z0-9_]+(?:\\\\[A-Za-z0-9_]+)*)\\\\Plugin::class/', file_get_contents( $main ), $m ) ) {
        $ns = $m[1];
    }
    if ( $ns ) {
        $class = $ns . '\\Plugin';
        if ( class_exists( $class ) ) {
            call_user_func( array( $class, 'init' ) );
            echo "[OK] {$class}::init() 执行成功\n";
        } else {
            $errors[] = "autoloader 未找到类 {$class}";
        }
    }
} catch ( Throwable $e ) {
    $errors[] = '未捕获异常: ' . $e->getMessage();
}

restore_error_handler();

$hooks = $GLOBALS['wp_stub_hooks'];
echo '钩子注册数: ' . count( $hooks ) . "\n";
foreach ( $hooks as $h ) {
    echo '  - ' . $h[0] . ' => ' . ( is_string( $h[1] ) ? $h[1] : gettype( $h[1] ) ) . "\n";
}

if ( $errors ) {
    echo "\n[FAIL] " . count( $errors ) . " 个问题:\n";
    foreach ( $errors as $e ) {
        echo "  - $e\n";
    }
    exit( 1 );
}
echo "\n[PASS] 运行时冒烟测试通过\n";
exit( 0 );
