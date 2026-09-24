"""Small workspace adapter to upstream HAPI; HAPI owns agents and their state."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path.home() / '.local/share/vps-workspaces'
SESSION_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')


def checked_session(value):
    if not isinstance(value, str) or not SESSION_ID.fullmatch(value):
        raise ValueError('Invalid HAPI session ID')
    return value


def config():
    return json.loads((ROOT / 'hapi/install.json').read_text())


class Hapi:
    def __init__(self):
        self.config = config()
        self.base = self.config.get('api_url') or f'http://127.0.0.1:{self.config["port"]}'
        self.token = None
        self.token = self.request('/api/auth', {'accessToken': self.config['token']})['token']

    def request(self, path, data=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                          headers=headers, method=method)
        try:
            with urlopen(request, timeout=90) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read().decode()[:500]
            raise RuntimeError(f'HAPI returned HTTP {error.code}: {detail}') from None

    def session(self, sid):
        return self.request('/api/sessions/' + checked_session(sid))['session']

    def ready(self, sid):
        session = self.session(sid)
        if session.get('metadata', {}).get('flavor') != 'codex':
            raise ValueError('Independent terminal attachment currently requires a Codex session')
        if not session.get('active'):
            for attempt in range(20):
                try:
                    result = self.request('/api/sessions/' + sid + '/resume', {})
                    break
                except RuntimeError as error:
                    # This specific error means the Hub has not dispatched a spawn.
                    # Never retry an ambiguous timeout or other failed mutation.
                    if 'RPC handler not registered' not in str(error) or attempt == 19:
                        raise
                    time.sleep(.5)
            if result.get('type') != 'success':
                raise RuntimeError('HAPI could not resume this session')
            for _ in range(100):
                session = self.session(sid)
                if session.get('active'):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('HAPI session did not become active')
        return session

    def create(self, directory, name, permission='default'):
        machines = self.request('/api/machines')['machines']
        local = [m for m in machines if m.get('active') and m.get('metadata', {}).get('host') == os.uname().nodename]
        if len(local) != 1:
            raise RuntimeError('Expected one online HAPI Runner on this VPS')
        result = self.request('/api/machines/' + local[0]['id'] + '/spawn', {
            'directory': str(Path(directory).expanduser().resolve()),
            'agent': 'codex', 'permissionMode': permission,
        })
        if result.get('type') != 'success':
            raise RuntimeError('HAPI spawn failed: ' + json.dumps(result))
        sid = checked_session(result['sessionId'])
        self.request('/api/sessions/' + sid, {'name': name}, method='PATCH')
        return sid


def link(sid=None):
    c = config()
    # Native HAPI token login; never expose this owner-wide link via workspace HTTP APIs.
    path = '/sessions/' + checked_session(sid) if sid else '/'
    return 'https://' + c['host'] + path + '?' + urlencode({'token': c['token']})


def attach(sid):
    Hapi().ready(checked_session(sid))
    # Use the standard installed wrapper, preserving one UI per terminal.
    wrapper = str(Path.home() / '.local/bin/hapi')
    os.execv(wrapper, [wrapper, 'resume', sid])


def assert_shell(surface):
    p = subprocess.run(['/usr/bin/tmux', '-L', 'vps-workspaces', 'list-panes', '-t', '=' + surface['session'],
                        '-F', '#{pane_current_command}'], capture_output=True, text=True)
    if p.returncode == 0 and any(cmd not in ('bash', 'zsh', 'sh', 'fish') for cmd in p.stdout.splitlines()):
        raise ValueError('This terminal still has a running program. Exit the old agent normally before binding or migrating; it will not be stopped automatically.')
