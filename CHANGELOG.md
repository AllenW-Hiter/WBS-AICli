# Unreleased — root support and project cleanup

- 新增管理器全局参数 `--allow-root`，为 AutoDL 等默认 root 的 Linux 环境显式启用安装、配置和启动；未启用时保持原有 root 拦截。
- root 安装缺失依赖时直接调用 `apt-get`，普通用户仍使用 `sudo`；预演显示与当前身份一致的命令。
- Bash 函数与旧式快捷命令保留显式传入的 `--allow-root`，路径沿用当前用户 HOME；旧配置导入继承该选项。
- 精简为运行程序与使用资料，删除测试脚本、测试报告和仓库开发指南，移除开发用 `self-test` 命令与测试框架导入；保留用户使用的 API 基础探测。
- 清理编辑器与安装器缓存，将 AI 编程助手文件、IDE 配置、测试文件和缓存加入 Git 忽略规则。
- 补充 AutoDL/root 使用说明；本轮未进行真实 AutoDL 部署、上游安装或服务商 API 调用。

# 2.0.1 — WBS-AICli repository edition

- 区分 `main` 发布版与 `dev` 开发版；发布版精简开发文档，保留离线自检，教程入口兼容单独的 README.md。
- 项目正式更名为 WBS-AICli，更新终端标题、帮助信息、主 README 与解压路径。
- 保留 `aicli` / `aicodex` / `aiclaude`、原脚本文件名与配置格式。
- 有意保留 `AI-CLI-TOOLKIT` Shell 管理标记、`AI_CLI_API_KEY` 及 v1 导入路径，避免覆盖旧配置或重复注册同名函数。
- 添加 Git 仓库落地指南、加强 .gitignore，声明 API Key、配置、历史与备份不应入库。
- 不改变安装来源、模型或服务商预设；不自动提交、推送或修改远程仓库。

# 2.0.0 — 2026-10-06

- 新增 `install-shell` / `remove-shell`：预览、确认、备份、语法校验、幂等更新 `.bashrc` 函数块；保留非托管内容和 HOME 权限。
- 新增 `aicli` / `aicodex` / `aiclaude` 函数；固定工具脚本路径，不改变工作目录，不向父 Shell 全局 export API 信息。
- 默认配置位置由 `~/.config/ai-cli-toolkit` 改为当前工具项目的 `config/`；提供显式 `--config-dir` 覆盖。
- 新增 `start` 交互：复用当前、选择其他、创建、编辑、查看；两款客户端各自持久保存选择及启动/退出记录。
- 新 API 配置在明文/权限风险提示后，默认选择保存 Key；仍可主动关闭。未保存配置首次启动时可保存本次输入。
- 新增 `edit`：未修改字段与同端点已有 Key 可回车保留；端点/鉴权方式变化强制重新输入，覆盖前备份。
- 新增 `import-v1`：复制旧 profile 与已保存 Key，保留原文件，重新生成 Codex 模型目录路径；不迁移原生历史或 OAuth。
- 保留旧式 `launchers`，但改为指向当前项目而不是再复制一套管理器。
- 原有 55 项离线测试继续通过；新增 42 项。另完成独立普通用户、真实 Bash 与模拟 CLI 的完整启动流程。

不会热切换已经运行的原生会话；不反向同步原生 `/model` 或显式 CLI 覆盖。服务商预设继承同日 v1 文档快照，此轮重点是本地工作流。
