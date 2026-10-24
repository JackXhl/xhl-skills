---
name: wordpress-plugin-dev
version: 1.4.0
description: WordPress 插件开发、审查、加固与发布技能。当任务涉及 WordPress 插件/主题代码（plugin.php、wp-content/plugins、add_action/add_filter、register_setting、wp_remote_*、admin-ajax、REST 路由、block.json、Gutenberg 块、WP 7.0+ AI Client / Connectors API / Abilities API、wp_register_ability、wp_ai_client_prompt、readme.txt 提交 wordpress.org）时使用。覆盖：新建插件脚手架、功能实现、代码审查、安全审计（nonce/capability/净化/转义）、性能优化、AI 功能集成、发布前检查。WordPress plugin development, security audit, Gutenberg, REST API, AI Client, Abilities API.
author: xhl-skills
license: MIT
tags: ["wordpress", "wordpress-plugin", "php", "security-audit", "gutenberg", "rest-api", "ai-client", "abilities-api", "wpcs"]
agent_created: true
---

# WordPress 插件开发（wordpress-plugin-dev）

## Overview

以资深 WordPress 插件工程师的标准完成插件开发、审查、加固与发布。默认遵循官方 API 与安全规范，产出"能过审、能上线"的代码，而不是"看起来能跑"的代码。

## 版本基线（2026-10-24 核实）

- 最新正式版 **WordPress 7.1.3**（2026-10-06 发布，**安全版本**，含 7 项安全修复——存储型 XSS、WXR 导出二阶 SQL 注入、未认证的私有/草稿评论泄露、`WP_Http::make_absolute_url()` DoS、Author 角色可置顶文章、Imgur oEmbed XSS、动态钩子名碰撞）。做兼容性测试时以此为基线
- **7.2** 处于 Beta（Beta 1 已于 2026-10 发布，最终发布日定为 **2026-12-08**）；Beta/RC 期是提反馈的窗口，插件作者应提前跑一遍 beta 回归
- 目标环境：WordPress **7.0+**，PHP **8.1+**（建议 8.2+）。注意 WP 7.0 起最低 PHP 要求为 **7.4**（已弃用 7.2/7.3）
- WP 7.0 起的核心新基础设施：
  - **AI Client**（`wp_ai_client_prompt()`，7.0）
  - **Connectors API**（Settings > Connectors 统一管理 API Key，7.0）
  - **Abilities API**（`wp_register_ability()`，**服务端 6.9 引入**，7.0 增加 JS 客户端，**7.1 增加统一 `meta.public` 暴露标志 + 4 个执行生命周期过滤器**）
  - **MCP Adapter**（把 Ability 暴露为 MCP 工具）——**独立包，不是核心的一部分**
- 7.2 预告（可能影响插件）：`wp_kses()` 基于 HTML API 重建、Application Passwords 改进、Secrets API（CLI-only，试验性）
- 写任何版本相关代码前，先 WebSearch 核实当时的最新版本与弃用情况；官方文档以 developer.wordpress.org 为准
- 版本保鲜：运行 `scripts/check_wp_versions.py`（查询 api.wordpress.org，与上述基线比对；离线时静默跳过）
- 兼容性口径：本 skill 默认 WP 7.0+ / PHP 8.1+（AI Client 教程要求）；若目标站需兼容 PHP 7.4，按官方 agent-skills 的兼容策略放宽，但不得为此删减安全规则

## 输入前提

开始前确认（缺失时先问用户，不臆测）：
- 仓库根目录 + 目标插件（主文件路径）；是完整站点仓库还是纯插件仓库（完整站点先定位到 `wp-content/plugins/` 或 `mu-plugins/` 下具体插件）
- 运行环境：单站点 vs 多站点（卸载/迁移逻辑不同）
- 目标 WP + PHP 版本（决定可用 API；`$wpdb->prepare()` 的 `%i` 标识符占位符需 WP 6.2+，与 PHP 版本无关）
- 是否要走 wordpress.org 发布（决定 readme.txt / Plugin Check / GPL 要求）

