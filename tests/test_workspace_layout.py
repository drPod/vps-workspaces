import unittest
from unittest.mock import patch

from vps_workspaces.workspace import snapshot_workspace


class LayoutTests(unittest.TestCase):
    def test_new_hapi_agent_is_adopted_without_starting_an_engine(self):
        state = {
            "workspace": "native",
            "revision": 2,
            "bindings": {},
            "doc": {"id": "demo", "layout": {"pane": {"surfaces": []}}},
        }
        tree = {
            "title": "Demo",
            "layout": {"pane": {"id": "p"}},
            "panes": [
                {
                    "id": "p",
                    "selected_surface_id": "s",
                    "surfaces": [
                        {"id": "s", "type": "terminal", "title": "New agent"},
                    ],
                }
            ],
        }
        agent = {"id": "agent-s", "type": "terminal", "session": "demo-agent-s", "hapi_session": "existing"}
        with patch("vps_workspaces.persistence.discover", return_value={"s": agent}) as remote:
            doc = snapshot_workspace("demo", state, tree)
        remote.assert_called_once_with("demo", tree)
        self.assertEqual(doc["layout"]["pane"]["surfaces"][0]["hapi_session"], "existing")
        self.assertEqual(state["bindings"]["s"], "agent-s")
        self.assertEqual(state["pending_surfaces"]["agent-s"], agent)
        with patch("vps_workspaces.workspace.remote") as remote:
            snapshot_workspace("demo", state, tree)
            remote.assert_not_called()

    def test_unknown_terminal_is_not_silently_saved_as_an_empty_shell(self):
        state = {"workspace": "native", "revision": 1, "bindings": {}, "doc": {"layout": {"pane": {"surfaces": []}}}}
        tree = {
            "panes": [{"id": "p", "surfaces": [{"id": "s", "type": "terminal", "title": "Shell"}]}],
            "layout": {"pane": {"id": "p"}},
        }
        with (
            patch("vps_workspaces.persistence.discover", return_value={}),
            self.assertRaisesRegex(ValueError, "Unmanaged terminal"),
        ):
            snapshot_workspace("demo", state, tree)

    def test_browser_tabs_keep_order_and_selected_tab_in_same_pane(self):
        state = {"doc": {"id": "demo", "layout": {"pane": {"surfaces": []}}}, "bindings": {}, "revision": 2}
        tree = {
            "title": "Demo",
            "layout": {"pane": {"id": "pane-one"}},
            "panes": [
                {
                    "id": "pane-one",
                    "selected_surface_id": "second",
                    "surfaces": [
                        {
                            "id": "first",
                            "type": "browser",
                            "title": "Report",
                            "url": "http://localhost:8766/report.html",
                        },
                        {"id": "second", "type": "browser", "title": "Studio", "url": "http://localhost:8765/"},
                    ],
                }
            ],
        }
        result = snapshot_workspace("demo", state, tree)
        pane = result["layout"]["pane"]
        self.assertEqual(pane["selected"], 1)
        self.assertEqual([s["title"] for s in pane["surfaces"]], ["Report", "Studio"])

    def test_unloaded_browser_keeps_saved_url_and_new_tab_is_blank(self):
        state = {
            "doc": {
                "id": "demo",
                "layout": {"pane": {"surfaces": [{"id": "saved", "type": "browser", "url": "https://example.com"}]}},
            },
            "bindings": {"old": "saved"},
            "revision": 1,
        }
        tree = {
            "title": "Demo",
            "layout": {"pane": {"id": "p"}},
            "panes": [
                {
                    "id": "p",
                    "selected_surface_id": "new",
                    "surfaces": [
                        {"id": "old", "type": "browser", "title": "Page", "url": None},
                        {"id": "new", "type": "browser", "title": "New tab", "url": None},
                    ],
                }
            ],
        }
        result = snapshot_workspace("demo", state, tree)
        self.assertEqual(
            [s["url"] for s in result["layout"]["pane"]["surfaces"]], ["https://example.com", "about:blank"]
        )
