# wechat-search-card

微信搜一搜推广卡片。给 Cursor / Claude Code / Codex 等兼容 [Agent Skills](https://agentskills.io) 的客户端使用。

> 仓库：https://github.com/JackXhl/xhl-skills.git  
> 脚本 License: MIT。`assets/search-mark.png` 是微信搜一搜标识，不在 MIT 授权内，只用于按官方物料指引拼卡片。

## 简介

左边贴小程序码原图，右边是红色搜一搜标和「微信搜一搜」，下面一条绿色搜索按钮。搜索词没给全就先问，给全了一条命令出图。

## 用法

```bash
python scripts/render_card.py --qr ./code.jpg --keyword "山雀视频下载"
```

自测：

```bash
python scripts/self_test.py
```

依赖：Python 3.10+、Pillow。中文字体用系统自带的；官方汉仪旗黑用 `--font` 指向本机文件，不要放进仓库。

## 安装

```bash
npx skills add JackXhl/xhl-skills --skill wechat-search-card
```

## 目录

```
wechat-search-card/
├── SKILL.md
├── README.md
├── assets/search-mark.png
└── scripts/
    ├── render_card.py
    └── self_test.py
```
