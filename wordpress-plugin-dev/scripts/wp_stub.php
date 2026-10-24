<?php
/**
 * wp-stub.php - 最小 WordPress 运行时存根。
 *
 * 用途：加载脚手架产出的插件并**真正执行**钩子回调，验证
 *  - PSR-4 autoloader 能否正确定位类文件
 *  - namespace 解析是否正确（Admin\ / Api\ / Ai\ / Blocks\ 子命名空间）
 *  - 常量是否在类使用前定义
 *  - 钩子是否按预期注册，且回调真的能跑通（不只是"登记成功"）
 *
 * 关键设计：add_action/add_filter 记录回调，do_action/fire 会真正调用它们。
 * 这暴露了一类被"只统计注册数"的存根掩盖的致命缺陷——
 * 在 plugins_loaded 回调内部再 add_action('plugins_loaded', ...) 时，
 * WordPress 的 WP_Hook 遍历的是该优先级的回调快照，同优先级新注册的回调
 * 在本次 do_action 中不会执行，于是子模块的 init() 永远不被调用。
 * 本存根用与 WP_Hook 一致的"快照 + 优先级"语义复现该行为。
 *
 * 仅覆盖生成代码实际调用到的 API；未实现的调用会抛错，便于暴露问题。
 *
 * 用法: php wp_stub.php <plugin_main_file>
 * 输出: 加载结果 + 已注册钩子清单 + 实际执行结果 + PASS/FAIL，失败时退出码 1。
 */

if ( ! defined( 'ABSPATH' ) ) {
    define( 'ABSPATH', __DIR__ . '/' );
}

$GLOBALS['wp_stub_hooks'] = array();
$GLOBALS['wp_stub_fired'] = array();
$GLOBALS['wp_stub_errors'] = array();
$GLOBALS['wp_stub_doing'] = array();

/**
 * 与 WP_Hook 一致的钩子存储：tag -> priority -> list of callbacks
 */
function wp_stub_register( $tag, $cb, $priority = 10 ) {
    $GLOBALS['wp_stub_hooks'][ $tag ][ $priority ][] = $cb;
    $GLOBALS['wp_stub_hooks'][ $tag ]['_order'] = array_keys(
        array_filter(
            $GLOBALS['wp_stub_hooks'][ $tag ],
            static function ( $k ) {
                return $k !== '_order';
            },
            ARRAY_FILTER_USE_KEY
        )
    );
    sort( $GLOBALS['wp_stub_hooks'][ $tag ]['_order'], SORT_NUMERIC );
}

function add_action( $tag, $cb, $priority = 10, $args = 1 ) {
    wp_stub_register( $tag, $cb, $priority );
    return true;
}
function add_filter( $tag, $cb, $priority = 10, $args = 1 ) {
    wp_stub_register( $tag, $cb, $priority );
    return true;
}
function remove_action( $tag, $cb, $priority = 10 ) { return true; }
function remove_filter( $tag, $cb, $priority = 10 ) { return true; }

/**
 * 执行钩子。语义对齐 WP_Hook::apply_filters()：
 * 按优先级升序遍历，每个优先级的回调列表在进入该优先级时取快照，
 * 因此"在回调执行中注册到同优先级的回调"不会在本次执行中跑。
 *
 * $args 为传给回调的参数（对齐 do_action( $tag, ...$args )）。
 * 官方有些动作带参数，例如 wp_connectors_init 会传入 WP_Connector_Registry 实例；
 * 不传参数会导致回调因实参不足而报错。
 */
function wp_stub_do_action( $tag, ...$args ) {
    if ( ! isset( $GLOBALS['wp_stub_hooks'][ $tag ] ) ) {
        return;
    }
    $priorities = $GLOBALS['wp_stub_hooks'][ $tag ]['_order'];
    $GLOBALS['wp_stub_doing'][ $tag ] = true;
    foreach ( $priorities as $p ) {
        // 快照语义：进入该优先级时固定回调列表
        $snapshot = $GLOBALS['wp_stub_hooks'][ $tag ][ $p ];
        foreach ( $snapshot as $cb ) {
            $GLOBALS['wp_stub_fired'][] = $tag;
            try {
                if ( is_array( $cb ) ) {
                    call_user_func_array( $cb, $args );
                } elseif ( $cb instanceof Closure ) {
                    call_user_func_array( $cb, $args );
                } elseif ( is_string( $cb ) && function_exists( $cb ) ) {
                    call_user_func_array( $cb, $args );
                }
            } catch ( Throwable $e ) {
                $GLOBALS['wp_stub_errors'][] = sprintf(
                    '钩子 %s 执行失败: %s',
                    $tag,
                    $e->getMessage()
                );
            }
        }
    }
    unset( $GLOBALS['wp_stub_doing'][ $tag ] );
}

