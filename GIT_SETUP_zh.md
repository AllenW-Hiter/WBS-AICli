# WBS-AICli：接入已初始化的 Git 仓库

适用前提：已完成 README 首次提交、`main` 分支、`origin` 和首次 push。下面不会重新初始化仓库、删除 `.git`、更改 origin 或强制推送。

## 1. 定位当前仓库

在之前执行 `git init` 的目录中运行：

```bash
git rev-parse --show-toplevel
git remote -v
git status --short
git log -1 --oneline
```

确认 origin 对应 `git@github.com:AllenW-Hiter/WBS-AICli.git`，目录确实是本项目。如果还有自己修改的未提交文件，先保存到仓库外的私有备份位置，再导入；不要把含 Key 的备份提交到 Git。

本地目录不必与仓库名相同。已有终端函数使用绝对路径，优先保留现有工作目录，或先决定最终固定目录，再安装函数。

## 2. 导入源码包

把 `WBS-AICli-source.tar.gz` 下载到本机。在原仓库根目录执行（压缩包位置按实际修改）：

```bash
REPO="$(git rev-parse --show-toplevel)"
ARCHIVE="$HOME/Downloads/WBS-AICli-source.tar.gz"

# 先分别确认输出和压缩包路径。
printf '仓库：%s\n压缩包：%s\n' "$REPO" "$ARCHIVE"
test -f "$ARCHIVE"
tar -tzf "$ARCHIVE"
```

确认后执行：

```bash
tar -xzf "$ARCHIVE" --strip-components=1 -C "$REPO"
cd "$REPO"
chmod +x ai_cli_setup.sh
sha256sum -c SHA256SUMS
```

源包顶层是 `WBS-AICli/`，`--strip-components=1` 将内容直接放入现有仓库，避免 `WBS-AICli/WBS-AICli/` 嵌套。包不包含 `.git/`、`config/` 或真实 Key；不会更改它们。但会覆盖同名源码和文档，包括初始的 README.md。已有自定义代码时，应先比较，不要盲目解压覆盖。

SHA256SUMS 对应这个发行包的原始内容；编辑源码后校验失败是正常的，不要将旧校验值宣称为新版本校验值。

## 3. 检查配置没有进入 Git

```bash
cat .gitignore
git check-ignore -v config/profiles/codex/example/key.txt
git ls-files -- config .env
git status --short
```

第一条检查 `/config/` 等规则。第二条检查规则匹配，不会创建或读取 Key 文件；应显示 `/config/`。第三条应无输出。`.gitignore` 只作用于未跟踪文件，不会清除已有跟踪记录。[G01][G02]

若 `git ls-files -- config .env` 有输出，先停止提交并检查是否曾进入历史。仅误暂存且从未提交时，可用 `git restore --staged -- config` 撤销暂存；已经提交的秘密不能靠改 `.gitignore` 清除。泄漏 Key 首先在服务商平台吊销/轮换，历史清理按 GitHub 指南处理，不要直接照抄强制推送命令。[G05]

## 4. 本地检查

```bash
bash -n ai_cli_setup.sh
bash ai_cli_setup.sh --version
bash ai_cli_setup.sh doctor
bash ai_cli_setup.sh self-test
```

版本应为 `2.0.1`。离线测试不安装真实客户端、不调用真实 API；Ubuntu 22.04 的 Python 3.10 缺少 tomllib，可跳过一个 TOML 解析检查，其余测试应通过。

## 5. 已有 v2 配置：在安装函数前处理

没有旧配置可跳过。本节只适用于把旧 v2 的完整私有 `config/` 移入一个尚未创建 config 的新工具目录。先退出正在使用这些配置的 Codex / Claude 会话。

```bash
# 修改为自己的旧工具目录。
OLD="$HOME/tools/ai-cli-toolkit-v2"

if [ ! -d "$OLD/config" ]; then
    printf '%s\n' '找不到旧 config：核对 OLD，未复制。'
elif [ -e "$REPO/config" ] || [ -L "$REPO/config" ]; then
    printf '%s\n' '目标 config 已存在：停止自动复制，避免覆盖或嵌套。'
else
    cp -a -- "$OLD/config" "$REPO/config"
    chmod 700 "$REPO/config"
fi
```

原来就在同一目录中的 config 不需要复制，源码包不会覆盖它。已经在新目录生成 config 的情况不要把旧 config 盲目合并进去；最稳妥的选择是保留原配置目录并在同一目录更新源码，或在新目录重新创建需要的配置。

整体复制会保留其中的状态、Key 和客户端文件，不保证原生客户端所有外部引用或旧会话都可跨目录迁移。不要删除旧目录，直到新入口和数据都验证完成。

