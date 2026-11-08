# WBS-AICli

Ubuntu / Debian 系统上的 **Codex 与 Claude Code 交互安装、API 配置管理与启动工具**。

版本：`2.0.1`。由 AI CLI Toolkit v2 更名而来，保留原使用方式和配置兼容性。

```text
~/.bashrc 函数
    └─ 固定路径的 WBS-AICli/ai_cli_setup.sh
        └─ 交互复用 / 切换 / 编辑 API 配置
            └─ 在调用者当前业务目录启动 Codex 或 Claude Code
```

## 文档

- 完整使用与密钥风险说明：**[README_zh.md](README_zh.md)**。
- GLM / Kimi / DeepSeek 配置教程：**[PROVIDERS_zh.md](PROVIDERS_zh.md)**。
- 官方资料索引：**[SOURCES.md](SOURCES.md)**。
- 版本更新：**[CHANGELOG.md](CHANGELOG.md)**。

## 一次性设置

先把程序放在长期保留的工具目录。如果已初始化 Git 仓库，导入源码后在其根目录执行以下命令，不要再 clone 或 git init。

```bash
bash ai_cli_setup.sh doctor
bash ai_cli_setup.sh install-shell
source ~/.bashrc

type aicli aicodex aiclaude
```

需要 Python 3.10+；Bash 入口调用系统 `/usr/bin/python3`，不需要为管理器安装 pip、npm 或 Conda 环境。默认以普通用户运行；AutoDL 等默认 root 的环境按下方方式显式启用。上游客户端安装与系统依赖安装有独立确认流程。

### AutoDL 等 root 环境

`--allow-root` 放在子命令前。用它安装 Shell 函数后，入口会保留该选项，日常命令无需重复添加：

```bash
bash ai_cli_setup.sh --allow-root install-shell
source ~/.bashrc

aicli install both
aicli configure codex
aicli configure claude
aicodex
```

不安装函数时，可以直接执行 `bash ai_cli_setup.sh --allow-root install both`、`bash ai_cli_setup.sh --allow-root start codex` 等命令。旧式 `launchers` 同样会保留显式传入的 `--allow-root`。

root 下安装缺失依赖直接调用 `apt-get`，不要求 `sudo`；普通用户仍使用 `sudo`。路径沿用当前用户的 HOME，通常为 `/root/.local/bin` 和 `/root/.bashrc`，API 配置仍默认保存在工具目录的 `config/`。安装器与原生客户端会继承 root 权限；该选项只控制本管理器的 root 检查，客户端自身的权限检查仍然生效。

## 日常使用

```bash
aicli                       # 总菜单
aicli install both          # 尚未安装两款客户端时使用
aicli configure codex       # 新建 Codex API / 官方登录配置
aicli configure claude      # 新建 Claude Code API / 官方登录配置

cd /path/to/your/project
aicodex                     # 回车复用当前配置，或选择其他接口
aiclaude
```

函数不改变调用者工作目录，不把 API Key 全局写入 `.bashrc`。Key 经隐藏输入；选择保存后以明文 `600` 权限存入本工具 `config/`。Codex、Claude 分别记录自己的选择。新建配置不自动联网试用；基础 API 测试需要单独确认，可能计费。

## 仓库与本地状态必须分开

```text
WBS-AICli/
├── README.md
├── ai_cli_setup.sh
├── ai_cli_manager.py
├── .gitignore
├── .gitattributes
├── 使用文档和 SHA256SUMS
└── config/                  # 本机私有运行状态，不提交 Git
    ├── state.json
    ├── profiles/            # API Key、原生 CLI 配置 / 登录 / 历史
    ├── backups/             # 可能包含旧 Key
    └── shell-backups/       # 可能包含原 .bashrc 中的秘密
```

`.gitignore` 不是加密，也不会移除已经跟踪的秘密。不要 `git add -f config`，不要把使用后的目录整体打包发布，不要让不可信 Agent 读取 `config/`。怀疑 Key 泄漏时，应在对应平台立即吊销或轮换，而不是仅删除本地文件。

## 命名兼容性

仓库和对外名称是 **WBS-AICli**。命令保留 `aicli`、`aicodex`、`aiclaude`，实现文件保留 `ai_cli_setup.sh`、`ai_cli_manager.py`。

源码里少数 `AI-CLI-TOOLKIT` 标记、`AI_CLI_API_KEY` 和 `~/.config/ai-cli-toolkit` 是兼容接口，不是漏改名称。不要全仓搜索替换：旧 Shell 标记需要被识别，Codex 已保存配置仍引用原环境变量，`import-v1` 也需要旧路径。

## 验证边界

`doctor` 提供只读环境检查；`aicli test 软件名 配置名` 在确认后发送一次基础 API 探测，仅验证短文本的非流式协议响应。真实安装、流式响应、工具调用及服务商权限需要在实际环境中确认。模型预设来自原文档快照，以当前账号授权为准。

仓库只保留运行程序、使用文档和校验清单。测试脚本、开发报告、AI 工具配置与编辑器缓存已纳入 Git 忽略规则；运行时配置和密钥也不提交。
