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
- **特性探测（不发请求、零成本、纯确定性判断）**：
  - `$builder->is_supported_for_text_generation()` / `is_supported_for_image_generation()` / `is_supported_for_text_to_speech_conversion()` / `is_supported_for_speech_generation()` / `is_supported_for_video_generation()` / `is_supported_for_music_generation()` / `is_supported_for_embedding_generation()` / `is_supported()`。展示 AI UI 前先探测
  - **`wp_supports_ai()` 是零参数函数**（官方签名 `wp_supports_ai(): bool`），判断当前环境是否允许使用 AI；受 `WP_AI_SUPPORT` 常量与 `wp_supports_ai` 过滤器控制。**它不接受 feature 参数**——能力维度要用 builder 上的 `is_supported_*()`
  - **嵌入（embedding）走独立入口**：`wp_ai_client_embedding( ...$input )` 返回 `WP_AI_Client_Embedding_Builder`，**自 WP 7.2.0 起**才提供。嵌入**不会自动选模型**——必须先用 `using_model()` 或 `using_provider_model()` 显式指定，且不同模型产出的向量不可互相比较。该 builder 只有无参的 `is_supported()`（不像 prompt builder 有 `is_supported_for_embedding_generation()`）
- **阻断提示**：`wp_ai_client_prevent_prompt` 过滤器可阻止提示词执行（返回 `true` 即阻止）；被阻止时 `is_supported_*()` 返回 `false`，生成方法返回 `WP_Error`（error code 为 `prompt_prevented`，status 503）
  - 过滤器回调**收到的是 builder 的克隆**（只读快照），参数为 `( bool $prevent, WP_AI_Client_Prompt_Builder $builder )`
  - 若 `wp_supports_ai()` 为 false（AI 被关闭），**错误码同样是 `prompt_prevented`**，但消息是 "AI features are not supported in this environment."——排查时要区分这两种成因
  - 另注意：**底层抛异常时**（网络错误、SDK 异常），`is_supported_*()` 同样返回 `false`，生成方法返回 `WP_Error`——所以 `false` 不一定意味着"不支持"，也可能意味着"调用失败了"
- **方法命名是 snake_case**：`WP_AI_Client_Prompt_Builder` 通过魔术方法 `__call` 把 snake_case 代理到底层 SDK 的 camelCase 方法。但**返回的结果对象是 SDK 的原生对象，方法是 camelCase**——这是最容易踩的边界
- **把 abilities 暴露给模型**：`->using_abilities( 'my-plugin/my-ability', ... )` 会把已注册的 ability 转成模型的 function declaration（函数名加 `wpab__` 前缀），模型即可直接调用你的 ability

模型来源：站点管理员在 **Settings > Connectors** 配置的官方 provider 插件（OpenAI / Anthropic / Google，以及第三方如国内五家连接器）。插件不自己存 Key、不自己写 HTTP 客户端。

## 2. Connectors API（统一凭证层）

- 站点侧：Settings > Connectors 一个页面存所有外部服务 API Key，"配置一次，处处可用"
- **内置连接器 ID（无任何前缀）**：`anthropic`（Claude）、`google`（Gemini）、`openai`（GPT）、`akismet`（非 AI，type 为 `spam_filtering`）。
  官方 provider 插件文件名分别是 `ai-provider-for-anthropic` / `ai-provider-for-google` / `ai-provider-for-openai`——**插件目录名不是连接器 ID**，别把两者混用
- 注册自己的连接器（挂 `wp_connectors_init`；注册表在 `init` 优先级 15 初始化，该动作在此之后触发）：

