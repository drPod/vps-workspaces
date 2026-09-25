from __future__ import annotations

import copy
import fcntl
import json
import os
import subprocess
import time
from typing import Any

from vps_workspaces import workspace as ws
from vps_workspaces.contracts import Workspace
from vps_workspaces.model import surfaces


def fingerprint(doc: Workspace) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items() if k not in ("title", "revision", "saved_at", "host")}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if isinstance(value, float):
            return round(value, 3)
        return value

    return json.dumps(normalize(doc), sort_keys=True)


class Debounce:
    def __init__(self, seconds: float = 2) -> None:
        self.seconds = seconds
        self.pending: dict[str, tuple[str, float]] = {}
        self.unsettled: dict[str, tuple[str, float]] = {}

    def ready(self, key: str, baseline: str, value: str, now: float) -> bool:
        if baseline == value:
            self.pending.pop(key, None)
            return False
        old = self.pending.get(key)
        if old is None or old[0] != value:
            self.pending[key] = (value, now)
            return False
        return now - old[1] >= self.seconds


def notify(name: str, error: str) -> None:
    print(f"{name}: autosave paused: {error}", flush=True)

    subprocess.run(
        [
            "osascript",
            "-e",
            'on run argv\ndisplay notification (item 1 of argv) with title "Workspace autosave paused"\nend run',
            name + ": " + error,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def tick(debounce: Debounce, errors: dict[str, tuple[int, str, bool]], now: float) -> None:
    with (ws.STATE / "autosave.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        directory = ws.STATE / "instances"
        directory.mkdir(exist_ok=True)

        for p in ws.STATE.glob("*.json"):
            state = json.loads(p.read_text())
            if isinstance(state, dict) and "workspace" in state and "bindings" in state and "doc" in state:
                ip = directory / (state["workspace"] + ".json")
                if not ip.exists():
                    ws.atomic_state(ip, dict(state, registry_name=p.stem))
        all_trees = ws.cmux("tree", "--all")
        trees = {w["id"]: w for window in all_trees["windows"] for w in window["workspaces"]}
        status = {}
        for p in directory.glob("*.json"):
            state = json.loads(p.read_text())
            wid, name = state["workspace"], state["registry_name"]
            if wid not in trees:
                continue
            status[wid] = {"workspace": name, "revision": state["revision"], "state": "watching"}
            try:
                candidate = copy.deepcopy(state)
                doc = ws.snapshot_workspace(name, candidate, trees[wid])
                saved_agents = {s["id"] for s in surfaces(state["doc"]["layout"]) if s["type"] == "terminal"}
                visible = {s["id"] for s in surfaces(doc["layout"])}
                if saved_agents - visible:
                    raise ValueError(
                        "A saved terminal is detached or closed. Its saved binding was preserved; "
                        "reconnect it, or use an explicit workspace save to confirm removal."
                    )
                value = fingerprint(doc)
                baseline = fingerprint(state["doc"])
                if wid in errors and errors[wid][0] == state["revision"] and errors[wid][2]:
                    status[wid].update(state="paused", error=errors[wid][1])
                    continue
                if debounce.ready(wid, baseline, value, now):
                    ws.save_state(name, candidate, trees[wid])
                    debounce.pending.pop(wid, None)
                    errors.pop(wid, None)
                    status[wid].update(state="saved", revision=candidate["revision"])
                debounce.unsettled.pop(wid, None)
                errors.pop(wid, None)
            except (ValueError, RuntimeError) as error:
                message = str(error)
                drafts = ws.STATE / "autosave-drafts"
                drafts.mkdir(exist_ok=True)
                ws.atomic_state(drafts / p.name, {"state": state, "native_tree": trees[wid], "error": message})
                status[wid].update(state="paused", error=message)

                retrying = "timed out" in message.lower() or "connection refused" in message.lower()
                if retrying:
                    status[wid]["state"] = "retrying"
                if retrying or message.startswith("Unmanaged terminal:"):
                    previous, since = debounce.unsettled.setdefault(wid, (message, now))
                    if previous != message:
                        debounce.unsettled[wid] = (message, now)
                        since = now
                    if now - since < (60 if retrying else 10):
                        continue
                conflict = "Workspace changed on another Mac" in message
                if errors.get(wid, (None, None))[1] != message:
                    notify(name, message)
                errors[wid] = (state["revision"], message, conflict)
        ws.atomic_state(
            ws.STATE / "autosave-status.json",
            {"checked_at": int(time.time()), "pid": os.getpid(), "instances": status},
        )


def main() -> None:
    os.umask(0o077)
    with (ws.STATE / "autosave-worker.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        ws.cmux("ping")
        debounce = Debounce()
        errors: dict[str, tuple[int, str, bool]] = {}
        status_path = ws.STATE / "autosave-status.json"
        if status_path.exists():
            previous = json.loads(status_path.read_text()).get("instances", {})
            errors = {
                wid: (s["revision"], s["error"], "Workspace changed on another Mac" in s["error"])
                for wid, s in previous.items()
                if s.get("state") in ("paused", "retrying") and s.get("error")
            }
        while True:
            try:
                tick(debounce, errors, time.monotonic())
            except (ValueError, RuntimeError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
                print(str(error), flush=True)
                if "Access denied" in str(error):
                    return
            time.sleep(1)


if __name__ == "__main__":
    main()
