#!/usr/bin/env python3
"""Install the upstream HAPI application on the VPS behind existing Caddy."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess

VERSION = "0.30.7"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    args = parser.parse_args()
    if not all(c.isalnum() or c in '.-' for c in args.host):
        parser.error("Expected a DNS hostname")
    os.umask(0o077)
    home = Path.home()
    root = home / '.local/share/vps-workspaces/hapi'
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / 'install.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {
        'token': secrets.token_urlsafe(32), 'port': 3006,
    }
    prefix = home / f'.local/lib/hapi-{VERSION}'
    binary = prefix / 'node_modules/@twsxtd/hapi-linux-x64/bin/hapi'
    if not binary.exists():
        subprocess.run(['npm', 'install', '--prefix', str(prefix), f'@twsxtd/hapi@{VERSION}', '--registry=https://registry.npmjs.org'], check=True)
    config.update(host=args.host, version=VERSION, binary=str(binary))
    config_path.write_text(json.dumps(config, indent=2))
    env = {
        'PATH': f'{home}/.local/share/vps-workspaces/bin:{home}/.local/bin:{home}/.npm-global/bin:{home}/.bun/bin:/usr/local/bin:/usr/bin:/bin',
        'HAPI_HOME': str(root / 'data'),
        'HAPI_API_URL': f'http://127.0.0.1:{config["port"]}',
        'HAPI_PUBLIC_URL': f'https://{args.host}',
        'HAPI_LISTEN_HOST': '127.0.0.1',
        'HAPI_LISTEN_PORT': str(config['port']),
        'CLI_API_TOKEN': config['token'],
        'TELEGRAM_NOTIFICATION': 'false',
        'SERVERCHAN_NOTIFICATION': 'false',
    }
    env_file = root / 'service.env'
    env_file.write_text(''.join(f'{k}={v}\n' for k, v in env.items()))
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / 'hapi'
    wrapper.write_text('#!/bin/sh\nset -a\n. ' + shlex.quote(str(env_file)) + '\nset +a\nexec ' + shlex.quote(str(binary)) + ' "$@"\n')
    wrapper.chmod(0o700)
    units = home / '.config/systemd/user'
    units.mkdir(parents=True, exist_ok=True)
    common = f'EnvironmentFile={env_file}\nUMask=0077\nWorkingDirectory={home}/Coding\n'
    (units / 'hapi-hub.service').write_text(f'''[Unit]
Description=HAPI Hub (upstream {VERSION})
After=network.target
[Service]
{common}ExecStart={binary} hub
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
''')
    (units / 'hapi-runner.service').write_text(f'''[Unit]
Description=HAPI Runner
After=network.target hapi-hub.service
[Service]
{common}Environment=HAPI_RUNNER_SUPERVISED=1
ExecStart={binary} runner start-sync --workspace-root {home}/Coding
KillMode=process
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
''')
    socket = home / 'deploy/www/hapi.sock'
    (units / 'hapi-proxy.socket').write_text(f'''[Unit]
Description=Private Caddy socket for HAPI
[Socket]
ListenStream={socket}
SocketMode=0600
RemoveOnStop=true
[Install]
WantedBy=sockets.target
''')
    (units / 'hapi-proxy.service').write_text(f'''[Unit]
Description=Systemd socket proxy to HAPI
After=hapi-hub.service
[Service]
ExecStart=/usr/lib/systemd/systemd-socket-proxyd 127.0.0.1:{config['port']}
NoNewPrivileges=true
''')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'hapi-hub.service', 'hapi-runner.service', 'hapi-proxy.socket'], check=True)
    site = home / 'deploy/caddy/sites/hapi.caddy'
    previous = site.read_text() if site.exists() else None
    site.write_text(f'{args.host} {{\n header Referrer-Policy no-referrer\n reverse_proxy unix//srv/hapi.sock\n}}\n')
    try:
        for command in ('validate', 'reload'):
            subprocess.run(['docker', 'exec', 'caddy', 'caddy', command, '--config', '/etc/caddy/Caddyfile'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        if previous is None:
            site.unlink()
        else:
            site.write_text(previous)
        raise
    print(f'HAPI installed: https://{args.host}')
    print('Private access settings:', config_path)


if __name__ == '__main__':
    main()
