from __future__ import annotations

import argparse
import fcntl
import subprocess
import sys
import time
from pathlib import Path

from vps_workspaces import remote
from vps_workspaces.contracts import HapiSession
from vps_workspaces.hapi_bridge import Hapi, assert_shell, checked_session, link
from vps_workspaces.model import checked_id, surfaces


def native_sessions(api: Hapi, native_id: str) -> list[HapiSession]:

    matches = []
    for summary in api.request("/api/sessions")["sessions"]:
        session = summary
        if not (summary.get("metadata") or {}).get("codexSessionId"):
            session = api.session(summary["id"])
        if (session.get("metadata") or {}).get("codexSessionId") == native_id:
            matches.append(session)
    return matches


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["list", "link", "new", "bind", "migrate"])
    p.add_argument("workspace", nargs="?")
    p.add_argument("surface", nargs="?")
    p.add_argument("session", nargs="?")
    p.add_argument("--permission", choices=["default", "read-only", "yolo"], default="default")
    a = p.parse_args()
    if a.action == "link":
        print(link())
        return
    api = Hapi()
    if a.action == "list":
        for session in api.request("/api/sessions")["sessions"]:
            meta = session.get("metadata") or {}
            print(
                session["id"],
                "active" if session.get("active") else "inactive",
                meta.get("name") or meta.get("path", ""),
            )
        return
    with (remote.ROOT / "registry.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        doc = remote.load(checked_id(a.workspace))
        surface = next(
            (s for s in surfaces(doc["layout"]) if s["id"] == a.surface and s["type"] == "terminal"),
            None,
        )
        if surface is None:
            raise ValueError("Unknown saved terminal surface")
        if surface.get("hapi_session"):
            raise ValueError("This pane is already bound to HAPI: " + surface["hapi_session"])
        assert_shell(surface)
        if a.action == "new":
            sid = api.create(surface.get("cwd", "~/Coding"), doc["name"] + ": " + surface["id"], a.permission)
        elif a.action == "bind":
            sid = checked_session(a.session)
            session = api.session(sid)
            if (session.get("metadata") or {}).get("flavor") != "codex":
                raise ValueError("Only Codex currently supports independent native attachments")
        else:
            native_id = checked_session(a.session)

            existing = native_sessions(api, native_id)
            if existing:
                raise ValueError("Thread is already in HAPI; use bind with " + existing[0]["id"])
            unit = "vws-hapi-import-" + native_id
            subprocess.run(
                [
                    "systemd-run",
                    "--user",
                    "--collect",
                    "--unit=" + unit,
                    "--property=UMask=0077",
                    "--working-directory=" + str(Path(surface.get("cwd", "~/Coding")).expanduser()),
                    str(Path.home() / ".local/bin/hapi"),
                    "codex",
                    "resume",
                    native_id,
                    "--started-by",
                    "runner",
                    "--permission-mode",
                    a.permission,
                ],
                check=True,
            )
            sid = None
            for _ in range(600):
                matches = [s for s in native_sessions(api, native_id) if s.get("active")]
                if matches:
                    sid = checked_session(matches[0]["id"])
                    break
                time.sleep(0.2)
            if not sid:
                raise RuntimeError(
                    "Import did not become ready. Inspect journalctl --user -u "
                    + unit
                    + "; workspace binding unchanged."
                )
        if sid is None:
            raise RuntimeError("HAPI returned no session ID")
        surface["hapi_session"] = sid
        remote.save(doc)
    print("Bound", a.workspace + "/" + a.surface, "to HAPI", sid)
    print("Reopen the saved workspace to attach an independent terminal frontend.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