## 工作流

### 第 1 步：任务分类

先判定任务类型，再决定加载哪些 reference：

| 任务类型 | 加载的 reference |
|---|---|
| 新建插件 / 脚手架 | `plugin-fundamentals.md` + `scripts/scaffold_plugin.py` |
| 功能实现（hooks/CPT/短代码/设置页/metabox） | `hooks-and-core-apis.md` |
| 安全审计 / 代码审查 | `security-checklist.md` + `scripts/wp_security_scan.py` |
| AI 功能（调大模型/注册连接器/注册 Ability） | `ai-client-connectors-abilities.md` |
| Gutenberg 块 / 前端资源 / Interactivity | `gutenberg-and-frontend.md` |
| 发布到 wordpress.org / 质量门禁 | `release-and-quality.md` |

### 第 2 步：检视现有代码

改动既有插件前：读主插件文件头（版本、Requires at least、Requires PHP）、目录结构、autoload 方式、既有 hooks 与选项前缀、编码规范（WPCS 还是自定义）。**沿袭代码库现有风格**，不擅自引入新架构。

### 第 3 步：实施

遵守下方强制规则。能用核心 API 就不自己造轮子（HTTP API、Options API、Settings API、Metadata API、REST API）。

### 第 4 步：验证

1. 运行 `scripts/wp_security_scan.py <插件目录>`，修正所有 HIGH/MEDIUM 发现
2. 有 PHP CLI 时运行 `scripts/check_php_syntax.py`（无 PHP 则跳过并告知用户）；**带命名空间的类文件必须过 `php -l`**——ABSPATH 守卫若写在 `namespace` 之前会直接 Fatal（见 `plugin-fundamentals.md` 的位置陷阱）
3. 新建插件或改动加载链路时，用 `scripts/wp_stub.php <主文件>` 做运行时冒烟：验证 autoloader 能定位类、子命名空间能解析、钩子按预期注册，**以及钩子回调真的被触发**（纯语法检查覆盖不到这些）
4. 运行 `scripts/check_wp_versions.py` 确认版本基线未过期
5. 功能验证优先用 wp-env / Playground；纯静态环境至少通读 diff 自查转义与权限
6. 发布类任务额外跑 `release-and-quality.md` 的清单
7. 改动了技能自身脚本时，运行 `scripts/self_test.py` 做回归（61 项断言，含杀软环境韧性）

## 强制规则（不可协商）

**安全**
- 浏览器/管理端会改变数据的操作：**同时**校验 capability（授权）与 nonce（意图）。`current_user_can()` 管授权，`wp_nonce_field()` / `check_admin_referer()` / `check_ajax_referer()` / `wp_verify_nonce()` 管 CSRF
- 把请求数据、选项、meta、短代码属性、REST 载荷、第三方响应全部视为不可信输入
- 输入侧 sanitize（`sanitize_text_field`、`absint`、`sanitize_key`、`wp_kses`…），输出侧按上下文 escape（`esc_html`、`esc_attr`、`esc_url`、`wp_kses_post`…）；"先净化再校验"优于"只净化"。**净化 ≠ 转义**：净化改写值、转义改写字符，入库时别用 `esc_*`
- 读 `$_POST`/`$_GET`/`$_REQUEST`/`$_COOKIE` 一律先 `wp_unslash()`（WP 内部 `wp_magic_quotes()` 已加斜杠）再 sanitize
- 传数据给 JS 用 `wp_add_inline_script` + `wp_json_encode`，**不要用 `wp_localize_script`**（它把标量强转字符串、丢类型）
- 每条 REST 路由必须给真实的 `permission_callback`（**WP 5.5 起缺失即触发 `_doing_it_wrong()`**，但路由仍会注册，别指望它拦住你）；绝不用 `__return_true` 公开敏感数据
- SQL 一律 `$wpdb->prepare()`；不拼接用户输入（`prepare()` 的**格式串**里插值变量同样等于拼接，必须用 `%s` 占位符传参）
- 禁止 `eval`、`assert`、`create_function`、`preg_replace` 的 /e、`base64_decode` 执行、`exec`/`shell_exec`/`system`/`proc_open`、`extract($_GET)`、`unserialize($_POST)`、`move_uploaded_file` 处理未校验上传
- 所有 PHP 文件顶部 `if ( ! defined( 'ABSPATH' ) ) exit;`

