#!/usr/bin/env python3
"""Enable code-server for an existing saved workspace. Run on the VPS."""

import json
import pathlib
import subprocess
import sys
from model import checked_id, surfaces

root = pathlib.Path.home() / ".local/share/vps-workspaces"
name = checked_id(sys.argv[1])
doc = json.loads((root / (name + ".json")).read_text())
binary = (
    pathlib.Path.home() / ".local/lib/code-server-4.138.0-linux-amd64/bin/code-server"
)
if not binary.exists():
    sys.exit("Install the pinned code-server 4.138.0 Linux amd64 release first.")
ide = root / "ide" / name
ide.mkdir(parents=True, exist_ok=True)
extensions = ide / "extensions"
extensions.mkdir(exist_ok=True)
link = extensions / "drpod.vps-workspaces-0.1.0"
if not link.exists():
    link.symlink_to(root / "app/ide-extension")
folders = []
for surface in surfaces(doc["layout"]):
    if surface["type"] == "terminal":
        cwd = str(pathlib.Path(surface.get("cwd", "~/Coding")).expanduser())
        if cwd not in folders:
            folders.append(cwd)
workspace = ide / (name + ".code-workspace")
workspace.write_text(
    json.dumps(
        {
            "folders": [{"path": p} for p in folders],
            "settings": {
                "workbench.colorTheme": "Default Dark Modern",
                "workbench.startupEditor": "none",
                "workbench.editor.enablePreview": False,
                "terminal.integrated.defaultLocation": "editor",
                "terminal.integrated.fontSize": 14,
                "terminal.integrated.enablePersistentSessions": False,
                "telemetry.telemetryLevel": "off",
                "window.commandCenter": True,
            },
        },
        indent=2,
    )
)
unit = pathlib.Path.home() / ".config/systemd/user" / ("vps-ide-" + name + ".service")
unit.write_text(f"""[Unit]
Description=code-server for {name}
After=network.target
[Service]
Environment=VWS_WORKSPACE={name}
UMask=0077
ExecStart={binary} --auth none --socket {pathlib.Path.home()}/deploy/www/vws-ide-{name}.sock --socket-mode 600 --user-data-dir {ide}/data --extensions-dir {extensions} --reconnection-grace-time 60 --disable-telemetry --disable-update-check --disable-workspace-trust --disable-proxy {workspace}
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
""")
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
subprocess.run(["systemctl", "--user", "enable", "--now", unit.name], check=True)
(root / (name + ".ide")).write_text(
    json.dumps({"workspace": str(workspace), "socket": str(pathlib.Path.home() / "deploy/www" / ("vws-ide-" + name + ".sock"))})
)
print("IDE enabled:", name)
