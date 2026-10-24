# 发布与质量门禁（release-and-quality）

## 1. 代码规范

- WordPress Coding Standards（WPCS）：Yoda 条件（`'value' === $var`）、tabs 缩进、数组用 `array()` 或短语法全库统一、控制结构空格风格
- DocBlock：每个函数/类/文件头 `@since`、`@param`、`@return`；版本号用语义化（MAJOR.MINOR.PATCH）
- PHPCS + `WordPress-Extra` ruleset；自动修复 `phpcbf`

## 2. 静态分析与测试

- **PHPStan** + `wp-phpstan`（WordPress 桩 + 扩展规则）；第三方类缺失时建 baseline 逐步收紧
- **Plugin Check**（wordpress.org 官方检查插件，含 PCP 检查项）：发布前必跑，处理所有 error
- **测试**：PHPUnit + WP 测试库（`wp-env` 起本地环境，`wp-env start` 后 `composer test`）；E2E 可上 Playground
- 最低验证矩阵：支持的 WP 最低版 × 最新版 × PHP 最低版 × 推荐版；多站点（如插件涉网络功能）

## 3. wordpress.org 提交清单

1. `readme.txt` 规范格式（stable tag、requires at least、tested up to、changelog、short description ≤150 字符）
2. GPL 兼容许可（整包 GPLv2 or later；第三方库逐个核对）
3. 命名/商标：slug 不用他人商标；插件名不含 "WordPress" 开头；`Plugin URI` 唯一
4. 头部 `Update URI` 填自有地址（防覆盖）；若走 SVN 托管则不需要
5. 不含：调用 home 的电话上报、无说明的加密/混淆代码、后门式远程代码、伪造 WP 核心文件
6. `Requires Plugins` 声明依赖；国际化用 `wordpress.org/translations` 托管
7. 资产：截图放 `assets/`（或 `.wordpress-org`），图标 SVG 128×128 内
8. 首次提交后等 review（通常 ≤14 天），按评审意见改

## 4. 版本策略与维护

- 破坏性变更升 MAJOR，并在 readme changelog 明示；`Requires at least` 提升要谨慎（会赶走用户）
- 弃用流程：先 `apply_filters_deprecated` / `do_action_deprecated` 通知，至少一个大版本后再移除
- 安全修复：私下修复 → 通知 Patchstack/WPScan → 同步发版，遵守负责任披露
- 数据库升级：`my_plugin_version` 选项比对，`admin_init` 里跑迁移，勿依赖激活钩子（未激活站点漏跑）

## 5. 分发渠道备忘

- wordpress.org（SVN，走 review）
- 自有站点/GitHub Releases：用 `Update URI` + 自定义更新检查（或 Plugin Update Checker 库）
- 多站点打包：WPRail 等打包工具；freemium 用 `Requires Plugins` 引导