function do_action( $tag, ...$args ) { wp_stub_do_action( $tag, ...$args ); }
function doing_action( $tag ) { return ! empty( $GLOBALS['wp_stub_doing'][ $tag ] ); }
function did_action( $tag ) { return count( array_keys( $GLOBALS['wp_stub_fired'], $tag, true ) ); }

function register_activation_hook( $file, $cb ) { wp_stub_register( 'activate', $cb, 0 ); }
function register_deactivation_hook( $file, $cb ) { wp_stub_register( 'deactivate', $cb, 0 ); }
function register_uninstall_hook( $file, $cb ) { return true; }
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
// 官方签名: wp_supports_ai(): bool —— 零参数，无 feature 参数。
// 受 WP_AI_SUPPORT 常量与 wp_supports_ai 过滤器控制。
function wp_supports_ai() { return true; }
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

// ---- Abilities API（WP 6.9+ / 7.0+）----
$GLOBALS['wp_stub_abilities'] = array();
$GLOBALS['wp_stub_ability_categories'] = array();

function wp_register_ability_category( $slug, $args = array() ) {
    if ( ! doing_action( 'wp_abilities_api_categories_init' ) ) {
        throw new RuntimeException( 'wp_register_ability_category 必须在 wp_abilities_api_categories_init 动作中调用' );
    }
    if ( ! preg_match( '/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $slug ) ) {
        throw new RuntimeException( 'ability 分类 slug 非法: ' . $slug );
    }
    $GLOBALS['wp_stub_ability_categories'][ $slug ] = $args;
    return null;
}
function wp_has_ability_category( $slug ) { return isset( $GLOBALS['wp_stub_ability_categories'][ $slug ] ); }
function wp_get_ability_categories() { return $GLOBALS['wp_stub_ability_categories']; }

// ---- Connectors API（WP 7.0+）----
// 官方: WP_Connector_Registry::register( string $id, array $args )
//   ID 正则 /^[a-z0-9_-]+$/；重复 ID -> _doing_it_wrong + 返回 null；
//   type 为 'ai_provider' 且 wp_supports_ai() 为 false -> 直接返回 null（无告警）。
//   authentication.method 仅接受 api_key / application_password / none。
$GLOBALS['wp_stub_connectors'] = array();

class WP_Connector_Registry {
    public static function get_instance() { return new self(); }

    public function is_registered( $id ) { return isset( $GLOBALS['wp_stub_connectors'][ $id ] ); }

    public function register( $id, $args = array() ) {
        if ( ! preg_match( '/^[a-z0-9_-]+$/', $id ) ) {
            throw new RuntimeException( '连接器 ID 非法（只允许小写字母数字、连字符、下划线）: ' . $id );
        }
        if ( $this->is_registered( $id ) ) {
            throw new RuntimeException( '连接器 ID 重复注册: ' . $id );
        }
        if ( empty( $args['name'] ) || ! is_string( $args['name'] ) ) {
            throw new RuntimeException( '连接器缺少必填参数 name: ' . $id );
        }
        if ( empty( $args['type'] ) || ! is_string( $args['type'] ) ) {
            throw new RuntimeException( '连接器缺少必填参数 type: ' . $id );
        }
        if ( ! isset( $args['authentication'] ) || ! is_array( $args['authentication'] ) ) {
            throw new RuntimeException( '连接器缺少必填参数 authentication: ' . $id );
        }
        $method = $args['authentication']['method'] ?? '';
        if ( ! in_array( $method, array( 'api_key', 'application_password', 'none' ), true ) ) {
            throw new RuntimeException(
                '连接器 authentication.method 必须是 api_key / application_password / none: ' . $id );
        }
        // 官方：AI provider 连接器受 wp_supports_ai() 门控，为 false 时静默返回 null。
        if ( 'ai_provider' === $args['type'] && ! wp_supports_ai() ) {
            return null;
        }
        $connector = array(
            'name'           => $args['name'],
            'description'    => isset( $args['description'] ) && is_string( $args['description'] )
                                ? $args['description'] : '',
            'type'           => $args['type'],
            'authentication' => array( 'method' => $method ),
        );
        if ( ! empty( $args['logo_url'] ) && is_string( $args['logo_url'] ) ) {
            $connector['logo_url'] = $args['logo_url'];
        }
        if ( in_array( $method, array( 'api_key', 'application_password' ), true ) ) {
            if ( ! empty( $args['authentication']['credentials_url'] ) ) {
                $connector['authentication']['credentials_url'] = $args['authentication']['credentials_url'];
            }
            // 官方：省略 setting_name 时自动生成为 connectors_{type}_{id}_{method}
            // （连字符归一化为下划线）。
            $connector['authentication']['setting_name'] = isset( $args['authentication']['setting_name'] )
                ? $args['authentication']['setting_name']
                : str_replace( '-', '_', "connectors_{$connector['type']}_{$id}_{$method}" );
            foreach ( array( 'constant_name', 'env_var_name' ) as $opt ) {
                if ( isset( $args['authentication'][ $opt ] ) ) {
                    $connector['authentication'][ $opt ] = $args['authentication'][ $opt ];
                }
            }
        }
        $connector['plugin'] = array();
        if ( ! empty( $args['plugin'] ) && is_array( $args['plugin'] ) ) {
            if ( ! empty( $args['plugin']['file'] ) ) {
                $connector['plugin']['file'] = $args['plugin']['file'];
            }
            if ( isset( $args['plugin']['is_active'] ) ) {
                if ( ! is_callable( $args['plugin']['is_active'] ) ) {
                    throw new RuntimeException( '连接器 plugin.is_active 必须是可调用对象: ' . $id );
                }
                $connector['plugin']['is_active'] = $args['plugin']['is_active'];
            }
        }
        if ( ! isset( $connector['plugin']['is_active'] ) ) {
            $connector['plugin']['is_active'] = '__return_true';
        }
        $GLOBALS['wp_stub_connectors'][ $id ] = $connector;
        return $connector;
    }

    public function unregister( $id ) {
        if ( ! $this->is_registered( $id ) ) {
            throw new RuntimeException( '连接器未注册，无法 unregister: ' . $id );
        }
        $c = $GLOBALS['wp_stub_connectors'][ $id ];
        unset( $GLOBALS['wp_stub_connectors'][ $id ] );
        return $c;
    }

    public function get_registered( $id ) {
        return $GLOBALS['wp_stub_connectors'][ $id ] ?? null;
    }

    public function get_all_registered() { return $GLOBALS['wp_stub_connectors']; }
}

function wp_is_connector_registered( $id ) {
    return isset( $GLOBALS['wp_stub_connectors'][ $id ] );
}
function wp_get_connector( $id ) {
    return $GLOBALS['wp_stub_connectors'][ $id ] ?? null;
}
function wp_get_connectors() { return $GLOBALS['wp_stub_connectors']; }

function wp_register_ability( $name, $args = array() ) {
    if ( ! doing_action( 'wp_abilities_api_init' ) ) {
        throw new RuntimeException( 'wp_register_ability 必须在 wp_abilities_api_init 动作中调用' );
    }
    if ( ! preg_match( '/^[a-z0-9-]+\/[a-z0-9-]+$/', $name ) ) {
        throw new RuntimeException( 'ability 名称非法: ' . $name );
    }
    if ( isset( $args['category'] ) && ! wp_has_ability_category( $args['category'] ) ) {
        throw new RuntimeException( 'ability 分类未注册: ' . $args['category'] );
    }
    // 官方 WP_Abilities_Registry::register() 文档标注 Required 的参数：
    // label / description / category / execute_callback / permission_callback。
    // 注意 category 在官方实现里是 isset() 条件校验（缺失时由 WP_Ability 构造器
    // 抛 InvalidArgumentException），这里统一按必填处理，提前给出可读错误。
    foreach ( array( 'label', 'description', 'category',
                     'execute_callback', 'permission_callback' ) as $req ) {
        if ( empty( $args[ $req ] ) ) {
            throw new RuntimeException( 'ability 缺少必填参数: ' . $req );
        }
    }
    $GLOBALS['wp_stub_abilities'][ $name ] = $args;
    return null;
}
function wp_has_ability( $name ) { return isset( $GLOBALS['wp_stub_abilities'][ $name ] ); }
function wp_get_abilities( $args = array() ) { return $GLOBALS['wp_stub_abilities']; }

// ---- AI Client（WP 7.0+）----
// 真实 API 的结果对象方法为 toText() / getTokenUsage()（camelCase），
// 不是 get_text()——存根按真实签名实现，用于暴露错误的调用方式。
function wp_ai_client_prompt( $prompt = '' ) { return new WpStubAiPrompt( $prompt ); }
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
    public function using_model_preference( ...$models ) { return $this; }
    public function is_supported_for_text_generation() { return true; }
    public function generate_text() { return 'stub text'; }
    public function generate_text_result() { return new WpStubAiResult( 'stub text' ); }
}

