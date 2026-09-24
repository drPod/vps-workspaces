from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
from functools import partial
from typing import NoReturn

from vps_workspaces.contracts import Surface, Workspace
from vps_workspaces.model import checked_id, surfaces, validate
from vps_workspaces.registry import WorkspaceRegistry
from vps_workspaces.storage import write_json as atomic

ROOT = pathlib.Path.home() / ".local/share/vps-workspaces"
ROOT.mkdir(parents=True, exist_ok=True)
ROOT.chmod(0o700)
TMUX = ["/usr/bin/tmux", "-L", "vps-workspaces"]


run = partial(subprocess.run, check=True)


def load(name: str) -> Workspace:
    return WorkspaceRegistry(ROOT).load(name)


def save(doc: Workspace) -> Workspace:
    validate(doc)
    name = doc["id"]
    path = ROOT / (name + ".json")
    old = load(name) if path.exists() else None
    if old and doc.get("revision") != old["revision"]:
        raise ValueError("Workspace changed on another Mac. Open the latest saved workspace before saving.")
    doc["host"] = old["host"] if old else name + "." + json.loads((ROOT / "settings.json").read_text())["base_domain"]
    doc["revision"] = (old.get("revision", 0) if old else 0) + 1
    doc["saved_at"] = int(time.time())
    documents = [d for d in WorkspaceRegistry(ROOT).documents() if d["id"] != name]
    documents.append(doc)
    from vps_workspaces.caddy_routes import prepare_previews, render

    site = pathlib.Path.home() / "deploy/caddy/sites/vps-workspaces.caddy"
    previous = site.read_text() if site.exists() else None
    rendered = render(documents)
    if rendered == previous:
        atomic(path, doc)
        return doc
    prepare_previews(documents)
    atomic(path, doc)
    try:
        site.write_text(rendered)
        run(
            ["docker", "exec", "caddy", "caddy", "validate", "--config", "/etc/caddy/Caddyfile"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        run(
            ["docker", "exec", "caddy", "caddy", "reload", "--config", "/etc/caddy/Caddyfile"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        if old:
            atomic(path, old)
        else:
            path.unlink(missing_ok=True)
        if previous is None:
            site.unlink(missing_ok=True)
        elif site.read_text() != previous:
            site.write_text(previous)
        raise
    return doc


def create(name: str, title: str, cwd: str) -> Workspace:
    checked_id(name)
    if (ROOT / (name + ".json")).exists():
        raise ValueError("Workspace already exists; use open " + name)
    directory = pathlib.Path(cwd).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("VPS directory does not exist: " + str(directory))
    session = terminal_session(name, "agent")
    doc: Workspace = {
        "id": name,
        "name": title,
        "layout": {
            "pane": {
                "surfaces": [
                    {
                        "id": "agent",
                        "type": "terminal",
                        "session": session,
                        "cwd": str(directory),
                    }
                ],
                "selected": 0,
            }
        },
    }
    from vps_workspaces.ide import ensure_ide

    validate(doc)
    ensure_ide(ROOT, doc)
    saved = save(doc)
    from vps_workspaces.hapi_bridge import Hapi

    sid = Hapi().create(str(directory), title)
    first = next(surfaces(saved["layout"]))
    first["hapi_session"] = sid
    return save(saved)


def prepare(name: str) -> Workspace:
    from vps_workspaces.ide import ensure_ide

    doc = load(name)
    ensure_ide(ROOT, doc)
    for surface in surfaces(doc["layout"]):
        if surface["type"] == "terminal" and not surface.get("hapi_session"):
            ensure(surface["session"], surface.get("cwd"))
    return doc


def current_name() -> str:
    workspace_id = os.environ.get("CMUX_WORKSPACE_ID")
    session = os.environ.get("VWS_SESSION")
    hapi = os.environ.get("HAPI_SESSION_ID")
    matches = set()
    for doc in WorkspaceRegistry(ROOT).documents():
        for surface in surfaces(doc["layout"]):
            if surface["type"] != "terminal":
                continue
            route = ROOT / (surface["session"] + ".route")
            if (session and surface["session"] == session) or (hapi and surface.get("hapi_session") == hapi):
                matches.add(doc["id"])
            elif workspace_id and route.exists():
                data = json.loads(route.read_text())
                if data.get("CMUX_WORKSPACE_ID") == workspace_id:
                    matches.add(doc["id"])
    if len(matches) != 1:
        raise ValueError("No unique managed workspace found; specify its name")
    return matches.pop()


def terminal_session(name: str, label: str) -> str:
    full = name + "-" + label
    return full if len(full) <= 48 else full[:35] + "-" + hashlib.sha256(full.encode()).hexdigest()[:12]


def prepare_terminal(name: str, label: str, revision: int | str) -> Surface:
    checked_id(label)
    doc = load(name)
    if doc["revision"] != int(revision):
        raise ValueError("Workspace changed on another Mac. Open the latest version first.")
    if any(s["id"] == label for s in surfaces(doc["layout"])):
        raise ValueError("That terminal already exists")
    pending_path = ROOT / (name + ".pending")
    pending = json.loads(pending_path.read_text()) if pending_path.exists() else {}
    if label not in pending:
        session = terminal_session(name, label)
        pending[label] = {
            "id": label,
            "type": "terminal",
            "title": label,
            "session": session,
            "cwd": "~/Coding",
        }
        atomic(pending_path, pending)
    ensure(pending[label]["session"], pending[label]["cwd"])
    return pending[label]


def ensure(session: str, cwd: str | None = None) -> str:
    checked_id(session)
    if subprocess.run([*TMUX, "has-session", "-t", "=" + session], check=False, capture_output=True).returncode:
        env = os.environ.copy()
        env["VWS_SESSION"] = session
        env["PATH"] = str(ROOT / "bin") + ":" + str(pathlib.Path.home() / ".cmux/bin") + ":" + env["PATH"]
        run(
            [
                *TMUX,
                "new-session",
                "-d",
                "-s",
                session,
                "-c",
                str(pathlib.Path(cwd).expanduser()) if cwd else str(pathlib.Path.home() / "Coding"),
                "-x",
                "120",
                "-y",
                "40",
                "-e",
                "VWS_SESSION=" + session,
                "-e",
                "PATH=" + env["PATH"],
                "/bin/bash",
            ],
            env=env,
        )
        run([*TMUX, "set-option", "-t", session, "status", "off"])
        run([*TMUX, "set-option", "-t", session, "history-limit", "20000"])
    run([*TMUX, "set-window-option", "-t", session, "window-size", "latest"])
    return session


def attach(name: str, surface: str) -> NoReturn:
    doc = load(name)
    s = next(
        (s for s in surfaces(doc["layout"]) if s["id"] == surface and s["type"] == "terminal"),
        None,
    )
    if s is None:
        pending_path = ROOT / (name + ".pending")
        pending = json.loads(pending_path.read_text()) if pending_path.exists() else {}
        s = pending.get(surface)
    if s is None:
        raise ValueError("Unknown terminal")
    session = s["session"]
    if not s.get("hapi_session"):
        ensure(session, s.get("cwd"))
    route = {
        k: v
        for k, v in os.environ.items()
        if k
        in (
            "CMUX_SOCKET_PATH",
            "CMUX_WORKSPACE_ID",
            "CMUX_SURFACE_ID",
            "CMUX_RELAY_ID",
            "CMUX_RELAY_TOKEN",
            "CMUX_TAB_ID",
        )
    }
    if route.get("CMUX_SOCKET_PATH"):
        atomic(ROOT / (session + ".route"), {**route, "saved_at": int(time.time())})
        for key, value in route.items():
            if key != "saved_at" and not s.get("hapi_session"):
                run([*TMUX, "set-environment", "-t", session, key, value])
    if s.get("hapi_session"):
        from vps_workspaces.hapi_bridge import attach as hapi_attach

        hapi_attach(s["hapi_session"])
    os.execv(TMUX[0], [*TMUX, "attach-session", "-t", "=" + session])


def main() -> None:
    try:
        action = sys.argv[1]
        if action == "create":
            with open(ROOT / "registry.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(json.dumps(create(*sys.argv[2:5])))
        elif action == "prepare":
            with open(ROOT / "registry.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(json.dumps(prepare(sys.argv[2])))
        elif action == "get":
            print(json.dumps(load(sys.argv[2])))
        elif action == "link":
            print(json.dumps(WorkspaceRegistry(ROOT).sharing_link(sys.argv[2])))
        elif action == "hapi-link":
            from vps_workspaces.hapi_bridge import link

            print(json.dumps(link()))
        elif action == "prepare-terminal":
            with open(ROOT / "registry.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(json.dumps(prepare_terminal(sys.argv[2], sys.argv[3], sys.argv[4])))
        elif action == "save":
            with open(ROOT / "registry.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(json.dumps(save(json.load(sys.stdin))))
        elif action == "list":
            print(json.dumps(WorkspaceRegistry(ROOT).documents()))
        elif action == "attach":
            attach(sys.argv[2], sys.argv[3])
        elif action == "ensure":
            d = load(sys.argv[2])
            print(
                json.dumps(
                    [
                        ensure(s["session"], s.get("cwd"))
                        for s in surfaces(d["layout"])
                        if s["type"] == "terminal" and not s.get("hapi_session")
                    ]
                )
            )
        else:
            raise ValueError("Unknown command")
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, subprocess.SubprocessError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
