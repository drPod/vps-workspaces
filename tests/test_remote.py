import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from vps_workspaces import remote, workspace


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.doc = json.loads(pathlib.Path("examples/demo.json").read_text())
        self.doc.update(revision=1, host="demo.example.com")
        (self.root / "demo.json").write_text(json.dumps(self.doc))
        (self.root / "settings.json").write_text('{"base_domain":"example.com"}')
        self.site = self.root / "deploy/caddy/sites/vps-workspaces.caddy"
        self.site.parent.mkdir(parents=True)
        self.site.write_text("original route")
        p = patch.object(remote, "ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)

    def test_existing_session_receives_latest_client_sizing(self):
        from types import SimpleNamespace

        with (
            patch.object(remote.subprocess, "run", return_value=SimpleNamespace(returncode=0)),
            patch.object(remote, "run") as run,
        ):
            remote.ensure("demo-agent")
        run.assert_called_once_with(
            [*remote.TMUX, "set-window-option", "-t", "demo-agent", "window-size", "latest"],
        )

    def test_prepare_is_unpublished_and_retryable(self):
        with patch.object(remote, "ensure"):
            first = remote.prepare_terminal("demo", "review", 1)
            self.assertEqual(first, remote.prepare_terminal("demo", "review", 1))
            self.assertEqual(remote.load("demo"), self.doc)
            with self.assertRaises(ValueError):
                remote.prepare_terminal("demo", "other", 0)

    def test_long_session_names_do_not_collide(self):
        with patch.object(remote, "ensure"):
            a = remote.prepare_terminal("demo", "a" * 47 + "b", 1)
            b = remote.prepare_terminal("demo", "a" * 47 + "c", 1)
        self.assertNotEqual(a["session"], b["session"])
        self.assertEqual(len(a["session"]), 48)

    def test_reload_failure_restores_registry_and_route(self):
        with (
            patch.object(pathlib.Path, "home", return_value=self.root),
            patch.object(remote, "run", side_effect=RuntimeError("reload failed")),
            patch("vps_workspaces.caddy_routes.prepare_previews"),
            self.assertRaises(RuntimeError),
        ):
            remote.save(copy.deepcopy(self.doc))
        self.assertEqual(remote.load("demo"), self.doc)
        self.assertEqual(self.site.read_text(), "original route")

    def test_native_creation_failure_does_not_publish(self):
        state = {"revision": 1, "workspace": "native-id", "bindings": {}}
        (self.root / "demo.json").write_text(json.dumps(state))
        with (
            patch.object(workspace, "STATE", self.root),
            patch.object(workspace, "remote", side_effect=[self.doc, {"id": "review"}]) as rpc,
            patch.object(workspace, "attach_command", return_value="attach"),
            patch.object(workspace, "cmux", side_effect=RuntimeError("creation failed")),
            patch.object(workspace, "save_workspace") as save,
        ):
            with self.assertRaises(RuntimeError):
                workspace.add_terminal("demo", "review")
            save.assert_not_called()
            self.assertEqual([c.args[0] for c in rpc.call_args_list], ["get", "prepare-terminal"])
        self.assertEqual(json.loads((self.root / "demo.json").read_text()), state)
