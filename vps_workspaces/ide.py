from __future__ import annotations

import hashlib
import pathlib
import shutil
import socket
import subprocess
import time

from vps_workspaces.contracts import Workspace
from vps_workspaces.model import surfaces
from vps_workspaces.storage import read_json, write_json
from vps_workspaces.templates import service_template


def ensure_ide(root: pathlib.Path, doc: Workspace) -> None:
    name = doc["id"]
    binary = pathlib.Path.home() / ".local/lib/code-server-4.138.0-linux-amd64/bin/code-server"
    if not binary.exists():
        raise RuntimeError("Install the pinned code-server 4.138.0 Linux amd64 release first.")
    ide = root / "ide" / name
    ide.mkdir(parents=True, exist_ok=True)
    extensions = ide / "extensions"
    extensions.mkdir(exist_ok=True)
    link = extensions / "drpod.vps-workspaces-0.1.0"
    if not link.exists() and not link.is_symlink():
        link.symlink_to(root / "app/ide-extension")
    folders = []
    for surface in surfaces(doc["layout"]):
        if surface["type"] == "terminal":
            cwd = str(pathlib.Path(surface.get("cwd", "~/Coding")).expanduser())
            if cwd not in folders:
                folders.append(cwd)
    workspace = ide / (name + ".code-workspace")
    settings = {
        "workbench.colorTheme": "Default Dark Modern",
        "workbench.startupEditor": "none",
        "workbench.editor.enablePreview": False,
        "terminal.integrated.defaultLocation": "editor",
        "terminal.integrated.fontSize": 14,
        "terminal.integrated.enablePersistentSessions": False,
        "telemetry.telemetryLevel": "off",
        "window.commandCenter": True,
    }
    config = read_json(workspace) if workspace.exists() else {}
    config["folders"] = [{"path": p} for p in folders]
    current_settings = config.setdefault("settings", {})
    for key, value in settings.items():
        current_settings.setdefault(key, value)
    if not workspace.exists() or config != read_json(workspace):
        write_json(workspace, config)
    data = ide / "data"
    if len(str(data / "code-server-ipc.sock").encode()) >= 104:
        data = root / "ide-data" / hashlib.sha256(name.encode()).hexdigest()[:12]
        if (ide / "data").exists() and not data.exists():
            shutil.copytree(ide / "data", data, ignore=shutil.ignore_patterns("*.sock", "*.lock"))
    unit = pathlib.Path.home() / ".config/systemd/user" / ("vps-ide-" + name + ".service")
    definition = service_template(
        "ide.service.in",
        name=name,
        binary=str(binary),
        home=str(pathlib.Path.home()),
        ide=str(ide),
        data=str(data),
        extensions=str(extensions),
        workspace=str(workspace),
    )
    unit.parent.mkdir(parents=True, exist_ok=True)
    if not unit.exists() or unit.read_text() != definition:
        unit.write_text(definition)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", unit.name], check=True)
    address = pathlib.Path.home() / "deploy/www" / ("vws-ide-" + name + ".sock")
    for _ in range(100):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.1)
                client.connect(str(address))
        except OSError:
            pass
        else:
            write_json(root / (name + ".ide"), {"workspace": str(workspace), "socket": str(address)})
            return
        time.sleep(0.1)
    raise RuntimeError("IDE socket did not become ready: " + name)
