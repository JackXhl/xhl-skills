# 发布与质量门禁（release-and-quality）

## 1. 代码规范

- WordPress Coding Standards（WPCS）：Yoda 条件（`'value' === $var`）、tabs 缩进、数组用 `array()` 或短语法全库统一、控制结构空格风格
- DocBlock：每个函数/类/文件头 `@since`、`@param`、`@return`；版本号用语义化（MAJOR.MINOR.PATCH）
- PHPCS + `WordPress-Extra` ruleset；自动修复 `phpcbf`

## 2. 静态分析与测试

- **PHPStan** + `wp-phpstan`（WordPress 桩 + 扩展规则）；第三方类缺失时建 baseline 逐步收紧
- **Plugin Check (PCP)**（wordpress.org 官方检查插件，仓库 `github.com/WordPress/plugin-check`）：发布前必跑，处理所有 error。可用后台界面（Tools > Plugin Check）或 WP-CLI `wp plugin check hello.php`；**CLI 默认只跑静态检查**，要含运行时检查需 `--require=./wp-content/plugins/plugin-check/cli.php`。它不能替代人工评审，只是提前暴露常见问题
- **测试**：PHPUnit + WP 测试库（`wp-env` 起本地环境，`wp-env start` 后 `composer test`）；E2E 可上 Playground
- 最低验证矩阵：支持的 WP 最低版 × 最新版 × PHP 最低版 × 推荐版；多站点（如插件涉网络功能）
- 注意 WP 7.0 / 7.1 的最低 PHP 要求是 **7.4**（`$required_php_version`），插件声明 `Requires PHP` 不要高于实际运行环境的上限

## 3. wordpress.org 提交清单

1. `readme.txt` 规范格式：短描述 **≤150 字符**（超出会被截断）、`Stable tag`（插件自身版本号，非 WP 版本）、`Requires at least`、`Tested up to`（只填主版本号，目录会自动补次版本号）、`Requires PHP`、`License`；changelog 保留当前大版本 + 上一个大版本，更早的移到 `changelog.txt`。**自 WP 5.8 起 readme.txt 不再解析 `Requires PHP` / `Requires at least`，这两个值以主 PHP 文件头部为准**
2. GPL 兼容许可（整包 GPLv2 or later；第三方库逐个核对）
3. 命名/商标：**slug** 不得以他人商标/项目名开头（含 "wordpress"、"plugin" 等，仅极端情况例外）；slug 只允许英文字母和数字；slug 提交后不可改（显示名可随时改）
4. 头部 `Update URI` 填自有地址（防被 wp.org 同名插件覆盖）；**发布到 wordpress.org 的插件不要设这个字段**
5. 不含：未经同意的对外电话上报（phoning home）、无说明的加密/混淆代码、后门式远程代码、伪造 WP 核心文件；对外链需用户明确同意
6. `Requires Plugins` 声明依赖（WP 6.5+）；国际化用 `wordpress.org/translations` 托管
7. 资产：SVN 仓库**顶层** `assets/` 目录（与 `trunk/`、`tags/` 同级，**不是** `trunk/assets`）；文件名即尺寸——横幅 `banner-772x250.png`（Retina `banner-1544x500.png`），图标 `icon-128x128.png|jpg|gif`（Retina `icon-256x256.*`）或 `icon.svg`（**用 SVG 必须同时提供 PNG 兜底**），截图 `screenshot-1.png` 起编号，文件名全小写
8. 首次提交后等待 review：官方称**在 14 个工作日内**完成初审；三个月内未完成的提交会被拒绝（期间有进展则保持开启）

## 4. 版本策略与维护

- 破坏性变更升 MAJOR，并在 readme changelog 明示；`Requires at least` 提升要谨慎（会赶走用户）
- 弃用流程：先 `apply_filters_deprecated` / `do_action_deprecated` 通知，至少一个大版本后再移除
- 安全修复：私下修复 → 通知 Patchstack/WPScan → 同步发版，遵守负责任披露
- 数据库升级：`my_plugin_version` 选项比对，`admin_init` 里跑迁移，勿依赖激活钩子（未激活站点漏跑）

## 5. 分发渠道备忘

- wordpress.org（SVN，走 review）
- 自有站点/GitHub Releases：用 `Update URI` + 自定义更新检查（或 Plugin Update Checker 库）
- 多站点打包：WPRail 等打包工具；freemium 用 `Requires Plugins` 引导
