# Gutenberg 与前端资源（gutenberg-and-frontend）

## 1. 块开发（block.json 优先）

- 块用 `block.json` 声明（`apiVersion: 3`，对应 **WP 6.3+**；apiVersion 2 对应 5.6，1 为初始版），`register_block_type( __DIR__ . '/build/blocks/my-block' )` 或 `register_block_type_from_metadata`
- apiVersion 3 要求块能在 iframe 编辑器内工作；**Gutenberg 23.6 与 WordPress 7.1 起无论 apiVersion 一律使用 iframe 编辑器**
- 属性/`supports`/`example`/`viewScript` 都放 block.json，PHP 端只做服务端渲染回调
- 动态块：`render_callback` 返回字符串，内部照常 escape；`$attributes` 已按 block.json 校验
- **弃用处理**：改属性结构必须写 `deprecated` 数组（旧 content 的 `save` 标记 + migrate），否则编辑器对存量内容报 "Invalid block"
- 工具链默认 `@wordpress/scripts`（`wp-scripts build/start`），除非项目已有 webpack/Vite 且有明确理由

## 2. 资源入队规范

```php
add_action( 'admin_enqueue_scripts', function ( string $hook ): void {
    if ( $hook !== 'settings_page_my-plugin' ) { return; }   // 只在目标屏幕
    wp_enqueue_script( 'my-plugin-admin', MY_PLUGIN_URL . 'assets/admin.js', array( 'jquery' ), MY_PLUGIN_VERSION, true );
    wp_enqueue_style( 'my-plugin-admin', MY_PLUGIN_URL . 'assets/admin.css', array(), MY_PLUGIN_VERSION );
    wp_add_inline_script(
        'my-plugin-admin',
        'window.MyPluginData = ' . wp_json_encode(
            array(
                'ajaxUrl' => admin_url( 'admin-ajax.php' ),
                'nonce'   => wp_create_nonce( 'my_plugin_action' ),
            )
        ) . ';',
        'before'
    );
} );
```

- 传数据给 JS 用 `wp_add_inline_script` + `wp_json_encode`（官方推荐）；`wp_localize_script` 只用于本地化字符串，且它会把标量值强转字符串、丢布尔/数字类型
- 版本参数用插件版本常量（开发期可用 `filemtime( 路径 )` 破缓存）。**注意没有 `wp_unique_version()` 这个函数**——它不存在于 WordPress 核心，写了会 Fatal
- 前端脚本别在管理端重复入队；依赖数组写全（`wp-i18n`、`wp-element` 等）
- CSS 加插件前缀作用域，避免污染主题/其他插件

## 3. 经典编辑器兼容（很多国内站点仍在用）

- 探测：`use_block_editor_for_post( $post )` 是**函数**（`int|WP_Post $post` → `bool`，WP 5.0 引入，6.1 从 wp-admin 移到 wp-includes），返回 false → 走 classic 路径；它同时也是同名 filter（`apply_filters( 'use_block_editor_for_post', $use_block_editor, $post )`）。注意它内部还依赖 `use_block_editor_for_post_type()`，且在 `?meta-box-loader` 场景会强制返回 false
- metabox：`add_meta_box()` + save 时 `current_user_can( 'edit_post', $post_id )` + nonce 校验 + `wp_slash` 处理
- 不要假设 tinyMCE 存在；JS 操作编辑器前 `typeof tinyMCE !== 'undefined'` 探测

## 4. Interactivity API（WP 6.5+，块前端交互首选）

- **必须先用 `data-wp-interactive` 声明交互区与命名空间**，该区及其子元素才会被激活；命名空间对应 JS 侧 `store( 'myPlugin', {...} )` 的第一个参数
- HTML 上用 `data-wp-on--<event>`（如 `data-wp-on--click="actions.toggle"`）绑事件、`data-wp-bind--<attr>`（如 `data-wp-bind--hidden="!context.isOpen"`）绑属性、`data-wp-context` 提供局部状态
- 同一事件绑多个回调用**三个连字符**：`data-wp-on--click---counter="actions.countClick"`（注意这会被当作事件名 `click---counter`，不是 `click` + id）
- store 用 `@wordpress/interactivity` 的 `store()`；作用域内用 `getContext()` / `getElement()` 取上下文与 DOM
- 服务端可直接渲染初始状态（SSR）：`data-wp-context` 的值必须是**字符串化 JSON**，服务端推荐用 `wp_interactivity_data_wp_context( $ctx )` 输出
- block.json 需加 `"supports": { "interactivity": true }`，并用 `viewScriptModule` 引入 Script Module（构建需加 `--experimental-modules`）
- 事件回调默认异步；要同步访问 `event.preventDefault()` 等需用 `withSyncEvent()` 包装
- 适合：点赞、筛选、弹层、表单步骤；复杂状态机仍可用框架

## 5. 可达性底线

- 每个交互控件可键盘到达；图标按钮加 `aria-label` / 屏幕阅读器文本
- 不用颜色单独传达状态（配图标/文字）；表单有关联 `<label>`
- 生成 UI 必须考虑 empty / loading / success / error 四态
