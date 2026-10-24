---
name: wordpress-plugin-dev
version: 1.0.0
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

- 最新正式版 **WordPress 7.1.3**（2026-10-06）；**7.2** 处于 Beta（2026-12-08 发布），Beta/RC 期是提反馈的窗口
- 目标环境：WordPress **7.0+**，PHP **8.1+**（建议 8.2+）
- WP 7.0 起的核心新基础设施：**AI Client**（`wp_ai_client_prompt()`）、**Connectors API**（Settings > Connectors 统一管理 API Key）、**Abilities API**（`wp_register_ability()`，6.9/7.0 引入，7.1 增加统一 `meta.public` 暴露标志）、**MCP Adapter**（把 Ability 暴露为 MCP 工具）
- 7.2 预告（可能影响插件）：`wp_kses()` 基于 HTML API 重建、Application Passwords 改进、Secrets API（CLI-only，试验性）
- 写任何版本相关代码前，先 WebSearch 核实当时的最新版本与弃用情况；官方文档以 developer.wordpress.org 为准
- 版本保鲜：运行 `scripts/check_wp_versions.py`（查询 api.wordpress.org，与上述基线比对；离线时静默跳过）
- 兼容性口径：本 skill 默认 WP 7.0+ / PHP 8.1+（AI Client 教程要求）；若目标站需兼容 PHP 7.4，按官方 agent-skills 的兼容策略放宽，但不得为此删减安全规则

## 输入前提

开始前确认（缺失时先问用户，不臆测）：
- 仓库根目录 + 目标插件（主文件路径）；是完整站点仓库还是纯插件仓库（完整站点先定位到 `wp-content/plugins/` 或 `mu-plugins/` 下具体插件）
- 运行环境：单站点 vs 多站点（卸载/迁移逻辑不同）
- 目标 WP + PHP 版本（决定可用 API 与 `$wpdb->prepare()` 占位符支持）
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
2. 有 PHP CLI 时运行 `scripts/check_php_syntax.py`（无 PHP 则跳过并告知用户）
3. 运行 `scripts/check_wp_versions.py` 确认版本基线未过期
4. 功能验证优先用 wp-env / Playground；纯静态环境至少通读 diff 自查转义与权限
5. 发布类任务额外跑 `release-and-quality.md` 的清单

## 强制规则（不可协商）

**安全**
- 浏览器/管理端会改变数据的操作：**同时**校验 capability（授权）与 nonce（意图）。`current_user_can()` 管授权，`wp_nonce_field()` / `check_admin_referer()` / `check_ajax_referer()` / `wp_verify_nonce()` 管 CSRF
- 把请求数据、选项、meta、短代码属性、REST 载荷、第三方响应全部视为不可信输入
- 输入侧 sanitize（`sanitize_text_field`、`absint`、`sanitize_key`、`wp_kses`…），输出侧按上下文 escape（`esc_html`、`esc_attr`、`esc_url`、`wp_kses_post`…）；"先净化再校验"优于"只净化"
- 每条 REST 路由必须给真实的 `permission_callback`；绝不用 `__return_true` 公开敏感数据
- SQL 一律 `$wpdb->prepare()`；不拼接用户输入
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
- `scaffold_plugin.py` — 生成符合规范的插件骨架（完整头部、ABSPATH 守卫、PSR-4 autoloader、uninstall.php、readme.txt、可选 --with-rest/--with-settings/--with-blocks/--with-ai 桩代码）
- `wp_security_scan.py` — 静态安全扫描：危险函数、混淆特征、未净化超全局、缺失 nonce/capability、隐藏文件、外联域名清单，输出分级报告
- `check_php_syntax.py` — PHP CLI 探测 + `php -l`（无 PHP 时优雅跳过）
- `check_wp_versions.py` — 版本保鲜检查（比对 api.wordpress.org 与本 skill 基线）

### references/
- `plugin-fundamentals.md` — 头部字段全集、目录规范、加载顺序、激活/停用/卸载、autoload、版本号陷阱
- `hooks-and-core-apis.md` — Hooks API 与常用核心 API（Options/Settings/HTTP/Metadata/CPT/Taxonomy/Cron/短代码/菜单/Ajax/i18n）
- `security-checklist.md` — 安全审查清单、净化/转义函数表、漏洞模式速查
- `ai-client-connectors-abilities.md` — WP 7.x AI 三件套：AI Client 流式 API、Connectors 注册与消费、Abilities 注册与暴露、MCP Adapter
- `gutenberg-and-frontend.md` — block.json、@wordpress/scripts、资源入队、弃用处理、Interactivity API 入门
- `release-and-quality.md` — WPCS、Plugin Check、PHPStan、测试（wp-env/PHPUnit）、wordpress.org 提交清单

### 官方文档速查
- 插件手册 developer.wordpress.org/plugins/ · 安全 developer.wordpress.org/apis/security/
- 函数参考 developer.wordpress.org/reference/functions/ · AI Client make.wordpress.org/core/2026/03/24/introducing-the-ai-client-in-wordpress-7-0/
- Abilities 参考 developer.wordpress.org/reference/functions/wp_register_ability/
- 参考实现：`ai-provider-for-china`（知更鸟 / zmingcx.com）连接器插件（在 `references/ai-client-connectors-abilities.md` 中有模式拆解）

### 与官方 agent-skills 的分工（2026-10-24 对比后确立）
- 官方 `WordPress/agent-skills`（github.com，2288 star）是 18 个技能的权威知识源：块/主题/模式/REST/Interactivity/WP-CLI/性能/PHPStan/Playground 等领域的**深度细节以其为准**；遇块开发、theme.json、WP-CLI 运维等超出本 skill 深度的话题，引导用户安装对应官方技能
- 本 skill 的定位：**可执行层**——脚手架、安全扫描、语法/版本检查这些拿来即用的脚本 + 中文语境 + AI 三件套的国内连接器实战模式，官方包以文档为主
- 官方维护机制（eval 场景、上游版本索引自动同步、CI）是本 skill 缺失的，涉及"哪个模式更正确"的争论时以官方为仲裁

## 故障模式与调试

| 症状 | 常见原因 |
|---|---|
| 激活钩子不触发 | 钩子注册位置不在主文件作用域；多站点网络激活；`register_activation_hook` 路径错 |
| 设置保存无效 | `register_setting` 的 group 与 `settings_fields()` 不一致；capability 不足；nonce 校验失败 |
| 卸载后数据残留 | uninstall.php 缺 `WP_UNINSTALL_PLUGIN` 守卫被跳过；多站点未循环 `get_sites()` |
| Ajax 返回 -1/0 | `check_ajax_referer` 失败（nonce 过期/action 名不符）或 `wp_ajax_{action}` 未注册 |
| REST 401/403 | `permission_callback` 过严；cookie nonce 未传（`X-WP-Nonce`） |
| CPT 404 | 激活时未 `flush_rewrite_rules()`，或正常请求里刷了（性能反模式） |
| "Invalid block" | 属性结构变更未写 `deprecated` 迁移 |
| 安全回归 | nonce 有但 capability 漏；输入净化了但输出未转义 |
| AI 功能不显示 | 未探测 `wp_supports_ai()` / 站点未配置 Connector；模型不支持某能力 |
