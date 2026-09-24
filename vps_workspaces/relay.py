from __future__ import annotations

import json
import os
import pathlib
import sys


def main() -> None:

    root = pathlib.Path.home() / ".local/share/vps-workspaces"
    session = os.environ.get("VWS_SESSION", "")
    if not session and os.environ.get("HAPI_SESSION_ID"):
        from vps_workspaces.model import surfaces

        for p in root.glob("*.json"):
            doc = json.loads(p.read_text())
            if "layout" in doc:
                matches = [
                    s["session"]
                    for s in surfaces(doc["layout"])
                    if s.get("hapi_session") == os.environ["HAPI_SESSION_ID"]
                ]
                if matches:
                    session = matches[0]
                    break
    if not session or "/" in session:
        sys.exit("This cmux adapter must run inside a managed workspace terminal.")
    try:
        route = json.loads((root / (session + ".route")).read_text())
    except FileNotFoundError:
        sys.exit("Open this workspace in cmux on a Mac to use its native browser controls.")
    env = os.environ.copy()
    for k in list(env):
        if k.startswith("CMUX_"):
            env.pop(k)
    env.update({k: v for k, v in route.items() if k.startswith("CMUX_")})
    cli = str(pathlib.Path.home() / ".cmux/bin/cmux")
    os.execve(cli, [cli, *sys.argv[1:]], env)


if __name__ == "__main__":
    main()
