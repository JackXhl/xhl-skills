# WP 7.x AI 三件套：AI Client / Connectors / Abilities（ai-client-connectors-abilities.md）

> WP 7.0（2026）起官方 AI 基础设施。写 AI 功能前先用 `function_exists` / `wp_supports_ai()` 探测，保证旧站优雅降级。

## 1. WordPress AI Client（provider 无关的 PHP 客户端）

入口函数 `wp_ai_client_prompt()` 返回流式 builder：

```php
// 文本生成（最常用）
$text = wp_ai_client_prompt( '总结 WordPress 缓存的好处。' )
    ->using_temperature( 0.7 )
    ->generate_text();

if ( is_wp_error( $text ) ) { /* 处理 */ return; }
echo wp_kses_post( $text );
```

常用方法：
- 选项：`using_temperature()`、`using_max_tokens()`、`using_top_p()`、`as_json_response( $schema )`（结构化输出）、`using_model_preference( 'model-a', 'model-b' )`（偏好非要求，按站点可用模型降级）
- 生成：`generate_text()` / `generate_texts( $n )` / `generate_image()` / `generate_images( $n )` / `generate_video()` / `convert_text_to_speech()` / `generate_speech()`
- **返回值类型（易错点）**：
  - `generate_text()` 返回 `string|WP_Error`
  - `generate_text_result()` 返回 `GenerativeAiResult|WP_Error`，其取文本的方法是 **`toText()`**（camelCase），另有 `toTexts()`、`toImageFile()`、`getTokenUsage()`、`getProviderMetadata()`、`getModelMetadata()`——**没有 `get_text()` 这个方法**，写成 snake_case 会直接 Fatal
- **特性探测（不发请求）**：`$builder->is_supported_for_text_generation()` / 对应 image/vision 方法。展示 AI UI 前先探测
- **阻断提示**：`wp_ai_client_prevent_prompt` 过滤器可阻止提示词执行（返回 `true` 即阻止）；被阻止时 `is_supported_*()` 返回 `false`，生成方法返回 `WP_Error`

模型来源：站点管理员在 **Settings > Connectors** 配置的官方 provider 插件（OpenAI / Anthropic / Google，以及第三方如国内五家连接器）。插件不自己存 Key、不自己写 HTTP 客户端。

## 2. Connectors API（统一凭证层）

- 站点侧：Settings > Connectors 一个页面存所有外部服务 API Key，"配置一次，处处可用"
- 默认 AI provider：`core/openai`（ai-provider-for-openai）、`core/claude`、`core/gemini`；密钥选项名约定 `connectors_ai_{provider}_api_key`
- 注册自己的连接器（`wp_connectors_init` 钩子，注册表在 `init` 优先级 15 初始化）：

```php
add_action( 'wp_connectors_init', function ( WP_Connector_Registry $registry ): void {
    if ( $registry->is_registered( 'my_service' ) ) { return; }
    $registry->register( 'my_service', array(
        'name'        => __( 'My Service', 'my-plugin' ),
        'description' => __( 'Syncs content with My Service.', 'my-plugin' ),
        'type'        => 'content_sync',
        'authentication' => array(
            'method'         => 'api_key',          // 或 'none'
            'credentials_url' => 'https://example.com/account/api-keys',
            'setting_name'   => 'my_plugin_my_service_api_key',
        ),
    ) );
} );
```

- 消费：`wp_is_connector_registered( 'openai' )` → `wp_get_connector( 'openai' )` 返回凭证与 base_url（已解密）；`wp_get_connectors()` 列全部
- ID 规则 `/^[a-z0-9_-]+$/`，注册表拒绝重复 ID；覆盖元数据需先 `unregister` 改完再 `register`，且先 `is_registered` 检查
- **AI provider 连接器受 `wp_supports_ai()` 门控**（可被 `WP_AI_SUPPORT` 常量或 `wp_supports_ai` 过滤器关闭），AI 插件必须特性探测

## 3. Abilities API（把功能注册为机器可调用能力）

**注册三步缺一不可**（漏任何一步都会静默失败或报 `_doing_it_wrong`）：

1. 分类必须**先**注册（`wp_abilities_api_categories_init` 动作）
2. `wp_register_ability()` 必须在 `wp_abilities_api_init` 动作内调用——否则返回 `null` 并触发 `_doing_it_wrong`
3. `execute_callback` 与 `permission_callback` 都是**必填**

