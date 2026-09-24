import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vps_workspaces import remote


class WorkspaceLinkTests(unittest.TestCase):
    def test_recovered_terminal_keeps_original_workspace_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = json.loads(Path("examples/demo.json").read_text())
            doc["layout"] = {
                "pane": {
                    "surfaces": [
                        {"id": "recovered", "type": "terminal", "session": "demo-recovered"},
                    ],
                    "selected": 0,
                }
            }
            (root / "demo.json").write_text(json.dumps(doc))
            (root / "demo-agent.route").write_text(json.dumps({"CMUX_WORKSPACE_ID": "ABCD"}))
            with patch.object(remote, "ROOT", root), patch.dict(os.environ, {"CMUX_WORKSPACE_ID": "abcd"}, clear=True):
                self.assertEqual(remote.current_name(), "demo")
            with (
                patch.object(remote, "ROOT", root),
                patch.dict(os.environ, {"CMUX_WORKSPACE_ID": "other"}, clear=True),
                self.assertRaisesRegex(ValueError, "No unique"),
            ):
                remote.current_name()

    def test_named_route_survives_removal_of_noninitial_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo.json").write_text(Path("examples/demo.json").read_text())
            (root / "demo-review.route").write_text(
                json.dumps(
                    {
                        "CMUX_WORKSPACE_ID": "native",
                        "workspace_name": "demo",
                    }
                )
            )
            with (
                patch.object(remote, "ROOT", root),
                patch.dict(os.environ, {"CMUX_WORKSPACE_ID": "native"}, clear=True),
            ):
                self.assertEqual(remote.current_name(), "demo")