**性能**
- 优化前先测量/定位热点；不为每次请求做昂贵远程 HTTP（必须做时加缓存、timeout、fallback）
- 正常请求中绝不调用 `flush_rewrite_rules()`（只在激活钩子里做）
- 不把大块少用数据存进 autoload 选项；不全局缓存用户私有数据
- 查询用 `fields => 'ids'`、分页、按需 `no_found_rows`

**i18n 与规范**
- 新公开字符串全部包 `__()` / `_e()`（JS 用 `@wordpress/i18n`），插件头声明 Text Domain + Domain Path
- 遵循 WordPress 编码规范（WPCS）：Yoda 条件、tab 缩进、完整 DocBlock

**设计**
- 管理/编辑器 UI 用 WordPress 原生组件与模式；不为美观牺牲可达性（empty/loading/error 状态、不用颜色单独传达信息、危险操作需确认）
- 前端输出尽量继承主题样式，插件 CSS 加作用域前缀

## Resources

### scripts/
- `scaffold_plugin.py` — 生成符合规范的插件骨架（完整头部、ABSPATH 守卫、PSR-4 autoloader、uninstall.php、readme.txt、可选 --with-rest/--with-settings/--with-blocks/--with-ai 桩代码；自动防护命名空间/常量名以数字开头、单引号断裂、头部注释注入、非 ASCII 名 slug 冲突等边界输入）
- `wp_security_scan.py` — 静态安全扫描：危险函数、混淆特征、未净化超全局、**污点传播**（超全局 → 变量 → `$wpdb->`/include/call_user_func/unserialize/文件写入）、SQL 拼接（含 `prepare()` 格式串插值）、缺失 nonce/capability、`wp_ajax_nopriv_`、`__return_true` 权限回调、REST 缺 `permission_callback`、短代码未转义、隐藏文件、外联域名清单，输出分级报告（`base64_decode`/`file_put_contents`/`move_uploaded_file` 等常见合法用法仅作提示级报告，不判 HIGH）
- `check_php_syntax.py` — PHP CLI 探测 + `php -l`。探测顺序：`PHP_BIN` 环境变量 → PATH → 常见安装位置（XAMPP/WAMP/Laragon/scoop/解压版，含未加入 PATH 的情况）——**只查 PATH 会让"已装 PHP"的机器静默跳过语法检查**；设 `WP_DEV_NO_PHP_SEARCH=1` 可关闭兜底扫描
- `check_wp_versions.py` — 版本保鲜检查（比对 api.wordpress.org 与本 skill 基线）
- `self_test.py` — 技能自测（eval-lite）：脚手架产出 php -l 校验、边界输入、中文名 slug 冲突、子模块引导方式、**运行时钩子真实触发**、ability 与连接器注册语义、**文档事实准确性核对**（连接器 ID / 零参数签名 / WP 7.1 过滤器 / REST 端点 / MCP 非核心 / **第 9 轮：菜单函数 capability 参数位置、dbDelta 空格误解、permission_callback 5.5 起、register_setting 无 permission_callback、register_meta 用 auth_callback、wp_localize_script 强转字符串、wp_unslash 语义、Requires 头部版本归属、apiVersion 3、Interactivity data-wp-interactive、Plugin Check (PCP)、资产文件名规范**）、**references 全量 PHP 代码块 php -l**、**全文件编码完整性（U+FFFD 替换字符检查）**、**PHP CLI 探测（PHP_BIN/PATH/常见位置三级 + 无 PHP 降级）**、扫描器污点传播与误报控制、脚本退出码与降级路径回归；CI 可直接运行
- `wp_stub.php` — 最小 WordPress 运行时存根：加载插件主文件并**真正执行** `plugins_loaded`/`init`/`rest_api_init`/`admin_*`/`wp_abilities_api_*`/`wp_connectors_init` 钩子（**带参动作钩子会正确传入回调参数**，如 `wp_connectors_init` 传注册表实例），验证 PSR-4 autoloader 定位、子命名空间解析、常量定义时机、钩子注册与回调执行；并能诊断三类致命模式——"在 `plugins_loaded` 回调内重复 `add_action('plugins_loaded')`"导致子模块永不执行、ability 分类未注册/挂错钩子、连接器重复注册（`php -l` 只管语法，这个管运行时）

