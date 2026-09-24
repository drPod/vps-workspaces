# Unencrypted backups with rsnapshot

Backups are ordinary files, intentionally **unencrypted**, managed by upstream [rsnapshot](https://rsnapshot.org/) and rsync. Unchanged files share hard links between snapshots. Do not edit files inside a snapshot; copy them out before changing them.

Locations:

- VPS: `~/.local/share/vps-workspaces-snapshots/` (a convenience symlink to `/var/lib/vps-workspaces-snapshots/` on the larger disk in this deployment)
- Mac: `~/Backups/vps-workspaces/`

`hourly.0` is newest, `hourly.1` the previous snapshot. Each snapshot has a timestamp in its filesystem metadata. Retention is 24 hourly, 7 daily, 4 weekly and 6 monthly slots; longer-period slots fill as time passes. Daily/weekly/monthly rotations happen when the first successful run in that period occurs.

## Scope and schedule

The VPS runs hourly through `vps-workspaces-backup.timer`. It saves `~/Coding` (including Git repositories), `~/.codex`, workspace/HAPI/IDE state, user systemd configuration, `~/deploy`, and shell/tmux configuration. Reinstallable dependencies, caches, sockets and Codex temporary helper files are excluded. This is a workspace-data backup, not a bootable operating-system image or a logical dump of every external database service.

The Mac's hourly LaunchAgent pulls the newest completed VPS snapshot over SSH and also snapshots local `~/Coding`, `~/.codex`, cmux application state, workspace state, `.zshrc` and SSH configuration. It runs when the Mac is awake and can reach the VPS. A shared lock prevents VPS snapshot rotation during the copy. The Mac maintains its own history, so rotating VPS snapshots does not delete the Mac's older retained snapshots.

SQLite files are copied using SQLite's online backup API before rsnapshot runs. The copies live in `.local/state/vps-workspaces-backup/sqlite/`, with a `manifest.json` mapping each copy to its original path. Consistent copies replace live SQLite files in the backup. If an existing database is corrupt, its raw files are preserved and the manifest/success report explicitly records the warning; this is not a repaired database.

On initial verification, `Coding/gradient-hackathon/data/swarmci.db` already failed SQLite integrity checks. Its raw files are retained. HAPI and Codex database restore checks are separate.

## Setup and status

Install rsnapshot with your package manager, then:

```sh
# VPS, from deployed repository:
python3 install-backups.py vps
# Mac, from local repository:
python3 install-backups.py mac --ssh-host myvps --remote-home /home/ubuntu
```

Configuration, logs, database staging and `last-success.json` are under `~/.local/state/vps-workspaces-backup/` on each machine. A failed run leaves older snapshots intact and does not publish a new success marker. The stored files retain private account permissions; there is no backup password.

## Restore

Copy a file or directory out of `hourly.0`, another hourly slot, or a daily/weekly/monthly slot. VPS files appear under `vps/home/ubuntu/`; Mac-local files appear under `mac/Users/<account>/` in Mac snapshots. Restore to a temporary directory first and verify it before replacing live files.

For SQLite, use the manifest's `.backup` copy, not a live database/WAL combination. Stop the corresponding service before replacing its database; restore the database under its original name and remove obsolete WAL/SHM files only as part of that controlled restore. Backups cannot restore unsaved editor buffers or running process memory.