class WpStubAiResult {
    private $text;
    public function __construct( $text ) { $this->text = $text; }
    // 真实 API 为 toText()（camelCase）
    public function toText() { return $this->text; }
    public function toTexts() { return array( $this->text ); }
    public function getTokenUsage() { return array(); }
    public function getProviderMetadata() { return array(); }
    public function getModelMetadata() { return array(); }
}

class WpStubAiClient {}

// ---- 执行冒烟测试 ----
$main = isset( $argv[1] ) ? $argv[1] : '';
if ( ! $main || ! is_file( $main ) ) {
    fwrite( STDERR, "用法: php wp_stub.php <plugin_main_file>\n" );
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
    // 无 Plugin 类的插件（如仅注册连接器/短代码的轻量插件）也要走生命周期，
    // 否则这些钩子永远不会被触发，存根就测不到它们。
    $has_plugin_class = false;
    if ( $ns ) {
        $class = $ns . '\\Plugin';
        if ( class_exists( $class ) ) {
            $has_plugin_class = true;
            // 走真实路径：让 plugins_loaded 钩子自己跑，验证子模块是否真的被引导
            wp_stub_do_action( 'plugins_loaded' );
            echo "[OK] plugins_loaded 已执行\n";
        } else {
            $errors[] = "autoloader 未找到类 {$class}";
        }
    }

    // 继续走后续生命周期钩子，验证子模块注册的钩子能被触发
    wp_stub_do_action( 'init' );
    // 官方：连接器注册表在 init 优先级 15 初始化，随后 do_action( 'wp_connectors_init', $registry )
    // 传入注册表实例——回调签名是 function ( WP_Connector_Registry $registry )。
    wp_stub_do_action( 'wp_connectors_init', WP_Connector_Registry::get_instance() );
    wp_stub_do_action( 'wp_abilities_api_categories_init' );
    wp_stub_do_action( 'wp_abilities_api_init' );
    wp_stub_do_action( 'admin_init' );
    wp_stub_do_action( 'admin_menu' );
    wp_stub_do_action( 'rest_api_init' );
    echo "[OK] 生命周期钩子已执行\n";
} catch ( Throwable $e ) {
    $errors[] = '未捕获异常: ' . $e->getMessage();
}