```php
add_action( 'wp_connectors_init', function ( WP_Connector_Registry $registry ): void {
    if ( $registry->is_registered( 'my_service' ) ) { return; }
    $registry->register( 'my_service', array(
        'name'        => __( 'My Service', 'my-plugin' ),
        'description' => __( 'Syncs content with My Service.', 'my-plugin' ),
        'type'        => 'content_sync',
        'authentication' => array(
            'method'          => 'api_key',          // 'api_key' | 'application_password' | 'none'
            'credentials_url' => 'https://example.com/account/api-keys',
            'setting_name'    => 'my_plugin_my_service_api_key',  // 省略则自动生成
            'constant_name'   => 'MYPLUGIN_API_KEY',  // 可选：PHP 常量来源
            'env_var_name'    => 'MYPLUGIN_API_KEY',  // 可选：环境变量来源
        ),
        'plugin'      => array(
            'file'      => 'my-plugin/my-plugin.php',  // 相对插件目录的路径
            'is_active' => static function (): bool { return defined( 'MY_PLUGIN_VERSION' ); },
        ),
    ) );
} );
```

- **消费**：`wp_is_connector_registered( 'openai' )` → `wp_get_connector( 'openai' )` 返回**元数据**数组（键：`name`、`description`、`type`、`authentication`，可选 `logo_url`、`plugin`），未注册时返回 `null`；`wp_get_connectors()` 列全部（以 ID 为键）
  - ⚠️ **返回的连接器数据里没有 `base_url`，也不含明文 API Key**——密钥要自己按 `authentication.setting_name` / `constant_name` / `env_var_name` 去取，别指望 `wp_get_connector()` 直接给你密钥
- **ID 规则** `/^[a-z0-9_-]+$/`；注册表拒绝重复 ID；覆盖元数据需先 `unregister` 改完再 `register`，且先 `is_registered` 检查（对不存在的 ID 调 `unregister` 会触发 `_doing_it_wrong`）
- **`setting_name` 省略时自动生成**为 `connectors_{type}_{id}_{method}`（连字符归一化为下划线），例如 type=`ai_provider`、id=`deepseek` → `connectors_ai_deepseek_api_key`
- **API Key 读取优先级**：环境变量 → PHP 常量 → 数据库选项。三者都拿不到才视为未配置
- **AI provider 连接器受 `wp_supports_ai()` 门控**（可被 `WP_AI_SUPPORT` 常量或 `wp_supports_ai` 过滤器关闭）；当 `type` 为 `ai_provider` 且 `wp_supports_ai()` 为 false 时，`register()` **静默返回 `null`**（不报 `_doing_it_wrong`），所以 AI 插件必须特性探测
- **AI provider 连接器是自动发现的**：provider 插件只要注册进 WP AI Client 的 provider registry，Connectors API 就会自动建好连接器，**不要手动重复注册**。`wp_connectors_init` 主要用于注册非 AI 连接器或覆盖既有连接器的元数据

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
- **必填参数**（官方标注 Required，缺一即注册失败）：`label`、`description`、`category`、`execute_callback`、`permission_callback`
  - ⚠️ **版本演进**（`wp_register_ability()` 的 `@since` 标注）：
    - `category`：**自 7.2.0 起可选**，省略时落到内置的 `uncategorized` 分类（这是一个"逃生舱"分类，给简单或过渡性场景用）。自定义分类仍必须先经 `wp_register_ability_category()` 注册
    - `permission_callback`：**自 7.2.0 起**，若提供了非空的 `required_capabilities` 列表则可省略——`required_capabilities` 里的每个能力都会在 `permission_callback` 之前用 `current_user_can()` 检查
    - `ability_class`（可选）：指定自定义 `WP_Ability` 子类；用自定义类时，核心**不再强制**`execute_callback` / `permission_callback` 的注册要求（校验责任转移给子类）
- input/output schema 用 JSON Schema（WP 实现 draft-04 子集，参考 REST schema 文档）；有入参/返回值时 schema 是强制的
- **`meta.public`（WP 7.1）**：统一对外暴露意图，REST 生效规则 `show_in_rest ?? public ?? false`（`??` 语义：显式 `false` 会被保留，不视为缺失）；MCP Adapter 从新版起尊重该标志
- **暴露 ≠ 授权**：`public` 只管可发现性，执行仍必须过 `permission_callback`，永远用真实 capability
- 调用：`WP_Ability::execute()`（支持 ability 组合，一个 ability 调另一个）
- 官方参考：`developer.wordpress.org/reference/functions/wp_register_ability/`；官方 AI 插件（wordpress.org 搜 "AI"）内含 Alt Text、摘要等大量 ability 实现可作范例

