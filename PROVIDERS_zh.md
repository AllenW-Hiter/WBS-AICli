# GLM / Kimi / DeepSeek 接入补充教程

本文件保留 v1 在 2026-10-06 核对的官方端点与模型预设，命令入口改为 v2。当前账号授权、套餐与上游兼容性需以真实平台为准；本轮未用真实 Key 复测。先阅读 [README.md](README.md) 的使用流程与密钥说明。

## 1. 先搞清楚：软件、模型、账号和接口是四件事

Codex CLI 和 Claude Code 是执行代码任务的客户端。把 Claude Code 指向 GLM，意味着**由 Claude Code 执行工作流程、GLM 提供模型推理**；不意味着买了 Claude 订阅，也不意味着获得了 Anthropic 官方模型。Codex 接入其他模型同理。

当前 Codex 自定义 provider 使用 **Responses API**，`wire_api = "responses"`；当前配置参考仅支持这一协议值。不要照旧教程改成 `wire_api = "chat"`。[S02]

Claude Code 的这些第三方直连方案使用 **Anthropic Messages 兼容接口**，不是普通 OpenAI Chat Completions。[S08][S10][S12][S14][S16]

```text
Codex             → 服务商的 Responses API
Claude Code       → 服务商的 Anthropic Messages 兼容 API
Chat Completions  → 不是上面两者的同义词
```

仅仅把 `/chat/completions` 改写成 `/responses` 或 `/messages`，不会自动完成协议转换。自建网关需要真正转换请求、SSE 事件、工具调用与结果、推理字段和错误结构。脚本不自动部署未经验证的转换网关，也不保证某个号称“OpenAI 兼容”的地址具备 Agent 能力。

与旧文章不同，截至本次核对，GLM、Kimi 开放平台、DeepSeek 都有官方 Codex 接入文档，可使用对应的原生 Responses 端点；不应笼统认为它们都必须经过转换代理。[S07][S09][S15]

## 2. 内置预设：先看平台，再选 Key

下表是 2026-10-06 文档快照，不是永久模型清单。模型是否开放、余额、套餐权限、地区与速率限制，以实际账号和服务商最新文档为准。向导可更改模型 ID；**更换模型后，不会继续套用原模型的上下文与能力假设**。

### Codex 预设

| 选择 | Base URL | 默认模型 | 凭据注意事项 |
|---|---|---|---|
| OpenAI 官方登录 | 官方客户端管理 | 官方默认 | 使用独立 `CODEX_HOME` 完成新的登录 |
| OpenAI 官方 API | `https://api.openai.com/v1` | 向导要求填写 | OpenAI API Key，与 ChatGPT 套餐不是同一计费入口 |
| GLM | `https://open.bigmodel.cn/api/v1` | `glm-5.3` | 按 GLM Codex 文档使用适用的 Coding Plan Key |
| Kimi 中国区开放平台 | `https://api.moonshot.cn/v1` | `kimi-k3` | 中国区开放平台 Key |
| Kimi 国际开放平台 | `https://api.moonshot.ai/v1` | `kimi-k3` | 国际区开放平台 Key，不跨区混用 |
| DeepSeek | `https://api.deepseek.com` | `deepseek-flash` | DeepSeek 平台 Key |
| 自定义 | 用户填写 | 用户填写 | 必须真实支持 Responses API |

GLM、DeepSeek 官方 Codex 指南包含模型目录配置。工具为已知预设生成最小 `models.json`，声明上下文、推理档位、工具类型等，未复制供应商长提示词模板。上下文填 0 或改为未知模型后不生成猜测性目录。目录字段和 CLI 版本有耦合，遇到模型目录读取错误应核对最新官方文档，而不是假定任何新旧版本都适用。[S07][S15]

### Claude Code 预设

| 选择 | Base URL | 主模型 / 轻量模型 | 鉴权方式 |
|---|---|---|---|
| Anthropic 官方登录 | 官方客户端管理 | 官方默认 | 客户端登录 |
| Anthropic 官方 API | `https://api.anthropic.com` | 向导要求填写 | `ANTHROPIC_API_KEY` |
| GLM | `https://open.bigmodel.cn/api/anthropic` | `glm-5.2[1m]` / `glm-4.7` | `ANTHROPIC_AUTH_TOKEN` |
| Kimi 中国区开放平台 | `https://api.moonshot.cn/anthropic` | `kimi-k3[1m]` / `kimi-k2.7-code` | `ANTHROPIC_AUTH_TOKEN` |
| Kimi 国际开放平台 | `https://api.moonshot.ai/anthropic` | 同上 | `ANTHROPIC_AUTH_TOKEN` |
| Kimi Code 编程会员 | `https://api.kimi.com/coding` | `k3-256k` | `ANTHROPIC_API_KEY` |
| DeepSeek | `https://api.deepseek.com/anthropic` | `deepseek-flash[1m]` / `deepseek-flash` | `ANTHROPIC_AUTH_TOKEN` |
| 自定义 | 用户填写 | 用户填写 | 在 Bearer Token 与 x-api-key 中选择 |