### references/
- `plugin-fundamentals.md` — 头部字段全集、目录规范、加载顺序、激活/停用/卸载、autoload、版本号陷阱
- `hooks-and-core-apis.md` — Hooks API 与常用核心 API（Options/Settings/HTTP/Metadata/CPT/Taxonomy/Cron/短代码/菜单/Ajax/i18n）
- `security-checklist.md` — 安全审查清单、净化/转义函数表、漏洞模式速查
- `ai-client-connectors-abilities.md` — WP 7.x AI 三件套：AI Client 流式 API（snake_case builder + camelCase 结果对象）、Connectors 注册与消费（**内置 ID 为 `anthropic`/`google`/`openai`，无前缀**）、Abilities 注册与暴露（REST 端点、annotations 决定 HTTP 方法、WP 7.1 生命周期过滤器）、MCP Adapter（**独立包，非核心**）
- `gutenberg-and-frontend.md` — block.json、@wordpress/scripts、资源入队、弃用处理、Interactivity API 入门
- `release-and-quality.md` — WPCS、Plugin Check、PHPStan、测试（wp-env/PHPUnit）、wordpress.org 提交清单

### 官方文档速查
- 插件手册 developer.wordpress.org/plugins/ · 安全 developer.wordpress.org/apis/security/
- 函数参考 developer.wordpress.org/reference/functions/ · AI Client make.wordpress.org/core/2026/03/24/introducing-the-ai-client-in-wordpress-7-0/
- Abilities 参考 developer.wordpress.org/reference/functions/wp_register_ability/
- 参考实现：`ai-provider-for-china`（知更鸟 / zmingcx.com）连接器插件（在 `references/ai-client-connectors-abilities.md` 中有模式拆解）

### 与官方 agent-skills 的分工（2026-10-24 对比后确立）
- 官方 `WordPress/agent-skills`（github.com，数千 star）是 18 个技能的权威知识源：块/主题/模式/REST/Interactivity/WP-CLI/性能/PHPStan/Playground 等领域的**深度细节以其为准**；遇块开发、theme.json、WP-CLI 运维等超出本 skill 深度的话题，引导用户安装对应官方技能
- 本 skill 的定位：**可执行层**——脚手架、安全扫描、语法/版本检查这些拿来即用的脚本 + 中文语境 + AI 三件套的国内连接器实战模式，官方包以文档为主
- 官方维护机制（eval 场景、上游版本索引自动同步、CI）是本 skill 缺失的，涉及"哪个模式更正确"的争论时以官方为仲裁

## 故障模式与调试

