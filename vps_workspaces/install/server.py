from __future__ import annotations

import argparse
import pathlib
import secrets
import subprocess

from vps_workspaces.storage import write_json
from vps_workspaces.templates import service_template


def main() -> None:

    p = argparse.ArgumentParser()
    p.add_argument("--base-domain", required=True)
    a = p.parse_args()
    root = pathlib.Path.home() / ".local/share/vps-workspaces"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)

    if not a.base_domain or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in a.base_domain):
        raise ValueError("Use a lowercase DNS base domain")
    write_json(root / "settings.json", {"base_domain": a.base_domain})
    if not (root / "access.json").exists():
        write_json(root / "access.json", {"key": secrets.token_hex(32)})
    (root / "bin").mkdir(exist_ok=True)
    wrapper = root / "bin/cmux"
    wrapper.write_text('#!/bin/sh\nexec python3 "$HOME/.local/share/vps-workspaces/app/workspace.py" relay "$@"\n')
    wrapper.chmod(0o700)
    units = pathlib.Path.home() / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    (units / "vps-workspaces.service").write_text(service_template("gateway.service"))
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "vps-workspaces"], check=True)
    print("Service installed. Retrieve each private link with remote.py link <workspace>.")


if __name__ == "__main__":
    main()
