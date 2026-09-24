#!/usr/bin/env python3
"""Debounced native cmux autosave. Start through shell-integration.zsh inside cmux."""
import copy
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import workspace as ws


def fingerprint(doc):
    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()
                    if k not in ('title', 'revision', 'saved_at', 'host')}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if isinstance(value, float):
            return round(value, 3)
        return value
    return json.dumps(normalize(doc), sort_keys=True)


class Debounce:
    def __init__(self, seconds=2):
        self.seconds = seconds
        self.pending = {}

    def ready(self, key, baseline, value, now):
        if baseline == value:
            self.pending.pop(key, None)
            return False
        old = self.pending.get(key)
        if old is None or old[0] != value:
            self.pending[key] = (value, now)
            return False
        return now - old[1] >= self.seconds


def notify(name, error):
    print(f'{name}: autosave paused: {error}', flush=True)
    # Local notification, no shell interpolation or external messaging.
    subprocess.run(['osascript', '-e', 'on run argv\ndisplay notification (item 1 of argv) with title "Workspace autosave paused"\nend run',
                    name + ': ' + error], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tick(debounce, errors, now):
    with (ws.STATE / 'autosave.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        directory = ws.STATE / 'instances'
        directory.mkdir(exist_ok=True)
        # Import states created before autosave, without losing multiple instances.
        for p in ws.STATE.glob('*.json'):
            state = json.loads(p.read_text())
            if isinstance(state, dict) and 'workspace' in state and 'bindings' in state and 'doc' in state:
                ip = directory / (state['workspace'] + '.json')
                if not ip.exists():
                    ws.atomic_state(ip, dict(state, registry_name=p.stem))
        all_trees = ws.cmux('tree', '--all')
        trees = {w['id']: w for window in all_trees['windows'] for w in window['workspaces']}
        status = {}
        for p in directory.glob('*.json'):
            state = json.loads(p.read_text())
            wid, name = state['workspace'], state['registry_name']
            if wid not in trees:
                continue
            status[wid] = {'workspace': name, 'revision': state['revision'], 'state': 'watching'}
            try:
                candidate = copy.deepcopy(state)
                doc = ws.snapshot_workspace(name, candidate, trees[wid])
                value = fingerprint(doc)
                baseline = fingerprint(state['doc'])
                # A conflict remains paused until manual resolution updates the local revision.
                if wid in errors and errors[wid][0] == state['revision'] and errors[wid][2]:
                    status[wid].update(state='paused', error=errors[wid][1])
                    continue
                if debounce.ready(wid, baseline, value, now):
                    ws.save_state(name, candidate, trees[wid])
                    debounce.pending.pop(wid, None)
                    errors.pop(wid, None)
                    status[wid].update(state='saved', revision=candidate['revision'])
            except (ValueError, RuntimeError) as error:
                message = str(error)
                drafts = ws.STATE / 'autosave-drafts'
                drafts.mkdir(exist_ok=True)
                ws.atomic_state(drafts / p.name, {'state': state, 'native_tree': trees[wid], 'error': message})
                status[wid].update(state='paused', error=message)
                # Network failures retry; revision conflicts/unmanaged panes await user action.
                conflict = 'Workspace changed on another Mac' in message or 'Unmanaged terminal' in message
                if errors.get(wid, (None, None))[1] != message:
                    notify(name, message)
                errors[wid] = (state['revision'], message, conflict)
        ws.atomic_state(ws.STATE / 'autosave-status.json', {'checked_at': int(time.time()), 'pid': os.getpid(), 'instances': status})


def main():
    os.umask(0o077)
    with (ws.STATE / 'autosave-worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        ws.cmux('ping')
        debounce, errors = Debounce(), {}
        while True:
            try:
                tick(debounce, errors, time.monotonic())
            except Exception as error:
                print(str(error), flush=True)
                if 'Access denied' in str(error):
                    return  # A later cmux shell hook can start an authorized worker.
            time.sleep(1)


if __name__ == '__main__':
    main()
