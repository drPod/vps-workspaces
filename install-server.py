#!/usr/bin/env python3
"""Run on the VPS after copying this repository into ~/.local/share/vps-workspaces/app."""

import argparse
import hashlib
import json
import pathlib
import secrets
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--base-domain", required=True)
a = p.parse_args()
root = pathlib.Path.home() / ".local/share/vps-workspaces"
root.mkdir(parents=True, exist_ok=True)
root.chmod(0o700)


def private(name, value):
    path = root / name
    path.write_text(value)
    path.chmod(0o600)


private("settings.json", json.dumps({"base_domain": a.base_domain}))
if not (root / "access.json").exists():
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    private(
        "access.json",
        json.dumps(
            {
                "salt": salt.hex(),
                "password_hash": hashlib.scrypt(
                    password.encode(), salt=salt, n=16384, r=8, p=1
                ).hex(),
                "key": secrets.token_hex(32),
            }
        ),
    )
    private("share-password", password + "\n")
(root / "bin").mkdir(exist_ok=True)
wrapper = root / "bin/cmux"
wrapper.write_bytes((root / "app/cmux-relay.py").read_bytes())
wrapper.chmod(0o700)
units = pathlib.Path.home() / ".config/systemd/user"
units.mkdir(parents=True, exist_ok=True)
(units / "vps-workspaces.service").write_text("""[Unit]
Description=Shared VPS workspaces (cmux / ttyd adapter)
After=network.target
[Service]
ExecStart=%h/.local/share/vps-workspaces/venv/bin/python %h/.local/share/vps-workspaces/app/server.py
WorkingDirectory=%h/.local/share/vps-workspaces/app
Restart=on-failure
RestartSec=3
UMask=0077
[Install]
WantedBy=default.target
""")
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
subprocess.run(["systemctl", "--user", "enable", "--now", "vps-workspaces"], check=True)
print("Service installed. Share password is in", root / "share-password")
