from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from vps_workspaces.model import surfaces
from vps_workspaces.registry import WorkspaceRegistry


def service_active(name: str) -> bool:
    return subprocess.run(["systemctl", "--user", "is-active", "--quiet", name], check=False).returncode == 0


def inspect_vps() -> dict[str, Any]:
    root = Path.home() / ".local/share/vps-workspaces"
    registry = WorkspaceRegistry(root)
    result: dict[str, Any] = {
        "role": "vps",
        "gateway": service_active("vps-workspaces.service"),
        "workspaces": [],
    }
    for doc in registry.documents():
        socket = Path.home() / "deploy/www" / ("vws-ide-" + doc["id"] + ".sock")
        result["workspaces"].append(
            {
                "id": doc["id"],
                "revision": doc.get("revision"),
                "ide": service_active("vps-ide-" + doc["id"] + ".service") and socket.is_socket(),
                "hapi_terminals": sum(bool(s.get("hapi_session")) for s in surfaces(doc["layout"])),
                "browsers": [s["url"] for s in surfaces(doc["layout"]) if s["type"] == "browser"],
            }
        )
    result["healthy"] = result["gateway"] and all(w["ide"] for w in result["workspaces"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if sys.platform == "darwin":
        from vps_workspaces.workspace import CLI, STATE, remote

        ping = subprocess.run([CLI, "ping"], check=False, capture_output=True, text=True)
        status = STATE / "autosave-status.json"
        result = {
            "role": "mac",
            "cmux_access": ping.returncode == 0,
            "cmux_error": ping.stderr.strip() if ping.returncode else None,
            "autosave": json.loads(status.read_text()) if status.exists() else None,
            "workspaces": [d["id"] for d in remote("list")],
            "healthy": ping.returncode == 0,
        }
    else:
        result = inspect_vps()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["role"].upper() + ": " + ("healthy" if result["healthy"] else "needs attention"))
        if result["role"] == "vps":
            for entry in result["workspaces"]:
                print(entry["id"] + ": IDE " + ("ready" if entry["ide"] else "unavailable"))
        elif result.get("cmux_error"):
            print(result["cmux_error"])
    if not result["healthy"]:
        raise SystemExit(1)