## 6. 写入 / 更新 Bash 函数

```bash
cd "$REPO"
bash ai_cli_setup.sh install-shell
source ~/.bashrc
type aicli aicodex aiclaude
aicli current
```

安装前显示函数块、请求确认并备份。保留旧的 `AI-CLI-TOOLKIT` 起止标记是为了更新 v2 的现有块，不是遗漏更名。`aicli current` 的工具项目路径应指向当前 WBS-AICli 仓库，默认配置目录应为其 `config/`。

Bash 交互式非登录 Shell 读取 `~/.bashrc`；当前已打开的终端用 `source ~/.bashrc` 加载。不是所有终端配置都会自动读取它；这里不修改 `.profile` 或 Zsh/Fish 的文件。[G06]

### 复制过 v2 配置并改变路径后的必要动作

```bash
aicli list

# 例：对自己存在的每份 Codex API 配置分别执行。
aicli edit codex glm
```

保持不需修改的字段、Key 提示处回车保留原值，最终确认保存。这样重新生成 Codex 模型目录绝对路径。必须对实际存在且需要使用的每份 Codex API 配置执行；没有 glm 配置就换成实际名称。旧备份内的绝对路径不会被统一修复，不要把跨目录 restore 当作迁移工具。

只有 v1 的 `~/.config/ai-cli-toolkit` 配置时，应改用 `aicli import-v1`。它不是 v2 目录迁移命令，不导入官方登录态或历史。

## 7. 首次真实使用

已有原生客户端时跳过安装：

```bash
aicli install both
```

需要新建配置时：

```bash
aicli configure codex
aicli configure claude
```

在独立测试目录运行：

```bash
mkdir -p "$HOME/tmp/wbs-aicli-smoke"
cd "$HOME/tmp/wbs-aicli-smoke"
aicodex
# 退出 Codex 后再测试另一款。
aiclaude
```

确认工作目录、模型/服务商显示和权限提示。函数不会自动跳入工具仓库，也不会热切换已经运行的客户端。给第三方模型访问业务代码前，先自行确认代码和数据发送范围。

## 8. 暂存、审阅、提交、推送

回到仓库。首次采用显式文件列表，不把整个工作目录无差别加入暂存区：

```bash
cd "$REPO"
git add -- .gitignore .gitattributes \
  README.md README_zh.md GIT_SETUP_zh.md PROVIDERS_zh.md \
  SOURCES.md CHANGELOG.md TEST_REPORT.txt SHA256SUMS \
  ai_cli_setup.sh ai_cli_manager.py test_toolkit.py

git diff --cached --name-only
git diff --cached --stat
git diff --cached --check
git diff --cached

git ls-files -- config .env
```

`git diff --cached` 审阅的是将要提交的内容；按 `q` 可退出分页器。确认没有真实 Key、配置、认证、备份和会话数据，再执行提交。[G03][G04]

```bash
git commit -m "feat: import WBS-AICli interactive CLI manager"
git push origin dev
```

首次 upstream 已设置，无需再次 `remote add origin` 或 `git init`。若远程领先、权限或分支保护导致拒绝，先查看错误并保留本地提交，不要用 `git push --force` 硬推。

完整源码和开发文档提交到 `dev`。发布到 `main` 时保留程序、自检脚本及使用文档，精简 README，并排除 `README_zh.md`、本 Git 指南和 `TEST_REPORT.txt`；重新生成仅包含发布文件的 `SHA256SUMS`。两分支都不提交本地 `config/` 或编辑器缓存。

## 9. 后续开发

先完成这一份可运行基线，再考虑重构目录、增加新命令或 CI。日常修改时：

```bash
cd "$REPO"
bash ai_cli_setup.sh self-test
git diff
# 只暂存本次确实修改的源码或文档。
git add -- ai_cli_manager.py test_toolkit.py
git diff --cached
git commit -m "fix: describe the actual change"
git push origin dev
```

不要执行 `git clean -fdx` 清理此项目：它会连同忽略的本地私有配置一起删除。不要将正在开发的 WBS-AICli 根目录自动视为可交给任何 Agent 任意读取；config 内仍有自己的凭据。

本源码包没有替维护者决定许可证，也没有替维护者向 GitHub 提交、推送、创建 release 或更改仓库可见性。

## 官方参考

- [G01] Git ignore：https://git-scm.com/docs/gitignore/
- [G02] Git check-ignore：https://git-scm.com/docs/git-check-ignore
- [G03] Git diff：https://git-scm.com/docs/git-diff
- [G04] GitHub 导入本地代码：https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- [G05] GitHub 敏感数据处理：https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- [G06] Bash 启动文件：https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html
