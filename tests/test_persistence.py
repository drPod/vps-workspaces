import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vps_workspaces import persistence, workspace


class PersistenceTests(unittest.TestCase):
    def test_recovered_native_surface_maps_to_original_agent(self):
        wid = "11111111-1111-1111-1111-111111111111"
        origin = "22222222-2222-2222-2222-222222222222"
        sid = "33333333-3333-3333-3333-333333333333"
        agent = {"id": "agent", "session": "demo-agent", "type": "terminal", "hapi_session": "existing"}
        listing = {"sessions": [{"session_id": f"ssh-{origin}-{sid}", "attachments": [{"attachment_id": "new"}]}]}
        with (
            patch.object(workspace, "cmux", return_value=listing),
            patch.object(workspace, "remote", side_effect=[{}, {sid: agent}]),
        ):
            self.assertEqual(persistence.discover("demo", {"id": wid}), {"new": agent})

    def test_local_workspace_does_not_query_hapi(self):
        with (
            patch.object(workspace, "cmux", return_value={"sessions": []}),
            patch.object(workspace, "remote") as remote,
        ):
            self.assertEqual(persistence.discover("demo", {"id": "local"}), {})
            remote.assert_not_called()

    def test_adoption_registers_layout_without_creating_an_agent(self):
        wid = "11111111-1111-1111-1111-111111111111"
        shell = {"id": "shell", "session": "shell", "type": "terminal", "cwd": "/tmp"}
        tree = {
            "id": wid,
            "title": "Work",
            "layout": {"pane": {"id": "pane"}},
            "panes": [
                {
                    "id": "pane",
                    "selected_surface_id": "browser",
                    "surfaces": [
                        {"id": "term", "type": "terminal", "title": "Shell"},
                        {"id": "browser", "type": "browser", "title": "Page", "url": "https://example.com"},
                    ],
                }
            ],
        }
        calls = []

        def remote(action, *args, doc=None):
            calls.append(action)
            return [] if action == "list" else dict(doc, revision=1)

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(workspace, "STATE", Path(tmp)),
            patch.object(persistence, "discover", return_value={"term": shell}),
            patch.object(workspace, "remote", side_effect=remote),
        ):
            persistence.adopt(tree)
            state = json.loads((Path(tmp) / "instances" / (wid + ".json")).read_text())
        self.assertEqual(calls, ["list", "import"])
        self.assertEqual(state["doc"]["layout"]["pane"]["surfaces"][1]["url"], "https://example.com")
        self.assertEqual(state["bindings"]["term"], "shell")

    def test_unrecognized_live_process_is_not_replaced(self):
        with patch.object(persistence, "discover", return_value={}), patch.object(workspace, "remote") as remote:
            persistence.adopt(
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "panes": [{"surfaces": [{"id": "busy", "type": "terminal"}]}],
                }
            )
            remote.assert_not_called()
