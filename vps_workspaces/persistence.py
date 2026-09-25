from __future__ import annotations

import fcntl
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from vps_workspaces.contracts import Instance, JsonObject, Surface
from vps_workspaces.model import surfaces


def shell() -> NoReturn:
    from vps_workspaces.remote import ROOT, TMUX, ensure
    from vps_workspaces.storage import write_json

    wid = str(UUID(os.environ["CMUX_WORKSPACE_ID"])).upper()
    sid = str(UUID(os.environ["CMUX_SURFACE_ID"])).upper()
    session = "shell-" + sid.lower()
    cwd = str(Path.home() / "Coding" if Path.cwd() == Path.home() else Path.cwd())
    directory = ROOT / "shells"
    directory.mkdir(exist_ok=True)
    surface: Surface = {"id": session, "type": "terminal", "session": session, "cwd": cwd}
    ensure(session, cwd)
    write_json(directory / (sid + ".json"), {"workspace": wid, "surface": surface})
    for key in ("CMUX_WORKSPACE_ID", "CMUX_SURFACE_ID", "CMUX_SOCKET_PATH", "CMUX_RELAY_ID", "CMUX_RELAY_TOKEN"):
        if os.environ.get(key):
            subprocess.run([*TMUX, "set-environment", "-t", session, key, os.environ[key]], check=True)
    os.execv(TMUX[0], [*TMUX, "attach-session", "-t", "=" + session])


def discover(name: str, current: JsonObject) -> dict[str, Surface]:
    from vps_workspaces import workspace as w

    wid = current["id"]
    sessions = w.cmux("ssh-session-list", "--workspace", wid).get("sessions", [])
    if not sessions:
        return {}
    result = w.remote("surface-agents", name, wid)
    origins: dict[str, dict[str, Surface]] = {wid: result}
    for session in sessions:
        parts = session["session_id"]
        if not parts.startswith("ssh-") or len(parts) != 77:
            continue
        origin, surface = parts[4:40], parts[41:]
        if origin not in origins:
            origins[origin] = w.remote("surface-agents", name, origin)
        if surface in origins[origin]:
            for attachment in session.get("attachments", []):
                result[attachment["attachment_id"]] = origins[origin][surface]
    return result


def adopt(current: JsonObject) -> None:
    from vps_workspaces import workspace as w

    wid = current["id"]
    name = "ws-" + UUID(wid).hex[:16]
    found = discover(name, current)
    terminals = [s for p in current["panes"] for s in p["surfaces"] if s["type"] == "terminal"]
    if not terminals or any(s["id"] not in found for s in terminals):
        return
    docs = w.remote("list")
    sessions = {s.get("hapi_session") or s["session"] for s in found.values()}
    matching = [
        d for d in docs if sessions & {s.get("hapi_session") or s.get("session") for s in surfaces(d["layout"])}
    ]
    if len(matching) > 1:
        raise ValueError("Terminal sessions belong to multiple saved workspaces")
    if matching:
        doc = matching[0]
        name = doc["id"]
        known = {
            s.get("hapi_session") or s.get("session"): s for s in surfaces(doc["layout"]) if s["type"] == "terminal"
        }
        found = {sid: known.get(s.get("hapi_session") or s["session"], s) for sid, s in found.items()}
    else:
        doc = {"id": name, "name": current["title"], "layout": {"pane": {"surfaces": [], "selected": 0}}}
    state: Instance = {
        "workspace": wid,
        "revision": doc.get("revision", 0),
        "bindings": {sid: s["id"] for sid, s in found.items()},
        "pending_surfaces": {s["id"]: s for s in found.values()},
        "doc": doc,
    }
    if not matching:
        state["doc"] = w.remote("import", doc=w.snapshot_workspace(name, state, current))
        state["revision"] = state["doc"]["revision"]
        state.pop("pending_surfaces", None)
    w.store(name, state)


def bootstrap() -> None:
    from vps_workspaces import workspace as w

    wid = os.environ.get("CMUX_WORKSPACE_ID")
    if not wid or os.environ.get("SSH_CONNECTION"):
        return
    current = w.tree(wid)
    if len(current["panes"]) != 1 or len(current["panes"][0]["surfaces"]) != 1:
        return
    title = current.get("title") or Path.cwd().name or "Workspace"
    with (w.STATE / "bootstrap.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = w.STATE / ("bootstrap-" + str(UUID(wid)) + ".json")
        if marker.exists():
            return
        created = w.cmux("ssh", w.SSH_HOST, "--name", title)
        new_id = w.ident(created, "workspace")
        if not new_id:
            raise RuntimeError("cmux did not create a remote workspace")
        w.atomic_state(marker, {"workspace": new_id})
        w.cmux("close-workspace", "--workspace", wid)


def install() -> None:
    from vps_workspaces import workspace as w

    if sys.platform == "darwin":
        target = Path.home() / ".zshrc"
        root = Path(__file__).resolve().parents[1]
        line = "source " + shlex.quote(str(root / "shell-integration.zsh"))
        w.atomic_state(w.STATE / "persistence.json", {"enabled": True})
        label = "com.drpod.vps-workspaces-autosave"
        agent = Path.home() / "Library/LaunchAgents" / (label + ".plist")
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_bytes(
            plistlib.dumps(
                {
                    "Label": label,
                    "ProgramArguments": ["/usr/bin/python3", str(root / "workspace.py"), "autosave"],
                    "RunAtLoad": True,
                    "KeepAlive": True,
                    "ThrottleInterval": 10,
                    "StandardOutPath": str(w.STATE / "autosave.log"),
                    "StandardErrorPath": str(w.STATE / "autosave.log"),
                }
            )
        )
        domain = "gui/" + str(os.getuid())
        subprocess.run(["launchctl", "bootout", domain + "/" + label], check=False, capture_output=True)
        subprocess.run(["launchctl", "bootstrap", domain, str(agent)], check=True)
    else:
        target = Path.home() / ".bashrc"
        root = Path.home() / ".local/share/vps-workspaces/app"
        line = "source " + shlex.quote(str(root / "shell-integration.bash"))
    text = target.read_text() if target.exists() else ""
    if ("shell-integration.zsh" if sys.platform == "darwin" else "shell-integration.bash") not in text:
        target.with_suffix(target.suffix + ".vws-backup").write_text(text)
        target.write_text(text + "\n" + line + "\n")
    print("Installed automatic workspace persistence")


def main() -> None:
    {"shell": shell, "bootstrap": bootstrap, "install": install}[sys.argv[1]]()
