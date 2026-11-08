#!/usr/bin/env python3
"""WBS-AICli 2.0.1 — Python >=3.10, standard library only.

No shell evaluation of keys, no pip/npm requirement, no whole-system upgrade.
Profiles are separate from the user's existing ~/.codex and ~/.claude.
Reviewed against official documentation on 2026-10-06. See README.md.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlsplit, urlunsplit, quote

VERSION = "2.0.1"
REVIEWED = "2026-10-06"
TOOLS = ("codex", "claude")
SOURCE_DIR = Path(__file__).resolve().parent
INSTALL_URLS = {
    "codex": "https://chatgpt.com/codex/install.sh",
    "claude": "https://claude.ai/install.sh",
}
DOCS = {
    "Codex 安装": "https://developers.openai.com/codex/cli",
    "Codex 配置参考": "https://developers.openai.com/codex/config-reference",
    "Codex 环境变量": "https://learn.chatgpt.com/docs/config-file/environment-variables",
    "Claude Code 安装": "https://code.claude.com/docs/en/setup",
    "Claude Code 环境变量": "https://code.claude.com/docs/en/env-vars",
    "Claude Code 配置优先级": "https://code.claude.com/docs/en/settings",
    "GLM → Codex": "https://docs.bigmodel.cn/cn/coding-plan/tool/codex",
    "GLM → Claude Code": "https://docs.bigmodel.cn/cn/guide/develop/claude",
    "Kimi 开放平台 CN → Codex": "https://platform.kimi.com/docs/guide/codex-kimi",
    "Kimi 开放平台 CN → Claude": "https://platform.kimi.com/docs/guide/claude-code-kimi",
    "Kimi 开放平台国际 → Codex": "https://platform.kimi.ai/docs/guide/codex-kimi",
    "Kimi Code → Claude": "https://www.kimi.com/code/docs/third-party-tools/claude-code.html",
    "DeepSeek → Codex": "https://api-docs.deepseek.com/quick_start/agent_integrations/codex/",
    "DeepSeek → Claude": "https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/",
}

# Endpoint/model snapshots, NOT promises that an account has access to a model.
# The operator can override the model and context window in the wizard.
PRESETS = {
    "codex": {
        "official": dict(label="OpenAI 官方账号登录（独立配置）", auth="login", base="", model="", context=0),
        "openai-api": dict(label="OpenAI 官方 API Key（独立计费）", auth="bearer", base="https://api.openai.com/v1", model="", context=0),
        "glm": dict(label="智谱 GLM Coding Plan / 中国区", auth="bearer", base="https://open.bigmodel.cn/api/v1", model="glm-5.3", context=1048576, effort="high", catalog="glm"),
        "kimi-cn": dict(label="Kimi 开放平台 / 中国区 API", auth="bearer", base="https://api.moonshot.cn/v1", model="kimi-k3", context=1048576),
        "kimi-global": dict(label="Kimi 开放平台 / 国际区 API", auth="bearer", base="https://api.moonshot.ai/v1", model="kimi-k3", context=1048576),
        "deepseek": dict(label="DeepSeek 官方 API", auth="bearer", base="https://api.deepseek.com", model="deepseek-flash", context=1048576, effort="high", catalog="deepseek"),
        "custom": dict(label="自定义 Responses API / 自建网关", auth="bearer", base="", model="", context=0),
    },
    "claude": {
        "official": dict(label="Anthropic 官方账号登录（独立配置）", auth="login", base="", model="", context=0),
        "anthropic-api": dict(label="Anthropic 官方 API Key（独立计费）", auth="x-api-key", base="https://api.anthropic.com", model="", context=0),
        "glm": dict(label="智谱 GLM / 中国区", auth="bearer", base="https://open.bigmodel.cn/api/anthropic", model="glm-5.2[1m]", small="glm-4.7", context=1048576, compact=1000000),
        "kimi-cn": dict(label="Kimi 开放平台 / 中国区 API", auth="bearer", base="https://api.moonshot.cn/anthropic", model="kimi-k3[1m]", small="kimi-k2.7-code", context=1048576, compact=1000000, effort="max"),
        "kimi-global": dict(label="Kimi 开放平台 / 国际区 API", auth="bearer", base="https://api.moonshot.ai/anthropic", model="kimi-k3[1m]", small="kimi-k2.7-code", context=1048576, compact=1000000, effort="max"),
        "kimi-code": dict(label="Kimi Code 编程会员 / 中国区（不是开放平台 Key）", auth="x-api-key", base="https://api.kimi.com/coding", model="k3-256k", context=262144, compact=262144, effort="high"),
        "deepseek": dict(label="DeepSeek 官方 API", auth="bearer", base="https://api.deepseek.com/anthropic", model="deepseek-flash[1m]", small="deepseek-flash", subagent="deepseek-flash", context=1048576, compact=786432, effort="max"),
        "custom": dict(label="自定义 Anthropic Messages API / 自建网关", auth="bearer", base="", model="", context=0),
    },
}
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy")
# Clear stale routing without removing arbitrary credentials needed by user's project.
ROUTING_KEYS = {
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORGANIZATION", "OPENAI_PROJECT",
    "CODEX_HOME", "CODEX_SQLITE_HOME", "CODEX_API_KEY", "CODEX_AUTH_TOKEN",
    "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_API_KEY_HELPER_TTL_MS",
    "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_ANTHROPIC_AWS", "AI_CLI_API_KEY",
    "API_TIMEOUT_MS", "ENABLE_TOOL_SEARCH", "BASH_ENV", "ENV",
}
NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:@+\[\]-]{0,191}\Z")
MAX_JSON = 2 * 1024 * 1024
# Keep the v2 marker and function names so install-shell updates existing entries.
BASH_BEGIN = "# >>> AI-CLI-TOOLKIT FUNCTIONS >>>"
BASH_END = "# <<< AI-CLI-TOOLKIT FUNCTIONS <<<"
FUNCTION_NAMES = ("aicli", "aicodex", "aiclaude")


class SessionTerminated(KeyboardInterrupt):
    """SIGTERM: unwind temporary-secret context managers before exit."""


def handle_term(signum, frame) -> None:
    raise SessionTerminated()


class UserError(Exception):
    """Expected error safe to display without a traceback or secret values."""


def say(message: str = "") -> None:
    print(message, flush=True)


def prompt(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        result = input(f"{message}{suffix}: ").strip()
    except EOFError as exc:
        raise UserError("输入已结束，操作取消。交互命令请在终端运行。") from exc
    return result or (default if default is not None else "")


def confirm(message: str) -> bool:
    return prompt(message + "（输入 y 确认，其余取消）", "n").lower() in ("y", "yes")


def choose(message: str, entries: list[tuple[str, str]]) -> str:
    say("\n" + message)
    for i, (_, label) in enumerate(entries, 1):
        say(f"  {i}. {label}")
    while True:
        answer = prompt("选择序号（0 取消）", "0")
        if answer == "0":
            raise UserError("已取消。")
        if answer.isdigit() and 1 <= int(answer) <= len(entries):
            return entries[int(answer) - 1][0]
        say("请输入菜单中的序号。")


def valid_name(value: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise UserError("配置名只能包含小写字母、数字、_、-；1–48 字符，以字母/数字开头。")
    return value


def valid_model(value: str, allow_empty: bool = False) -> str:
    if not value and allow_empty:
        return value
    if not MODEL_RE.fullmatch(value):
        raise UserError("模型 ID 不能为空，且不能包含空格、引号、反斜杠或控制字符。")
    return value


def valid_key(value: str) -> str:
    if not value or len(value) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise UserError("API Key 必须是非空、无空白和控制字符的 ASCII 字符串。")
    return value


def valid_base(value: str) -> str:
    if not value or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise UserError("Base URL 不能为空，不能含空格、反斜杠或控制字符。")
    try:
        u = urlsplit(value)
        host, port = u.hostname, u.port
    except ValueError as exc:
        raise UserError("Base URL 的主机或端口格式不正确。") from exc
    if not host or u.username is not None or u.password is not None or u.query or u.fragment:
        raise UserError("Base URL 必须有主机；不允许内嵌账号、密码、查询参数或 # 片段。")
    if port is not None and not 1 <= port <= 65535:
        raise UserError("端口必须在 1–65535 范围内。")
    if u.scheme != "https" and not (u.scheme == "http" and host in ("localhost", "127.0.0.1", "::1")):
        raise UserError("远端接口必须使用 HTTPS；HTTP 仅允许 localhost / 127.0.0.1 / ::1。")
    normalized = value.rstrip("/")
    if normalized.endswith(("/responses", "/chat/completions", "/messages")):
        raise UserError("请填写 Base URL，不要附加 /responses、/messages 或 /chat/completions。")
    return normalized


def integer(value: str, lower: int = 0, upper: int = 10_000_000) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise UserError("请输入整数。") from exc
    if not lower <= number <= upper:
        raise UserError(f"数值必须在 {lower}–{upper} 之间。")
    return number


def no_symlinks(path: Path) -> None:
    # Follow no symlink components in managed configuration paths.
    for item in (path, *path.parents):
        if item.is_symlink():
            raise UserError(f"为避免写入意外位置，拒绝符号链接路径：{item}")


def private_dir(path: Path) -> None:
    no_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise UserError(f"目录不属于当前用户：{path}")
    path.chmod(0o700)


def atomic_write(path: Path, data: str | bytes, mode: int = 0o600) -> None:
    no_symlinks(path)
    private_dir(path.parent)
    if path.exists() and (not path.is_file() or path.stat().st_uid != os.getuid()):
        raise UserError(f"不是当前用户拥有的普通文件：{path}")
    raw = data.encode("utf-8") if isinstance(data, str) else data
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def safe_read(path: Path, limit: int = MAX_JSON) -> bytes:
    no_symlinks(path)
    if not path.is_file() or path.stat().st_uid != os.getuid():
        raise UserError(f"文件不存在、不属于当前用户或不是普通文件：{path}")
    if path.stat().st_size > limit:
        raise UserError(f"文件过大，拒绝读取：{path.name}")
    return path.read_bytes()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def read_json(path: Path) -> dict:
    try:
        value = json.loads(safe_read(path))
    except (ValueError, UnicodeError) as exc:
        raise UserError(f"JSON 格式不正确：{path.name}") from exc
    if not isinstance(value, dict):
        raise UserError(f"JSON 根节点必须是对象：{path.name}")
    return value


def clean_env(source: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if source is None else source)
    for name in list(env):
        if name in ROUTING_KEYS or name.startswith("ANTHROPIC_"):
            env.pop(name, None)
    return env


def proxy_display(value: str) -> str:
    try:
        u = urlsplit(value)
        if not u.hostname:
            return "已设置（格式未识别，不显示原值）"
        host = f"[{u.hostname}]" if ":" in u.hostname else u.hostname
        netloc = host + (f":{u.port}" if u.port else "")
        if u.username is not None or u.password is not None:
            netloc = "***:***@" + netloc
        return urlunsplit((u.scheme, netloc, "", "", ""))
    except ValueError:
        return "已设置（格式未识别，不显示原值）"


def model_catalog(profile: dict) -> dict | None:
    """Minimal catalog for documented GLM/DeepSeek Codex integrations.

    It deliberately does not copy a vendor's long instructions template.
    Unknown/custom model IDs get no guessed catalog.
    """
    family = profile.get("catalog")
    known = {"glm": {"glm-5.3", "glm-5-turbo"}, "deepseek": {"deepseek-flash", "deepseek-v4-pro"}}
    if family not in known or profile["model"] not in known[family] or not profile.get("context"):
        return None
    model = profile["model"]
    item = {
        "slug": model, "display_name": model,
        "description": "User-selected API model", "default_reasoning_level": profile.get("effort") or "high",
        "supported_reasoning_levels": [{"effort": e, "description": e} for e in ("low", "high", "max")],
        "shell_type": "shell_command", "visibility": "list", "supported_in_api": True,
        "priority": 0, "base_instructions": "",
        "supports_reasoning_summaries": True, "default_reasoning_summary": "none",
        "support_verbosity": family == "deepseek", "apply_patch_tool_type": "freeform",
        "truncation_policy": {"mode": "tokens" if family == "deepseek" else "bytes", "limit": 10000},
        "context_window": profile["context"], "max_context_window": profile["context"],
        "effective_context_window_percent": 95, "supports_parallel_tool_calls": True,
        "experimental_supported_tools": [], "input_modalities": ["text"],
        "prefer_websockets": False,
    }
    if model == "deepseek-flash":
        item["input_modalities"].append("image")
        item["minimal_client_version"] = "0.144.0"
    return {"models": [item]}


def codex_config(profile: dict, runtime: Path) -> str:
    # JSON basic strings are TOML-compatible for the validated values used here.
    q = lambda x: json.dumps(str(x), ensure_ascii=True)
    lines = ["# Generated by WBS-AICli; API key is NOT stored in this TOML.",
             'approval_policy = "on-request"', 'sandbox_mode = "workspace-write"']
    if profile["auth"] == "login":
        return "\n".join(lines) + "\n"
    lines += [f'model = {q(profile["model"])}', 'model_provider = "aikit"', 'web_search = "disabled"']
    if profile.get("context"):
        lines.append(f'model_context_window = {profile["context"]}')
    if profile.get("effort"):
        lines.append(f'model_reasoning_effort = {q(profile["effort"])}')
    if model_catalog(profile):
        lines += [f'model_catalog_json = {q(runtime / "models.json")}', 'model_reasoning_summary = "none"']
    lines += ["", "[model_providers.aikit]", f'name = {q(profile["name"])}',
              f'base_url = {q(profile["base"])}', 'env_key = "AI_CLI_API_KEY"',
              'wire_api = "responses"', 'requires_openai_auth = false', 'supports_websockets = false']
    return "\n".join(lines) + "\n"


def claude_settings(profile: dict, key: str | None = None) -> dict:
    env = {"DISABLE_AUTOUPDATER": "1"}
    if profile["auth"] == "login":
        return {"env": env}
    env.update({"ANTHROPIC_BASE_URL": profile["base"], "ANTHROPIC_MODEL": profile["model"],
                "ANTHROPIC_DEFAULT_OPUS_MODEL": profile["model"],
                "ANTHROPIC_DEFAULT_SONNET_MODEL": profile["model"],
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": profile.get("small") or profile["model"],
                "ANTHROPIC_DEFAULT_FABLE_MODEL": profile["model"],
                "CLAUDE_CODE_SUBAGENT_MODEL": profile.get("subagent") or profile["model"],
                "CLAUDE_CODE_USE_BEDROCK": "0", "CLAUDE_CODE_USE_VERTEX": "0",
                "CLAUDE_CODE_USE_FOUNDRY": "0", "CLAUDE_CODE_USE_ANTHROPIC_AWS": "0",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "API_TIMEOUT_MS": "300000"})
    if profile.get("context"):
        env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(profile["context"])
        env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(profile.get("compact") or profile["context"])
    if profile.get("effort"):
        env["CLAUDE_CODE_EFFORT_LEVEL"] = profile["effort"]
    if key is not None:
        # CLI --settings overrides stale project/user values. No secret on argv.
        auth_name = "ANTHROPIC_AUTH_TOKEN" if profile["auth"] == "bearer" else "ANTHROPIC_API_KEY"
        other = "ANTHROPIC_API_KEY" if auth_name == "ANTHROPIC_AUTH_TOKEN" else "ANTHROPIC_AUTH_TOKEN"
        env[auth_name] = key
        env[other] = ""
    return {"env": env}


def validate_profile(p: dict) -> dict:
    if p.get("schema") != 1 or p.get("tool") not in TOOLS:
        raise UserError("配置版本或软件类型不正确。")
    valid_name(p.get("name", ""))
    if p.get("auth") not in ("login", "bearer", "x-api-key"):
        raise UserError("不支持的鉴权方式。")
    if p["auth"] != "login":
        valid_base(p.get("base", ""))
        valid_model(p.get("model", ""))
        for field in ("small", "subagent"):
            if p.get(field):
                valid_model(p[field])
    for name in ("context", "compact"):
        if type(p.get(name, 0)) is not int or not 0 <= p.get(name, 0) <= 10_000_000:
            raise UserError("上下文参数必须是合理的整数。")
    if p.get("context") and p.get("compact", 0) > p["context"]:
        raise UserError("压缩窗口不能大于模型上下文窗口。")
    if p.get("effort", "") not in ("", "none", "minimal", "low", "medium", "high", "xhigh", "max"):
        raise UserError("推理强度值不合法。")
    if type(p.get("save_key", False)) is not bool:
        raise UserError("save_key 必须是布尔值。")
    if p.get("catalog") not in (None, "glm", "deepseek"):
        raise UserError("未知模型目录类型。")
    return p


def curl_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


def probe_payload(p: dict) -> tuple[str, dict]:
    # [1m] is a Claude CLI hint, not an API model ID.
    model = re.sub(r"\[1m\]$", "", p["model"])
    if p["tool"] == "codex":
        return p["base"].rstrip("/") + "/responses", {
            "model": model, "input": "Reply with OK only.", "max_output_tokens": 64, "stream": False}
    return p["base"].rstrip("/") + "/v1/messages", {
        "model": model, "max_tokens": 64, "messages": [{"role": "user", "content": "Reply with OK only."}], "stream": False}


def save_key_choice() -> bool:
    """Explicit disclosure; this version defaults to persistence as requested."""
    while True:
        value = prompt("保存 API Key 到工具配置（明文文件 600；y 保存供下次复用，n 每次输入）", "y").lower()
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        say("请输入 y 或 n。")


def split_bash_block(text: str) -> tuple[str, str, bool]:
    """Preserve all text outside exactly one owned, complete marker block."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == BASH_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == BASH_END]
    if not starts and not ends:
        if BASH_BEGIN in text or BASH_END in text:
            raise UserError(".bashrc 中的工具标记格式异常；拒绝自动修改，请检查标记行。")
        return text, "", False
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise UserError(".bashrc 中有重复或不完整的工具标记；拒绝自动修改。")
    return "".join(lines[:starts[0]]), "".join(lines[ends[0] + 1:]), True