restore_error_handler();

$hooks = $GLOBALS['wp_stub_hooks'];
echo '钩子注册数: ' . count( $hooks ) . "\n";
foreach ( $hooks as $tag => $data ) {
    if ( '_order' === $tag ) {
        continue;
    }
    foreach ( $data as $p => $cbs ) {
        if ( '_order' === $p ) {
            continue;
        }
        foreach ( $cbs as $cb ) {
            $name = is_array( $cb ) ? ( is_string( $cb[0] ) ? $cb[0] : gettype( $cb[0] ) ) . '::' . $cb[1]
                : ( is_object( $cb ) ? 'Closure' : (string) $cb );
            echo "  - {$tag} [{$p}] => {$name}\n";
        }
    }
}

echo '实际触发的钩子: ' . implode( ', ', array_unique( $GLOBALS['wp_stub_fired'] ) ) . "\n";

if ( ! empty( $GLOBALS['wp_stub_abilities'] ) ) {
    echo '已注册 ability: ' . implode( ', ', array_keys( $GLOBALS['wp_stub_abilities'] ) ) . "\n";
}

if ( ! empty( $GLOBALS['wp_stub_connectors'] ) ) {
    echo '已注册连接器: ' . implode( ', ', array_keys( $GLOBALS['wp_stub_connectors'] ) ) . "\n";
}

