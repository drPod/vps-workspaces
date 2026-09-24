import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import backup


class BackupTests(unittest.TestCase):
    def test_online_snapshot_includes_committed_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);root=home/'data';root.mkdir();stage=home/'stage';stage.mkdir()
            db=root/'live.sqlite';conn=sqlite3.connect(db)
            try:
                conn.execute('pragma journal_mode=wal');conn.execute('create table example(value text)')
                conn.execute('insert into example values (?)',('saved',));conn.commit()
                with patch.object(backup.Path,'home',return_value=home):
                    manifest=backup.sqlite_copies([root],stage)
                self.assertEqual(len(manifest),1)
                restored=sqlite3.connect(manifest[0]['snapshot'])
                try:self.assertEqual(restored.execute('select value from example').fetchone()[0],'saved')
                finally:restored.close()
                self.assertEqual(json.loads((stage/'manifest.json').read_text()),manifest)
            finally:conn.close()
