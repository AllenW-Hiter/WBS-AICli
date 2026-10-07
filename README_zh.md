# WBS-AICli：Bash 函数入口 + 交互 API 切换 + 项目内保存

版本：2.0.1 · 2026-10-06 · Ubuntu 22.04 / 24.04 与相近 Debian 系 Linux · Python 3.10+

**这一版按以下工作方式组织：`~/.bashrc` 中的函数 → 固定工具目录中的脚本 → 交互选择已保存 API → 在调用者当前目录启动 Codex / Claude Code。**

“项目内保存”指本工具项目的 `config/`，不是你正在开发的业务代码仓库。不要将 API Key 放进业务仓库的 `.env`、`.bashrc` 或 Git。

> 从 v2 更名而来；日常命令、配置格式、密钥环境变量和旧管理标记保持兼容。已初始化 Git 仓库时，先看 `GIT_SETUP_zh.md`，不要再次 `git init`。

## 1. 一次性设置

请使用普通用户，不要 `sudo bash`。仅安装缺失的系统依赖时会单独请求 sudo。

先把整个工具包解压到一个不会随手删除的固定目录。例如在下载文件所在目录执行：

```bash
mkdir -p "$HOME/tools"
tar -xzf WBS-AICli-source.tar.gz -C "$HOME/tools"
cd "$HOME/tools/WBS-AICli"

# 只检查，不改配置，不联网请求模型
bash ai_cli_setup.sh doctor

# 安装交互函数：预览、确认、备份并修改 ~/.bashrc
bash ai_cli_setup.sh install-shell

# 仅需在这个已经打开的终端执行一次
source ~/.bashrc
```

也可以直接运行 `bash ai_cli_setup.sh`，在中文主菜单选择 **10：写入/更新 ~/.bashrc 交互函数**。ZIP 解压后的目录名称相同。

**正确路径是 `~/.bashrc`，不是 `~/bashrc`。** Bash 的交互式非登录 Shell 通常读取前者；登录 Shell 的读取链由 `.bash_profile` / `.profile` 决定。函数没有出现时，在 Bash 终端手动执行 `source ~/.bashrc`。本工具不修改登录配置或 Zsh/Fish 配置。[S18]

此后不需要再进入工具目录，也不要求把工具目录加入 PATH。工具的 Bash 入口会使用系统 `/usr/bin/python3 -B -I`，不会使用当前 Conda 环境中的 Python。

## 2. 日常只用三个入口

```bash
aicli       # 完整管理菜单：安装、配置、恢复、导入等
aicodex     # Codex 的交互 API 选择与启动
aiclaude    # Claude Code 的交互 API 选择与启动
```

例如：

```bash
cd ~/your-business-project
aicodex
```

菜单会显示类似：

```text
=== codex 交互启动 ===
工作目录（不会自动切换）：/home/yourname/your-business-project
配置目录：/home/yourname/tools/WBS-AICli/config
当前配置：glm | <已保存的模型> | <已保存的 Base URL>
API Key：使用已保存的 Key（不显示值）
  1. 使用当前配置启动（默认）
  2. 选择其他已保存配置并启动
  3. 新建/重新指定 API 配置
  4. 修改当前配置（地址 / 模型 / Key）
  5. 查看全部已保存配置
  0. 返回终端
选择 [1]:
```

已有当前配置时，**直接回车就使用该配置**。没有配置时，默认进入新建；已有若干配置但尚未选择当前配置时，默认进入选择。

Codex 和 Claude 各自记住自己的选择。例如 Codex 用 GLM、Claude 用 DeepSeek，彼此不覆盖。退出 CLI 后回到业务目录所在的 Shell；下一次运行交互入口继续显示已保存的选择。

> 不要把“不用进入工具目录”理解成“无需选择业务工作目录”。本工具不会自动 `cd`。在哪个目录调用，客户端就从哪个目录启动；显式传给原客户端的目录参数仍可改变它自己的工作目录。

## 3. 首次安装客户端、配置 API

已有客户端时可跳过安装，直接配置。

```bash
# 客户端安装：保留逐项下载、审阅和执行确认
aicli install both

# 为两款软件分别创建配置
aicli configure codex
aicli configure claude

# 之后在你的业务工作目录启动
aicodex
aiclaude
```

