#!/usr/bin/env python3
"""Manage HAPI bindings for saved workspace panes. Run on the VPS."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

import remote
from model import checked_id, surfaces
from hapi_bridge import Hapi, assert_shell, checked_session, link


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['list', 'link', 'new', 'bind', 'migrate'])
    p.add_argument('workspace', nargs='?')
    p.add_argument('surface', nargs='?')
    p.add_argument('session', nargs='?')
    p.add_argument('--permission', choices=['default', 'read-only', 'yolo'], default='default')
    a = p.parse_args()
    if a.action == 'link':
        print(link())
        return
    api = Hapi()
    if a.action == 'list':
        for session in api.request('/api/sessions')['sessions']:
            meta = session.get('metadata') or {}
            print(session['id'], 'active' if session.get('active') else 'inactive', meta.get('name') or meta.get('path', ''))
        return
    with (remote.ROOT / 'registry.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        doc = remote.load(checked_id(a.workspace))
        surface = next((s for s in surfaces(doc['layout']) if s['id'] == a.surface and s['type'] == 'terminal'), None)
        if surface is None:
            raise ValueError('Unknown saved terminal surface')
        if surface.get('hapi_session'):
            raise ValueError('This pane is already bound to HAPI: ' + surface['hapi_session'])
        assert_shell(surface)
        if a.action == 'new':
            sid = api.create(surface.get('cwd', '~/Coding'), doc['name'] + ': ' + surface['id'], a.permission)
        elif a.action == 'bind':
            sid = checked_session(a.session)
            session = api.session(sid)
            if session.get('metadata', {}).get('flavor') != 'codex':
                raise ValueError('Only Codex currently supports independent native attachments')
        else:
            native_id = checked_session(a.session)
            # Never silently create another engine for a native thread already in HAPI.
            existing = [s for s in api.request('/api/sessions')['sessions'] if (s.get('metadata') or {}).get('codexSessionId') == native_id]
            if existing:
                raise ValueError('Thread is already in HAPI; use bind with ' + existing[0]['id'])
            unit = 'vws-hapi-import-' + native_id
            subprocess.run(['systemd-run', '--user', '--collect', '--unit=' + unit,
                            '--property=UMask=0077', '--working-directory=' + str(Path(surface.get('cwd', '~/Coding')).expanduser()),
                            str(Path.home() / '.local/bin/hapi'), 'codex', 'resume', native_id,
                            '--started-by', 'runner', '--permission-mode', a.permission], check=True)
            sid = None
            for _ in range(100):
                matches = [s for s in api.request('/api/sessions')['sessions'] if (s.get('metadata') or {}).get('codexSessionId') == native_id and s.get('active')]
                if matches:
                    sid = checked_session(matches[0]['id'])
                    break
                time.sleep(.2)
            if not sid:
                raise RuntimeError('Import did not become ready. Inspect journalctl --user -u ' + unit + '; workspace binding unchanged.')
        surface['hapi_session'] = sid
        remote.save(doc)
    print('Bound', a.workspace + '/' + a.surface, 'to HAPI', sid)
    print('Reopen the saved workspace to attach an independent terminal frontend.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit(str(error))
