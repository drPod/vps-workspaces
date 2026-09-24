import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vps_workspaces import autosave, workspace


class AutosaveTests(unittest.TestCase):
    def test_debounce_saves_only_stable_changes(self):
        d = autosave.Debounce(2)
        self.assertFalse(d.ready("a", "old", "new", 0))
        self.assertFalse(d.ready("a", "old", "newer", 1))
        self.assertFalse(d.ready("a", "old", "newer", 2))
        self.assertTrue(d.ready("a", "old", "newer", 3))
        self.assertFalse(d.ready("a", "newer", "newer", 4))
        self.assertEqual(d.pending, {})

    def test_terminal_status_and_small_ratio_noise_do_not_save(self):
        a = {"name": "Demo", "layout": {"split": 0.50001, "title": "Codex busy", "url": "https://example.com"}}
        b = copy.deepcopy(a)
        b["layout"].update(split=0.50002, title="Codex idle")
        self.assertEqual(autosave.fingerprint(a), autosave.fingerprint(b))
        b["layout"]["url"] = "https://example.com/next"
        self.assertNotEqual(autosave.fingerprint(a), autosave.fingerprint(b))

    def test_saving_old_instance_does_not_replace_current_instance(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(workspace, "STATE", Path(tmp)):
            workspace.store("demo", {"workspace": "one", "bindings": {}, "revision": 1})
            workspace.store("demo", {"workspace": "two", "bindings": {}, "revision": 1})
            workspace.store_instance("demo", {"workspace": "one", "bindings": {}, "revision": 2})
            self.assertEqual(json.loads((Path(tmp) / "demo.json").read_text())["workspace"], "two")
            self.assertEqual(json.loads((Path(tmp) / "instances/one.json").read_text())["revision"], 2)

    def test_conflict_preserves_local_revision(self):
        state = {"workspace": "one", "revision": 2, "doc": {}, "bindings": {}}
        with (
            patch.object(workspace, "snapshot_workspace", return_value={"revision": 2}),
            patch.object(workspace, "remote", side_effect=RuntimeError("Workspace changed on another Mac")),
            patch.object(workspace, "store_instance") as store,
        ):
            with self.assertRaises(RuntimeError):
                workspace.save_state("demo", state, {})
            self.assertEqual(state["revision"], 2)
            store.assert_not_called()

    def test_two_changed_copies_pause_loser_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(workspace, "STATE", Path(tmp)):
            for wid in ("one", "two"):
                workspace.store(
                    "demo", {"workspace": wid, "bindings": {}, "revision": 1, "doc": {"id": "demo", "name": "old"}}
                )
            trees = {"windows": [{"workspaces": [{"id": "one"}, {"id": "two"}]}]}
            server_revision = [1]

            def rpc(action, doc):
                if doc["revision"] != server_revision[0]:
                    raise RuntimeError("Workspace changed on another Mac")
                server_revision[0] += 1
                return dict(doc, revision=server_revision[0])

            def snapshot(name, state, current):
                return dict(state["doc"], name=current["id"], revision=state["revision"])

            with (
                patch.object(workspace, "cmux", return_value=trees),
                patch.object(workspace, "snapshot_workspace", side_effect=snapshot),
                patch.object(workspace, "remote", side_effect=rpc),
                patch.object(autosave, "notify"),
            ):
                d = autosave.Debounce()
                errors = {}
                autosave.tick(d, errors, 0)
                autosave.tick(d, errors, 3)
                autosave.tick(d, errors, 4)
            self.assertEqual(server_revision[0], 2)
            self.assertEqual(len(errors), 1)
            status = json.loads((Path(tmp) / "autosave-status.json").read_text())
            self.assertEqual(sum(s["state"] == "paused" for s in status["instances"].values()), 1)
            self.assertEqual(len(list((Path(tmp) / "autosave-drafts").glob("*.json"))), 1)