| 症状 | 常见原因 |
|---|---|
| 激活钩子不触发 | 钩子注册位置不在主文件作用域；多站点网络激活；`register_activation_hook` 路径错 |
| **插件能激活但 REST/设置页/块/ability 全部不出现** | **在 `plugins_loaded` 回调内部又 `add_action('plugins_loaded', ...)`——WP_Hook 遍历同优先级的回调快照，同优先级新注册的回调本次不执行，子模块 `init()` 永不运行。改为在 `Plugin::init()` 里直接调用子模块 `init()`** |
| 设置保存无效 | `register_setting` 的 group 与 `settings_fields()` 不一致；capability 不足；nonce 校验失败 |
| 卸载后数据残留 | uninstall.php 缺 `WP_UNINSTALL_PLUGIN` 守卫被跳过；多站点未循环 `get_sites()` |
| Ajax 返回 -1/0 | `check_ajax_referer` 失败（nonce 过期/action 名不符）或 `wp_ajax_{action}` 未注册 |
| REST 401/403 | `permission_callback` 过严；cookie nonce 未传（`X-WP-Nonce`） |
| **ability 注册无效（返回 null / 控制台报 doing_it_wrong）** | `category` 指向的分类未先用 `wp_register_ability_category()` 注册；或不在 `wp_abilities_api_init` 动作内调用 `wp_register_ability()` |
| **ability 静默消失（不报错，但调用时不存在）** | 三种注册错误都不会让插件 fatal，只是安静地少一个 ability：①分类从未注册 ②分类挂到了 `wp_abilities_api_init`（应为 `wp_abilities_api_categories_init`）③`category` slug 指向未注册分类。按"分类已注册 → 动作正确 → 必填参数齐全 → slug 正则"顺序逐个排除，用 `wp_has_ability_category()` / `wp_has_ability()` 自检 |
| **连接器查不到（`wp_is_connector_registered()` 恒为 false）** | 内置连接器 ID 是 `anthropic` / `google` / `openai`（**无 `core/` 前缀**）；`core/openai` 之类的写法永远查不到。另外 `type` 为 `ai_provider` 且 `wp_supports_ai()` 为 false 时 `register()` 会**静默返回 null** |
| **连接器密钥取不到** | `wp_get_connector()` 只返回**元数据**（name/description/type/authentication/plugin），**不含 base_url 也不含明文密钥**；密钥要按 `authentication.setting_name` / `constant_name` / `env_var_name` 自行读取，优先级为 环境变量 → PHP 常量 → 数据库 |
| **AI 调用返回 WP_Error / 调用到不存在的方法** | `generate_text()` 返回 `string\|WP_Error`；取元数据用 `generate_text_result()` + `toText()`（camelCase），**不是** `get_text()`；站点未配置 Connector 时用 `is_supported_for_text_generation()` 先探测 |
| CPT 404 | 激活时未 `flush_rewrite_rules()`，或正常请求里刷了（性能反模式） |
| **子菜单页面对所有人不可见 / 权限错乱** | `add_submenu_page()` 的 capability 在**第 4** 个参数（`$parent_slug, $page_title, $menu_title, $capability, ...`），不是第 3 个；`add_menu_page()` / `add_options_page()` 才在第 3 个。照抄"第三个参数是 capability"会把 capability 传到 `$menu_title` |
| **REST 路由意外公开** | `register_rest_route` 未给 `permission_callback` **自 WP 5.5 起触发 `_doing_it_wrong()` 但不会阻止路由注册**——不写等于裸奔，务必显式给（公开数据写 `__return_true`） |
| **JS 拿到的是字符串而非布尔/数字** | 用了 `wp_localize_script`：它内部把所有标量强转字符串并做 `html_entity_decode`。传数据用 `wp_add_inline_script` + `wp_json_encode` |
| **存进去的 `&` 变成了 `&amp;`** | 入库时用了 `esc_html`/`esc_attr`。净化（`sanitize_*`）与转义（`esc_*`）是两件事：入库用净化，输出才转义 |
| **读到的值多了一层反斜杠** | 忘了 `wp_unslash()`：WP 内部 `wp_magic_quotes()` 已给超全局加过斜杠 |
| **dbDelta 建表不生效** | 硬性要求是**每个字段/索引单独一行**、字段名在行首；"PRIMARY KEY 必须两个空格"是误解（官方正则是 `\s+`，一个空格即可） |
| **插件目录里读不到自建版本更新** | 设了 `Update URI` 指向非 wp.org 地址后，wp.org API 就不再返回该插件的更新——这是预期行为，第三方分发才需要设；发布到 wp.org 的插件不要设 |
| "Invalid block" | 属性结构变更未写 `deprecated` 迁移 |
| 安全回归 | nonce 有但 capability 漏；输入净化了但输出未转义 |
| AI 功能不显示 | 未探测 `wp_supports_ai()` / 站点未配置 Connector；模型不支持某能力 |
