# 评测

在技能目录下：

```bash
python scripts/check.py <一份能过的成稿.md>
# 期望：check passed

python scripts/check.py evals/fail-spec.md
# 期望：退出码 1，打出打码 / 绝对值得收藏 / 真正全面 / 范文产品名 / 翻案腔 等 FAIL
# 无水印、100+ 为 WARN，须对照事实卡
```

脚本只抓硬伤词。人味、对图、预期仍靠 `references/checks.md` 五项人工关。
