# WBS-AICli

Ubuntu / Debian 系统上的 **Codex 与 Claude Code 交互安装、API 配置管理与启动工具**。

版本：`2.0.1`。支持官方账号登录、官方 API、GLM、Kimi、DeepSeek 和自定义兼容接口。

```text
~/.bashrc 函数
    └─ 固定路径的 WBS-AICli/ai_cli_setup.sh
        └─ 交互复用 / 切换 / 编辑 API 配置
            └─ 在调用者当前业务目录启动 Codex 或 Claude Code
```

## 文档

- GLM / Kimi / DeepSeek 配置教程：**[PROVIDERS_zh.md](PROVIDERS_zh.md)**。
- 官方资料索引：**[SOURCES.md](SOURCES.md)**。
- 版本更新：**[CHANGELOG.md](CHANGELOG.md)**。

## 一次性设置

需要 Linux / Ubuntu / Debian、Python 3.10+ 和 Bash。请将工具放在长期保留的目录，以普通用户运行。

下载 GitHub 的源码 ZIP 并解压，或克隆发布分支：

```bash
git clone --branch main --single-branch https://github.com/AllenW-Hiter/WBS-AICli.git
cd WBS-AICli
```

已有工具目录时，直接进入该目录进行设置：

```bash
bash ai_cli_setup.sh doctor
bash ai_cli_setup.sh self-test
bash ai_cli_setup.sh install-shell
source ~/.bashrc

type aicli aicodex aiclaude
```

Bash 入口调用系统 `/usr/bin/python3`，无需为管理器安装 pip、npm 或 Conda 环境。不要 `sudo bash`；安装缺失系统依赖和上游客户端时会分别请求确认。安装器先下载到本地，供查看与确认后执行。

函数安装到 `~/.bashrc`。Zsh / Fish 用户可直接运行 `bash /工具绝对路径/ai_cli_setup.sh ...`，或进入 Bash 后加载函数。保留完整工具目录，移动目录后需要重新运行 `install-shell`。

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

首次创建配置时，按提示选择平台、配置名、模型和 Key 保存方式。之后运行 `aicodex` / `aiclaude`，回车复用当前配置，或在菜单中选择其他配置、新建或编辑。改变接口地址或鉴权方式后，需要重新输入 Key。

## 常用命令

```bash
aicli current                       # 查看两款客户端的当前配置
aicli list                          # 查看全部已保存配置，不显示 Key
aicli edit codex                     # 编辑 Codex 当前配置
aicli edit claude                    # 编辑 Claude 当前配置
aicli doctor                        # 只读环境检查
aicli --dry-run install both         # 预览安装流程
aicli test codex glm                 # 经确认后发送一次基础 API 测试
aicli restore                       # 恢复配置备份

# 指定已有配置，直接启动并传递原生客户端参数
aicli run codex glm -- exec '说明这个项目的结构'
aicli run claude deepseek -- -p '说明这个项目的结构'

# 从旧版 ~/.config/ai-cli-toolkit 导入配置
aicli import-v1

# 移除 Bash 函数入口
aicli remove-shell
unset -f aicli aicodex aiclaude
```

示例中的 `glm`、`deepseek` 需替换为实际保存的配置名。管理器参数 `--dry-run`、`--config-dir` 放在子命令前。

## 本地配置与密钥

```text
WBS-AICli/
├── README.md
├── ai_cli_setup.sh
├── ai_cli_manager.py
└── config/                  # 首次配置时创建的本机私有数据
    ├── state.json
    ├── profiles/            # API Key、原生 CLI 配置 / 登录 / 历史
    ├── backups/             # 可能包含旧 Key
    └── shell-backups/       # 可能包含原 .bashrc 中的秘密
```

配置保存在工具项目的 `config/`，不是正在开发的业务仓库。目录权限为 `700`，敏感文件为 `600`；这是访问控制，密钥仍为本地明文。选择不保存 Key 时，启动时隐藏输入。

覆盖配置会备份旧 Key；关闭保存不会清除历史备份。Claude 会话使用含 Key 的临时设置，正常退出会清理，强制终止可能留下 `session-*`。停止相关会话后再检查残留或编辑、恢复其配置。

不要将 `config/` 上传 GitHub、整体打包分享或交给不可信程序。怀疑 Key 泄漏时，应在服务商控制台吊销或轮换。移除函数入口不会删除客户端、配置或备份。

更新时保留 `config/`。整体移动工具目录后，需要重新安装函数；Codex 使用模型目录的配置还需运行 `aicli edit codex 配置名` 并保存，以更新其中的绝对路径。

## 接口与配置说明

Codex 配置使用 Responses API，Claude Code 配置使用 Anthropic Messages 兼容接口。自定义服务商必须支持对应协议；仅支持 Chat Completions 的地址不能直接套用。平台、地区和套餐必须与 Key 匹配，具体见服务商教程。

每份配置使用独立的客户端配置目录，部分登录状态、会话历史、插件和用户设置也会分开。项目设置、组织策略及原生命令行覆盖仍可能影响最终行为，首次启动请检查客户端 `/status`。

运行中的会话不会热切换 API，客户端内部的 `/model` 或临时参数也不会反向更新本工具的默认配置。要修改下次启动的选择，请使用管理器菜单或 `edit`。

`self-test` 提供离线自检。Python 3.10 缺少 `tomllib`，会跳过一项 TOML 解析检查。基础 API 测试只验证短文本的非流式协议响应；真实客户端安装、流式响应、工具调用及服务商权限需要在实际环境中确认。模型预设来自 2026-10-06 文档快照，以当前账号授权为准。
