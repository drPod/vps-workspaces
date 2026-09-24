import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from vps_workspaces.install import backups as installer


class BackupInstallTests(unittest.TestCase):
    def test_reinstall_keeps_relocated_snapshots_and_additional_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            home = pathlib.Path(directory)
            state = home / ".local/state/vps-workspaces-backup"
            state.mkdir(parents=True)
            (home / ".config/systemd/user").mkdir(parents=True)
            source = home / ".local/share/quant-outreach"
            source.mkdir(parents=True)
            snapshots = home / "larger-disk/snapshots"
            config_path = state / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "snapshot_root": str(snapshots),
                        "sqlite_roots": [str(source)],
                        "excludes": ["custom-cache"],
                    }
                )
            )
            with (
                patch.object(installer.Path, "home", return_value=home),
                patch.object(installer.shutil, "which", side_effect=lambda name: "/usr/bin/" + name),
                patch.object(installer.subprocess, "run"),
                patch.object(installer.os, "umask"),
                patch("sys.argv", ["install-backups.py", "vps"]),
            ):
                installer.main()
            config = json.loads(config_path.read_text())
            self.assertEqual(config["snapshot_root"], str(snapshots))
            self.assertIn(str(source), config["sqlite_roots"])
            self.assertIn("custom-cache", config["excludes"])
            self.assertIn(str(source) + "/\tvps/", (state / "rsnapshot.conf").read_text())