新建配置支持官方账号登录、官方 API、GLM、Kimi、DeepSeek 和自定义协议兼容接口。服务商、地区、套餐与接口区别见 **PROVIDERS_zh.md**；预设继承 v1 的 2026-10-06 文档快照，不保证所有账号或客户端版本都支持全部模型。

创建新 API 配置的步骤是：选择平台 → 配置名 → 模型及能力参数 → 选择是否保存 Key → 隐藏输入 Key → 确认保存。自定义接口另需填写 Base URL 和相应鉴权方式。

**v2 的 Key 保存选项默认是 `y`**，提示会明确告知这是本地明文、权限 `600`。最终确认保存后，下次启动直接读取已有 Key，不需要重复输入。也可以主动选择 `n`：只保存地址、模型等设置，启动时再隐藏输入。首次启动这种未保存 Key 的配置时，也会询问是否保存本次输入以便下次复用。

保存配置不自动发送 API 请求。单独测试必须再次授权，并可能计费：

```bash
aicli test codex glm
aicli test claude deepseek
```

这是固定短文本的基础协议探测，不读取业务项目文件，不等于工具调用、流式响应和完整 Agent 能力已验证。

## 4. 重新指定、保留或更换 Key

在 `aicodex` / `aiclaude` 菜单选择 4，或直接：

```bash
aicli edit codex          # 修改 Codex 当前配置
aicli edit claude         # 修改 Claude 当前配置
aicli edit codex glm      # 修改指定的已保存配置
```

未修改的字段直接回车。已有保存的 Key 且接口地址与鉴权方式不变时，新 Key 提示处直接回车可保留旧 Key；输入新值则替换。已有配置覆盖前会备份。

**改变 Base URL 或鉴权方式后，不能用回车自动复用旧 Key，必须重新输入。** 这是为了避免把原平台的凭据自动发给新地址。修改模型后不会继续套用原模型的目录、上下文等能力猜测。

选择 3 或 `configure` 可重新选择平台，使用不同配置名保留多份 API，例如 `glm-work`、`glm-personal`。Codex 和 Claude 的协议及端点可能不同，不会自动将一款客户端的整份配置复制给另一款。

当前配置名、启动时间、退出时间和退出码保存在 `config/state.json`，两款软件独立记录。配置在确认保存时就落盘，启动时再记住本次选择；不是等正常退出才保存。退出码不被当作“API 认证成功”的凭据。并发启动时，较早会话的退出记录不会覆盖较新会话的记录和选择。

**这里只记住本工具管理的配置。** 原生客户端会话中的 `/model`、临时 `--model` 或其他 CLI 配置覆盖，不会被自动反向同步成管理器的新配置。要改变本工具之后使用的默认模型，请使用 `edit`。

## 5. 写入 ~/.bashrc 的实际形式

自动生成的块类似下面这样，实际使用经过 Shell 引号处理的绝对路径，还包含路径不存在时的提示：

```bash
# >>> AI-CLI-TOOLKIT FUNCTIONS >>>
aicli() {
    command /bin/bash '/home/yourname/tools/WBS-AICli/ai_cli_setup.sh' "$@"
}
aicodex() { aicli start codex -- "$@"; }
aiclaude() { aicli start claude -- "$@"; }
# <<< AI-CLI-TOOLKIT FUNCTIONS <<<
```

不要照抄示例用户名；运行 `install-shell` 会根据实际目录生成。

`.bashrc` 只保存函数入口，**不保存 Key、模型配置或全局 provider 环境变量**。函数不 `cd`，不更改调用者的环境；参数按 `"$@"` 原样转发。原生 `codex` / `claude` 不被改成同名函数，也没有递归调用它们的风险。

每次安装会先预览，做 `bash -n` 语法检查，但不执行 `.bashrc` 内容；确认后备份并原子替换。只更新两个标记之间的块，其他内容保留；重复执行且内容相同时不会追加或产生多余备份。HOME 目录权限不会被顺带修改。

检测到重复/残缺标记、常见同名函数/别名定义、符号链接 `.bashrc`、组/其他用户可写权限或确认期间文件变化时会拒绝自动覆盖。不会递归执行所有被 `.bashrc` 引用的文件来排查命名冲突；入口行为异常时请用 `type aicli aicodex aiclaude` 检查是否还有其他地方定义了同名对象。

