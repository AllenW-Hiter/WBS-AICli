#!/usr/bin/env python3
"""Offline tests. No real installer, AI request, sudo, or user's home is used."""
from __future__ import annotations
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("manager_under_test", HERE / "ai_cli_manager.py")
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
try:
    import tomllib
except ImportError:
    tomllib = None  # Ubuntu 22.04 / Python 3.10 has no stdlib tomllib.


def profile(tool="codex", preset="glm", name=None, saved=False):
    p = copy.deepcopy(m.PRESETS[tool][preset])
    p.update(schema=1, tool=tool, name=name or preset, preset=preset, save_key=saved, reviewed=m.REVIEWED)
    if p["auth"] != "login" and not p["model"]:
        p["model"] = "test-model"
        p["base"] = p["base"] or "http://127.0.0.1:9000/v1"
    return p


class ValidationTests(unittest.TestCase):
    def test_valid_names(self):
        for value in ("glm", "test-01", "kimi_cn", "1"):
            self.assertEqual(m.valid_name(value), value)

    def test_invalid_names(self):
        for value in ("", "../x", "a/b", "a;id", "foo bar", "-bad", "中文", "a" * 49):
            with self.subTest(value=value), self.assertRaises(m.UserError):
                m.valid_name(value)

    def test_remote_https(self):
        self.assertEqual(m.valid_base("https://api.example.com/v1/"), "https://api.example.com/v1")

    def test_local_http(self):
        for host in ("localhost", "127.0.0.1", "[::1]"):
            self.assertEqual(m.valid_base(f"http://{host}:9000/v1"), f"http://{host}:9000/v1")

    def test_reject_unsafe_urls(self):
        values = ["http://api.example.com/v1", "file:///tmp/test", "https://a:b@example.com/v1", "https://example.com/?key=secret", "https://example.com/#secret", "https://example.com:99999/v1", "https://example.com/\nx", "https://example.com\\x", "https://x/responses", "https://x/v1/messages", "https://x/v1/chat/completions"]
        for value in values:
            with self.subTest(value=value), self.assertRaises(m.UserError):
                m.valid_base(value)

    def test_model_hints_allowed(self):
        self.assertEqual(m.valid_model("deepseek-flash[1m]"), "deepseek-flash[1m]")
        self.assertEqual(m.valid_model("org/model:latest"), "org/model:latest")

    def test_model_injection_rejected(self):
        for value in ("$(id)", "a\nb", "a\"b", "a b", ""):
            with self.assertRaises(m.UserError):
                m.valid_model(value)

    def test_key_not_shell_evaluated(self):
        self.assertEqual(m.valid_key("sk-$(id)`whoami`;<>\"'\\"), "sk-$(id)`whoami`;<>\"'\\")
        for value in ("", "a\nb", "a b", "x\x1b", "x" * 8193):
            with self.assertRaises(m.UserError):
                m.valid_key(value)

    def test_curl_quote(self):
        self.assertEqual(m.curl_quote('a"b\\c'), '"a\\"b\\\\c"')

    def test_proxy_redacted(self):
        result = m.proxy_display("http://alice:secret@localhost:1234/path?token=secret")
        self.assertEqual(result, "http://***:***@localhost:1234")
        self.assertNotIn("secret", result)

    def test_env_isolation(self):
        env = m.clean_env({"ANTHROPIC_AUTH_TOKEN": "secret", "ANTHROPIC_BASE_URL": "old", "CODEX_HOME": "old", "OPENAI_API_KEY": "old", "BASH_ENV": "bad", "CONDA_PREFIX": "keep", "GITHUB_TOKEN": "keep", "HTTPS_PROXY": "keep"})
        self.assertEqual(env, {"CONDA_PREFIX": "keep", "GITHUB_TOKEN": "keep", "HTTPS_PROXY": "keep"})

    def test_all_presets_valid(self):
        for tool, presets in m.PRESETS.items():
            for preset in presets:
                with self.subTest(tool=tool, preset=preset):
                    m.validate_profile(profile(tool, preset))

    def test_invalid_compact(self):
        p = profile("claude", "glm")
        p["compact"] = p["context"] + 1
        with self.assertRaises(m.UserError):
            m.validate_profile(p)

    def test_zero_context_disables_catalog(self):
        p = profile()
        p["context"] = 0
        self.assertIsNone(m.model_catalog(p))
        self.assertNotIn("model_catalog_json", m.codex_config(p, Path("/tmp/runtime")))

    def test_unknown_model_no_guessed_catalog(self):
        p = profile()
        p["model"] = "future-model"
        self.assertIsNone(m.model_catalog(p))

    def test_codex_protocol_is_responses(self):
        text = m.codex_config(profile(), Path("/tmp/space ' folder"))
        self.assertIn('wire_api = "responses"', text)
        self.assertNotIn('wire_api = "chat"', text)
        self.assertIn('approval_policy = "on-request"', text)
        self.assertIn('sandbox_mode = "workspace-write"', text)
        self.assertIn('env_key = "AI_CLI_API_KEY"', text)

    @unittest.skipIf(tomllib is None, "TOML parser is not in Python 3.10 stdlib")
    def test_all_codex_toml_parses(self):
        for preset in m.PRESETS["codex"]:
            with self.subTest(preset=preset):
                tomllib.loads(m.codex_config(profile("codex", preset), Path("/tmp/测试 ' a")))

    def test_catalog_json_roundtrip(self):
        for preset in ("glm", "deepseek"):
            catalog = m.model_catalog(profile("codex", preset))
            self.assertEqual(json.loads(m.json_text(catalog)), catalog)
            self.assertGreater(catalog["models"][0]["context_window"], 0)

    def test_claude_auth_types(self):
        for preset, expected in (("glm", "ANTHROPIC_AUTH_TOKEN"), ("kimi-code", "ANTHROPIC_API_KEY")):
            env = m.claude_settings(profile("claude", preset), "secret")["env"]
            self.assertEqual(env[expected], "secret")
            other = "ANTHROPIC_AUTH_TOKEN" if expected == "ANTHROPIC_API_KEY" else "ANTHROPIC_API_KEY"
            self.assertEqual(env[other], "")

    def test_persistent_claude_settings_no_key(self):
        text = m.json_text(m.claude_settings(profile("claude", "glm")))
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)

    def test_probe_routes_and_hint_removal(self):
        url, payload = m.probe_payload(profile("claude", "deepseek"))
        self.assertEqual(url, "https://api.deepseek.com/anthropic/v1/messages")
        self.assertEqual(payload["model"], "deepseek-flash")
        url, _ = m.probe_payload(profile("codex", "kimi-cn"))
        self.assertEqual(url, "https://api.moonshot.cn/v1/responses")

    def test_python_310_syntax(self):
        for name in ("ai_cli_manager.py", "test_toolkit.py"):
            ast.parse((HERE / name).read_text(), feature_version=(3, 10))

    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(HERE / "ai_cli_setup.sh")], check=True)

    def test_root_guard(self):
        with mock.patch.object(m.os, "geteuid", return_value=0), self.assertRaises(m.UserError):
            m.App().guard()

    def test_parser_cli_argument_forwarding(self):
        args = m.parser().parse_args(["run", "claude", "glm", "--", "-p", "hello"])
        self.assertEqual(args.cli_args, ["-p", "hello"])


class FileAndExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aikit-test-")
        self.home = Path(self.temp.name) / "home with ' quote"
        self.home.mkdir()
        self.project = self.home / "tool project with ' quote"
        self.project.mkdir()
        for filename in ("ai_cli_manager.py", "ai_cli_setup.sh"):
            shutil.copyfile(HERE / filename, self.project / filename)
        self.app = m.App(home=self.home, project=self.project)
        self.guard = mock.patch.object(self.app, "guard")
        self.guard.start()
        self.out = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.out)
        self.redirect.start = lambda: self.redirect.__enter__()
        self.redirect.start()

    def tearDown(self):
        self.redirect.__exit__(None, None, None)
        self.guard.stop()
        self.temp.cleanup()

    def save(self, tool="codex", preset="glm", saved=False, key="sk-test", name=None):
        p = profile(tool, preset, name, saved)
        self.app.save_profile(p, key if saved else None)
        return p

    def test_constructor_does_not_create_tree(self):
        self.assertFalse(self.app.root.exists())
        self.assertFalse(self.app.data.exists())

    def test_save_permissions_and_roundtrip(self):
        p = self.save(saved=True)
        folder = self.app.profile_dir("codex", "glm")
        self.assertEqual(self.app.load("codex", "glm"), p)
        self.assertEqual(stat.S_IMODE((folder / "key.txt").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
        self.assertEqual(self.app.get_key(p), "sk-test")
        for f in ("profile.json", "codex/config.toml", "codex/models.json"):
            self.assertNotIn("sk-test", (folder / f).read_text())

    def test_no_key_saved_by_default(self):
        self.save()
        self.assertFalse((self.app.profile_dir("codex", "glm") / "key.txt").exists())

    def test_original_configuration_preserved(self):
        originals = [self.home / ".codex/config.toml", self.home / ".claude/settings.json", self.home / ".claude.json", self.home / ".bashrc", self.home / ".profile"]
        for f in originals:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("original-data")
        self.save()
        self.save("claude", "glm")
        self.save(saved=True, key="new-key")
        self.assertTrue(all(f.read_text() == "original-data" for f in originals))

    def test_overwrite_backup_contains_old_key(self):
        self.save(saved=True, key="old-key")
        self.save(saved=True, key="new-key")
        snapshots = list((self.app.root / "backups").glob("*/snapshot.json"))
        self.assertEqual(len(snapshots), 1)
        snapshot = json.loads(snapshots[0].read_text())
        self.assertEqual(snapshot["files"]["key.txt"], "old-key\n")
        self.assertEqual(stat.S_IMODE(snapshots[0].stat().st_mode), 0o600)

    def test_restore_key_and_model(self):
        old = self.save(saved=True, key="old-key")
        new = copy.deepcopy(old)
        new["model"] = "replacement"
        new.pop("catalog")
        self.app.save_profile(new, "new-key")
        with mock.patch.object(m, "choose", return_value="0"), mock.patch.object(m, "confirm", return_value=True):
            self.app.restore()
        self.assertEqual(self.app.load("codex", "glm")["model"], old["model"])
        self.assertEqual(self.app.get_key(old), "old-key")
        self.assertEqual(len(list((self.app.root / "backups").glob("*/snapshot.json"))), 2)

    def test_malformed_backup_no_partial_restore(self):
        p = self.save(saved=True)
        self.save(saved=True, key="second-key")
        target = next((self.app.root / "backups").glob("*/snapshot.json"))
        data = json.loads(target.read_text())
        data["files"]["codex/config.toml"] = 123
        target.write_text(json.dumps(data))
        before = self.app.get_key(p)
        with mock.patch.object(m, "choose", return_value="0"), mock.patch.object(m, "confirm", return_value=True), self.assertRaises(m.UserError):
            self.app.restore()
        self.assertEqual(self.app.get_key(p), before)

    def test_key_removed_when_persistence_disabled(self):
        self.save(saved=True)
        self.save()
        self.assertFalse((self.app.profile_dir("codex", "glm") / "key.txt").exists())

    def test_reject_world_readable_key(self):
        p = self.save(saved=True)
        (self.app.profile_dir("codex", "glm") / "key.txt").chmod(0o644)
        with self.assertRaises(m.UserError):
            self.app.get_key(p)

    def test_reject_symlink_write(self):
        target = self.home / "target"
        target.write_text("keep")
        alias = self.home / "alias"
        alias.symlink_to(target)
        with self.assertRaises(m.UserError):
            m.atomic_write(alias, "changed")
        self.assertEqual(target.read_text(), "keep")

    def test_reject_symlink_parent(self):
        target = self.home / "target"
        target.mkdir()
        alias = self.home / "alias"
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaises(m.UserError):
            m.atomic_write(alias / "new", "changed")

    def test_dry_install_no_subprocess_or_files(self):
        self.app.dry_run = True
        with mock.patch.object(m.subprocess, "run", side_effect=AssertionError("external call")):
            self.app.install("both")
            self.app.configure("codex")
            self.app.install_launchers()
        self.assertFalse(self.app.root.exists())
        self.assertFalse(self.app.data.exists())

    def test_dry_run_profile_no_key_or_execution(self):
        self.save(saved=True)
        self.app.dry_run = True
        with mock.patch.object(self.app, "get_key", side_effect=AssertionError("key read")), mock.patch.object(m.subprocess, "run", side_effect=AssertionError("execution")):
            self.assertEqual(self.app.run_profile("codex", "glm"), 0)
            self.app.test_profile("codex", "glm")

    def test_misplaced_dry_run_rejected(self):
        self.save()
        with self.assertRaises(m.UserError), mock.patch.object(m.subprocess, "run", side_effect=AssertionError("execution")):
            self.app.run_profile("codex", "glm", ["--dry-run"])

    def test_codex_child_env_and_returncode(self):
        self.save(saved=True)
        def execute(command, **kw):
            self.assertEqual(command, ["/fake/codex", "exec", "hello"])
            self.assertEqual(kw["env"]["AI_CLI_API_KEY"], "sk-test")
            self.assertEqual(kw["env"]["CODEX_HOME"], str(self.app.profile_dir("codex", "glm") / "codex"))
            self.assertNotIn("ANTHROPIC_AUTH_TOKEN", kw["env"])
            return subprocess.CompletedProcess(command, 7)
        with mock.patch.object(m.shutil, "which", return_value="/fake/codex"), mock.patch.object(m.subprocess, "run", side_effect=execute), mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "old-secret"}):
            self.assertEqual(self.app.run_profile("codex", "glm", ["--", "exec", "hello"]), 7)

    def test_claude_session_secret_and_cleanup(self):
        self.save("claude", "glm", saved=True)
        seen = []
        def execute(command, **kw):
            self.assertNotIn("sk-test", " ".join(command))
            self.assertEqual(command[:3], ["/fake/claude", "-p", "hello"])
            settings = Path(command[-1])
            seen.append(settings)
            self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o600)
            self.assertEqual(json.loads(settings.read_text())["env"]["ANTHROPIC_AUTH_TOKEN"], "sk-test")
            self.assertNotIn("ANTHROPIC_AUTH_TOKEN", kw["env"])
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(m.shutil, "which", return_value="/fake/claude"), mock.patch.object(m.subprocess, "run", side_effect=execute):
            self.app.run_profile("claude", "glm", ["-p", "hello"])
        self.assertTrue(seen)
        self.assertFalse(seen[0].exists())

    def test_temporary_secret_cleaned_on_interrupt(self):
        self.save("claude", "glm", saved=True)
        with mock.patch.object(m.shutil, "which", return_value="/fake/claude"), mock.patch.object(m.subprocess, "run", side_effect=m.SessionTerminated), self.assertRaises(m.SessionTerminated):
            self.app.run_profile("claude", "glm")
        self.assertEqual(list(self.app.profile_dir("claude", "glm").glob("session-*")), [])

    def test_host_managed_route_not_overridden(self):
        self.save("claude", "glm")
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST": "1"}), self.assertRaises(m.UserError):
            self.app.run_profile("claude", "glm")

    def test_probe_success_key_not_on_argv(self):
        self.save(saved=True)
        def execute(command, **kw):
            self.assertNotIn("sk-test", " ".join(command))
            self.assertIn("sk-test", kw["input"])
            self.assertNotIn("--location", command)
            self.assertNotIn("--retry", command)
            return subprocess.CompletedProcess(command, 0, '{"object":"response","status":"completed"}\n__AIKIT_STATUS__:200', "")
        with mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m.shutil, "which", return_value="/fake/curl"), mock.patch.object(m.subprocess, "run", side_effect=execute):
            self.app.test_profile("codex", "glm")
        self.assertNotIn("sk-test", self.out.getvalue())

    def test_probe_failed_exit_path_and_no_raw_key(self):
        self.save(saved=True)
        result = subprocess.CompletedProcess([], 0, '{"error":{"message":"sk-test"}}\n__AIKIT_STATUS__:401', "")
        with mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m.shutil, "which", return_value="/fake/curl"), mock.patch.object(m.subprocess, "run", return_value=result), self.assertRaises(m.UserError) as error:
            self.app.test_profile("codex", "glm")
        self.assertNotIn("sk-test", str(error.exception) + self.out.getvalue())

    def test_probe_decline_no_request(self):
        self.save()
        with mock.patch.object(m, "confirm", return_value=False), mock.patch.object(m.subprocess, "run", side_effect=AssertionError("network")):
            self.app.test_profile("codex", "glm")

    def test_launchers_contain_no_key_and_parse(self):
        self.save(saved=True)
        with mock.patch.object(m, "confirm", return_value=True):
            self.app.install_launchers()
        for path in self.app.bin.iterdir():
            self.assertNotIn("sk-test", path.read_text())
            self.assertIn("-B -I", path.read_text())
            subprocess.run(["bash", "-n", str(path)], check=True)
        result = subprocess.run([str(self.app.bin / "ai-cli"), "--version"], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), m.VERSION)

    def test_launcher_collision_not_overwritten(self):
        self.app.bin.mkdir(parents=True)
        existing = self.app.bin / "ai-cli"
        existing.write_text("custom-existing-file")
        with mock.patch.object(m, "confirm", return_value=True), self.assertRaises(m.UserError):
            self.app.install_launchers()
        self.assertEqual(existing.read_text(), "custom-existing-file")

    def test_doctor_is_read_only_and_redacted(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret", "HTTPS_PROXY": "http://alice:proxy-secret@localhost:5555"}), mock.patch.object(m.subprocess, "run", side_effect=AssertionError("execution")):
            self.app.doctor()
        self.assertNotIn("top-secret", self.out.getvalue())
        self.assertNotIn("proxy-secret", self.out.getvalue())
        self.assertFalse(self.app.root.exists())

    def test_configuration_cancel_leaves_no_files(self):
        with mock.patch.object(m, "choose", return_value="official"), mock.patch.object(m, "prompt", return_value="official"), mock.patch.object(m, "confirm", return_value=False):
            self.app.configure("codex")
        self.assertFalse(self.app.root.exists())

    def test_install_download_review_execute_order(self):
        actions = []
        installed = [False]
        def which(name, path=None):
            return "/fake/curl" if name == "curl" else ("/fake/codex" if installed[0] else None)
        def execute(command, **kw):
            if command[0] == "curl":
                actions.append("download")
                Path(command[command.index("--output") + 1]).write_text("#!/bin/sh\nexit 0\n")
            elif "-n" in command:
                actions.append("syntax-check")
            elif "--version" in command:
                actions.append("version")
                return subprocess.CompletedProcess(command, 0, "codex mock-version\n", "")
            else:
                actions.append("install")
                installed[0] = True
            return subprocess.CompletedProcess(command, 0, "", "")
        with mock.patch.object(self.app, "deps"), mock.patch.object(m.shutil, "which", side_effect=which), mock.patch.object(m, "confirm", side_effect=[True, False, True]), mock.patch.object(m.subprocess, "run", side_effect=execute):
            self.app.install("codex")
        self.assertEqual(actions, ["download", "syntax-check", "install", "version"])
        self.assertEqual(len(list((self.app.data / "installers").glob("*.sha256"))), 1)

    def test_installer_html_rejected(self):
        def execute(command, **kw):
            self.assertEqual(command[0], "curl")
            Path(command[command.index("--output") + 1]).write_text("<html>blocked</html>")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(self.app, "deps"), mock.patch.object(m.shutil, "which", side_effect=lambda name, path=None: "/fake/curl" if name == "curl" else None), mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m.subprocess, "run", side_effect=execute), self.assertRaises(m.UserError):
            self.app.install("codex")

    def test_installer_execution_declined(self):
        actions = []
        def execute(command, **kw):
            actions.append(command)
            if command[0] == "curl":
                Path(command[command.index("--output") + 1]).write_text("#!/bin/sh\nexit 0\n")
            else:
                self.assertIn("-n", command)
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(self.app, "deps"), mock.patch.object(m.shutil, "which", side_effect=lambda name, path=None: "/fake/curl" if name == "curl" else None), mock.patch.object(m, "confirm", side_effect=[True, False, False]), mock.patch.object(m.subprocess, "run", side_effect=execute):
            self.app.install("codex")
        self.assertEqual(len(actions), 2)

    def test_dry_dependencies_read_dpkg_only(self):
        self.app.dry_run = True
        commands = []
        def execute(command, **kw):
            commands.append(command)
            self.assertEqual(command[0], "dpkg-query")
            return subprocess.CompletedProcess(command, 0 if command[-1] != "curl" else 1, "install ok installed", "")
        with mock.patch.object(m.shutil, "which", return_value="/fake/system-tool"), mock.patch.object(m.subprocess, "run", side_effect=execute):
            self.app.deps()
        self.assertEqual(len(commands), 3)
        self.assertIn("install --no-install-recommends curl", self.out.getvalue())

    def test_custom_key_with_shell_characters_stays_literal(self):
        key = "sk-$(touch${IFS}/tmp/do-not-create);`id`\"'\\"
        p = self.save(saved=True, key=key)
        self.assertEqual(self.app.get_key(p), key)


