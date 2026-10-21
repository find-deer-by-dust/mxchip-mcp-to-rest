"""Offline checks for the single Python entry point."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import main


class MainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "requirements.txt").write_text("mcpo==0.0.20\n")
        for replacement in (patch.object(main, "ROOT", self.root),
                            patch.object(sys, "path", sys.path[:]),
                            patch.dict(os.environ, {"AUTHORIZATION": "Bearer test-token", "HOST": "0.0.0.0",
                                                   "PORT": "8000", "API_KEY": ""})):
            replacement.start()
            self.addCleanup(replacement.stop)

    def run_entry(self):
        captured = {}

        def serve(*, args):
            captured["args"] = args
            path = Path(args[args.index("--config") + 1])
            captured["path"] = path
            captured["config"] = json.loads(path.read_text())
            captured["authorization"] = os.environ["AUTHORIZATION"]

        modules = {"mcpo": types.SimpleNamespace(app=serve),
                   "dotenv": types.SimpleNamespace(load_dotenv=Mock())}
        with patch.object(main, "ensure_dependencies"), patch.dict(sys.modules, modules), \
             patch.object(sys, "version_info", (3, 11)), patch("builtins.print"):
            main.main()
        return captured

    def test_authorization_is_enough_to_start_both_http_tools(self):
        os.environ["AUTHORIZATION"] = "test-token"
        result = self.run_entry()
        self.assertEqual(result["authorization"], "Bearer test-token")
        self.assertEqual(result["args"][:4], ["--host", "0.0.0.0", "--port", "8000"])
        self.assertEqual(set(result["config"]["mcpServers"]), {"dehumidifier"})
        self.assertNotIn("--api-key", result["args"])
        self.assertNotIn("test-token", json.dumps(result["config"]))
        self.assertFalse(result["path"].exists(), "temporary config must be cleaned up")

    def test_http_api_key_is_optional_and_independent(self):
        os.environ["API_KEY"] = "client-device-key"
        result = self.run_entry()
        self.assertEqual(result["args"][-2:], ["--api-key", "client-device-key"])
        self.assertEqual(result["authorization"], "Bearer test-token")

    def test_missing_authorization_uses_hidden_prompt(self):
        os.environ["AUTHORIZATION"] = ""
        with patch.object(main.getpass, "getpass", return_value="supplied-interactively") as prompt:
            result = self.run_entry()
        prompt.assert_called_once()
        self.assertEqual(result["authorization"], "Bearer supplied-interactively")

    def test_invalid_authorization_or_port_is_rejected(self):
        for token, port in (("Bearer ", "8000"), ("bad\ntoken", "8000"),
                            ("valid", "0"), ("valid", "65536")):
            with self.subTest(token=token, port=port):
                os.environ.update(AUTHORIZATION=token, PORT=port)
                with self.assertRaises(ValueError):
                    self.run_entry()

    def test_dependencies_install_once_inside_project(self):
        with patch.object(main.importlib.util, "find_spec", return_value=object()), \
             patch.object(main.subprocess, "run") as install, patch("builtins.print"):
            main.ensure_dependencies()
            command = install.call_args.args[0]
            self.assertEqual(command[:4], [sys.executable, "-m", "pip", "install"])
            self.assertEqual(command[command.index("--target") + 1], str(self.root / ".packages"))
            main.ensure_dependencies()
            install.assert_called_once()

    def test_missing_pip_is_bootstrapped_without_system_install(self):
        with patch.object(main.importlib.util, "find_spec", return_value=None), \
             patch.object(main.urllib.request, "urlopen", return_value=io.BytesIO(b"# pip bootstrap")), \
             patch.object(main.subprocess, "run") as install, patch("builtins.print"):
            main.ensure_dependencies()
        self.assertEqual(install.call_count, 2)
        for invocation in install.call_args_list:
            command = invocation.args[0]
            self.assertEqual(command[command.index("--target") + 1], str(self.root / ".packages"))

    def test_failed_dependency_install_can_be_retried(self):
        with patch.object(main.importlib.util, "find_spec", return_value=object()), \
             patch.object(main.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")), \
             patch("builtins.print"), self.assertRaises(subprocess.CalledProcessError):
            main.ensure_dependencies()
        self.assertFalse((self.root / ".packages/.requirements.sha256").exists())


if __name__ == "__main__":
    unittest.main()
