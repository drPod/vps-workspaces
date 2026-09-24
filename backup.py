#!/usr/bin/env python3
"""Prepare consistent SQLite copies, then delegate snapshots and retention to rsnapshot."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import shlex
import subprocess
import time

SKIP_DIRS = {'node_modules', '.git', '.venv', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.next', '.turbo', '.cache', '__pycache__', 'Cache', 'CachedData', 'cache', 'runtime'}


def sqlite_copies(roots, stage):
    manifest = []
    for root in roots:
        for directory, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and Path(directory) / d != stage]
            for name in files:
                if not name.endswith(('.db', '.sqlite', '.sqlite3', '.vscdb')):
                    continue
                source = Path(directory) / name
                try:
                    with source.open('rb') as f:
                        if f.read(16) != b'SQLite format 3\x00':
                            continue
                except FileNotFoundError:
                    continue
                relative = source.relative_to(Path.home())
                target = stage / (str(relative) + '.backup')
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix('.partial')
                temp.unlink(missing_ok=True)
                deadline = time.monotonic() + 90
                def progress(status, remaining, total):
                    if time.monotonic() > deadline:
                        raise TimeoutError('SQLite backup timed out: ' + str(source))
                src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=15)
                dst = sqlite3.connect(temp)
                verified = True
                try:
                    src.backup(dst, pages=256, progress=progress, sleep=.05)
                    if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                        raise sqlite3.DatabaseError('SQLite snapshot verification failed: ' + str(source))
                except sqlite3.DatabaseError as error:
                    verified = False
                    print('Database requires attention; preserving raw files:', source, str(error), flush=True)
                    manifest.append({'source': str(source), 'error': str(error), 'raw_files_preserved': True})
                finally:
                    dst.close(); src.close()
                if not verified:
                    temp.unlink(missing_ok=True)
                    continue
                os.replace(temp, target)
                manifest.append({'source': str(source), 'snapshot': str(target)})
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    a = p.parse_args()
    os.umask(0o077)
    config_path = Path(a.config).expanduser()
    config = json.loads(config_path.read_text())
    state = config_path.parent
    with (state / 'run.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        roots = [Path(x).expanduser() for x in config.get('sqlite_roots', [])]
        stage = Path(config['sqlite_stage'])
        stage.mkdir(parents=True, exist_ok=True)
        manifest = sqlite_copies(roots, stage)
        exclusions = list(config.get('excludes', []))
        for db in manifest:
            if 'snapshot' not in db:
                continue
            exclusions.extend([db['source'], db['source'] + '-wal', db['source'] + '-shm', db['source'] + '-journal'])
        Path(config['exclude_file']).write_text('\n'.join(exclusions) + '\n')
        # Pull only a completed VPS snapshot; its database copies are already consistent.
        if config.get('remote_ready'):
            subprocess.run(['ssh', '-o', 'BatchMode=yes', config['ssh_host'], 'test -f ' + shlex.quote(config['remote_ready'])], check=True)
        binary = config['rsnapshot']
        command = [binary, '-c', config['rsnapshot_config']]
        subprocess.run(command + ['sync'], check=True)
        rotation_path = state / 'rotation.json'
        rotation = json.loads(rotation_path.read_text()) if rotation_path.exists() else {}
        periods = [('monthly', time.strftime('%Y-%m')), ('weekly', time.strftime('%G-%V')), ('daily', time.strftime('%Y-%m-%d'))]
        predecessors = {'monthly': 'weekly.3', 'weekly': 'daily.6', 'daily': 'hourly.23'}
        for period, key in periods:
            if rotation.get(period) != key and (Path(config['snapshot_root']) / predecessors[period]).exists():
                subprocess.run(command + [period], check=True)
                rotation[period] = key
        subprocess.run(command + ['hourly'], check=True)
        rotation_path.write_text(json.dumps(rotation))
        (state / 'last-success.json').write_text(json.dumps({'time': int(time.time()), 'snapshot_root': config['snapshot_root'], 'sqlite_databases': len(manifest), 'warnings': [d for d in manifest if 'error' in d]}, indent=2))
        print('Snapshot complete:', config['snapshot_root'])


if __name__ == '__main__':
    main()