// ---- 语义校验：子模块的 init 必须真的跑过 ----
//
// 致命缺陷模式：在 plugins_loaded 回调内部再 add_action( 'plugins_loaded', ... )。
// WordPress 的 WP_Hook 遍历的是该优先级的回调快照，同优先级新注册的回调
// 在本次 do_action 中不会执行 -> 子模块 init() 永远不被调用 -> 插件能激活，
// 但 REST 路由 / 设置页 / 块 / ability 全都不存在（静默致命，php -l 查不出）。
//
// 这里检测"注册了子模块 init 钩子，但对应下游钩子从未被注册/触发"的组合。
$submodule_init_tags = array(
    'rest_api_init',
    'admin_menu',
    'admin_init',
    'wp_abilities_api_init',
    'wp_abilities_api_categories_init',
);

$registered = array_keys( $hooks );
$triggered  = array_unique( $GLOBALS['wp_stub_fired'] );

// 情形 A：子模块 init 被注册到 plugins_loaded（快照陷阱），但下游钩子没注册
$init_registered = 0;
foreach ( $hooks['plugins_loaded'] ?? array() as $p => $cbs ) {
    if ( '_order' === $p ) {
        continue;
    }
    foreach ( $cbs as $cb ) {
        $name = is_array( $cb ) ? ( is_string( $cb[0] ) ? $cb[0] : '' ) : '';
        if ( false !== strpos( $name, '\\' ) && false === strpos( $name, '\\Plugin' ) ) {
            $init_registered++;
        }
    }
}

if ( $init_registered > 0 ) {
    $missing = array();
    foreach ( $submodule_init_tags as $t ) {
        if ( ! in_array( $t, $registered, true ) ) {
            $missing[] = $t;
        }
    }
    if ( $missing ) {
        $errors[] = sprintf(
            "检测到致命模式：子模块 init 被注册到 'plugins_loaded'（共 %d 个），"
            . "但其下游钩子 [%s] 从未被注册。\n"
            . "         WordPress 的 WP_Hook 遍历同优先级的回调快照，同优先级新注册的回调\n"
            . "         在本次 do_action 中不会执行 —— 子模块 init() 永远不会运行。\n"
            . "         正确做法：在 Plugin::init() 中**直接调用**子模块的 init() 方法，"
            . "而不是再次 add_action( 'plugins_loaded', ... )。",
            $init_registered,
            implode( ', ', $missing )
        );
    }
}

// 情形 B：子模块 init 已直接调用，但下游钩子一个都没注册（引导链路断了）
if ( $init_registered === 0 && count( $hooks ) >= 2 ) {
    $has_downstream = false;
    foreach ( $submodule_init_tags as $t ) {
        if ( in_array( $t, $registered, true ) ) {
            $has_downstream = true;
            break;
        }
    }
    if ( ! $has_downstream ) {
        $errors[] = "子模块引导链路断裂：注册了钩子但没有任何下游生命周期钩子"
            . "（rest_api_init / admin_menu / admin_init / wp_abilities_api_init）。";
    }
}

// 情形 C：ability 注册了但分类没注册（WP 会 _doing_it_wrong 并拒绝注册）
if ( ! empty( $GLOBALS['wp_stub_abilities'] ) ) {
    foreach ( $GLOBALS['wp_stub_abilities'] as $aname => $aargs ) {
        $cat = $aargs['category'] ?? '';
        if ( '' !== $cat && ! wp_has_ability_category( $cat ) ) {
            $errors[] = sprintf( 'ability "%s" 的分类 "%s" 未注册。', $aname, $cat );
        }
    }
}

foreach ( $GLOBALS['wp_stub_errors'] as $e ) {
    $errors[] = $e;
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
