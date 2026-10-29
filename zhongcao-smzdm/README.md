# zhongcao-smzdm

什么值得买式种草长文技能。给 Cursor / Claude Code / Codex / WorkBuddy 等兼容 [Agent Skills](https://agentskills.io) 的客户端使用。

> 仓库：https://github.com/JackXhl/xhl-skills.git  
> License: MIT

## 简介

学范文的**结构与口气**，不学范文的产品承诺。换产品只换事实卡和当前截图。

适用：什么值得买、知乎、CSDN 等可放链接的安利长文。不适用：小红书图文卡片、口播视频脚本。

种子范文：[免费抖音视频下载神器，连文案都能提取](https://post.smzdm.com/p/anvp2rq7/)

## 能力

1. 标题槽位：每次出 3 个，不堆范文原句
2. 8 节安利骨架（可砍成 5 节），开场三拍不能删
3. 对图硬停止：数字、按钮、规格必须能指到当前截图
4. 五项检验：词汇 / 表达 / 预期 / 情感 / 结构语法
5. `scripts/check.py` 拦住打码、翻案腔、范文产品名等硬伤

## 目录

```
zhongcao-smzdm/
├── SKILL.md
├── README.md
├── references/
│   ├── structure.md
│   ├── title.md
│   ├── voice.md
│   ├── checks.md
│   ├── banned.md
│   └── golden.md
├── scripts/check.py
└── evals/
    ├── README.md
    └── fail-spec.md
```

## 安装

```bash
npx skills add JackXhl/xhl-skills --skill zhongcao-smzdm
npx skills add JackXhl/xhl-skills --skill zhongcao-smzdm --agent cursor --agent claude-code --agent codex
npx skills add JackXhl/xhl-skills --skill zhongcao-smzdm -g -y
```

## 使用前必须给

1. 事实卡：能说 / 不能说 / 边界
2. 当前截图或可核验的官网页

没有事实卡不准写兑现不了的卖点。

## 自检

```bash
python scripts/check.py evals/fail-spec.md
# 期望退出码 1
```