class V2InteractionTests(unittest.TestCase):
    setUp = FileAndExecutionTests.setUp
    tearDown = FileAndExecutionTests.tearDown
    save = FileAndExecutionTests.save

    def test_project_local_default_not_cwd_or_home(self):
        self.assertEqual(self.app.root, self.project / "config")
        self.assertNotEqual(self.app.root, self.home / ".config/ai-cli-toolkit")
        self.assertFalse(self.app.root.exists())

    def test_explicit_config_override(self):
        other = m.App(home=self.home, project=self.project, config_root=self.home / "different")
        self.assertEqual(other.root, self.home / "different")
        self.assertIn("--config-dir", other.bash_block())

    def test_state_persists_independently_per_tool(self):
        self.save(saved=True)
        self.save("claude", "deepseek", saved=True)
        self.app.set_current("codex", "glm")
        self.app.set_current("claude", "deepseek")
        restarted = m.App(home=self.home, project=self.project)
        self.assertEqual(restarted.current_name("codex"), "glm")
        self.assertEqual(restarted.current_name("claude"), "deepseek")
        self.assertNotIn("sk-test", (self.app.root / "state.json").read_text())
        self.assertEqual(stat.S_IMODE((self.app.root / "state.json").stat().st_mode), 0o600)

    def test_state_missing_does_not_create_files(self):
        self.assertIsNone(self.app.current_name("codex"))
        self.assertFalse(self.app.root.exists())

    def test_state_missing_profile_not_auto_switched(self):
        self.save()
        self.app.set_current("codex", "glm")
        (self.app.profile_dir("codex", "glm") / "profile.json").unlink()
        self.assertIsNone(self.app.current_name("codex"))

    def test_bad_state_not_silently_overwritten(self):
        self.save()
        path = self.app.root / "state.json"
        path.write_text('{"schema":99,"tools":{}}')
        with self.assertRaises(m.UserError): self.app.set_current("codex", "glm")
        self.assertIn('99', path.read_text())

    def test_invalid_state_profile_path_rejected(self):
        self.save()
        (self.app.root / "state.json").write_text('{"schema":1,"tools":{"codex":{"selected":"../escape"}}}')
        with self.assertRaises(m.UserError): self.app.current_name("codex")

    def test_session_exit_record_and_no_secret(self):
        self.save(saved=True)
        with mock.patch.object(m.shutil, "which", return_value="/fake/codex"), mock.patch.object(m.subprocess, "run", return_value=subprocess.CompletedProcess([], 9)):
            self.assertEqual(self.app.run_profile("codex", "glm"), 9)
        state = self.app.read_state()
        record = state["tools"]["codex"]
        self.assertEqual(record["selected"], "glm")
        self.assertEqual(record["last_run"]["exit_code"], 9)
        self.assertEqual(record["last_run"]["status"], "exited")
        self.assertNotIn("sk-test", json.dumps(state))

    def test_failed_executable_not_marked_success(self):
        self.save(saved=True)
        with mock.patch.object(m.shutil, "which", return_value="/fake/codex"), mock.patch.object(m.subprocess, "run", side_effect=OSError(2, "not found")), self.assertRaises(OSError):
            self.app.run_profile("codex", "glm")
        record = self.app.read_state()["tools"]["codex"]["last_run"]
        self.assertEqual(record["status"], "failed_to_start")
        self.assertIsNone(record["exit_code"])

    def test_older_session_cannot_overwrite_newer_session_state(self):
        self.save(saved=True)
        self.save(preset="deepseek", saved=True)
        def run(command, **kw):
            self.app.set_current("codex", "deepseek")
            state = self.app.read_state()
            state["tools"]["codex"]["last_run"] = {"id":"newer", "profile":"deepseek", "status":"starting"}
            m.atomic_write(self.app.root / "state.json", m.json_text(state))
            return subprocess.CompletedProcess(command, 7)
        with mock.patch.object(m.shutil, "which", return_value="/fake/codex"), mock.patch.object(m.subprocess, "run", side_effect=run):
            self.app.run_profile("codex", "glm")
        self.assertEqual(self.app.current_name("codex"), "deepseek")
        self.assertEqual(self.app.read_state()["tools"]["codex"]["last_run"]["id"], "newer")

    def test_current_selection_changed_during_run_preserved(self):
        self.save(saved=True)
        self.save(preset="deepseek", saved=True)
        def run(command, **kw):
            self.app.set_current("codex", "deepseek")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(m.shutil, "which", return_value="/fake/codex"), mock.patch.object(m.subprocess, "run", side_effect=run):
            self.app.run_profile("codex", "glm")
        self.assertEqual(self.app.current_name("codex"), "deepseek")

    def test_start_enter_reuses_saved_profile(self):
        self.save(saved=True)
        self.app.set_current("codex", "glm")
        with mock.patch.object(m, "prompt", return_value="1"), mock.patch.object(self.app, "run_profile", return_value=4) as run:
            self.assertEqual(self.app.start("codex", ["--", "exec", "hello there"]), 4)
        run.assert_called_once_with("codex", "glm", ["--", "exec", "hello there"])

    def test_start_choose_other_saved_profile(self):
        self.save(saved=True)
        self.save(preset="deepseek", saved=True)
        self.app.set_current("codex", "glm")
        with mock.patch.object(m, "prompt", return_value="2"), mock.patch.object(self.app, "pick_profile", return_value=("codex", "deepseek")), mock.patch.object(self.app, "run_profile", return_value=0) as run:
            self.app.start("codex")
        run.assert_called_once_with("codex", "deepseek", None)

    def test_start_cancel_does_not_write_or_launch(self):
        with mock.patch.object(m, "prompt", return_value="0"), mock.patch.object(self.app, "run_profile", side_effect=AssertionError("launch")):
            self.assertEqual(self.app.start("claude"), 0)
        self.assertFalse(self.app.root.exists())

    def test_start_new_configuration_menu_path(self):
        with mock.patch.object(m, "prompt", side_effect=["3", "0"]), mock.patch.object(self.app, "configure") as configure:
            self.app.start("codex")
        configure.assert_called_once_with("codex")

    def test_start_dry_run_has_no_side_effects(self):
        self.app.dry_run = True
        with mock.patch.object(m, "prompt", side_effect=AssertionError("prompt")), mock.patch.object(m.subprocess, "run", side_effect=AssertionError("run")):
            self.assertEqual(self.app.start("codex"), 0)
        self.assertFalse(self.app.root.exists())

    def test_save_key_prompt_defaults_to_yes(self):
        with mock.patch.object(m, "prompt", side_effect=lambda message, default: default):
            self.assertTrue(m.save_key_choice())

    def test_newly_entered_unsaved_key_can_persist(self):
        p = self.save()
        with mock.patch.object(self.app, "ask_key", return_value="sk-fresh"), mock.patch.object(m, "save_key_choice", return_value=True):
            self.assertEqual(self.app.get_key(p), "sk-fresh")
        loaded = self.app.load("codex", "glm")
        self.assertTrue(loaded["save_key"])
        self.assertEqual(self.app.get_key(loaded), "sk-fresh")

    def test_key_persistence_can_be_declined(self):
        p = self.save()
        with mock.patch.object(self.app, "ask_key", return_value="sk-ephemeral"), mock.patch.object(m, "save_key_choice", return_value=False):
            self.app.get_key(p)
        self.assertFalse((self.app.profile_dir("codex", "glm") / "key.txt").exists())

    def test_edit_enter_keeps_saved_key(self):
        self.save(saved=True)
        with mock.patch.object(m, "prompt", side_effect=lambda message, default=None: default), mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m, "save_key_choice", return_value=True), mock.patch.object(self.app, "ask_key_or_keep", return_value=""):
            self.app.edit_profile("codex", "glm")
        self.assertEqual(self.app.get_key(self.app.load("codex", "glm")), "sk-test")
        self.assertEqual(self.app.current_name("codex"), "glm")

    def test_edit_key_updates_and_backs_up_old_key(self):
        self.save(saved=True)
        with mock.patch.object(m, "prompt", side_effect=lambda message, default=None: default), mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m, "save_key_choice", return_value=True), mock.patch.object(self.app, "ask_key_or_keep", return_value="sk-new"):
            self.app.edit_profile("codex", "glm")
        self.assertEqual(self.app.get_key(self.app.load("codex", "glm")), "sk-new")
        backup = next((self.app.root / "backups").glob("*/snapshot.json"))
        self.assertIn("sk-test", backup.read_text())

    def test_endpoint_change_forces_new_key(self):
        self.save(saved=True)
        def answer(message, default=None):
            return "https://new.example/v1" if message == "Base URL" else default
        with mock.patch.object(m, "prompt", side_effect=answer), mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m, "save_key_choice", return_value=True), mock.patch.object(self.app, "ask_key", return_value="sk-new-endpoint") as ask, mock.patch.object(self.app, "ask_key_or_keep", side_effect=AssertionError("old-key reuse")):
            self.app.edit_profile("codex", "glm")
        ask.assert_called_once()
        self.assertEqual(self.app.get_key(self.app.load("codex", "glm")), "sk-new-endpoint")

    def test_endpoint_change_decline_preserves_profile(self):
        p = self.save(saved=True)
        with mock.patch.object(m, "prompt", return_value="https://new.example/v1"), mock.patch.object(m, "confirm", return_value=False):
            self.app.edit_profile("codex", "glm")
        self.assertEqual(self.app.load("codex", "glm"), p)

    def test_edit_model_clears_guessed_catalog(self):
        self.save(saved=True)
        def answer(message, default=None):
            return "different-model" if message == "模型 ID" else default
        with mock.patch.object(m, "prompt", side_effect=answer), mock.patch.object(m, "confirm", return_value=True), mock.patch.object(m, "save_key_choice", return_value=True), mock.patch.object(self.app, "ask_key_or_keep", return_value=""):
            self.app.edit_profile("codex", "glm")
        p = self.app.load("codex", "glm")
        self.assertEqual(p["context"], 0)
        self.assertNotIn("catalog", p)

    def test_bash_install_preserves_original_and_home_permissions(self):
        path = self.home / ".bashrc"
        original = '# custom\nexport MY_VAR="keep"\n'
        path.write_text(original)
        path.chmod(0o644)
        self.home.chmod(0o755)
        with mock.patch.object(m, "confirm", return_value=True): self.app.install_shell()
        self.assertTrue(path.read_text().startswith(original))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(self.home.stat().st_mode), 0o755)
        backups = list((self.app.root / "shell-backups").glob("*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)

    def test_bash_install_idempotent(self):
        with mock.patch.object(m, "confirm", return_value=True): self.app.install_shell()
        first = (self.home / ".bashrc").read_text()
        with mock.patch.object(m, "confirm", side_effect=AssertionError("unexpected prompt")): self.app.install_shell()
        self.assertEqual((self.home / ".bashrc").read_text(), first)
        self.assertEqual(first.count(m.BASH_BEGIN), 1)

    def test_bash_remove_preserves_outside_text(self):
        path = self.home / ".bashrc"
        path.write_text('# before\n' + self.app.bash_block() + '# after\n')
        with mock.patch.object(m, "confirm", return_value=True): self.app.install_shell(remove=True)
        self.assertEqual(path.read_text(), '# before\n# after\n')

    def test_bash_conflicting_function_refused(self):
        path = self.home / ".bashrc"
        for text in ('aicli() { echo custom; }\n', 'alias aicodex="mytool"\n', 'function aiclaude { echo other; }\n'):
            path.write_text(text)
            with self.assertRaises(m.UserError): self.app.install_shell()
            self.assertEqual(path.read_text(), text)

    def test_bash_duplicate_or_malformed_marker_refused(self):
        path = self.home / ".bashrc"
        for text in (m.BASH_BEGIN + '\n', self.app.bash_block() * 2, m.BASH_END + '\n' + m.BASH_BEGIN + '\n'):
            path.write_text(text)
            with self.assertRaises(m.UserError): self.app.install_shell()
            self.assertEqual(path.read_text(), text)

    def test_bash_symlink_refused(self):
        target = self.home / "realbashrc"
        target.write_text("# target\n")
        (self.home / ".bashrc").symlink_to(target)
        with self.assertRaises(m.UserError): self.app.install_shell()
        self.assertEqual(target.read_text(), "# target\n")

    def test_bash_invalid_syntax_refused_without_execution(self):
        path = self.home / ".bashrc"
        text = 'if then\n'
        path.write_text(text)
        with self.assertRaises(m.UserError): self.app.install_shell()
        self.assertEqual(path.read_text(), text)
        self.assertFalse(self.app.root.exists())

    def test_bash_conflict_during_confirmation_detected(self):
        path = self.home / ".bashrc"
        path.write_text("# original\n")
        def confirm(message):
            path.write_text("# concurrent change\n")
            return True
        with mock.patch.object(m, "confirm", side_effect=confirm), self.assertRaises(m.UserError):
            self.app.install_shell()
        self.assertEqual(path.read_text(), "# concurrent change\n")

    def test_bash_decline_no_write(self):
        with mock.patch.object(m, "confirm", return_value=False): self.app.install_shell()
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertFalse(self.app.root.exists())

    def test_bash_dry_run_no_write(self):
        self.app.dry_run = True
        with mock.patch.object(m.subprocess, "run", side_effect=AssertionError("exec")): self.app.install_shell()
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertFalse(self.app.root.exists())

    def test_bash_functions_no_key_no_global_exports(self):
        self.save(saved=True, key="sk-super-private")
        with mock.patch.object(m, "confirm", return_value=True): self.app.install_shell()
        text = (self.home / ".bashrc").read_text()
        self.assertNotIn("sk-super-private", text)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", text)
        self.assertNotIn("export ", text)
        self.assertNotIn("codex()", text.replace("aicodex()", ""))

    def test_real_bash_functions_keep_cwd_and_forward_special_args(self):
        # Run real Bash against a stub project script; no real API or CLI.
        stub = self.project / "ai_cli_setup.sh"
        stub.write_text("#!/bin/bash\n/usr/bin/python3 -I -c 'import os,sys,json; print(json.dumps({\"cwd\":os.getcwd(),\"argv\":sys.argv[1:]}))' \"$@\"\n")
        path = self.home / ".bashrc"
        path.write_text(self.app.bash_block())
        work = self.home / "business project"
        work.mkdir()
        payload = 'a b;$(touch SHOULD_NOT_EXIST)"\'\\'
        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", 'source "$1"; aicodex exec "$2"; pwd', "test", str(path), payload], cwd=work, text=True, capture_output=True, check=True)
        lines = result.stdout.splitlines()
        data = json.loads(lines[0])
        self.assertEqual(data["argv"], ["start", "codex", "--", "exec", payload])
        self.assertEqual(data["cwd"], str(work))
        self.assertEqual(lines[-1], str(work))
        self.assertFalse((work / "SHOULD_NOT_EXIST").exists())

    def test_real_bash_claude_parameter_forwarding(self):
        (self.project / "ai_cli_setup.sh").write_text('#!/bin/bash\nprintf "<%s>\\n" "$@"\n')
        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", self.app.bash_block() + '\naiclaude -p "hello world"'], text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.splitlines(), ['<start>', '<claude>', '<-->', '<-p>', '<hello world>'])

    def test_bash_missing_project_exits_with_useful_code(self):
        (self.project / "ai_cli_setup.sh").unlink()
        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", self.app.bash_block() + '\naicli doctor'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 127)

    def test_import_v1_regenerates_paths_preserves_original(self):
        legacy = m.App(home=self.home, project=self.project, config_root=self.app.legacy_root)
        old = profile(saved=True)
        with mock.patch.object(legacy, "guard"): legacy.save_profile(old, "sk-legacy")
        old_config = (legacy.profile_dir("codex", "glm") / "codex/config.toml").read_text()
        with mock.patch.object(m, "confirm", return_value=True): self.app.import_v1()
        p = self.app.load("codex", "glm")
        self.assertEqual(self.app.get_key(p), "sk-legacy")
        new_config = (self.app.profile_dir("codex", "glm") / "codex/config.toml").read_text()
        self.assertIn(str(self.app.root), new_config)
        self.assertNotIn(str(legacy.root), new_config)
        self.assertEqual((legacy.profile_dir("codex", "glm") / "codex/config.toml").read_text(), old_config)

    def test_import_decline_leaves_new_config_empty(self):
        legacy = m.App(home=self.home, project=self.project, config_root=self.app.legacy_root)
        with mock.patch.object(legacy, "guard"): legacy.save_profile(profile(saved=True), "sk-legacy")
        with mock.patch.object(m, "confirm", return_value=False): self.app.import_v1()
        self.assertFalse(self.app.root.exists())

    def test_current_display_redacted(self):
        self.save(saved=True, key="sk-never-display")
        self.app.set_current("codex", "glm")
        self.app.show_current()
        self.assertNotIn("sk-never-display", self.out.getvalue())

    def test_new_parser_commands(self):
        args = m.parser().parse_args(["start", "claude", "--", "-p", "hello world"])
        self.assertEqual(args.cli_args, ["-p", "hello world"])
        args = m.parser().parse_args(["edit", "codex"])
        self.assertIsNone(args.profile)
        for cmd in ("install-shell", "remove-shell", "import-v1", "current"):
            self.assertEqual(m.parser().parse_args([cmd]).command, cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
