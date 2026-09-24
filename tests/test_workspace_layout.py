import unittest

from vps_workspaces.workspace import snapshot_workspace


class LayoutTests(unittest.TestCase):
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
