#!/usr/bin/env python3
"""SSH-only registry and tmux attachment adapter; not exposed through HTTP."""

import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from model import checked_id, validate, surfaces, browser_host, local_browser
from sharing import share_url

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
    documents = []
    for p in ROOT.glob("*.json"):
        if p.name in ("access.json", "settings.json"):
            continue
        d = doc if p == path else json.loads(p.read_text())
        if "layout" in d:
            documents.append(d)
    if not path.exists():
        documents.append(doc)
    from caddy_routes import render, prepare_previews
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


def prepare_terminal(name, label, revision):
    """Reserve a terminal without publishing a guessed layout to other clients."""
    checked_id(label)
    doc = load(name)
    if doc["revision"] != int(revision):
        raise ValueError(
            "Workspace changed on another Mac. Open the latest version first."
        )
    if any(s["id"] == label for s in surfaces(doc["layout"])):
        raise ValueError("That terminal already exists")
    pending_path = ROOT / (name + ".pending")
    pending = json.loads(pending_path.read_text()) if pending_path.exists() else {}
    if label not in pending:
        full = name + "-" + label
        session = (
            full
            if len(full) <= 48
            else full[:35] + "-" + hashlib.sha256(full.encode()).hexdigest()[:12]
        )
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
    run(*TMUX, "set-window-option", "-t", session, "window-size", "latest")
    return session


def attach(name, surface):
    doc = load(name)
    s = next(
        (
            s
            for s in surfaces(doc["layout"])
            if s["id"] == surface and s["type"] == "terminal"
        ),
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
        route["saved_at"] = int(time.time())
        atomic(ROOT / (session + ".route"), route)
        for key, value in route.items():
            if key != "saved_at" and not s.get("hapi_session"):
                run(*TMUX, "set-environment", "-t", session, key, value)
    if s.get("hapi_session"):
        from hapi_bridge import attach as hapi_attach
        hapi_attach(s["hapi_session"])
    os.execv(TMUX[0], [*TMUX, "attach-session", "-t", "=" + session])


if __name__ == "__main__":
    try:
        action = sys.argv[1]
        if action == "get":
            print(json.dumps(load(sys.argv[2])))
        elif action == "link":
            print(
                json.dumps(
                    share_url(
                        json.loads((ROOT / "access.json").read_text()),
                        load(sys.argv[2]),
                    )
                )
            )
        elif action == "hapi-link":
            from hapi_bridge import link
            print(json.dumps(link()))
        elif action == "prepare-terminal":
            with open(ROOT / "registry.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                print(
                    json.dumps(prepare_terminal(sys.argv[2], sys.argv[3], sys.argv[4]))
                )
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
                        if s["type"] == "terminal" and not s.get("hapi_session")
                    ]
                )
            )
        else:
            raise ValueError("Unknown command")
    except Exception as e:
        sys.exit(str(e))
