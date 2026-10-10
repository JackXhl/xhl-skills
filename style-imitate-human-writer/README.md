# style-imitate-human-writer

一体化范文仿写活人写作Skill，适配Cursor / Claude Code / Continue，用于UGC种草测评长文生成。

> 仓库归属：xhl-skills (https://github.com/JackXhl/xhl-skills.git)
> License: MIT

## 简介

输入一篇参考范文，自动抽取文章写作DNA；结合你自己的图片说明、视频实测素材，生成低AI味、活人感UGC文章。内置事实防幻觉、AI句式黑名单、四层自检流水线。
适用平台：什么值得买、小红书、知乎、公众号、B站专栏。

## 能力清单

1. ✅ 范文风格蒸馏，提取文章结构、叙事逻辑、配图插入范式
2. ✅ 素材事实锁定，强制禁止编造素材以外内容
3. ✅ 内置human-writing活人写作约束，消除典型AI腔
4. ✅ 配套 `check_prose.py` 脚本，静态扫描文本AI特征
5. ✅ 完整交付物：Writing-DNA、素材审计清单、正文、自检报告

## 目录

```
style-imitate-human-writer/
├── SKILL.md                # 主技能文件，Agent加载入口
├── README.md
├── assets/check_prose.py   # AI句式静态检查脚本
└── examples/
    ├── input_sample.md
    └── output_sample.md
```

## 使用方法

### 方式1：Cursor项目内加载（推荐）
1. 将 `style-imitate-human-writer` 文件夹放入项目根目录
2. 在Cursor对话执行：
```
Load skill style-imitate-human-writer，读取SKILL.md，启用。
```
3. 传入范文 + 图片/视频素材，发起写作任务。

### 方式2：写入 .cursorrules
将SKILL.md内容合并进项目 `.cursorrules`，项目全局默认启用本Skill。

## 调用示例

```
启用 style-imitate-human-writer
参考范文：
【粘贴文章全文】
自有素材（图片/视频/实测笔记）：
截图1：软件主界面，包含XX按钮；视频片段：操作演示，出现报错；实测：网速不足时加载缓慢。
写作要求：值得买风格，2000字左右，markdown。
```

## 配套脚本 check_prose.py

静态扫描输出文本，自动识别黑名单AI句式，输出违规位置。

```bash
python assets/check_prose.py your_article.md
```

## 重要注意事项

1. 只能接收图片/视频**文字描述**，不能自动OCR图片、解析视频画面。
2. 仿写只学习写作风格结构，禁止洗稿原文案例，注意版权风险。
3. LLM幻觉无法完全消除，生成稿件务必人工复核事实。

## Changelog

v1.0.0
- 初版一体化四阶段流水线
- 融合human-writing反AI写作规则
- 新增素材审计、事实锁机制
