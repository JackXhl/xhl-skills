# xhl-skills
xhl的agent skill技能包

遵循 [Agent Skills](https://agentskills.io) 开放规范：每个技能是一个包含 `SKILL.md` 的目录，可被 Claude Code、Codex、Cursor、Copilot 等 80+ 客户端发现和使用。

## 技能列表

| 技能 | 说明 |
| --- | --- |
| [style-imitate-human-writer](./style-imitate-human-writer/) | 范文仿写 · 活人写作：提取 Writing-DNA 指纹，素材事实锁死，四层自检，输出低 AI 痕迹 UGC 长文 |
| [wordpress-plugin-dev](./wordpress-plugin-dev/) | WordPress 插件开发、审查、加固与发布：脚手架、安全扫描、AI Client / Connectors / Abilities 集成、wordpress.org 过审 |
| [zhongcao-smzdm](./zhongcao-smzdm/) | 什么值得买式种草长文：标题槽位、8 节安利骨架、词汇/表达/预期/情感/结构五项检验。与具体产品解耦，换产品只换事实卡和截图 |

## 安装

```bash
# 安装单个技能
npx skills add JackXhl/xhl-skills --skill zhongcao-smzdm
npx skills add JackXhl/xhl-skills --skill wordpress-plugin-dev

# 安装全部技能
npx skills add JackXhl/xhl-skills
```

[![skills.sh](https://skills.sh/b/JackXhl/xhl-skills)](https://skills.sh/JackXhl/xhl-skills)

## License

[MIT](./LICENSE)