`.bashrc` 本身是链接文件的 dotfiles 布局不自动处理，以免改错真实目标；需自行决定将显示出的函数块放到哪个受管理源文件。

## 6. 接口切换的底层实现

这个工具不是 API 中转服务器，也不运行协议转换代理；它是本地的配置选择器和启动器。

**Codex**：每份配置有自己的 `codex/config.toml`。启动时为子进程设置 `CODEX_HOME`，API Key 通过 `AI_CLI_API_KEY` 交给 `env_key` 引用的 provider。TOML 保存 Base URL、模型和 `wire_api = "responses"`，不保存 API Key。当前 Codex 自定义 provider 要求 Responses 协议，而不只是 Chat Completions。[S02][S03]

**Claude Code**：每份配置有自己的 `claude/` 设置目录，启动时设置 `CLAUDE_CONFIG_DIR`。地址、模型与鉴权变量通过会话专用 `--settings` JSON 传入；根据服务商使用 `ANTHROPIC_AUTH_TOKEN` 或 `ANTHROPIC_API_KEY`。[S05][S06][S17]

启动器清理已知旧路由变量，但不清空项目需要的全部环境。只有这次 CLI 子进程使用所选路由，不会把它全局 export 到父终端。组织强制策略仍然有效；工具检测到 Claude provider 由宿主管理时会拒绝切换，不绕过策略。[S05][S06]

**配置目录隔离也会使部分用户级设置、会话历史和插件分开。** 全局 MCP、技能、插件及登录状态不会保证自动出现在新的独立配置中。原生客户端仍可能读取业务项目中的设置；命令行显式覆盖也可能影响最终模型，因此以客户端 `/status` 显示为准。[S03][S05][S06]

## 7. 文件与目录

首次运行后可能出现：

```text
WBS-AICli/
  ai_cli_setup.sh
  ai_cli_manager.py
  README_zh.md
  PROVIDERS_zh.md
  SOURCES.md
  CHANGELOG.md
  test_toolkit.py
  TEST_REPORT.txt
  SHA256SUMS
  .gitignore
  config/                          # 运行时创建，不在发行包中
    .lock
    state.json                     # 当前选择、最近一次启动/退出状态，不含本工具的 Key
    profiles/
      codex/glm/
        profile.json               # 地址、模型、保存方式等
        key.txt                    # 保存时才存在，明文 600
        codex/config.toml
        codex/models.json          # 部分已知模型才生成
      claude/deepseek/
        profile.json
        key.txt
        claude/settings.json       # 本工具常驻设置不含 Key
        session-.../settings.json  # 会话期临时文件，含 Key，600
    backups/                       # 覆盖配置前的快照，可能含旧 Key
    shell-backups/                  # 原 .bashrc 备份，可能含其原有秘密
    cache/installers/              # 下载的官方安装器及 SHA256
```

`config/` 目录设为 `700`，本工具的敏感文件设为 `600`。**这是访问控制，不是加密**；同一用户进程、root、恶意程序及不恰当的同步或备份仍可能读取凭据。不要向不可信 Agent 开放整个工具目录；本工具不是凭据隔离容器。

`.gitignore` 排除了 `config/`，但不能阻止 `git add -f`，也不会移除已经被 Git 跟踪的文件。不要将使用后的整个工具目录直接压缩发送或公开同步；排障时只提供去敏信息。发行包中不含任何用户真实 Key。

Claude 临时设置在正常返回、可处理的中断后清理；SIGKILL、断电和崩溃可能留下 `session-*`。停止相关会话后检查残留。客户端自己也可能存储认证状态或日志，本工具不承诺整个系统“密钥从不落盘”。

配置覆盖和恢复会备份旧 Key。改为不保存会删除当前 `key.txt`，不会擦除历史快照；需要用户自行管理。怀疑泄漏时应在服务商控制台吊销/轮换凭据。

## 8. 从 v1 迁移

新包无需重装已经存在的 Codex / Claude。安装函数并 `source ~/.bashrc` 后执行：

```bash
aicli import-v1
```

导入来源固定为旧版 `~/.config/ai-cli-toolkit`；目标是新项目的 `config/`。会询问确认，复制配置与已经保存的 Key，保留原文件；目标同名配置要单独确认覆盖，并先备份。

导入会重新生成 Codex 的绝对模型目录路径；不会直接复制旧路径。**不迁移会话历史、官方账号 OAuth 登录态或旧备份**。官方账号配置首次使用需重新登录，旧历史仍在旧目录。