这些默认值分别来自各产品的接入指南，所以 **GLM 在两款客户端的默认模型名并不相同**，不是脚本拼写错误。`[1m]` 是相应 Claude Code 接入指南使用的上下文提示；基础 API 探测会去掉这个提示再提交模型 ID。[S08][S10][S12][S16]

### Kimi 特别容易选错

**Kimi 开放平台 API Key ≠ Kimi Code 编程会员 Key。** 中国区和国际区也有不同端点。先明确购买/开通的是哪一种，再选择菜单预设，不能只看到“Kimi”就随意交换 Key。[S09]–[S14]

本工具为 Kimi Code 会员只提供已核对的 Claude Code 预设；这不是在断言该套餐绝对不能支持其他客户端。Codex 接入请优先按 Kimi 开放平台官方 Responses 文档配置。需要使用其他套餐或新端点时，先核对官方声明，再选“自定义”。

Kimi 官方 Claude Code 指南提醒，`kimi-k2.7-code` 需要 thinking；本工具不主动关闭它。出现相关 400 错误时，检查项目或手动设置是否禁用了 thinking，不要只更换 Key。[S10][S12]

## 3. 从零到运行：GLM、Kimi、DeepSeek

下文配置命令可在工具目录执行；安装 Bash 函数后，可从任意目录用 `aicli` 代替 `bash ai_cli_setup.sh`。API Key 在服务商自己的控制台创建；**不要把 Key 发给聊天助手、贴进问题截图，或以明文参数写进 Shell 命令**。脚本会在需要时隐藏输入。

### 3.1 两款客户端使用 GLM

```bash
bash ai_cli_setup.sh install both

# 选择 GLM；配置名保留 glm。
bash ai_cli_setup.sh configure codex
bash ai_cli_setup.sh configure claude

# 查看不含密钥的配置摘要
bash ai_cli_setup.sh list
```

向导依次确认模型、上下文上限、Claude 的轻量模型与压缩窗口、推理强度和密钥保存方式。不确定的新模型参数可将上下文填 0、推理强度填 `auto`，而不是随意宣称支持一百万上下文。已有官方预设可以先保留，再按账号权限调整。

GLM 为 Codex 使用 `/api/v1`，为 Claude Code 使用 `/api/anthropic`。不要将旧 Chat Completions 示例中的 `/api/paas/v4` 或其他不同用途的地址直接填进上述预设。[S07][S08]

进入一个新建测试目录，再启动对应客户端：

```bash
mkdir -p "$HOME/ai-cli-smoke-test"
cd "$HOME/ai-cli-smoke-test"

# 按 README.md 安装 Bash 函数后，使用 aicodex / aiclaude 启动。
```

第一次建议让 Agent 只创建一个简单文本文件，再查看差异。先验证短任务、文件修改和工具调用，再用于真实项目；不要一开始就授予所有命令自动执行权限。

### 3.2 两款客户端使用 Kimi 开放平台

```bash
bash ai_cli_setup.sh configure codex
# 选择 Kimi 开放平台 / 中国区，配置名 kimi-cn。

bash ai_cli_setup.sh configure claude
# 选择同一地区的 Kimi 开放平台，配置名 kimi-cn。
```

国际区用户在两处选择 `kimi-global` 并使用国际区 Key。代码可通过两款客户端访问同一平台，但会话历史、客户端设置和上下文缓存并不会因此自动共享。

持有 Kimi Code 会员 Key 的用户：为 Claude Code 选择 `kimi-code`，不要填到 `kimi-cn` 或 `kimi-global`。默认 `k3-256k`；升级套餐所支持的其他 ID 需按当前账户说明填写。[S14]

### 3.3 两款客户端使用 DeepSeek

```bash
bash ai_cli_setup.sh configure codex
# 选择 DeepSeek，配置名 deepseek。

bash ai_cli_setup.sh configure claude
# 选择 DeepSeek，配置名 deepseek。
```

Codex 使用 Responses Base URL；Claude Code 使用 `/anthropic` Base URL。当前指南的主模型为 `deepseek-flash`，Codex 指南还包含 `deepseek-v4-pro` 示例；不要盲目沿用只针对旧型号的配置。[S15][S16]

工具的轻量探测只验证一条非流式响应，真正的代码编辑、多轮工具调用及长任务仍由实际 CLI 运行验证。


官方来源编号见 SOURCES.md。
