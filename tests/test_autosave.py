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
                    "demo",
                    {
                        "workspace": wid,
                        "bindings": {},
                        "revision": 1,
                        "doc": {"id": "demo", "name": "old", "layout": {"pane": {"surfaces": []}}},
                    },
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

    def test_detached_terminal_does_not_erase_saved_agent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(workspace, "STATE", Path(tmp)):
            workspace.store(
                "demo",
                {
                    "workspace": "one",
                    "bindings": {},
                    "revision": 1,
                    "doc": {"layout": {"pane": {"surfaces": [{"id": "agent", "type": "terminal"}]}}},
                },
            )
            with (
                patch.object(workspace, "cmux", return_value={"windows": [{"workspaces": [{"id": "one"}]}]}),
                patch.object(workspace, "snapshot_workspace", return_value={"layout": {"pane": {"surfaces": []}}}),
                patch.object(workspace, "remote") as remote,
                patch.object(autosave, "notify") as notify,
            ):
                errors = {}
                debounce = autosave.Debounce()
                autosave.tick(debounce, errors, 0)
                autosave.tick(debounce, errors, 3)
                remote.assert_not_called()
                notify.assert_called_once()
            self.assertIn("preserved", errors["one"][1])
            self.assertTrue((Path(tmp) / "autosave-drafts/one.json").exists())

    def test_transient_helper_does_not_notify_but_persistent_shell_does(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(workspace, "STATE", Path(tmp)):
            doc = {"layout": {"pane": {"surfaces": []}}}
            workspace.store("demo", {"workspace": "one", "bindings": {}, "revision": 1, "doc": doc})
            with (
                patch.object(workspace, "cmux", return_value={"windows": [{"workspaces": [{"id": "one"}]}]}),
                patch.object(workspace, "snapshot_workspace") as snapshot,
                patch.object(autosave, "notify") as notify,
            ):
                debounce, errors = autosave.Debounce(), {}
                snapshot.side_effect = ValueError("Unmanaged terminal: helper")
                autosave.tick(debounce, errors, 0)
                autosave.tick(debounce, errors, 2)
                notify.assert_not_called()
                snapshot.side_effect = None
                snapshot.return_value = doc
                autosave.tick(debounce, errors, 3)
                self.assertEqual(debounce.unsettled, {})
                snapshot.side_effect = ValueError("Unmanaged terminal: helper")
                autosave.tick(debounce, errors, 4)
                autosave.tick(debounce, errors, 13)
                notify.assert_not_called()
                autosave.tick(debounce, errors, 14)
                autosave.tick(debounce, errors, 15)
                notify.assert_called_once()

    def test_timeout_retries_then_notifies_once_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(workspace, "STATE", Path(tmp)):
            doc = {"layout": {"pane": {"surfaces": []}}}
            workspace.store("demo", {"workspace": "one", "bindings": {}, "revision": 1, "doc": doc})
            with (
                patch.object(workspace, "cmux", return_value={"windows": [{"workspaces": [{"id": "one"}]}]}),
                patch.object(workspace, "snapshot_workspace", return_value=dict(doc, name="changed")),
                patch.object(workspace, "save_state", side_effect=RuntimeError("<urlopen error timed out>")) as save,
                patch.object(autosave, "notify") as notify,
            ):
                debounce, errors = autosave.Debounce(), {}
                for now in (0, 3, 30, 62):
                    autosave.tick(debounce, errors, now)
                notify.assert_not_called()
                status = json.loads((Path(tmp) / "autosave-status.json").read_text())
                self.assertEqual(status["instances"]["one"]["state"], "retrying")
                autosave.tick(debounce, errors, 63)
                autosave.tick(debounce, errors, 64)
                notify.assert_called_once()
                save.side_effect = None
                autosave.tick(debounce, errors, 65)
                self.assertEqual(debounce.unsettled, {})
                self.assertEqual(errors, {})
