from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from vps_workspaces.codex import binary, start
from vps_workspaces.storage import read_json, write_json


def main() -> None:
    command = binary()
    settings = Path.home() / ".codex/app-server-daemon/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    value = read_json(settings) if settings.exists() else {}
    value.setdefault("updater", {})["autoUpdateEnabled"] = False
    write_json(settings, value)
    if sys.platform == "linux":
        relay = Path.home() / ".local/share/vps-workspaces/bin/cmux"
        link = Path.home() / ".local/bin/cmux"
        if relay.exists() and not link.exists():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(relay)
        unit = Path.home() / ".config/systemd/user/vws-codex.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(f"""[Unit]
Description=Native Codex shared daemon
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={command} app-server daemon start
Environment=PATH={Path.home()}/.local/bin:{Path.home()}/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
UMask=0077
CPUWeight=200
MemoryLow=256M

[Install]
WantedBy=default.target
""")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", unit.name], check=True)
    elif sys.platform == "darwin":
        label = "com.drpod.vps-workspaces-codex"
        unit = Path.home() / "Library/LaunchAgents" / (label + ".plist")
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_bytes(
            plistlib.dumps(
                {
                    "Label": label,
                    "ProgramArguments": [command, "app-server", "daemon", "start"],
                    "RunAtLoad": True,
                    "EnvironmentVariables": {"PATH": os.environ["PATH"]},
                }
            )
        )
        domain = f"gui/{os.getuid()}"
        if subprocess.run(["launchctl", "print", f"{domain}/{label}"], capture_output=True, check=False).returncode:
            subprocess.run(["launchctl", "bootstrap", domain, str(unit)], check=True)
    print("Native Codex daemon:", start())