原来的 `ai-cli`、`codex-glm` 等快捷文件仍可能指向旧版。新版推荐只使用 `aicli` / `aicodex` / `aiclaude`，避免混用两套配置。需要兼容旧式文件入口时，可以显式运行 `aicli launchers`；v2 的快捷文件改为指向当前工具项目，不再复制一套管理器。

## 9. 其他常用操作

```bash
aicli current                     # 查看两款软件当前选择，不显示 Key
aicli list                        # 查看所有已保存配置
aicli doctor                      # 环境检查，不运行真实 CLI 或 API
aicli --dry-run install both       # 预演安装
aicli --dry-run install-shell      # 预览函数安装，不写文件
aicli --dry-run start codex        # 预演交互启动，不读 Key
aicli restore                     # 恢复本工具管理的配置快照
aicli self-test                   # 离线测试，不安装真实客户端，不调用真实 API

# 这些仍先显示本工具的交互菜单，再将参数传给原生 CLI
aicodex exec '说明这个测试项目的结构'
aiclaude -p '说明这个测试项目的结构'

# 明确指定已保存配置、跳过选择菜单；未保存 Key 时仍需输入
aicli run codex glm -- exec '说明这个测试项目的结构'
aicli run claude deepseek -- -p '说明这个测试项目的结构'
```

`--dry-run` 和 `--config-dir` 是管理器参数，放在子命令前；不要写成 `aicodex --dry-run`。高级场景可用 `bash /绝对路径/ai_cli_setup.sh --config-dir /私有目录 ...`；默认无需设置。

恢复命令恢复 profile、Key 与客户端管理配置，不是整机备份，不恢复二进制、完整会话或官方登录态。备份包含绝对模型目录位置，默认用于原路径恢复，不作为跨路径迁移工具。

代理可在 `aicli` 主菜单 12 设置，只作用于该次管理器及其启动的子进程，不保存。退出菜单后不会让随后新开的 `aicodex` 自动继承刚才的临时代理；需要同一次代理上下文时，在该菜单内使用选项 8 启动。APT 经 sudo 的代理继承由系统配置决定。

## 10. 卸载入口、更新和移动目录

只移除函数入口：

```bash
aicli remove-shell
unset -f aicli aicodex aiclaude
```

第二行清除当前 Shell 已加载的函数；新终端将不再加载已删除的标记块。此操作不删除 API 配置、Key、备份或客户端。

查看/手动恢复 `.bashrc` 备份时，注意整文件恢复也会回退你之后的其他更改。正常只撤销本工具入口，优先使用 `remove-shell`。

更新本工具时，应保留现有 `config/`，仅更新程序、文档和测试文件；不要把含真实 Key 的旧目录无差别上传。更新后从实际安装目录重新执行 `bash ai_cli_setup.sh install-shell`。

建议保持工具目录固定。整体移动目录后，先重新注册函数；使用 Codex 模型目录配置时，还需要对相应配置运行 `aicli edit codex 配置名` 并确认保存，以重新生成原生配置中的绝对路径。仅修改 `.bashrc` 路径并不会自动修复所有旧备份中的路径。

正在运行的会话不会热切换 API。编辑、恢复同一份配置前，先结束使用它的会话；文件写入是单文件原子替换加管理器锁，不是覆盖所有文件与原生客户端写入的数据库事务。

## 11. 验证范围

本更名版重新执行 **97 项离线自动化测试**，包括真实 Bash 语法与函数转发测试、Python 3.10 语法解析、项目内配置、独立选择记忆、更新密钥、端点变化禁止旧 Key 自动复用、工作目录保留、管理标记幂等与 v1 导入等。详细结果和本轮附加检查见 `TEST_REPORT.txt`。

**没有在 Ubuntu 22.04/24.04 真机或虚拟机上验证上游在线安装，没有使用真实 Key 调用任何服务商，也没有做 ARM64 实机认证。** Python 3.10 的标准库没有 `tomllib`，在该版本运行自测时 TOML 解析测试会明确跳过，不因此要求安装 pip 包。

本轮更名不变更服务商预设，也不宣称重新完成供应商在线核验。预设继承原包的文档快照；实际模型权限和接口行为仍需使用自己的账号验证。
