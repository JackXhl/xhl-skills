# 安全审查清单（security-checklist）

基于官方 Common APIs Handbook（Security 章节）与实战审计经验。审查或编写插件时逐项过。

## 1. 五项指导原则（官方）

1. 永不信任用户输入
2. 尽可能晚地 escape
3. 一切来自不可信源的数据都要 escape（数据库、用户、第三方 API）
4. 永不假设
5. sanitize 可用，但 validate/reject 更好

## 2. 权限 × Nonce 决策矩阵

| 场景 | capability | nonce |
|---|---|---|
| 后台设置保存 | `manage_options` | `check_admin_referer` |
| 前台表单（评论/投稿） | 按角色（`edit_posts` 等） | `wp_nonce_field` + `wp_verify_nonce` |
| admin-ajax | `current_user_can(...)` | `check_ajax_referer` |
| REST 写操作 | `permission_callback` 返回真实能力 | REST 用 cookie nonce（`wp_rest`） |
| REST 公开读 | `__return_true` 仅限真正公开数据 | — |
| cron/CLI | 不依赖当前用户，验证数据来源 | — |

原则：**capability 管授权（你是谁），nonce 管意图（是不是你发的）**。二者不可互相替代。

## 3. 净化函数表（输入侧）

| 数据类型 | 函数 |
|---|---|
| 单行文本 | `sanitize_text_field` |
| 多行文本（保留换行） | `sanitize_textarea_field` |
| 邮箱 | `sanitize_email` |
| URL（入库） | `esc_url_raw` |
| 选项键/标识 | `sanitize_key` |
| 标题/slug | `sanitize_title` |
| HTML（受限标签） | `wp_kses` / `wp_kses_post`（后者=post 级权限标签） |
| 文件名 | `sanitize_file_name` |
| 整数 | `absint` / `intval` |
| 布尔 | `rest_sanitize_boolean` |
| 数组 | 按值类型递归处理，白名单键 |
| SQL 标识符（表/列名） | 白名单校验，`$wpdb->prepare` 不能参数化标识符 |

## 4. 转义函数表（输出侧）

| 上下文 | 函数 |
|---|---|
| HTML 文本间 | `esc_html` |
| HTML 属性内 | `esc_attr` |
| URL（href/src） | `esc_url` |
| 富文本（post 级） | `wp_kses_post` |
| 翻译 + 转义合一 | `esc_html__` / `esc_attr__` |
| JS 内联数据 | `wp_json_encode` + `wp_add_inline_script`（勿手拼字符串） |
| `<script>` 内容 | 禁止直接输出用户数据 |

## 5. 危险函数黑名单（静态扫描依据）

出现即高危（除极少数正当场景且加注释）：
- 代码执行：`eval`、`assert`、`create_function`、`preg_replace` 带 `/e`
- 命令执行：`exec`、`shell_exec`、`system`、`passthru`、`proc_open`、`popen`
- 混淆/隐藏：`base64_decode`（执行上下文）、`gzinflate`、`gzuncompress`、`str_rot13`、`chr(...)` 长链拼接
- 文件风险：`file_put_contents`（用户可控路径）、`move_uploaded_file`、`fopen` 写模式、`include $_GET`
- 变量劫持：`extract($_GET/$_POST)`、`parse_str`、`$$var`
- 反序列化：`unserialize($_POST/$_COOKIE)`
- 回调滥用：`call_user_func` / `call_user_func_array` 的第一个参数来自用户输入

## 6. 常见漏洞模式

- **存储型 XSS**：设置页/ meta 保存时未净化，输出时未转义 → 双侧都要处理
- **CSRF**：表单/Ajax 缺 nonce → 所有改变状态的操作加 nonce
- **越权**：Ajax/REST 只验证登录不验证能力；用 `edit_posts` 而非具体能力（如 `edit_others_posts`）
- **SQL 注入**：字符串拼接进 `$wpdb->query/get_results`
- **SSRF / 开放代理**：`wp_remote_get($user提供的URL)` 无校验、无 timeout、把响应体透出
- **路径穿越**：`file_get_contents( MY_DIR . $_GET['file'] )`
- **信息泄露**：把 `$e->getMessage()`、堆栈、SQL 直接回显给低权限用户（记 `error_log`，回显通用文案）

## 7. 自动化

- 本 skill 的 `scripts/wp_security_scan.py <目录>` 可批量检查第 5 节黑名单、混淆特征、未净化超全局、缺失 ABSPATH 守卫、隐藏文件、外联域名
- 官方工具：Plugin Check（wordpress.org 插件检查）、PHPStan + wp-phpstan（静态分析）
- 审查结论分级：HIGH（可直接利用）/ MEDIUM（需条件）/ LOW（卫生问题）/ INFO
