from __future__ import annotations

import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from vps_workspaces.install.resources import configure

SOURCE = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_preserves_settings_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('# Keep me\nmodel = "existing"\n[shell_environment_policy.set]\nCUSTOM = "value"\n')
            configure(path, {"BASH_ENV": "/adapter"})
            configure(path, {"BASH_ENV": "/adapter"})
            self.assertEqual(len(list(path.parent.glob("*.before-resources-*"))), 1)
            self.assertIn("# Keep me", path.read_text())
            result = tomllib.loads(path.read_text())
            self.assertEqual(result["model"], "existing")
            self.assertEqual(result["shell_environment_policy"]["set"]["CUSTOM"], "value")

    def test_does_not_replace_another_shell_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            original = '[shell_environment_policy.set]\nBASH_ENV = "/another"\n'
            path.write_text(original)
            with self.assertRaisesRegex(RuntimeError, "Existing BASH_ENV"):
                configure(path, {"BASH_ENV": "/adapter"})
            self.assertEqual(path.read_text(), original)


@unittest.skipUnless(os.environ.get("VWS_TEST_CGROUP"), "requires an explicitly delegated test cgroup")
class CgroupTests(unittest.TestCase):
    def run_shell(self, command: str, mode: str = "-c") -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            env = {
                **os.environ,
                "BASH_ENV": str(SOURCE / "deploy/agent-tools-env.bash"),
                "AGENTCG_WRAPPER": str(SOURCE / "vendor/agentcgroup/bash_wrapper.sh"),
                "AGENTCG_ROOT": os.environ["VWS_TEST_CGROUP"],
                "AGENTCG_LOG": str(Path(directory) / "metrics.jsonl"),
                "AGENT_RESOURCE_HINT": "memory:low",
            }
            return subprocess.run(
                ["/bin/bash", mode, command],
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=45,
                input="stdin preserved\n",
            )

    def test_login_and_nonlogin_preserve_stdio_and_exit(self) -> None:
        for mode in ("-lc", "-c"):
            with self.subTest(mode=mode):
                result = self.run_shell("cat; cat /proc/self/cgroup; echo stderr >&2; exit 7", mode)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertIn("stdin preserved", result.stdout)
                self.assertIn("/tool_", result.stdout)
                self.assertEqual(result.stderr, "stderr\n")

    def test_oom_kills_command_but_supervisor_reports_it(self) -> None:
        result = self.run_shell('python3 -c "x=bytearray(320*1024*1024)"')
        self.assertEqual(result.returncode, 137, result.stderr)
        self.assertIn("256 MiB memory budget", result.stderr)
        self.assertFalse(list(Path(os.environ["VWS_TEST_CGROUP"]).glob("tool_*")))


if __name__ == "__main__":
    unittest.main()
