# Hooks 与核心 API（hooks-and-core-apis）

## 1. Hooks API

```php
add_action( 'init', 'my_func', 10, 2 );            // 动作：在时机点执行
add_filter( 'the_content', 'my_filter', 20 );      // 过滤器：必须 return 值
remove_action( 'init', 'other_func', 10 );         // 移除需同 callback 同优先级
do_action( 'my_plugin_event', $arg );              // 暴露自己的扩展点
```

- 类方法回调：`array( $this, 'method' )` 或 `array( MyClass::class, 'static_method' )`
- 过滤器**永远 return**（哪怕原样返回）；动作不要 return 业务值
- 移除别人加的 hook 需在对方 `add_action` 之后执行（`plugins_loaded` 或更高优先级），且优先级一致
- 条件挂载：仅需在后台运行时用 `is_admin()` 包裹 `add_action( 'admin_menu', ... )`

## 2. 常用核心 API 速查

| 需求 | API |
|---|---|
| 存/取配置 | Options API：`get_option` / `update_option` / `add_option` / `delete_option`；批量用 `add_settings_*` |
| 设置页 | Settings API：`register_setting`（带 `sanitize_callback`、`type`、`show_in_rest`、`label`、`description`）+ `add_settings_section` / `add_settings_field`。注意 `register_setting()` **没有** `permission_callback` 参数，权限靠 Settings API 的 option group 机制 |
| 远程请求 | HTTP API：`wp_remote_get/post`（设 `timeout`、检查 `is_wp_error`、`wp_remote_retrieve_response_code/body`） |
| 文章附加数据 | Metadata API：`get_post_meta` / `update_post_meta` / `register_meta`（带 `sanitize_callback`、`show_in_rest`）。注意权限回调的键名是 **`auth_callback`**（不是 `permission_callback`）；不传时默认落到 `is_protected_meta()` 的判定，受保护 meta 自动 `__return_false` |
| 自定义文章类型 | `register_post_type`（激活时 `flush_rewrite_rules`）。**保留名不可占用**：`post`/`page`/`attachment`/`revision`/`nav_menu_item`/`custom_css`/`customize_changeset`/`oembed_cache`/`user_request`/`wp_block`/`wp_global_styles`/`wp_navigation`/`wp_template`/`wp_template_part`，以及会与核心冲突的 `action`/`author`/`order`/`theme`。另需前缀或自定义 `query_var` 避免撞核心查询变量 |
| 分类法 | `register_taxonomy` |
| 定时任务 | WP-Cron：`wp_schedule_event` / `wp_next_scheduled` / `wp_clear_scheduled_hook`；低频用 `wp_schedule_single_event`；高并发站提醒用户改系统 cron |
| 短代码 | `add_shortcode`；回调 **return 字符串**不 echo；属性用 `shortcode_atts` 合并默认值 |
| 后台菜单 | `add_menu_page` / `add_options_page` 的**第 3** 个参数是 capability（如 `manage_options`）；`add_submenu_page` 的 capability 在**第 4** 位（顺序是 `$parent_slug, $page_title, $menu_title, $capability, $menu_slug, $callback`）——别把三个函数的参数位置搞混 |
| Ajax | `wp_ajax_{action}`（登录用户）+ `wp_ajax_nopriv_{action}`（未登录，慎用）；必须 `check_ajax_referer` + `current_user_can`，`wp_send_json_success/error` 收尾 |
| REST | `register_rest_route`：`permission_callback` **自 WP 5.5 起必填**（缺失会触发 `_doing_it_wrong()`，但不会阻止路由注册；公开端点写 `__return_true`）；`args` 声明 schema；`rest_ensure_response` 返回。必须在 `rest_api_init` 及其之后调用（早于 5.1 会 `_doing_it_wrong`） |
| 入队资源 | `wp_enqueue_script/style`（依赖数组、版本号用插件常量或 `filemtime()` 破缓存、仅在实际页面入队）。**没有 `wp_unique_version()` 这个核心函数**，别写 |
| 数据库 | `$wpdb->prepare` 拼接；自定义表用 `dbDelta` 建表。**真正的硬性要求是"每个字段/索引单独一行、字段名在行首"**（`dbDelta` 按 `\n` 切行解析）；`PRIMARY KEY` 与 `KEY` 之间官方正则是 `\s+`，**一个空格即可**，"必须两个空格"是流传很广的误解 |

## 3. Settings API 完整模式

```php
add_action( 'admin_init', function (): void {
    register_setting( 'my_plugin_group', 'my_plugin_option', array(
        'type'              => 'array',
        'default'           => array(),
        'sanitize_callback' => 'my_plugin_sanitize_option',
        'show_in_rest'      => false,
    ) );
    add_settings_section( 'my_plugin_main', '主要设置', '__return_false', 'my-plugin' );
    add_settings_field( 'api_key', 'API Key', 'my_plugin_render_api_key', 'my-plugin', 'my_plugin_main' );
} );
```

`sanitize_callback` 是输入侧净化的主战场：每个字段按类型处理（`sanitize_text_field`、`esc_url_raw`、`absint`、数组递归）。

## 4. 管理端表单三件套（缺一不可）

```php
// 1. 权限
if ( ! current_user_can( 'manage_options' ) ) { return; }
// 2. Nonce 生成
wp_nonce_field( 'my_plugin_save', 'my_plugin_nonce' );
// 3. 校验 + 净化 + 保存
check_admin_referer( 'my_plugin_save', 'my_plugin_nonce' );
$value = sanitize_text_field( wp_unslash( $_POST['my_field'] ?? '' ) );
```

`$_POST/$_GET/$_REQUEST/$_COOKIE` 读取一律先 `wp_unslash()` 再按类型 sanitize。WordPress 内部通过私有函数 `wp_magic_quotes()` 给 `$_GET`/`$_POST`/`$_COOKIE`/`$_SERVER` 统一加斜杠（并把 `$_REQUEST` 强制重建为 `$_GET + $_POST`），所以必须先 unslash。`wp_unslash()` 内部是 `stripslashes_deep()`，**只对字符串去斜杠**，数组递归处理，其他类型（int/bool/null）原样返回。

输出到 HTML 属性用 `esc_attr`、文本用 `esc_html`、URL 用 `esc_url`。

⚠️ **传数据给 JS 用 `wp_add_inline_script` + `wp_json_encode`，不要用 `wp_localize_script`**：官方明确说明后者"只应在真正要本地化字符串时使用"，且其内部会把所有标量值强转成字符串（`html_entity_decode( (string) $value )`），布尔/数字会丢失类型；自 WP 5.7 起传非数组还会触发 `_doing_it_wrong()`。

## 5. 版本兼容写法

- 新 API 探测：`function_exists()` / `class_exists()` / `version_compare( $wp_version, '7.0', '>=' )`，缺失时优雅降级
- 不要复制核心函数做 polyfill（会撞名），用前缀包裹自己的实现
- `wp_is_block_theme()` 探测块主题；编辑器相关功能探测 `use_block_editor_for_post()` / Classic Editor 插件存在性