### REST 端点与 HTTP 方法由 annotations 决定（易漏）

Abilities API 自动暴露 REST 路由，插件**不需要自己写 `register_rest_route()`**：

```
GET    /wp-json/wp-abilities/v1/abilities            # 列表（可按 category / namespace / annotations 过滤）
GET    /wp-json/wp-abilities/v1/abilities/{name}     # 单个
GET|POST|DELETE /wp-json/wp-abilities/v1/abilities/{name}/run
```

**`run` 端点用哪个 HTTP 方法由 `meta.annotations` 决定，不是随便选**：

| annotations | 客户端应使用 |
|---|---|
| `readonly: true` | **GET**（只读能力必须用 GET，这是要求不是建议） |
| `destructive: true` **且** `idempotent: true` | **DELETE** |
| 其余情况 | **POST** |

⚠️ **DELETE 需要两个标注同时为 true**。官方 `WP_REST_Abilities_V1_Run_Controller::validate_request_method()` 的判定是 `readonly` 优先，其次 `destructive && idempotent` **同时**成立才用 DELETE。只写 `destructive: true` 而不写 `idempotent: true`，会落回 **POST**（不是 DELETE）——这与直觉相反，务必两个都写。

- 路由注册用的是 `WP_REST_Server::ALLMETHODS`（因为注册路由时插件还没注册 ability，官方注释解释了这个取舍），**方法不匹配不会 404，而是返回 405** `rest_ability_invalid_method`
- GET / DELETE 的 `input` 放在 URL 编码的 `input` 查询参数里；POST 放在 JSON body 的 `{"input": {...}}`
  - 推论：**`input` 是长文本的能力不要标 `readonly: true`**——那会强制走 GET，长内容塞进 URL 查询串会被服务器截断，且语义上"生成类"操作本就不是幂等的
- **所有 Abilities REST 端点都要求已认证用户**——匿名用户连"有哪些 ability"都看不到。会话 cookie、应用密码（外部集成首选）、自定义认证插件都可以
- 常见错误码：`ability_invalid_input`、`ability_invalid_permissions`（403）、`ability_invalid_output`、`ability_missing_input_schema`、`ability_invalid_permission_callback`、`ability_callback_exception`
- REST 层错误码：`rest_ability_not_found`（404）、`rest_ability_invalid_method`（405）、`rest_ability_cannot_execute`
- 客户端应当**先读取 ability 元数据再决定方法**，不要按名字硬编码

### WP 7.1 新增的执行生命周期过滤器

7.1 给 `WP_Ability::execute()` 加了 **6 个**过滤器（此前只有 `wp_before_execute_ability` / `wp_after_execute_ability` 两个 action，只能观察不能干预）：

| 过滤器 | 时机 | 用途 |
|---|---|---|
| `wp_pre_execute_ability` | 流水线最前，在归一化/校验/鉴权之前 | 返回非原值即**短路**整个执行（维护模式、限流、缓存、测试 mock） |
| `wp_ability_normalize_input` | schema 默认值应用后、校验前 | 注入上下文元数据、补充 JSON Schema 表达不了的默认值 |
| `wp_ability_validate_input` | 输入校验阶段 | 干预/收紧 schema 校验结论；**只在定义了非空 `input_schema` 时才触发** |
| `wp_ability_permission_result` | `permission_callback` 执行后 | 追加授权规则；**返回 `true` 可以推翻原回调的拒绝，需谨慎** |
| `wp_ability_execute_result` | 回调返回后、输出校验前 | 改写/脱敏最终结果 |
| `wp_ability_validate_output` | 输出校验阶段 | 干预输出 schema 校验结论 |

