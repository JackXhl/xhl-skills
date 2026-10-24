# wordpress-plugin-dev

WordPress 插件开发、审查、加固与发布技能。以资深 WordPress 插件工程师的标准，产出"能过审、能上线"的代码，而不是"看起来能跑"的代码。

## 能力覆盖

- **新建插件**：规范头部、ABSPATH 守卫、PSR-4 autoloader、uninstall.php、readme.txt
- **功能实现**：Hooks API、Options/Settings API、HTTP API、CPT/Taxonomy、Cron、短代码、Ajax、REST 路由
- **安全审计**：nonce + capability 双重校验、输入净化 / 输出转义、`$wpdb->prepare()`、危险函数扫描
- **WP 7.x AI 三件套**：AI Client（`wp_ai_client_prompt`）、Connectors API、Abilities API（`wp_register_ability`）、MCP Adapter
- **Gutenberg**：block.json、`@wordpress/scripts`、资源入队、Interactivity API 入门
- **发布**：WPCS、Plugin Check、PHPStan、wp-env 测试、wordpress.org 提交清单

## 安装

```bash
npx skills add JackXhl/xhl-skills --skill wordpress-plugin-dev
```

## 目录结构

```
wordpress-plugin-dev/
├── SKILL.md               # 版本基线 / 工作流 / 强制规则 / 故障模式速查
├── README.md
├── references/            # 6 篇参考资料（按任务类型按需加载）
│   ├── plugin-fundamentals.md          # 头部字段、目录规范、激活/卸载、版本号陷阱、namespace 位置陷阱
│   ├── hooks-and-core-apis.md          # Hooks API 与常用核心 API
│   ├── security-checklist.md           # 安全审查清单、净化/转义函数表、漏洞模式
│   ├── ai-client-connectors-abilities.md  # AI 三件套 + 国内连接器实战拆解
│   ├── gutenberg-and-frontend.md       # 块开发与前端资源
│   └── release-and-quality.md          # 质量门禁与发布清单
└── scripts/               # 5 个可执行脚本（Python 3.8+，无第三方依赖）
    ├── scaffold_plugin.py     # 生成符合规范的插件骨架
    ├── wp_security_scan.py    # 静态安全扫描，输出分级报告
    ├── check_php_syntax.py    # php -l 语法检查（无 PHP 环境自动跳过）
    ├── check_wp_versions.py   # 版本保鲜检查（比对 api.wordpress.org）
    └── self_test.py           # 技能自测：14 项断言（脚手架/边界输入/扫描/降级路径回归）
```

## 使用示例

```bash
# 生成新插件骨架（可选 --with-rest/--with-settings/--with-blocks/--with-ai）
python scripts/scaffold_plugin.py --name "My Plugin" --path ./my-plugin --with-settings --with-rest

# 安全扫描既有插件
python scripts/wp_security_scan.py /path/to/plugin-dir

# 确认版本基线未过期
python scripts/check_wp_versions.py

# 运行技能自测（修改脚本后必跑）
python scripts/self_test.py
```

## 环境基线

- WordPress 7.0+（2026-10 最新正式版 7.1.3）
- PHP 8.1+（建议 8.2+）；目标站需兼容 PHP 7.4 时按官方兼容策略放宽，但不删减安全规则
- 脚本仅需 Python 3.8+，无第三方依赖；无网络时版本保鲜检查自动跳过
- PHP CLI 可选：安装后自动启用脚手架产出的 `php -l` 语法断言（推荐 PHP 8.4+）

## 质量验证

- **安全扫描器**：真实生产插件（`ai-provider-for-china`，5 家国内大模型连接器）实测 HIGH=0，与人工审计结论一致；恶意夹具实测 HIGH=11、10 类威胁全覆盖
- **脚手架产出**：全选项生成的 10 个 PHP 文件经 PHP 8.5 `php -l` 逐一验证（曾借此修复 namespace 声明位置导致的 7 文件致命错误）
- **自测套件**：`self_test.py` 14 项断言全绿（含无选项生成、数字开头/单引号/`*/` 注入等边界输入）；对 Windows 实时杀软（火绒/Defender）隔离夹具的场景内置重试与跳过韧性
- **CI**：`.github/workflows/skill-ci.yml` 在 ubuntu（自测套件）与 windows（脚手架 php -l）双平台运行

## License

MIT
