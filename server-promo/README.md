# server-promo

云服务器推广图文技能。给 Cursor / Claude Code / Codex 等兼容 [Agent Skills](https://agentskills.io) 的客户端使用。

> 仓库：https://github.com/JackXhl/xhl-skills.git  
> License: MIT

## 简介

一家一段写云服务器、免费试用、学生机、游戏开服。配置和价格后面紧跟实页截图，链接藏在中文里。

适用：腾讯云、阿里云、雨云等试用和优惠长文。不适用：`zhongcao-smzdm` 的 8 节安利骨架、小红书卡片、控制台 / SSH 教程。

## 能力

1. 厂商分节：适合谁、配置价格、边界、截图、中文入口
2. 开场只分人，结尾只说谁选谁，不催领、不堆链接
3. 图文对得上：桌面宽度实页截图，发白图和画面里没有的名字不能写
4. 口气走优惠帖。写完必须自己审查，`scripts/check_article.py` 和 `check_prose.py` 不过不准交

## 目录

```
server-promo/
├── SKILL.md
├── README.md
├── examples.md
└── scripts/check_article.py
```

## 安装

```bash
npx skills add JackXhl/xhl-skills --skill server-promo
npx skills add JackXhl/xhl-skills --skill server-promo --agent cursor --agent claude-code --agent codex
npx skills add JackXhl/xhl-skills --skill server-promo -g -y
```

## 使用前必须给

1. 各家推广链接，原样保留
2. 能打开的官网或试用页，用来截图核对配置和价格

## 自检

写完先审图文，再跑脚本。退出码不是 0，不能把稿交给用户。

```bash
python scripts/check_article.py 稿件.md
```
