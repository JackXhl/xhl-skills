# Gutenberg 与前端资源（gutenberg-and-frontend）

## 1. 块开发（block.json 优先）

- 块用 `block.json` 声明（`apiVersion: 3`），`register_block_type( __DIR__ . '/build/blocks/my-block' )` 或 `register_block_type_from_metadata`
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
    wp_localize_script( 'my-plugin-admin', 'MyPluginData', array( 'ajaxUrl' => admin_url( 'admin-ajax.php' ), 'nonce' => wp_create_nonce( 'my_plugin_action' ) ) );
} );
```

- 版本参数用插件版本（开发期可用 `filemtime` 或 `wp_unique_version` 破缓存）
- 前端脚本别在管理端重复入队；依赖数组写全（`wp-i18n`、`wp-element` 等）
- CSS 加插件前缀作用域，避免污染主题/其他插件

## 3. 经典编辑器兼容（很多国内站点仍在用）

- 探测：`use_block_editor_for_post( $post )` 为 false → 走 classic 路径
- metabox：`add_meta_box()` + save 时 `current_user_can( 'edit_post', $post_id )` + nonce 校验 + `wp_slash` 处理
- 不要假设 tinyMCE 存在；JS 操作编辑器前 `typeof tinyMCE !== 'undefined'` 探测

## 4. Interactivity API（WP 6.5+，块前端交互首选）

- HTML 上加 `data-wp-on--click`、`data-wp-bind--hidden` 等指令，store 用 `@wordpress/interactivity` 的 `store()`
- 服务端可直接渲染初始状态（SSR），无需为简单交互引入 React 水合
- 适合：点赞、筛选、弹层、表单步骤；复杂状态机仍可用框架

## 5. 可达性底线

- 每个交互控件可键盘到达；图标按钮加 `aria-label` / 屏幕阅读器文本
- 不用颜色单独传达状态（配图标/文字）；表单有关联 `<label>`
- 生成 UI 必须考虑 empty / loading / success / error 四态
