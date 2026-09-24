import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vps_workspaces.storage import write_json


class StorageTests(unittest.TestCase):
    def test_failed_replace_preserves_previous_document_and_removes_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            write_json(path, {"revision": 1})
            with (
                patch("vps_workspaces.storage.os.replace", side_effect=OSError("disk failure")),
                self.assertRaises(OSError),
            ):
                write_json(path, {"revision": 2})
            self.assertEqual(json.loads(path.read_text()), {"revision": 1})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_serialization_failure_does_not_truncate_existing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            write_json(path, {"revision": 1})
            with self.assertRaises(TypeError):
                write_json(path, {"invalid": object()})
            self.assertEqual(json.loads(path.read_text()), {"revision": 1})
            self.assertEqual(list(Path(directory).iterdir()), [path])
