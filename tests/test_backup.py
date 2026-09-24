import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vps_workspaces import backup


class BackupTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rsnapshot") and shutil.which("rsync"), "requires rsnapshot and rsync")
    def test_first_snapshot_keeps_all_sources_and_next_snapshot_keeps_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            snapshots = root / "snapshots"
            snapshots.mkdir()
            sources = [root / "first", root / "second"]
            for source in sources:
                source.mkdir()
                (source / "saved.txt").write_text("original")
            excludes = state / "exclude.txt"
            excludes.touch()
            conf = state / "rsnapshot.conf"
            rows = [
                ("config_version", "1.2"),
                ("snapshot_root", str(snapshots) + "/"),
                ("cmd_rsync", shutil.which("rsync")),
                ("cmd_cp", "/bin/cp"),
                ("cmd_rm", "/bin/rm"),
                ("retain", "hourly\t24"),
                ("retain", "daily\t7"),
                ("retain", "weekly\t4"),
                ("retain", "monthly\t6"),
                ("sync_first", "1"),
                ("rsync_short_args", "-a"),
                ("rsync_long_args", "--delete --relative"),
                ("exclude_file", str(excludes)),
            ]
            rows += [("backup", str(source) + "/\tfiles/") for source in sources]
            conf.write_text("\n".join(k + "\t" + v for k, v in rows) + "\n")
            config = state / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "rsnapshot": shutil.which("rsnapshot"),
                        "rsnapshot_config": str(conf),
                        "snapshot_root": str(snapshots),
                        "sqlite_stage": str(state / "sqlite"),
                        "exclude_file": str(excludes),
                    }
                )
            )
            with patch.object(sys, "argv", ["backup.py", "--config", str(config)]):
                backup.main()
                self.assertTrue((state / "last-success.json").exists())
                for source in sources:
                    saved = snapshots / "hourly.0/files" / str(source).lstrip("/") / "saved.txt"
                    self.assertEqual(saved.read_text(), "original")
                (sources[0] / "saved.txt").write_text("updated")
                backup.main()
            relative = Path("files") / str(sources[0]).lstrip("/") / "saved.txt"
            self.assertEqual((snapshots / "hourly.0" / relative).read_text(), "updated")
            self.assertEqual((snapshots / "hourly.1" / relative).read_text(), "original")

    def test_online_snapshot_includes_committed_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "data"
            root.mkdir()
            stage = home / "stage"
            stage.mkdir()
            db = root / "live.sqlite"
            conn = sqlite3.connect(db)
            try:
                conn.execute("pragma journal_mode=wal")
                conn.execute("create table example(value text)")
                conn.execute("insert into example values (?)", ("saved",))
                conn.commit()
                with patch.object(backup.Path, "home", return_value=home):
                    manifest = backup.sqlite_copies([root], stage)
                self.assertEqual(len(manifest), 1)
                restored = sqlite3.connect(manifest[0]["snapshot"])
                try:
                    self.assertEqual(restored.execute("select value from example").fetchone()[0], "saved")
                finally:
                    restored.close()
                self.assertEqual(json.loads((stage / "manifest.json").read_text()), manifest)
            finally:
                conn.close()
