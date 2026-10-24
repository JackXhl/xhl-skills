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
| SQL 标识符（表/列名） | 白名单校验。`$wpdb->prepare()` 不能参数化标识符（`%i` 占位符需 **WP 6.2+** 才支持，且仍建议白名单） |
| meta 值 | `sanitize_meta( $meta_key, $meta_value, $object_type, $object_subtype )`（按注册时声明的 `sanitize_callback` 走） |
| 去斜杠（读超全局后） | `wp_unslash()`（**先于**任何 sanitize） |

## 4. 转义函数表（输出侧）

| 上下文 | 函数 |
|---|---|
| HTML 文本间 | `esc_html` |
| HTML 属性内 | `esc_attr` |
| URL（href/src） | `esc_url` |
| 富文本（post 级） | `wp_kses_post` |
| 翻译 + 转义合一 | `esc_html__` / `esc_attr__` |
| JS 内联数据 | `wp_json_encode` + `wp_add_inline_script`（勿手拼字符串；**不要用 `wp_localize_script`**——它会把标量强转字符串、丢类型，官方要求它只用于本地化字符串） |
| `<script>` 内容 | 禁止直接输出用户数据 |

⚠️ **净化不等于转义**：`sanitize_*` 是输入侧清洗（改写值），`esc_*` 是输出侧编码（改写字符）。二者不能互相替代——存进库的原始值应该在读取后按上下文 `esc_*` 输出；入库时用 `esc_html` 会把 `&` 变成 `&amp;` 并永久破坏数据。

⚠️ **`wp_unslash()` 先于净化**：WP 通过私有 `wp_magic_quotes()` 给 `$_GET`/`$_POST`/`$_COOKIE`/`$_SERVER` 加了斜杠，必须先 `wp_unslash()` 再 sanitize。它只处理字符串与数组（递归），其他类型原样返回。

## 5. 危险函数黑名单（静态扫描依据）

出现即高危（除极少数正当场景且加注释）：
- 代码执行：`eval`、`assert`、`create_function`、`preg_replace` 带 `/e`
- 命令执行：`exec`、`shell_exec`、`system`、`passthru`、`proc_open`、`popen`
- 混淆/隐藏：`base64_decode` 的结果直接进入执行函数、`gzinflate`、`gzuncompress`、`str_rot13`、`chr(...)` 长链拼接
- 文件风险：`file_put_contents`（路径含用户输入）、`move_uploaded_file`、`fopen` 写模式、`include $_GET`
- 变量劫持：`extract($_GET/$_POST)`、`parse_str`（未使用第二参数时）、`$$var`
- 反序列化：`unserialize($_POST/$_COOKIE)`
- SQL 注入：`$wpdb->query/get_results` 等直接拼接用户输入（应改用 `prepare`）
- 回调滥用：`call_user_func` / `call_user_func_array` 的第一个参数来自用户输入
- REST 缺参：`register_rest_route` 未提供 `permission_callback`（**WP 5.5 起**缺失即触发 `_doing_it_wrong()`；路由仍会注册，所以别指望它报错来提醒你）

## 6. 常见漏洞模式

- **存储型 XSS**：设置页/ meta 保存时未净化，输出时未转义 → 双侧都要处理
- **CSRF**：表单/Ajax 缺 nonce → 所有改变状态的操作加 nonce
- **越权**：Ajax/REST 只验证登录不验证能力；用 `edit_posts` 而非具体能力（如 `edit_others_posts`）
- **SQL 注入**：字符串拼接进 `$wpdb->query/get_results`
- **SSRF / 开放代理**：`wp_remote_get($user提供的URL)` 无校验、无 timeout、把响应体透出
- **路径穿越**：`file_get_contents( MY_DIR . $_GET['file'] )`
- **信息泄露**：把 `$e->getMessage()`、堆栈、SQL 直接回显给低权限用户（记 `error_log`，回显通用文案）

## 7. 自动化

- 本 skill 的 `scripts/wp_security_scan.py <目录>` 可批量检查第 5 节黑名单、混淆特征、未净化超全局、SQL 拼接、缺失 ABSPATH 守卫、缺失 nonce/capability、`wp_ajax_nopriv_`、REST 缺 `permission_callback`、短代码未转义、隐藏文件、外联域名
- **污点传播（v2 能力）**：扫描器先收集"由超全局赋值的变量"，再判断这些变量是否流入危险汇聚点（`$wpdb->*` / `include` / `call_user_func` / `unserialize` / 文件写入）。这覆盖了直接拼接正则扫不到的两段式写法：

```php
$id  = $_GET['id'];
$sql = "SELECT * FROM {$wpdb->posts} WHERE ID = " . $id;
$wpdb->get_results( $sql );        // ← 直接拼接正则扫不到，污点传播可捕获
```

- 两个易混的 SQL 场景：`$wpdb->prepare( "… %s", $val )` 是安全写法，不报；`$wpdb->prepare( "… " . $id )` **不安全**——`prepare()` 只转义 `%s` 占位符，格式串里直接插值等于拼接，`prepare()` 救不了
- 误报控制：`base64_decode`/`file_put_contents`/`parse_str`/`move_uploaded_file` 等常见合法用法仅作提示级报告，不会直接判 HIGH（`move_uploaded_file` 是 WordPress 上传的标准落盘方式，`wp_handle_upload` 内部即用它）；HIGH 基本可直接作为可疑点排查
- 官方工具：Plugin Check（wordpress.org 插件检查）、PHPStan + wp-phpstan（静态分析）
- 审查结论分级：HIGH（可直接利用）/ MEDIUM（需条件）/ LOW（卫生问题）/ INFO
