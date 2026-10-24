# 插件基础规范（plugin-fundamentals）

## 1. 文件头（header）字段全集

主 PHP 文件顶部必须是 header 注释，**只有主文件带 header**。最小只写 `Plugin Name`，但发布级插件应写全：

```php
<?php
/**
 * Plugin Name:       My Plugin
 * Plugin URI:        https://example.com/my-plugin
 * Description:       一句话说明，<140 字符。
 * Version:           1.0.0
 * Requires at least: 7.0
 * Requires PHP:      8.1
 * Author:            Your Name
 * Author URI:        https://example.com
 * License:           GPL v2 or later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Update URI:        https://example.com/my-plugin/
 * Text Domain:       my-plugin
 * Domain Path:       /languages
 * Requires Plugins:  my-other-plugin
 */
```

字段要点：
- `Requires at least` / `Requires PHP`：WP 5.5+/5.1+ 起支持，缺失时旧版 WP 不拦截激活
- `Update URI`：第三方分发必填，防止被同名 wordpress.org 插件更新覆盖
- `Requires Plugins`：WP 6.5+ 支持，逗号分隔的 wordpress.org slug（不带路径）
- `Network: true`：仅多站点网络激活时使用
- **版本号陷阱**：WP 用 PHP `version_compare()` 比较版本，`1.02 > 1.1`。发新版前确认 `version_compare('new','old','>')` 为真

## 2. 目录结构（推荐）

```
my-plugin/
├── my-plugin.php            # 主文件：header + 常量 + 引导
├── uninstall.php            # 仅卸载时运行，清理数据（或用 register_uninstall_hook）
├── readme.txt               # wordpress.org 发布用
├── languages/               # .pot/.po/.mo
├── src/                     # PSR-4: MyPlugin\ => src/
│   ├── Admin/  Public/  Api/ ...
├── assets/                  # css/js/images（按 admin/public 分目录更佳）
└── vendor/                  # composer 依赖（发布时按指南处理）
```

主文件引导模式（参考实战插件 ai-provider-for-china 的写法）：

```php
if ( ! defined( 'ABSPATH' ) ) { exit; }

define( 'MY_PLUGIN_VERSION', '1.0.0' );
define( 'MY_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'MY_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

require_once MY_PLUGIN_DIR . 'src/autoload.php';   // PSR-4 spl_autoload_register

register_activation_hook( __FILE__, 'my_plugin_activate' );
register_deactivation_hook( __FILE__, 'my_plugin_deactivate' );

add_action( 'plugins_loaded', 'my_plugin_init' );
```

PSR-4 autoloader 模板：

```php
spl_autoload_register( function ( string $class ): void {
    $prefix = 'MyPlugin\\';
    if ( strpos( $class, $prefix ) !== 0 ) { return; }
    $file = MY_PLUGIN_DIR . 'src/' . str_replace( '\\', '/', substr( $class, strlen( $prefix ) ) ) . '.php';
    if ( file_exists( $file ) ) { require_once $file; }
} );
```

**namespace 声明位置陷阱**（致命错误，`php -l` 才能发现）：PHP 要求 `namespace X;` 必须是文件的**第一条语句**（只允许 `declare` 在前），注释除外。因此带命名空间的类文件里，ABSPATH 守卫必须写在 `namespace` **之后**：

```php
<?php
/**
 * @package MyPlugin\Admin
 */

namespace MyPlugin\Admin;

if ( ! defined( 'ABSPATH' ) ) { exit; }   // 守卫放这里，不是上面

class SettingsPage {}
```

守卫写在 namespace 之前会直接 Fatal error（"Namespace declaration statement has to be the very first statement"），插件一激活就白屏——肉眼审查极易漏掉，务必用 `php -l` 或本 skill 的 `scripts/check_php_syntax.py` 验证。

## 3. 生命周期钩子

- **activation**：建表、默认选项、`flush_rewrite_rules()`（CPT/重写规则在此刷新，且只在此）
- **deactivation**：清定时任务（`wp_clear_scheduled_hook`）、清临时缓存；**不删用户数据**
- **uninstall**（`uninstall.php` 或 `register_uninstall_hook`）：删选项、表、meta。多站点要循环 `get_sites()`。uninstall.php 中先 `if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) exit;`
- 检查依赖：激活时版本不足应 `deactivate_plugins()` + `wp_die()` 提示，不要静默失败

## 4. 加载顺序速查

`mu-plugins` → 按文件名的 `plugins`（激活的，字母序）→ `plugins_loaded` 之后才可用大部分 API。注意：
- 主题 `functions.php` 晚于插件加载；插件不要假设主题存在
- `init`：注册 CPT/taxonomy/shortcode 的标准时机；`admin_menu`/`wp_ajax_*` 各自钩子
- Connectors 注册表在 `init` 优先级 15 初始化，`wp_connectors_init` 触发；之后 `wp_get_connector()` 等公共函数可用

## 5. 多语言（i18n）要点

- 头部声明 `Text Domain`（等于插件 slug）+ `Domain Path: /languages`
- PHP：`__( 'Text', 'my-plugin' )`、`_e()`、`_n()`、`_x()`；JS：`@wordpress/i18n` 的 `__()`
- 字符串不带品牌名硬编码进句子（不同语言语序）；`load_plugin_textdomain` 在 WP 4.6+ 对 wordpress.org 托管插件已非必需（WP 自动加载），但自托管翻译仍可用