def update_bash_text(text: str, block: str | None) -> str:
    prefix, suffix, found = split_bash_block(text)
    if found:
        return prefix + (block or "") + suffix
    if block is None:
        return text
    return text + ("\n" if text and not text.endswith("\n") else "") + block


def replace_shell_file(path: Path, raw: bytes, mode: int) -> None:
    """Atomic replacement WITHOUT chmod'ing HOME (unlike private config writes)."""
    no_symlinks(path)
    if not path.parent.is_dir() or path.parent.stat().st_uid != os.getuid():
        raise UserError(".bashrc 的父目录不存在或不属于当前用户。")
    if path.exists() and (not path.is_file() or path.stat().st_uid != os.getuid()):
        raise UserError(".bashrc 不是当前用户的普通文件。")
    fd, temporary = tempfile.mkstemp(prefix=".aikit-bashrc-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class App:
    def __init__(self, home: Path | None = None, dry_run: bool = False,
                 project: Path | None = None, config_root: Path | None = None,
                 allow_root: bool = False):
        self.home = (home or Path.home()).absolute()
        self.project = (project or SOURCE_DIR).absolute()
        self.root = (config_root or (self.project / "config")).expanduser().absolute()
        self.legacy_root = self.home / ".config" / "ai-cli-toolkit"
        self.data = self.root / "cache"
        self.bin = self.home / ".local" / "bin"
        self.dry_run = dry_run
        self.allow_root = allow_root
        self.proxy_overrides: dict[str, str | None] = {}

    def guard(self) -> None:
        if os.geteuid() == 0 and not (self.dry_run or self.allow_root):
            raise UserError("默认仅允许普通用户运行；AutoDL 等 root 环境请显式传入 --allow-root（放在子命令之前）。")
        if platform.system() != "Linux":
            raise UserError("本脚本仅面向 Linux / Debian 系统。")

    def environment(self) -> dict[str, str]:
        env = dict(os.environ)
        for key, value in self.proxy_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "/usr/bin:/bin")
        return env

    def profile_dir(self, tool: str, name: str) -> Path:
        if tool not in TOOLS:
            raise UserError("软件必须是 codex 或 claude。")
        return self.root / "profiles" / tool / valid_name(name)

    @contextlib.contextmanager
    def lock(self):
        self.guard()
        private_dir(self.root)
        lockfile = self.root / ".lock"
        no_symlinks(lockfile)
        fd = os.open(lockfile, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise UserError("另一个配置写入操作正在进行，请关闭它后重试。") from exc
            yield
        finally:
            os.close(fd)

    def load(self, tool: str, name: str) -> dict:
        p = validate_profile(read_json(self.profile_dir(tool, name) / "profile.json"))
        if p["tool"] != tool or p["name"] != name:
            raise UserError("配置内容与目录名不一致。")
        return p

    def profiles(self, tool: str | None = None) -> list[dict]:
        out = []
        for target in ([tool] if tool else TOOLS):
            folder = self.root / "profiles" / target
            no_symlinks(folder)
            if folder.exists():
                for path in sorted(folder.iterdir()):
                    if path.is_dir() and NAME_RE.fullmatch(path.name) and (path / "profile.json").exists():
                        out.append(self.load(target, path.name))
        return out

    def show_profiles(self) -> None:
        items = self.profiles()
        if not items:
            say("尚无本工具管理的配置；现有 ~/.codex 和 ~/.claude 不受影响。")
        for p in items:
            say(f'{p["tool"]:6}  {p["name"]:18}  {p["model"] or "官方登录/默认模型"}')
            say(f'        {p["base"] or "官方登录端点"} | 密钥：' + ("本地保存（明文 600）" if p.get("save_key") else "未保存/启动时输入"))

    def doctor(self) -> None:
        say(f"WBS-AICli {VERSION} | 文档核对：{REVIEWED}")
        try:
            release = Path("/etc/os-release").read_text()
            info = dict(line.split("=", 1) for line in release.splitlines() if "=" in line)
            say("系统：" + info.get("PRETTY_NAME", "未知").strip('"'))
        except OSError:
            say("系统：无法读取 /etc/os-release")
        say(f"架构：{platform.machine()} | Python：{platform.python_version()}")
        say(f"当前用户 UID：{os.geteuid()} | Conda：{'已激活（脚本使用系统 Python）' if os.environ.get('CONDA_PREFIX') else '未激活'}")
        for command in ("curl", "git", "codex", "claude"):
            say(f"{command}: {shutil.which(command, path=self.environment()['PATH']) or '未找到'}")
        for key in PROXY_KEYS:
            if self.environment().get(key):
                say(f"{key}: " + ("已设置（不显示名单）" if "no_proxy" == key.lower() else proxy_display(self.environment()[key])))
        stale = [key for key in os.environ if key in ROUTING_KEYS or key.startswith("ANTHROPIC_")]
        if stale:
            say("发现已有模型/认证环境变量（不显示值）：" + ", ".join(sorted(stale)))
            say("本工具的独立启动器会清理相关变量；直接运行原始命令仍沿用原环境。")
        say("原始配置目录：" + ", ".join(f'{p}: {"存在" if p.exists() else "不存在"}' for p in (self.home / ".codex", self.home / ".claude")))
        say("工具配置目录：" + str(self.root))
        self.show_profiles()
        say("此检查不安装、不写配置、不请求 AI API，也不运行外部 CLI 的自检。")

    def deps(self) -> None:
        self.guard()
        if not shutil.which("apt-get") or not shutil.which("dpkg-query"):
            raise UserError("未找到 apt-get / dpkg-query；只支持 Debian 系发行版。")
        missing = []
        for package in ("ca-certificates", "curl", "git"):
            result = subprocess.run(["dpkg-query", "-W", "-f=${Status}", package], capture_output=True, text=True)
            if result.returncode or result.stdout.strip() != "install ok installed":
                missing.append(package)
        if not missing:
            say("系统依赖已齐备：ca-certificates、curl、git。")
            return
        say("仅安装缺失依赖：" + ", ".join(missing))
        say("不会安装 Node.js、pip 包，不会执行 upgrade / full-upgrade，也不替换 APT 源。")
        prefix = [] if os.geteuid() == 0 else ["sudo"]
        update_command = [*prefix, "apt-get", "update"]
        install_command = [*prefix, "apt-get", "install", "--no-install-recommends", *missing]
        if self.dry_run:
            say("[dry-run] " + shlex.join(update_command))
            say("[dry-run] " + shlex.join(install_command))
            return
        if not confirm("执行上述 APT 操作"):
            return
        if prefix and not shutil.which("sudo"):
            raise UserError("缺少 sudo，请让管理员安装上述依赖后重试。")
        subprocess.run(update_command, check=True)
        subprocess.run(install_command, check=True)

    def install(self, tool: str) -> None:
        if tool == "both":
            self.install("codex")
            self.install("claude")
            return
        self.guard()
        if platform.machine() not in ("x86_64", "amd64", "aarch64", "arm64"):
            raise UserError("仅为 Linux x86_64 / ARM64 开放自动安装。其他架构请核对官方支持。")
        say(f"\n安装/更新 {tool}：{INSTALL_URLS[tool]}")
        say("使用官方原生安装器；先下载到文件、显示 SHA256，可查看内容，再单独确认执行。")
        say("安装器及其下载的二进制属于第三方代码；当前 SHA256 是留档值，不等于独立的签名验证。")
        if self.dry_run:
            user = "root" if os.geteuid() == 0 else "当前用户"
            say(f"[dry-run] 检查依赖 → 下载官方安装器 → 人工审阅/确认 → {user} 执行 → 检查版本。")
            return
        self.deps()
        if not shutil.which("curl"):
            raise UserError("缺少 curl；未下载安装器。")
        existing = shutil.which(tool, path=self.environment()["PATH"])
        if existing:
            say("检测到已有命令：" + existing)
            if not confirm("继续可能新增原生安装或更新已有版本；保留原配置，继续"):
                return
        if not confirm("从上面的官方地址下载安装器"):
            return
        downloads = self.data / "installers"
        private_dir(downloads)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = downloads / f"{tool}-{stamp}.sh"
        no_symlinks(destination)
        result = subprocess.run(["curl", "-q", "--fail", "--show-error", "--silent", "--location",
                                 "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "5",
                                 "--connect-timeout", "20", "--max-time", "180", "--retry", "2",
                                 "--max-filesize", "5242880", "--output", str(destination), INSTALL_URLS[tool]], env=self.environment())
        if result.returncode:
            destination.unlink(missing_ok=True)
            raise UserError("官方安装器下载失败。请检查 DNS、网络、代理及证书；未执行任何下载内容。")
        destination.chmod(0o600)
        content = safe_read(destination, 5242880)
        if not content.startswith(b"#!") or b"<html" in content[:512].lower():
            raise UserError("下载内容不像 Shell 安装脚本，拒绝执行。")
        shell = "/bin/sh" if tool == "codex" else "/bin/bash"
        check = subprocess.run([shell, "-n", str(destination)], capture_output=True)
        if check.returncode:
            raise UserError("官方安装器未通过 shell 语法检查，拒绝执行。")
        digest = hashlib.sha256(content).hexdigest()
        atomic_write(destination.with_suffix(".sha256"), f"{digest}  {destination.name}\n")
        say("本地文件：" + str(destination))
        say("SHA256：" + digest)
        if confirm("在终端查看下载的安装脚本"):
            # Render control characters safely, never use a shell-based pager.
            text = content.decode("utf-8", errors="replace")
            say("".join(c if c in "\n\t" or ord(c) >= 32 and ord(c) != 127 else f"\\x{ord(c):02x}" for c in text))
        channel = ""
        if tool == "claude":
            channel = prompt("Claude 安装频道或版本（stable / latest / 具体版本）", "stable")
            if channel not in ("stable", "latest") and not re.fullmatch(r"\d+\.\d+\.\d+", channel):
                raise UserError("频道或版本格式不正确。")
        if not confirm("执行此官方安装器（会联网下载并安装程序到用户目录）"):
            say("未执行。已下载脚本保留在上述路径。")
            return
        if hashlib.sha256(safe_read(destination, 5242880)).hexdigest() != digest:
            raise UserError("审阅期间安装文件发生变化，拒绝执行。")
        env = clean_env(self.environment())
        # Official installer settings should not inherit model-profile roots.
        command = [shell, str(destination)] + ([channel] if channel else [])
        subprocess.run(command, env=env, check=True)
        executable = shutil.which(tool, path=env["PATH"])
        if not executable:
            raise UserError("安装器结束，但未在 PATH 或 ~/.local/bin 找到命令。请查看安装输出；不能据此确认安装成功。")
        result = subprocess.run([executable, "--version"], env=env, check=True, capture_output=True, text=True, timeout=30)
        say("命令：" + executable)
        say("版本：" + result.stdout.strip())
        say('当前终端可执行：export PATH="$HOME/.local/bin:$PATH"')
        say("未自动修改 .bashrc / .profile；官方安装器自身行为以其输出和内容为准。")

    def configure(self, tool: str) -> dict | None:
        self.guard()
        if self.dry_run:
            say(f"[dry-run] 将引导选择 {tool} 服务商、Base URL、模型、密钥保存方式；不读取密钥、不写文件。")
            return
        preset_name = choose("选择服务商（模型名为核对日的预设，可自行修改）", [(k, p["label"]) for k, p in PRESETS[tool].items()])
        p = copy.deepcopy(PRESETS[tool][preset_name])
        p.update(schema=1, tool=tool, preset=preset_name, name=valid_name(prompt("配置名", preset_name)), save_key=False, reviewed=REVIEWED)
        folder = self.profile_dir(tool, p["name"])
        old_exists = (folder / "profile.json").exists()
        if old_exists and not confirm("同名配置已存在，将先备份其配置与密钥，再覆盖。继续"):
            return
        say("现有 ~/.codex、~/.claude、Shell 配置文件不会被覆盖。")
        if p["auth"] != "login":
            if preset_name == "custom":
                say("协议要求：" + ("Responses API（不是 Chat Completions）" if tool == "codex" else "Anthropic Messages API（不是 OpenAI Chat Completions）"))
                if not confirm("已确认服务商支持上述协议，并信任该接口接收代码和密钥"):
                    return
                p["base"] = valid_base(prompt("Base URL（不要附加 /responses 或 /messages）"))
                if tool == "claude":
                    p["auth"] = choose("选择服务商要求的鉴权头", [("bearer", "Authorization: Bearer（ANTHROPIC_AUTH_TOKEN）"), ("x-api-key", "x-api-key（ANTHROPIC_API_KEY）")])
            else:
                p["base"] = valid_base(p["base"])
                say("Base URL：" + p["base"])
                say("API Key 必须与平台、地区及套餐匹配；不自动跨平台复用。")
            original_model = p["model"]
            p["model"] = valid_model(prompt("模型 ID（以控制台实际授权为准）", original_model or None))
            if p["model"] != original_model:
                p.pop("catalog", None)
                p["context"] = 0
                p.pop("compact", None)
                p.pop("effort", None)
                p["small"] = p["model"]
                p.pop("subagent", None)
                say("模型已修改：不会沿用原模型的上下文/能力猜测，请填写新模型参数。")
            p["context"] = integer(prompt("模型上下文 token 上限（不确定填 0，交由 CLI 默认）", str(p["context"])))
            if tool == "claude":
                p["small"] = valid_model(prompt("轻量/Haiku 档模型 ID", p.get("small") or p["model"]))
                if p["context"]:
                    p["compact"] = integer(prompt("自动压缩窗口 token（不能大于上下文上限）", str(min(p.get("compact", p["context"]), p["context"]))), 1, p["context"])
                else:
                    p.pop("compact", None)
            p["effort"] = prompt("推理强度（输入 auto 表示不显式指定）", p.get("effort") or "auto")
            if p["effort"] == "auto":
                p["effort"] = ""
            p["save_key"] = save_key_choice()
        key = None
        if p["save_key"]:
            key = self.ask_key()
        p = validate_profile(p)
        say(f'\n即将保存：{p["tool"]}/{p["name"]} → {p["base"] or "官方登录"} → {p["model"] or "默认模型"}')
        if not confirm("确认保存"):
            return
        self.save_profile(p, key)
        self.set_current(tool, p["name"])
        say("已保存并设为该软件的当前配置；这不代表真实 API 已验证。")
        say(f'交互启动：{"aicodex" if tool == "codex" else "aiclaude"}；直接启动：aicli run {tool} {p["name"]}')
        return p

    @staticmethod
    def ask_key() -> str:
        if not sys.stdin.isatty():
            raise UserError("密钥输入必须在交互式终端进行，防止 getpass 降级为明文回显。")
        return valid_key(getpass.getpass("API Key（输入不回显，不进入 Shell 历史）: ").strip())

    def snapshot(self, tool: str, name: str) -> Path:
        folder = self.profile_dir(tool, name)
        files = ("profile.json", "key.txt", "codex/config.toml", "codex/models.json", "claude/settings.json")
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.root / "backups" / f"{tool}--{name}--{stamp}"
        payload = {"schema": 1, "tool": tool, "name": name, "files": {}}
        for relative in files:
            path = folder / relative
            if path.exists():
                payload["files"][relative] = safe_read(path).decode("utf-8")
        private_dir(backup)
        atomic_write(backup / "snapshot.json", json_text(payload))
        return backup

    def save_profile(self, p: dict, key: str | None) -> None:
        validate_profile(p)
        if p.get("save_key"):
            valid_key(key or "")
        with self.lock():
            folder = self.profile_dir(p["tool"], p["name"])
            if (folder / "profile.json").exists():
                backup = self.snapshot(p["tool"], p["name"])
                say("旧配置备份：" + str(backup))
            private_dir(folder)
            if p.get("save_key"):
                atomic_write(folder / "key.txt", key + "\n")
            else:
                no_symlinks(folder / "key.txt")
                (folder / "key.txt").unlink(missing_ok=True)
            if p["tool"] == "codex":
                runtime = folder / "codex"
                private_dir(runtime)
                catalog = model_catalog(p)
                if catalog:
                    atomic_write(runtime / "models.json", json_text(catalog))
                else:
                    no_symlinks(runtime / "models.json")
                    (runtime / "models.json").unlink(missing_ok=True)
                atomic_write(runtime / "config.toml", codex_config(p, runtime))
            else:
                runtime = folder / "claude"
                private_dir(runtime)
                # Persistent settings intentionally contain NO key.
                atomic_write(runtime / "settings.json", json_text(claude_settings(p)))
            # Write profile manifest last. Individual files are atomically replaced.
            atomic_write(folder / "profile.json", json_text(p))

    def get_key(self, p: dict) -> str:
        if p.get("save_key"):
            path = self.profile_dir(p["tool"], p["name"]) / "key.txt"
            no_symlinks(path)
            if path.exists() and stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise UserError("密钥文件权限过宽，请先 chmod 600 该配置的 key.txt。")
            return valid_key(safe_read(path, 8193).decode("utf-8").strip())
        key = self.ask_key()
        if save_key_choice():
            p["save_key"] = True
            self.save_profile(p, key)
            say("本次输入的 Key 已存入此配置；下次可直接复用。")
        return key

    def pick_profile(self, tool: str | None = None) -> tuple[str, str]:
        options = self.profiles(tool)
        if not options:
            raise UserError("请先创建配置。")
        value = choose("选择配置", [(f'{p["tool"]}/{p["name"]}', f'{p["tool"]}/{p["name"]}  {p["model"] or "官方登录"}') for p in options])
        return tuple(value.split("/", 1))

    def run_profile(self, tool: str, name: str, extra: list[str] | None = None) -> int:
        self.guard()
        p = self.load(tool, name)
        extra = list(extra or [])
        if extra[:1] == ["--"]:
            extra = extra[1:]
        if "--dry-run" in extra:
            raise UserError("--dry-run 必须位于 run 子命令之前；未启动任何 CLI。")
        if self.dry_run:
            say(f'[dry-run] {tool}/{name} → {p["base"] or "官方登录"} → {p["model"] or "默认模型"}；不读密钥、不启动 CLI。')
            return 0
        # Host-managed environments should not be silently routed around.
        if os.environ.get("CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST") and tool == "claude":
            raise UserError("检测到宿主管理的 Claude provider；请使用宿主配置，不在此环境切换。")
        executable = shutil.which(tool, path=self.environment()["PATH"])
        if not executable:
            raise UserError(f"未找到 {tool}，请先安装。")
        folder = self.profile_dir(tool, name)
        env = clean_env(self.environment())
        runtime = folder / tool
        no_symlinks(runtime)
        if not runtime.is_dir():
            raise UserError("独立配置目录缺失；请重新配置或恢复备份。")
        print(f'启动 {tool}/{name} | 模型：{p["model"] or "官方默认"} | {p["base"] or "官方登录"}', file=sys.stderr, flush=True)
        print("保留项目设置与组织管理策略；首次会话请检查 /status 和权限提示。", file=sys.stderr, flush=True)
        if tool == "codex":
            env["CODEX_HOME"] = str(runtime)
            if p["auth"] != "login":
                env["AI_CLI_API_KEY"] = self.get_key(p)
            return self.execute_session(tool, name, [executable, *extra], env)
        env["CLAUDE_CONFIG_DIR"] = str(runtime)
        env["DISABLE_AUTOUPDATER"] = "1"
        if p["auth"] == "login":
            return self.execute_session(tool, name, [executable, *extra], env)
        key = self.get_key(p)
        # A regular file is required by current --settings; never place a key on argv.
        with tempfile.TemporaryDirectory(prefix="session-", dir=folder) as temp:
            settings = Path(temp) / "settings.json"
            atomic_write(settings, json_text(claude_settings(p, key)))
            command = [executable, *extra, "--settings", str(settings)]
            return self.execute_session(tool, name, command, env)

    def test_profile(self, tool: str, name: str) -> None:
        self.guard()
        p = self.load(tool, name)
        if p["auth"] == "login":
            say("账号登录配置请启动 CLI 后完成官方登录；不会读取/复用浏览器令牌。")
            return
        endpoint, payload = probe_payload(p)
        say("将发送一条固定短文本到：" + endpoint)
        say("不会读取项目文件；可能产生 API 费用。这仅检查非流式基础协议，不验证工具调用或完整 Agent 能力。")
        if p.get("preset") == "kimi-code":
            say("Kimi Code 套餐可能限制非 Coding Agent 的直接调用；探测被拒不等于 Claude Code 不可用。")
        if self.dry_run:
            say("[dry-run] 不读取 Key、不发送请求。")
            return
        if not confirm("授权发送这一个 API 请求"):
            return
        if not shutil.which("curl"):
            raise UserError("基础测试需要 curl。")
        key = self.get_key(p)
        auth_header = f"x-api-key: {key}" if p["auth"] == "x-api-key" else f"Authorization: Bearer {key}"
        config = "\n".join([
            "url = " + curl_quote(endpoint), 'request = "POST"',
            "header = " + curl_quote(auth_header), 'header = "Content-Type: application/json"',
            'header = "anthropic-version: 2023-06-01"' if tool == "claude" else 'header = "Accept: application/json"',
            "data = " + curl_quote(json.dumps(payload)),
        ]) + "\n"
        command = ["curl", "-q", "--silent", "--show-error", "--connect-timeout", "20", "--max-time", "120",
                   "--max-filesize", "2097152", "--proto", "=http,https", "--config", "-",
                   "--write-out", "\n__AIKIT_STATUS__:%{http_code}"]
        result = subprocess.run(command, input=config, capture_output=True, text=True, env=self.environment(), timeout=130)
        if result.returncode:
            # Never echo stderr: a proxy error might include proxy credentials.
            raise UserError(f"请求失败，curl 退出码 {result.returncode}。检查网络、DNS、代理和证书；为保护凭据，不打印原始网络错误。")
        body, sep, status = result.stdout.rpartition("\n__AIKIT_STATUS__:")
        if not sep or not status.isdigit():
            raise UserError("无法解析 HTTP 状态。")
        say("HTTP " + status)
        try:
            value = json.loads(body)
        except ValueError:
            raise UserError("服务未返回 JSON；可能是错误地址、代理拦截或登录网页。不会输出原始响应。")
        expected = isinstance(value, dict) and (value.get("object") == "response" if tool == "codex" else value.get("type") == "message")
        if 200 <= int(status) < 300 and expected and not value.get("error") and value.get("status") not in ("failed", "cancelled"):
            say("收到符合基础协议结构的响应。仍需用 CLI 验证 SSE、工具调用、权限与长任务。")
        else:
            hints = {400: "参数/模型能力不兼容。", 401: "密钥、地区或套餐端点不匹配。", 402: "余额或计费问题。", 403: "权限、区域或允许工具限制。", 404: "模型或接口路径不存在。", 429: "额度、速率或并发限制。"}
            raise UserError("基础探测未通过：" + hints.get(int(status), "响应结构不兼容或服务端异常。") + "为避免回显凭据，不显示原始响应。")

    def install_launchers(self) -> None:
        self.guard()
        profiles = self.profiles()
        say("可选兼容入口：在 ~/.local/bin 创建 ai-cli 与各配置的命令，全部指向当前工具项目。")
        say("不会把 API Key 写入启动器，也不会覆盖不属于本工具的已有同名文件。")
        if self.dry_run:
            say("[dry-run] 不复制、不创建命令。")
            return
        if not confirm("安装/更新快捷命令"):
            return
        with self.lock():
            target = self.project
            private_dir(self.bin)
            prefix = "#!/usr/bin/env bash\n# AI-CLI-TOOLKIT MANAGED LAUNCHER\nset -euo pipefail\nset +x\n"
            root_option = " --allow-root" if self.allow_root else ""
            launchers = {"ai-cli": prefix + f'exec /usr/bin/python3 -B -I {shlex.quote(str(target / "ai_cli_manager.py"))}{root_option} --config-dir {shlex.quote(str(self.root))} "$@"\n'}
            for p in profiles:
                filename = f'{p["tool"]}-{p["name"]}'
                launchers[filename] = prefix + f'exec /usr/bin/python3 -B -I {shlex.quote(str(target / "ai_cli_manager.py"))}{root_option} --config-dir {shlex.quote(str(self.root))} run {p["tool"]} {p["name"]} -- "$@"\n'
            # Validate ALL collisions before writing any launcher.
            for name in launchers:
                path = self.bin / name
                no_symlinks(path)
                if path.exists() and b"# AI-CLI-TOOLKIT MANAGED LAUNCHER" not in safe_read(path, 32768):
                    raise UserError(f"已有非本工具文件，拒绝覆盖：{path}")
            for name, content in launchers.items():
                atomic_write(self.bin / name, content, 0o700)
                say("命令：" + name)
        say('当前终端执行：export PATH="$HOME/.local/bin:$PATH"')
        say("快捷命令始终读取最新保存的同名配置；新配置需要重新生成一次快捷命令。")

    def restore(self) -> None:
        self.guard()
        backups = self.root / "backups"
        no_symlinks(backups)
        choices = sorted([p for p in backups.iterdir() if p.is_dir() and (p / "snapshot.json").is_file()], reverse=True) if backups.exists() else []
        if not choices:
            raise UserError("没有备份。备份会在覆盖同名配置时自动创建。")
        if self.dry_run:
            say(f"[dry-run] 发现 {len(choices)} 份备份；不读取其中的密钥，不恢复。")
            return
        selected = choose("选择恢复点（可能包含当时的明文密钥）", [(str(i), p.name) for i, p in enumerate(choices)])
        snapshot = read_json(choices[int(selected)] / "snapshot.json")
        tool, name = snapshot.get("tool"), valid_name(snapshot.get("name", ""))
        folder = self.profile_dir(tool, name)
        files = snapshot.get("files", {})
        allowlist = {"profile.json", "key.txt", "codex/config.toml", "codex/models.json", "claude/settings.json"}
        if not isinstance(files, dict) or set(files) - allowlist or "profile.json" not in files:
            raise UserError("备份结构无效。")
        if any(not isinstance(text, str) for text in files.values()):
            raise UserError("备份字段不是文本；未修改当前配置。")
        p = validate_profile(json.loads(files["profile.json"]))
        required = "codex/config.toml" if tool == "codex" else "claude/settings.json"
        if required not in files:
            raise UserError("备份缺少运行配置；未修改当前配置。")
        for relative in ("codex/models.json", "claude/settings.json"):
            if relative in files and not isinstance(json.loads(files[relative]), dict):
                raise UserError("备份中的 JSON 配置无效；未修改当前配置。")
        if (p["tool"], p["name"]) != (tool, name):
            raise UserError("备份身份不匹配。")
        if p.get("save_key"):
            valid_key(files.get("key.txt", "").strip())
        if not confirm(f"恢复 {tool}/{name}（先备份当前配置；不会恢复/删除会话历史）"):
            return
        with self.lock():
            if (folder / "profile.json").exists():
                self.snapshot(tool, name)
            # Manifest last, matching save_profile; each file is atomic, not a multi-file transaction.
            for relative in sorted(allowlist - {"profile.json"}) + ["profile.json"]:
                destination = folder / relative
                no_symlinks(destination)
                if relative in files:
                    if not isinstance(files[relative], str):
                        raise UserError("备份字段不是文本。")
                    atomic_write(destination, files[relative])
                elif destination.exists():
                    destination.unlink()
        say("已恢复配置及当时保存的密钥。若密钥已吊销，请重新配置。")

    def proxy_menu(self) -> None:
        action = choose("代理仅作用于本次管理器及其启动的子进程，不写系统文件", [("inherit", "继承原终端代理"), ("off", "本次禁用代理"), ("set", "填写明确的代理协议/主机/端口")])
        if action == "inherit":
            self.proxy_overrides = {}
        elif action == "off":
            self.proxy_overrides = dict.fromkeys(PROXY_KEYS)
        else:
            scheme = choose("代理协议", [(x, x) for x in ("http", "https", "socks5h")])
            host = prompt("代理主机（例如 127.0.0.1；IPv6 不加方括号）")
            if not re.fullmatch(r"[A-Za-z0-9.:-]+", host) or not host:
                raise UserError("代理主机格式不正确。")
            port = integer(prompt("代理端口（不猜测默认值）"), 1, 65535)
            credentials = ""
            if confirm("代理需要用户名/密码"):
                username = prompt("代理用户名")
                if not sys.stdin.isatty():
                    raise UserError("代理密码输入需要交互终端。")
                password = getpass.getpass("代理密码（不回显）: ")
                credentials = quote(username, safe="") + ":" + quote(password, safe="") + "@"
            authority = f"[{host}]" if ":" in host else host
            url = f"{scheme}://{credentials}{authority}:{port}"
            self.proxy_overrides = dict.fromkeys(PROXY_KEYS)
            if scheme == "socks5h":
                self.proxy_overrides.update(ALL_PROXY=url, all_proxy=url)
                say("curl 下载/探测支持 SOCKS5h；CLI 自身对 ALL_PROXY 的支持以各版本为准，失败时使用 HTTP CONNECT 代理。")
            else:
                self.proxy_overrides.update(HTTP_PROXY=url, HTTPS_PROXY=url, http_proxy=url, https_proxy=url)
            self.proxy_overrides.update(NO_PROXY="localhost,127.0.0.1,::1", no_proxy="localhost,127.0.0.1,::1")
            say("本次代理：" + proxy_display(url))
        say("APT 经 sudo 不保证继承此代理；需要时请使用已经配置好的 APT 代理。")

    def read_state(self) -> dict:
        path = self.root / "state.json"
        no_symlinks(path)
        if not path.exists():
            return {"schema": 1, "tools": {}}
        value = read_json(path)
        if value.get("schema") != 1 or not isinstance(value.get("tools"), dict):
            raise UserError("state.json 格式不正确；请先备份检查，不会静默覆盖。")
        for tool, record in value["tools"].items():
            if tool not in TOOLS or not isinstance(record, dict):
                raise UserError("state.json 中的软件记录不正确。")
            if record.get("selected") is not None:
                valid_name(record["selected"])
            if "last_run" in record and not isinstance(record["last_run"], dict):
                raise UserError("state.json 中的启动记录不正确。")
        return value

    def current_name(self, tool: str) -> str | None:
        if tool not in TOOLS:
            raise UserError("软件必须是 codex 或 claude。")
        name = self.read_state()["tools"].get(tool, {}).get("selected")
        if name and (self.profile_dir(tool, name) / "profile.json").is_file():
            self.load(tool, name)
            return name
        return None

    def set_current(self, tool: str, name: str) -> None:
        self.load(tool, name)
        if self.dry_run:
            return
        with self.lock():
            state = self.read_state()
            record = state["tools"].setdefault(tool, {})
            record["selected"] = name
            record["selected_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            atomic_write(self.root / "state.json", json_text(state))

    def show_current(self) -> None:
        say("工具项目：" + str(self.project))
        say("配置目录：" + str(self.root))
        for tool in TOOLS:
            name = self.current_name(tool)
            if name:
                p = self.load(tool, name)
                say(f'{tool}: {name} | {p["base"] or "官方登录"} | {p["model"] or "默认模型"}')
            else:
                say(f"{tool}: 尚未选择当前配置")
        say("当前配置是本工具的选择记录，不代表最近一次请求认证成功。")

    def execute_session(self, tool: str, name: str, command: list[str], env: dict[str, str]) -> int:
        # Do not hold the file lock for the life of a potentially long CLI session.
        run_id = uuid.uuid4().hex
        with self.lock():
            state = self.read_state()
            record = state["tools"].setdefault(tool, {})
            record["selected"] = name
            record["last_run"] = {"id": run_id, "profile": name,
                                  "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                  "status": "starting", "exit_code": None}
            atomic_write(self.root / "state.json", json_text(state))
        status, code = "failed_to_start", None
        try:
            result = subprocess.run(command, env=env)
            code, status = result.returncode, "exited"
            return code
        except SessionTerminated:
            code, status = 143, "interrupted"
            raise
        except KeyboardInterrupt:
            code, status = 130, "interrupted"
            raise
        finally:
            # An older session exiting must not clobber a newer session/selection.
            try:
                with self.lock():
                    state = self.read_state()
                    record = state["tools"].get(tool, {}).get("last_run", {})
                    if record.get("id") == run_id:
                        record.update(status=status, exit_code=code,
                                      finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
                        atomic_write(self.root / "state.json", json_text(state))
            except (UserError, OSError, ValueError, TypeError):
                print("警告：无法更新本次退出记录；上次保存的 API 配置仍保留，请检查 config/state.json。", file=sys.stderr)

    def start(self, tool: str, extra: list[str] | None = None) -> int:
        self.guard()
        if tool not in TOOLS:
            raise UserError("软件必须是 codex 或 claude。")
        if self.dry_run:
            say(f"[dry-run] 打开 {tool} 交互启动菜单；不读密钥、不写文件、不启动 CLI。")
            return 0
        while True:
            name = self.current_name(tool)
            say(f"\n=== {tool} 交互启动 ===")
            say("工作目录（不会自动切换）：" + str(Path.cwd()))
            say("配置目录：" + str(self.root))
            if name:
                p = self.load(tool, name)
                say(f'当前配置：{name} | {p["model"] or "官方默认"} | {p["base"] or "官方登录"}')
                say("API Key：" + ("使用已保存的 Key（不显示值）" if p.get("save_key") else "官方登录" if p["auth"] == "login" else "启动时隐藏输入"))
            else:
                say("尚无当前配置，可选择已保存的配置或新建。")
            say("  1. 使用当前配置启动（默认）\n  2. 选择其他已保存配置并启动\n  3. 新建/重新指定 API 配置\n  4. 修改当前配置（地址 / 模型 / Key）\n  5. 查看全部已保存配置\n  0. 返回终端")
            answer = prompt("选择", "1" if name else "2" if self.profiles(tool) else "3")
            try:
                if answer == "0": return 0
                if answer == "1":
                    if not name:
                        say("请先选择或创建配置。")
                        continue
                    return self.run_profile(tool, name, extra)
                if answer == "2":
                    selected_tool, selected = self.pick_profile(tool)
                    return self.run_profile(selected_tool, selected, extra)
                if answer == "3": self.configure(tool)
                elif answer == "4":
                    if not name: say("尚无当前配置，请先新建或选择。")
                    else: self.edit_profile(tool, name)
                elif answer == "5": self.show_profiles()
                else: say("请输入菜单中的序号。")
            except (UserError, OSError, subprocess.SubprocessError) as exc:
                display_error(exc)

    @staticmethod
    def ask_key_or_keep() -> str:
        if not sys.stdin.isatty():
            raise UserError("密钥输入必须在交互式终端进行。")
        value = getpass.getpass("新 API Key（不回显；直接回车保留已有 Key）: ").strip()
        return valid_key(value) if value else ""

    def edit_profile(self, tool: str, name: str) -> dict | None:
        self.guard()
        if self.dry_run:
            say(f"[dry-run] 修改 {tool}/{name}，不读密钥、不写配置。")
            return None
        old = self.load(tool, name)
        if old["auth"] == "login":
            say("这是官方账号登录配置。要改用 API，请选择“新建/重新指定 API 配置”。")
            return None
        p = copy.deepcopy(old)
        say(f"修改 {tool}/{name}：不需要修改的字段直接回车；覆盖前会备份。")
        p["base"] = valid_base(prompt("Base URL", old["base"]))
        if p["base"] != old["base"]:
            say("接口地址已改变：不会自动向新地址复用旧 Key，必须重新输入。")
            if not confirm("已确认新地址可信，并支持此客户端要求的协议"):
                return None
            p["preset"], p["label"] = "custom", "自定义 / 修改后的接口"
        p["model"] = valid_model(prompt("模型 ID", old["model"]))
        if p["model"] != old["model"]:
            p.pop("catalog", None)
            p.pop("compact", None)
            p.pop("effort", None)
            p.pop("subagent", None)
            p["context"], p["small"] = 0, p["model"]
        if tool == "claude":
            p["auth"] = prompt("鉴权方式 bearer 或 x-api-key", old["auth"])
            if p["auth"] not in ("bearer", "x-api-key"):
                raise UserError("Claude API 鉴权必须为 bearer 或 x-api-key。")
        p["context"] = integer(prompt("模型上下文 token 上限（未知填 0）", str(p.get("context", 0))))
        if tool == "claude":
            p["small"] = valid_model(prompt("轻量/Haiku 档模型 ID", p.get("small") or p["model"]))
            if p["context"]:
                p["compact"] = integer(prompt("自动压缩窗口 token", str(min(p.get("compact", p["context"]), p["context"]))), 1, p["context"])
            else:
                p.pop("compact", None)
        p["effort"] = prompt("推理强度（auto 表示不显式指定）", p.get("effort") or "auto")
        if p["effort"] == "auto": p["effort"] = ""
        p["save_key"] = save_key_choice()
        key = None
        if p["save_key"]:
            if old.get("save_key") and (p["base"], p["auth"]) == (old["base"], old["auth"]):
                key = self.ask_key_or_keep() or self.get_key(old)
            else:
                key = self.ask_key()
        validate_profile(p)
        say(f'将保存：{tool}/{name} → {p["base"]} → {p["model"]}；Key 不显示。')
        if not confirm("确认保存并设为当前配置"):
            return None
        self.save_profile(p, key)
        self.set_current(tool, name)
        say("已更新；只影响之后通过本工具新启动的会话，不会热切换已经运行的进程。")
        return p

    def bash_block(self) -> str:
        script = shlex.quote(str(self.project / "ai_cli_setup.sh"))
        root_option = " --allow-root" if self.allow_root else ""
        config_option = "" if self.root == self.project / "config" else " --config-dir " + shlex.quote(str(self.root))
        return (BASH_BEGIN + "\n"
                "# Only function entry points; no API keys and no global provider exports.\n"
                "aicli() {\n"
                f"    if [[ ! -f {script} ]]; then\n"
                "        printf '%s\\n' '工具脚本不存在；请在工具的新位置重新运行 install-shell。' >&2\n"
                "        return 127\n"
                "    fi\n"
                f'    command /bin/bash {script}{root_option}{config_option} "$@"\n'
                "}\n"
                'aicodex() { aicli start codex -- "$@"; }\n'
                'aiclaude() { aicli start claude -- "$@"; }\n'
                + BASH_END + "\n")

    def install_shell(self, remove: bool = False) -> None:
        self.guard()
        path = self.home / ".bashrc"
        no_symlinks(path)
        existed = path.exists()
        original = safe_read(path) if existed else b""
        try:
            text = original.decode("utf-8")
        except UnicodeError as exc:
            raise UserError(".bashrc 不是有效 UTF-8 文本，拒绝自动改写。") from exc
        prefix, suffix, found = split_bash_block(text)
        if remove and not found:
            say(".bashrc 中没有本工具的函数块；无需修改。")
            return
        if not remove:
            if not (self.project / "ai_cli_setup.sh").is_file():
                raise UserError("工具项目缺少 ai_cli_setup.sh；请保留完整工具目录。")
            outside = prefix + suffix
            for name in FUNCTION_NAMES:
                pattern = rf"(?m)^\s*(?:function\s+{name}(?:\s*\(\s*\))?\s*\{{|{name}\s*\(\s*\)\s*\{{|alias\s+{name}=)"
                if re.search(pattern, outside):
                    raise UserError(f".bashrc 的非托管区域已有 {name} 函数或别名；不会覆盖，请先解决命名冲突。")
        candidate = update_bash_text(text, None if remove else self.bash_block())
        if candidate == text:
            say("函数块已是当前内容；没有重复追加，没有创建多余备份。")
            return
        say(("将移除" if remove else "将安装/更新") + " ~/.bashrc 中标记包围的函数块。")
        say("函数：aicli / aicodex / aiclaude；原始 codex / claude 命令不会被覆盖。")
        if not remove: say(self.bash_block())
        say("不写入 Key，不全局 export API 变量，不改变工作目录；先备份原 .bashrc。")
        say("这是 Bash 函数，不自动修改 Zsh/Fish 或登录 Shell 的 .profile。")
        if self.dry_run:
            say("[dry-run] 不写 .bashrc，不创建备份。")
            return
        check = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-n"],
                               input=candidate.encode("utf-8"), capture_output=True,
                               env=clean_env(self.environment()))
        if check.returncode:
            raise UserError("候选 .bashrc 未通过 bash -n；保留原文件，未执行其中内容。")
        if not confirm("确认备份后修改 .bashrc"):
            return
        with self.lock():
            no_symlinks(path)
            if path.exists() != existed or (safe_read(path) if existed else b"") != original:
                raise UserError("确认期间 .bashrc 已被其他程序更改；未覆盖，请重试。")
            mode = stat.S_IMODE(path.stat().st_mode) if existed else 0o600
            if mode & 0o022:
                raise UserError(".bashrc 对组或其他用户可写；请先收紧权限后重试。")
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            if existed:
                backup = self.root / "shell-backups" / f"bashrc--{stamp}.bak"
                atomic_write(backup, original)
                say("原文件备份：" + str(backup))
            replace_shell_file(path, candidate.encode("utf-8"), mode)
        if remove:
            say("已移除持久函数块。当前终端执行：unset -f aicli aicodex aiclaude")
            say("未删除 API 配置、密钥、备份或客户端。")
        else:
            say("已写入。当前终端执行：source ~/.bashrc；也可新开一个 Bash 终端。")
            say("从任意业务目录运行 aicodex / aiclaude；保留此工具目录，不要只留下 .sh。")

    def import_v1(self) -> None:
        self.guard()
        if self.root == self.legacy_root:
            raise UserError("当前配置目录已经是 v1 目录，无需向自身导入。")
        legacy = App(home=self.home, project=self.project, config_root=self.legacy_root,
                     allow_root=self.allow_root)
        options = legacy.profiles()
        if not options:
            say("未找到旧版工具配置：" + str(self.legacy_root))
            return
        say(f"从 {self.legacy_root} 导入 {len(options)} 份配置到 {self.root}。")
        say("复制配置和已经保存的明文 Key；保留原文件，不迁移会话历史、OAuth 登录态或旧备份。")
        if self.dry_run:
            say("[dry-run] 不读取 Key、不导入。")
            return
        if not confirm("确认导入以上配置"):
            return
        count = 0
        for p in options:
            tool, name = p["tool"], p["name"]
            if (self.profile_dir(tool, name) / "profile.json").exists():
                if not confirm(f"{tool}/{name} 已存在，先备份再覆盖"):
                    continue
            key = legacy.get_key(p) if p.get("save_key") else None
            self.save_profile(p, key)
            count += 1
        say(f"已导入 {count} 份配置；通过 aicodex / aiclaude 的“选择已保存配置”使用。")
        say("新目录下的官方账号登录配置需要重新登录；Codex 模型目录路径已按新位置生成。")

    def menu(self) -> int:
        say(f"\nWBS-AICli {VERSION} — Ubuntu / Debian 交互安装与多 API 配置")
        say("工具项目：" + str(self.project) + "\n配置目录：" + str(self.root))
        if self.dry_run:
            say("DRY-RUN：不下载、不安装、不保存配置、不请求模型。")
        while True:
            say("\n  1. 只读环境检查\n  2. 安装缺失系统依赖\n  3. 安装/更新 Codex\n  4. 安装/更新 Claude Code\n  5. 依次安装/更新两款 CLI\n  6. 新建/覆盖 API 或官方登录配置\n  7. 查看配置\n  8. 交互启动（复用上次 / 切换 / 新建 / 修改）\n  9. API 基础测试（需另行授权，可能计费）\n 10. 写入/更新 ~/.bashrc 交互函数（推荐）\n 11. 恢复配置备份\n 12. 设置本次代理\n 13. 查看教程与官方文档\n 14. 导入 v1 配置（保留原文件）\n 15. 移除 ~/.bashrc 中本工具的函数\n 16. 可选：安装旧式快捷命令文件\n  0. 退出")
            choice = prompt("选择", "0")
            try:
                if choice == "0":
                    return 0
                if choice == "1": self.doctor()
                elif choice == "2": self.deps()
                elif choice in ("3", "4", "5"): self.install({"3": "codex", "4": "claude", "5": "both"}[choice])
                elif choice == "6": self.configure(choose("选择软件", [(x, x) for x in TOOLS]))
                elif choice == "7": self.show_profiles()
                elif choice == "8":
                    code = self.start(choose("选择软件", [(x, x) for x in TOOLS]))
                    say(f"CLI 已退出，退出码：{code}")
                elif choice == "9": self.test_profile(*self.pick_profile())
                elif choice == "10": self.install_shell()
                elif choice == "11": self.restore()
                elif choice == "12": self.proxy_menu()
                elif choice == "13": show_docs()
                elif choice == "14": self.import_v1()
                elif choice == "15": self.install_shell(remove=True)
                elif choice == "16": self.install_launchers()
                else: say("无效选项。")
            except (UserError, OSError, subprocess.SubprocessError) as exc:
                display_error(exc)


def show_docs() -> None:
    guide = SOURCE_DIR / "README_zh.md"
    if not guide.is_file():
        guide = SOURCE_DIR / "README.md"
    say("使用教程：" + str(guide))
    say("服务商教程：" + str(SOURCE_DIR / "PROVIDERS_zh.md"))
    say("官方文档（核对日期 " + REVIEWED + "）：")
    for label, url in DOCS.items():
        say(label + "\n  " + url)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WBS-AICli — Ubuntu/Debian Codex + Claude Code 安装、隔离配置和启动器。")
    p.add_argument("--dry-run", action="store_true", help="只显示计划；必须放在子命令之前")
    p.add_argument("--allow-root", action="store_true", help="允许 root 运行（如 AutoDL）；子进程继承 root 权限，必须放在子命令之前")
    p.add_argument("--version", action="version", version=VERSION)
    p.add_argument("--config-dir", type=Path, help="高级选项：覆盖配置目录；默认是工具项目/config，不是当前工作目录")
    sub = p.add_subparsers(dest="command")
    for name in ("menu", "doctor", "deps", "list", "launchers", "restore", "docs", "install-shell", "remove-shell", "import-v1", "current"):
        sub.add_parser(name)
    sub.add_parser("install").add_argument("tool", choices=(*TOOLS, "both"))
    sub.add_parser("configure").add_argument("tool", choices=TOOLS)
    start = sub.add_parser("start", help="交互复用上次配置、切换或重新配置")
    start.add_argument("tool", choices=TOOLS)
    start.add_argument("cli_args", nargs=argparse.REMAINDER)
    edit = sub.add_parser("edit", help="修改已存配置；省略配置名时使用当前配置")
    edit.add_argument("tool", choices=TOOLS)
    edit.add_argument("profile", nargs="?")
    for name in ("run", "test"):
        s = sub.add_parser(name)
        s.add_argument("tool", choices=TOOLS)
        s.add_argument("profile")
        if name == "run":
            s.add_argument("cli_args", nargs=argparse.REMAINDER, help="用 -- 分隔要传给原始 CLI 的参数")
    return p


def display_error(exc: Exception) -> None:
    if isinstance(exc, UserError):
        say("错误：" + str(exc))
    elif isinstance(exc, subprocess.CalledProcessError):
        say(f"外部命令失败，退出码 {exc.returncode}；请查看前面的命令输出。")
    elif isinstance(exc, subprocess.TimeoutExpired):
        say("命令超时；没有把超时当作成功。")
    elif isinstance(exc, OSError):
        say(f"系统操作失败（{type(exc).__name__}，errno={exc.errno}）；请检查权限、磁盘和路径。")
    else:
        say("操作失败：" + type(exc).__name__)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    app = App(dry_run=args.dry_run, config_root=args.config_dir, allow_root=args.allow_root)
    command = args.command or "menu"
    try:
        if command == "menu": return app.menu()
        if command == "doctor": app.doctor()
        elif command == "deps": app.deps()
        elif command == "install": app.install(args.tool)
        elif command == "configure": app.configure(args.tool)
        elif command == "list": app.show_profiles()
        elif command == "start": return app.start(args.tool, args.cli_args)
        elif command == "edit":
            selected = args.profile or app.current_name(args.tool)
            if not selected: raise UserError("该软件尚无当前配置，请先 configure 或 start。")
            app.edit_profile(args.tool, selected)
        elif command == "install-shell": app.install_shell()
        elif command == "remove-shell": app.install_shell(remove=True)
        elif command == "import-v1": app.import_v1()
        elif command == "current": app.show_current()
        elif command == "run": return app.run_profile(args.tool, args.profile, args.cli_args)
        elif command == "test": app.test_profile(args.tool, args.profile)
        elif command == "launchers": app.install_launchers()
        elif command == "restore": app.restore()
        elif command == "docs": show_docs()
        return 0
    except (UserError, OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        display_error(exc)
        return 1
    except SessionTerminated:
        say("\n收到终止信号，已退出会话并清理临时配置。")
        return 143
    except KeyboardInterrupt:
        say("\n已取消。")
        return 130


if __name__ == "__main__":
    os.umask(0o077)
    signal.signal(signal.SIGTERM, handle_term)
    raise SystemExit(main())
