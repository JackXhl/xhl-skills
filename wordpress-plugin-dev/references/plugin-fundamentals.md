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
- **头部值卫生**：从别处复制来的插件名/描述可能带入 `*/`（提前闭合注释、甚至注入代码）、换行（截断 header 字段）、单引号（若该值进入 PHP 字符串字面量会语法错误）；以数字开头的名字做 namespace/常量前缀时须加前缀（`2026 Tools` → `Plugin2026Tools` / `PLUGIN_2026_TOOLS_*`）
- **非 ASCII（中文）插件名**：WordPress 的 slug / Text Domain 需为小写 ASCII。中文名提取不到 ASCII 片段时若一律回退到固定值会导致**多个插件生成到同一目录**（第二个直接失败）；正确做法是用名称哈希生成稳定且唯一的 slug，或用 `--slug` 显式指定
- **`Update URI` 的副作用**：设置 `Update URI` 后，WordPress 将不再从 wordpress.org 更新该插件，只认自建源。发布到 wordpress.org 的插件**不应**设置此字段（第三方分发的才需要）

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

**钩子快照陷阱（致命且静默）**：`WP_Hook::apply_filters()` 遍历的是**当前优先级回调的快照**。因此在某个回调内部再 `add_action()` 到**同一个钩子、同一优先级**，新注册的回调在本次 `do_action` 中**不会执行**——而该钩子通常只触发一次，于是子模块的 `init()` 永远不会被调用。

典型症状：插件能正常激活、没有报错，但 REST 路由不注册、设置页不出现、块不显示、ability 注册不上——`php -l` 完全查不出来（语法没问题）。

错误写法：

```php
// Plugin.php（挂在 plugins_loaded 上）
class Plugin {
    public static function init(): void {
        add_action( 'plugins_loaded', array( Admin\SettingsPage::class, 'init' ) ); // ← 永不执行
        add_action( 'plugins_loaded', array( Api\RestRoutes::class, 'init' ) );     // ← 永不执行
    }
}
```

正确写法——**直接调用**子模块的 `init()`：

```php
public static function init(): void {
    Admin\SettingsPage::init();  // 子模块内部自己 add_action('admin_menu', ...) 等
    Api\RestRoutes::init();
}
```

注意区分两种情形：
- 往**别的**钩子注册（`plugins_loaded` 回调里 `add_action('init', ...)`、`add_action('rest_api_init', ...)`）——**没问题**，这些钩子还没触发
- 往**当前正在执行**的钩子注册（同钩子同优先级）——**不生效**

用本 skill 的 `scripts/wp_stub.php` 做运行时冒烟可自动诊断该模式（它复现了 WP_Hook 的快照语义）。

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