```php
// 第 1 步：注册分类（slug 只允许小写字母数字与连字符）
add_action( 'wp_abilities_api_categories_init', function (): void {
    wp_register_ability_category( 'my-plugin', array(
        'label'       => __( 'My Plugin', 'my-plugin' ),
        'description' => __( 'Abilities provided by My Plugin.', 'my-plugin' ),
    ) );
} );

// 第 2 步：注册 ability
add_action( 'wp_abilities_api_init', function (): void {
    wp_register_ability( 'my-plugin/export-posts', array(
        'label'               => __( 'Export posts', 'my-plugin' ),
        'description'         => __( 'Exports posts as CSV.', 'my-plugin' ),
        'category'            => 'my-plugin',        // 必须已注册，否则注册失败
        'input_schema'        => array(
            'type'        => 'string',
            'description' => __( 'The text to be analyzed.', 'my-plugin' ),
            'minLength'   => 10,
            'required'    => true,                  // 顶层标记，不是 properties 内某个字段的
        ),
        'output_schema'       => array(
            'type' => 'string',
        ),
        'execute_callback'    => 'my_plugin_export_posts',
        'permission_callback' => function (): bool { return current_user_can( 'edit_posts' ); },
        'meta'                => array(
            'annotations' => array( 'readonly' => true ),
            'public'      => true,                   // 7.1 起统一暴露标志
        ),
    ) );
} );
```

- 命名：`vendor/ability`，只允许小写字母数字、连字符与斜杠（正则 `^[a-z0-9-]+/[a-z0-9-]+$`）；分类 slug 正则 `^[a-z0-9]+(?:-[a-z0-9]+)*$`
- input/output schema 用 JSON Schema（WP 实现 draft-04 子集，参考 REST schema 文档）；有入参/返回值时 schema 是强制的
- **`meta.public`（WP 7.1）**：统一对外暴露意图，REST 生效规则 `show_in_rest ?? public ?? false`；MCP Adapter 从新版起尊重该标志
- **暴露 ≠ 授权**：`public` 只管可发现性，执行仍必须过 `permission_callback`，永远用真实 capability
- 调用：`WP_Ability::execute()`（支持 ability 组合，一个 ability 调另一个）
- 官方参考：`developer.wordpress.org/reference/functions/wp_register_ability/`；官方 AI 插件（wordpress.org 搜 "AI"）内含 Alt Text、摘要等大量 ability 实现可作范例

### 三类注册错误的排查顺序

**注册错了不会让插件 fatal，只是安静地少一个 ability**——站点照常运行、前台无异常，只有调用该 ability 时才发现"不存在"。因此排查要按下面的顺序逐个排除：

| 症状 | 根因 | 判定方式 |
|---|---|---|
| 分类未注册 | `wp_register_ability_category()` 没调，或挂在 `wp_abilities_api_init`（错钩子） | 分类必须挂在 `wp_abilities_api_categories_init` |
| ability 注册返回 `null` | `wp_register_ability()` 不在 `wp_abilities_api_init` 动作内 | 严格用 `doing_action( 'wp_abilities_api_init' )` 自检 |
| ability 完全查不到 | 上面任一错误，或 `category` 指向未注册的 slug | 先 `wp_has_ability_category()` 再 `wp_has_ability()` |

**自查顺序**：先确认分类已注册 → 再确认 ability 挂在正确动作 → 再确认必填参数齐全 → 最后看 slug/name 正则。

> `scripts/wp_stub.php` 存根已内置这三类校验：分类未注册、分类挂错钩子都会直接 `exit 1` 并打印原因；`scripts/self_test.py` 中有对应的负向夹具回归，保证存根本身不会"永远通过"。
>
> 注意 `wp_register_ability_category(` 是 `wp_register_ability(` 的**前缀**，写静态检查脚本时若用 `strpos()` 找首次出现位置会命中错误位置（注释里的这两个词也会干扰）；必须先剥离注释，再按**方法定义顺序**比较。

## 4. MCP Adapter

把已注册 abilities 暴露为 MCP 工具，AI 编码助手（Claude Code、Cursor 等）可直接操作站点。插件侧无需特殊代码，注册好 ability 并设 `meta.public` 即可被其消费。

## 5. 实战模式：AI Provider 连接器插件（国内五家）

以 ai-provider-for-china（知更鸟 / zmingcx.com）为范本，结构为：

1. 每个 provider 一个类继承 `WordPress\AiClient\Providers\ApiBasedImplementation\AbstractApiProvider`：实现 `baseUrl()`、`createModel()`、`createProviderMetadata()`、`createProviderAvailability()`、`createModelMetadataDirectory()`
2. 模型类继承 `AbstractOpenAiCompatibleTextGenerationModel`，覆写 `createRequest()` 指向自家端点；国内厂商普遍不支持 `json_schema` response_format，统一 trait 移除该参数
3. 模型元数据目录实现 `ModelMetadataDirectoryInterface`（静态模型清单 + 能力声明）
4. `AiClient::defaultRegistry()->registerProvider( ... )` 在 `init` 注册
5. 可用性检查用真实请求打 `/models` 端点，读 `connectors_ai_{slug}_api_key` 选项；密钥只发往官方域名
6. 如需自动批准连接器使用：`WordPress\AI\Connector_Approval\Approvals_Store`（`set_approval( $basename, $slug, true )`）
7. 安全红线同样适用：endpoint 可被管理员改（中转/代理场景属有意设计），但必须受 `manage_options` + nonce 保护
