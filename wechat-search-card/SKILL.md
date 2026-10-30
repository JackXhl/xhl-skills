---
name: wechat-search-card
version: 1.0.0
description: >-
  Compose a WeChat Search promo card (微信搜一搜) from a real mini-program code
  and a search keyword. Use when the user asks for 微信搜一搜图片、搜一搜物料、
  小程序码搜索卡片, or to put 搜索词 on a QR card. Do not guess the keyword
  or redraw the code.
author: xhl-skills
license: MIT
tags: ["wechat", "design", "qrcode", "promo"]
---

# 微信搜一搜卡片

左码、右「微信搜一搜」、下绿搜索条。码用原图像素贴上去，搜索词只能用用户说出的那句。

版式、绿色 `#07C160`、按钮随文字变宽，都在脚本里。不要重新设计。

## 什么时候必须先问

下面任何一条成立，先停，问完再跑脚本。问的时候不要附上你猜的词。

- 没有搜索词，或搜索词是从仓库名、品牌、上一张卡片推出来的
- 没有小程序码，或这一轮有多张图，分不清哪张是码
- 搜索词超过 12 个字（脚本会以退出码 2 拒绝，确认后加 `--allow-long`）
- 目标文件已经存在（退出码 3，确认后加 `--force`）

用户同一句话里已经给了码和搜索词：不要再确认，直接跑。

有 AskQuestion 时，只用来选用户已经给出的图片。搜索词不要做成选项。

## 生成

脚本就在本文件旁边：`scripts/render_card.py`。用这份绝对路径。不要在用户项目里另找同名脚本，也不要用文生图重画。

```bash
python "<本技能目录>/scripts/render_card.py" --qr "<小程序码>" --keyword "<搜索词>"
```

`--out` 可省略，默认写到码旁边：`微信搜一搜-<搜索词>.png`。

缺 Pillow 时只执行 `pip install pillow`，不要改渲染脚本。官方汉仪旗黑不进仓库。要那套字，加 `--font path/to/HYQiHei-60S.otf`，或设置 `WECHAT_SEARCH_FONT`。不传则用微软雅黑 Bold，没有再退到黑体。

```
- [ ] 搜索词是用户原话，不是从品牌或文件名猜的
- [ ] 码只有一张，或用户已经指定哪一张
- [ ] 脚本退出码是 0
- [ ] 打开成图：搜索条上的字和原话一致，四角透明，不要填成黑边或白边
```

没勾完不要把图交给用户。码是原图缩放，不要说成重新绘制的二维码。

## 不要做

- 用产品名、公众号名、文件名填搜索词。出现过把词猜成「柚见下载」，正确词是用户后来说的「山雀视频下载」。
- 用文生图重画小程序码或红色搜一搜标。
- 把按钮拉到和标题一样宽。字短，按钮就短。
- 把 `.otf` 字体提交进仓库。

标识文件见 [assets/search-mark.png](assets/search-mark.png)。它是微信搜一搜标识，不在 MIT 授权里，只用来按物料指引拼这张卡片。
