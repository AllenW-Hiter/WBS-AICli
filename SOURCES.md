# 官方来源索引

v1 服务商快照日期：2026-10-06；v2 同日复核 Codex 配置和 Claude 环境/设置机制。模型和端点是当日文档快照，不构成永久免费、持续可用或账号已获授权的保证。以下均为厂商官方文档；安装不使用第三方镜像。

| 标识 | 官方页面 | 用于核对 |
|---|---|---|
| S01 | https://developers.openai.com/codex/cli | Codex 官方 CLI、原生安装入口、登录 |
| S02 | https://developers.openai.com/codex/config-reference | Responses-only wire_api、env_key、自定义 provider、模型目录、审批与沙箱、WebSocket |
| S03 | https://learn.chatgpt.com/docs/config-file/environment-variables | CODEX_HOME 与配置目录 |
| S04 | https://code.claude.com/docs/en/setup | Claude 原生安装、stable/latest、用户目录、自动更新 |
| S05 | https://code.claude.com/docs/en/env-vars | CLAUDE_CONFIG_DIR、鉴权/模型/后端变量、宿主管理、禁用非必要流量的功能影响 |
| S06 | https://code.claude.com/docs/en/settings | 用户/项目/命令行/受管理设置及优先级 |
| S07 | https://docs.bigmodel.cn/cn/coding-plan/tool/codex | GLM Responses 端点、glm-5.3、Coding Plan、models.json |
| S08 | https://docs.bigmodel.cn/cn/guide/develop/claude | GLM Anthropic 兼容端点、Claude 模型映射 |
| S09 | https://platform.kimi.com/docs/guide/codex-kimi | Kimi 中国区 Responses、kimi-k3、Key 地区 |
| S10 | https://platform.kimi.com/docs/guide/claude-code-kimi | Kimi 中国区 Messages、模型档位、thinking 注意事项 |
| S11 | https://platform.kimi.ai/docs/guide/codex-kimi | Kimi 国际区 Responses、国际区端点 |
| S12 | https://platform.kimi.ai/docs/guide/claude-code-kimi | Kimi 国际区 Messages、上下文与轻量模型 |
| S13 | https://www.kimi.ai/academy/use-kimi-api-in-codex-and-claude-code | Kimi 原生 Responses / Messages 支持；页面标示更新于 2026-09-17 |
| S14 | https://www.kimi.com/code/docs/third-party-tools/claude-code.html | Kimi Code 编程套餐、coding 端点、x-api-key、k3-256k |
| S15 | https://api-docs.deepseek.com/quick_start/agent_integrations/codex/ | DeepSeek 原生 Responses、deepseek-flash / deepseek-v4-pro、模型目录 |
| S16 | https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/ | DeepSeek Anthropic 端点、Claude 模型映射及上下文 |
| S17 | https://code.claude.com/docs/en/cli-reference | --settings 普通文件要求与参数行为 |

## 安装源

```text
https://chatgpt.com/codex/install.sh
https://claude.ai/install.sh
```

安装脚本在用户明确同意下载时取回；本包不附带上游二进制或伪造上游校验值。保存的 SHA256 仅记录收到的脚本内容，不等同于独立供应链认证。

## 有意没有照抄的内容

服务商示例有时将密钥直接写进 TOML、Shell 或 JSON。本工具使用隐藏输入、Codex 环境变量和 Claude 会话级设置文件，并明确披露明文文件与备份的风险。

本工具未复制任何服务商长提示词模板，不采用自动跳过初始化、伪造客户端身份、禁用全部权限检查、全局 trust 所有目录等做法。模型目录仅包含已核对预设的最小元数据，其完整 Agent 行为仍应由真实运行验证。

部分历史文章仍使用已改变的安装方式、Node.js 下限、旧模型 ID 或 `wire_api="chat"`。遇到冲突时，应分别以客户端最新配置文档和服务商对应产品的接入文档为准，而不是将所有版本示例混在一起。

## v2 工作流参考

| 标识 | 官方页面 | 用途 |
|---|---|---|
| S18 | https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html | Bash 启动文件；另以真实 Bash 测试函数加载和参数转发 |
| S19 | https://developers.openai.com/codex/config-advanced | CODEX_HOME、原生状态位置 |

v2 重点复核 S02、S05、S06、S19。服务商模型与端点继续使用同日 v1 资料，不将此轮离线测试宣称为真实服务商 API 验证。