- 执行顺序：`wp_ability_invoked` → `wp_pre_execute_ability` → `normalize_input()` → `wp_ability_normalize_input` → `validate_input()` → `wp_ability_validate_input` → `check_permissions()` → `wp_ability_permission_result` → `wp_before_execute_ability` → 回调 → `wp_ability_execute_result` → `validate_output()` → `wp_ability_validate_output` → `wp_after_execute_ability`
- `wp_pre_execute_ability` 的短路判定靠一个**哨兵对象**（`WP_Filter_Sentinel`）：只有返回值与哨兵**不同**才算短路，因此要继续正常执行必须**原样返回收到的 `$pre`**（不能返回 `null`/`false`——那会被当成短路并原样返回给调用方）
- `wp_ability_permission_result` 的返回值有**安全默认**：只有 `bool` 或 `WP_Error` 会被接受，**其他任何返回值都被强制转为 `false`**（即拒绝）。想放行必须显式返回 `true`
- 这 6 个过滤器对**全站每个 ability 都会触发**（`wp_ability_validate_input` / `wp_ability_validate_output` 例外，只在该 ability 定义了相应 schema 时触发），回调里务必先按 `$ability_name` 判断目标
- 另有 `wp_ability_invoked` action 在最开头触发（原始输入，适合做审计日志）；但它拿到的是**未归一化的原始输入**，可能含凭证或隐私数据，不要无差别记录
- `wp_get_abilities()` 在 7.1 起支持按 `category` / `namespace` / `meta` 过滤，并新增 `wp_get_abilities_item_include`、`wp_get_abilities_result` 两个过滤器（7.2 起还可用等价的 `item_include_callback` / `result_callback` **参数**，以及 `has_required_capabilities` 布尔参数用来排除无权限要求的能力）

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

把已注册 abilities 暴露为 MCP 工具，AI 编码助手（Claude Code、Cursor、VS Code、ChatGPT 等）可直接操作站点。

- **它不是 WordPress 核心的一部分**，而是独立包（`github.com/WordPress/mcp-adapter`），2026-10-07 起也已上架 wordpress.org 插件目录（v0.7.0，要求 WP 6.9+ / PHP 7.4+）。之所以留在核心外，是因为 MCP 规范仍在变动
- **默认是保守的：WordPress abilities 默认私有**。要让某个 ability 被 MCP 暴露，需显式设置 `meta.public`（或通道专用的 `meta.mcp.public`）
- 插件侧不需要写任何 MCP 代码：注册好 ability 并设 `meta.public` 即可被消费；Adapter 负责 HTTP / STDIO 传输，并且**仍然会执行每个 ability 的 `permission_callback`**
- `meta.public` 只表达"你的插件愿意被外部调用"的意图，**不负责安装服务器、不负责选传输方式、也不负责连接某个客户端**——不要为了"上 MCP"给站点强加依赖

## 5. 实战模式：AI Provider 连接器插件（国内五家）

以 ai-provider-for-china（知更鸟 / zmingcx.com）为范本，结构为：

1. 每个 provider 一个类继承 `WordPress\AiClient\Providers\ApiBasedImplementation\AbstractApiProvider`：实现 `baseUrl()`、`createModel()`、`createProviderMetadata()`、`createProviderAvailability()`、`createModelMetadataDirectory()`
2. 模型类继承 `AbstractOpenAiCompatibleTextGenerationModel`，覆写 `createRequest()` 指向自家端点；国内厂商普遍不支持 `json_schema` response_format，统一 trait 移除该参数
3. 模型元数据目录实现 `ModelMetadataDirectoryInterface`（静态模型清单 + 能力声明）
4. `AiClient::defaultRegistry()->registerProvider( ... )` 在 `init` 优先级 5 注册（注册前先 `hasProvider()` 判重）
5. 可用性检查用真实请求打 `/models` 端点，读 `connectors_ai_{slug}_api_key` 选项；密钥只发往官方域名
6. 如需自动批准连接器使用：`WordPress\AI\Connector_Approval\Approvals_Store`（`set_approval( $basename, $slug, true )`）——该类不存在时需优雅降级（`class_exists()` 判断）
7. 安全红线同样适用：endpoint 可被管理员改（中转/代理场景属有意设计），但必须受 `manage_options` + nonce 保护
8. 可选：用 `wpai_preferred_text_models` 过滤器把已配置密钥的 provider 模型加入首选列表，让摘要等内置 AI 功能也能走国内 provider
