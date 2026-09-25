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

    def duplicate_fixture(self, bound=True):
        agent = {
            "id": "saved-agent",
            "type": "terminal",
            "session": "original-shell",
            "codex_thread": "01a0d987-7d17-7c30-ad23-8fd90a9a74b7",
        }
        state = {
            "workspace": "native",
            "revision": 3,
            "bindings": {"old": agent["id"], **({"new": agent["id"]} if bound else {})},
            "doc": {"id": "demo", "name": "Demo", "layout": {"pane": {"surfaces": [agent]}}},
        }
        tree = {
            "title": "Demo",
            "layout": {"pane": {"id": "p"}},
            "panes": [
                {
                    "id": "p",
                    "selected_surface_id": "new",
                    "surfaces": [
                        {"id": "old", "type": "terminal", "title": "Old"},
                        {"id": "new", "type": "terminal", "title": "New"},
                    ],
                }
            ],
        }
        return agent, state, tree

    def test_two_viewers_of_one_thread_have_distinct_stable_layout_ids(self):
        from vps_workspaces.model import validate

        for bound in (True, False):
            with self.subTest(bound=bound):
                agent, state, tree = self.duplicate_fixture(bound)
                with patch("vps_workspaces.persistence.discover", return_value={"old": agent, "new": agent}):
                    doc = validate(snapshot_workspace("demo", state, tree))
                tabs = doc["layout"]["pane"]["surfaces"]
                self.assertNotEqual(tabs[0]["id"], tabs[1]["id"])
                self.assertEqual(tabs[0]["codex_thread"], tabs[1]["codex_thread"])
                self.assertEqual(doc["layout"]["pane"]["selected"], 1)
                with patch("vps_workspaces.persistence.discover") as discover:
                    self.assertEqual(snapshot_workspace("demo", state, tree), doc)
                    discover.assert_not_called()

    def test_duplicate_binding_rediscovers_shell_after_agent_moved(self):
        from vps_workspaces.model import validate

        agent, state, tree = self.duplicate_fixture()
        shell = {"id": "saved-agent", "type": "terminal", "session": "original-shell"}
        with patch("vps_workspaces.persistence.discover", return_value={"old": shell, "new": agent}):
            doc = validate(snapshot_workspace("demo", state, tree))
        tabs = doc["layout"]["pane"]["surfaces"]
        self.assertNotIn("codex_thread", tabs[0])
        self.assertEqual(tabs[0]["session"], "original-shell")
        self.assertEqual(tabs[1]["codex_thread"], agent["codex_thread"])

    def test_ambiguous_duplicate_does_not_guess_or_drop_a_terminal(self):
        agent, state, tree = self.duplicate_fixture()
        with (
            patch("vps_workspaces.persistence.discover", return_value={"new": agent}),
            self.assertRaisesRegex(ValueError, "Cannot identify terminals"),
        ):
            snapshot_workspace("demo", state, tree)
