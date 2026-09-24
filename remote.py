#!/usr/bin/env python3
"""SSH-only registry and tmux attachment adapter; not exposed through HTTP."""

import fcntl
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from model import checked_id, validate, surfaces, browser_host, local_browser

ROOT = pathlib.Path.home() / ".local/share/vps-workspaces"
ROOT.mkdir(parents=True, exist_ok=True)
ROOT.chmod(0o700)
TMUX = ["/usr/bin/tmux", "-L", "vps-workspaces"]


def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)


def atomic(path, doc):
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, "w") as f:
        json.dump(doc, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def load(name):
    return json.loads((ROOT / (checked_id(name) + ".json")).read_text())


def save(doc):
    validate(doc)
    name = doc["id"]
    path = ROOT / (name + ".json")
    old = load(name) if path.exists() else None
    if old and doc.get("revision") != old["revision"]:
        raise ValueError(
            "Workspace changed on another Mac. Open the latest saved workspace before saving."
        )
    doc["host"] = (old or {}).get(
        "host",
        name + "." + json.loads((ROOT / "settings.json").read_text())["base_domain"],
    )
    doc["revision"] = (old or {}).get("revision", 0) + 1
    doc["saved_at"] = int(time.time())
    atomic(path, doc)
    hosts = []
    for p in ROOT.glob("*.json"):
        if p.name in ("access.json", "settings.json"):
            continue
        d = json.loads(p.read_text())
        if "layout" not in d:
            continue
        hosts.append(d["host"])
        hosts.extend(
            browser_host(d, s)
            for s in surfaces(d["layout"])
            if s["type"] == "browser" and local_browser(s)
        )
    site = pathlib.Path.home() / "deploy/caddy/sites/vps-workspaces.caddy"
    previous = site.read_text() if site.exists() else None
    site.write_text(
        ", ".join(sorted(set(hosts)))
        + " {\n reverse_proxy unix//srv/vps-workspaces.sock\n}\n"
    )
    try:
        run(
            "docker",
            "exec",
            "caddy",
            "caddy",
            "validate",
            "--config",
            "/etc/caddy/Caddyfile",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        run(
            "docker",
            "exec",
            "caddy",
            "caddy",
            "reload",
            "--config",
            "/etc/caddy/Caddyfile",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        if previous is None:
            site.unlink(missing_ok=True)
        else:
            site.write_text(previous)
        if old:
            atomic(path, old)
        else:
            path.unlink(missing_ok=True)
        raise
    return doc


def ensure(session, cwd=None):
    checked_id(session)
    if subprocess.run(
        [*TMUX, "has-session", "-t", "=" + session], capture_output=True
    ).returncode:
        env = os.environ.copy()
        env["VWS_SESSION"] = session
        env["PATH"] = (
            str(ROOT / "bin")
            + ":"
            + str(pathlib.Path.home() / ".cmux/bin")
            + ":"
            + env["PATH"]
        )
        run(
            *TMUX,
            "new-session",
            "-d",
            "-s",
            session,
            "-c",
            str(pathlib.Path(cwd).expanduser())
            if cwd
            else str(pathlib.Path.home() / "Coding"),
            "-x",
            "120",
            "-y",
            "40",
            "-e",
            "VWS_SESSION=" + session,
            "-e",
            "PATH=" + env["PATH"],
            "/bin/bash",
            env=env,
        )
        run(*TMUX, "set-option", "-t", session, "status", "off")
        run(*TMUX, "set-option", "-t", session, "history-limit", "20000")
        run(*TMUX, "set-window-option", "-t", session, "window-size", "smallest")
    return session


def attach(name, surface):
    doc = load(name)
    s = next(
        s
        for s in surfaces(doc["layout"])
        if s["id"] == surface and s["type"] == "terminal"
    )
    session = s["session"]
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
        route["saved_at"] = int(time.time())
        atomic(ROOT / (session + ".route"), route)
        for key, value in route.items():
            if key != "saved_at":
                run(*TMUX, "set-environment", "-t", session, key, value)
    os.execv(TMUX[0], [*TMUX, "attach-session", "-t", "=" + session])


if __name__ == "__main__":
    try:
        action = sys.argv[1]
        if action == "get":
            print(json.dumps(load(sys.argv[2])))
        elif action == "save":
            with open(ROOT / "registry.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(json.dumps(save(json.load(sys.stdin))))
        elif action == "list":
            print(
                json.dumps(
                    [
                        json.loads(p.read_text())
                        for p in ROOT.glob("*.json")
                        if p.name not in ("access.json", "settings.json")
                    ]
                )
            )
        elif action == "attach":
            attach(sys.argv[2], sys.argv[3])
        elif action == "ensure":
            d = load(sys.argv[2])
            print(
                json.dumps(
                    [
                        ensure(s["session"], s.get("cwd"))
                        for s in surfaces(d["layout"])
                        if s["type"] == "terminal"
                    ]
                )
            )
        else:
            raise ValueError("Unknown command")
    except Exception as e:
        sys.exit(str(e))
