import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vps_workspaces.ide import ensure_ide


class IdeTests(unittest.TestCase):
    def test_failed_socket_does_not_publish_ready_marker_and_preserves_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = home / "state"
            binary = home / ".local/lib/code-server-4.138.0-linux-amd64/bin/code-server"
            binary.parent.mkdir(parents=True)
            binary.touch()
            ide = root / "ide/demo"
            ide.mkdir(parents=True)
            config = ide / "demo.code-workspace"
            config.write_text(json.dumps({"settings": {"terminal.integrated.fontSize": 19}}))
            doc = {
                "id": "demo",
                "layout": {
                    "pane": {
                        "surfaces": [{"id": "shell", "type": "terminal", "session": "demo-shell", "cwd": str(home)}]
                    }
                },
            }
            with (
                patch("pathlib.Path.home", return_value=home),
                patch("vps_workspaces.ide.subprocess.run"),
                patch("vps_workspaces.ide.time.sleep"),
                patch("vps_workspaces.ide.socket.socket") as socket,
            ):
                socket.return_value.__enter__.return_value.connect.side_effect = ConnectionRefusedError()
                with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                    ensure_ide(root, doc)
            self.assertFalse((root / "demo.ide").exists())
            self.assertEqual(json.loads(config.read_text())["settings"]["terminal.integrated.fontSize"], 19)
