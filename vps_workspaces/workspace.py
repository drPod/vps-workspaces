from __future__ import annotations

import argparse
import base64
import copy
import fcntl
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
from collections import Counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from vps_workspaces.contracts import Instance, JsonObject, Layout, Surface, Workspace
from vps_workspaces.model import checked_id, surfaces, validate
from vps_workspaces.storage import write_json as atomic_state

CLI = "/Applications/cmux.app/Contents/Resources/bin/cmux"
STATE = pathlib.Path.home() / ".local/state/vps-workspaces"
STATE.mkdir(parents=True, exist_ok=True)
REMOTE = ".local/share/vps-workspaces/app/remote.py"
SSH_HOST = os.environ.get("VWS_SSH_HOST", "myvps")


def cmux(*args: str) -> Any:
    p = subprocess.run([CLI, "--json", "--id-format", "uuids", *args], check=False, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    try:
        return json.loads(p.stdout)
    except ValueError:
        return p.stdout.strip()


def remote(action: str, *args: str, doc: Workspace | None = None) -> Any:
    p = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            SSH_HOST,
            shlex.join(["python3", REMOTE, action, *args]),
        ],
        check=False,
        input=json.dumps(doc) if doc is not None else None,
        capture_output=True,
        text=True,
    )
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return json.loads(p.stdout)


def tree(workspace: str) -> JsonObject:
    d = cmux("tree", "--all")
    for w in d["windows"]:
        for ws in w["workspaces"]:
            if ws["id"] == workspace:
                return ws
    raise ValueError("Workspace is no longer open")


def ident(value: object, kind: str) -> str | None:
    if isinstance(value, dict):
        if kind + "_id" in value:
            return value[kind + "_id"]
        for v in value.values():
            found = ident(v, kind)
            if found:
                return found
    return None


def attach_command(name: str, s: Surface) -> str:
    return "python3 ~/" + REMOTE + " " + shlex.join(["attach", name, s["id"]])


def store(name: str, value: JsonObject | Instance) -> None:
    p = STATE / (name + ".json")
    atomic_state(p, value)
    if isinstance(value, dict) and "workspace" in value and "bindings" in value:
        directory = STATE / "instances"
        directory.mkdir(exist_ok=True)
        atomic_state(directory / (value["workspace"] + ".json"), dict(value, registry_name=name))


def store_instance(name: str, state: Instance) -> None:
    path = STATE / (name + ".json")
    current = json.loads(path.read_text()) if path.exists() else {}
    if current.get("workspace") == state["workspace"]:
        store(name, state)
    else:
        directory = STATE / "instances"
        directory.mkdir(exist_ok=True)
        atomic_state(directory / (state["workspace"] + ".json"), dict(state, registry_name=name))


def open_workspace(name: str) -> str:
    with (STATE / "autosave.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _open_workspace(name)


def _open_workspace(name: str) -> str:
    doc = remote("prepare", name)
    validate(doc)

    first = next(surfaces(doc["layout"]))
    created = cmux("ssh", SSH_HOST, "--name", doc["name"])
    ws = ident(created, "workspace")
    if not ws:
        raise RuntimeError("No workspace returned by cmux")
    time.sleep(1)
    initial = tree(ws)["panes"][0]
    for _ in range(30):
        try:
            sessions = cmux("ssh-session-list", "--workspace", ws).get("sessions", [])
            if any(session.get("attachments") for session in sessions):
                time.sleep(1)
                break
        except RuntimeError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("SSH workspace did not become ready; existing sessions were preserved")
    bindings = {}
    pane_bindings = {}

    def add_surface(s: Surface, pane: str) -> str:
        args = [
            "new-surface",
            "--type",
            s["type"],
            "--workspace",
            ws,
            "--pane",
            pane,
            "--focus",
            "false",
        ]
        args += ["--url", s["url"]] if s["type"] == "browser" else ["--command", attach_command(name, s)]
        sid = ident(cmux(*args), "surface")
        if sid is None:
            raise RuntimeError("cmux returned no surface ID")
        return sid

    def leaf(node: Layout, pane: str, surface: str) -> None:
        pane_bindings[pane] = node["pane"].get("id", pane)
        for i, s in enumerate(node["pane"]["surfaces"]):
            sid = surface if i == 0 else add_surface(s, pane)
            bindings[sid] = s["id"]
            cmux(
                "rename-tab",
                "--workspace",
                ws,
                "--surface",
                sid,
                s.get("title", s["id"]),
            )

        selected = node["pane"].get("selected", 0)
        selected_id = next(sid for sid, label in bindings.items() if label == node["pane"]["surfaces"][selected]["id"])
        cmux("focus-panel", "--workspace", ws, "--panel", selected_id)

    def walk(node: Layout, pane: str, surface: str) -> None:
        if "pane" in node:
            return leaf(node, pane, surface)
        right_first = next(surfaces(node["children"][1]))
        direction = "right" if node["direction"] == "horizontal" else "down"
        cmux("focus-pane", "--workspace", ws, "--pane", pane)
        args = [
            "new-pane",
            "--type",
            right_first["type"],
            "--workspace",
            ws,
            "--direction",
            direction,
            "--focus",
            "false",
        ]
        args += (
            ["--url", right_first["url"]]
            if right_first["type"] == "browser"
            else ["--command", attach_command(name, right_first)]
        )
        result = cmux(*args)
        rp = ident(result, "pane")
        rs = ident(result, "surface")
        if not rp or not rs:
            raise RuntimeError("cmux did not return split identities")

        target = node.get("split", 0.5)
        if abs(target - 0.5) > 0.001:
            flag = "-R" if direction == "right" else "-D"
            calibration = cmux("resize-pane", "--workspace", ws, "--pane", pane, flag, "--amount", "1")
            old = calibration.get("old_divider_position")
            new = calibration.get("new_divider_position")
            if old is None or new is None:
                raise RuntimeError("cmux cannot report split sizing; workspace remains open for inspection")
            delta = new - old
            if abs(delta) < 1e-9:
                raise RuntimeError("cmux could not resize this split")
            amount = round((target - new) / delta)
            if amount:
                use = flag if amount > 0 else ("-L" if direction == "right" else "-U")
                cmux(
                    "resize-pane",
                    "--workspace",
                    ws,
                    "--pane",
                    pane,
                    use,
                    "--amount",
                    str(abs(amount)),
                )
        walk(node["children"][0], pane, surface)
        walk(node["children"][1], rp, rs)

    initial_surface = initial["surfaces"][0]["id"]
    replacement = add_surface(first, initial["id"])
    cmux("close-surface", "--workspace", ws, "--surface", initial_surface)
    initial_surface = replacement
    walk(doc["layout"], initial["id"], initial_surface)
    store(
        name,
        {
            "workspace": ws,
            "revision": doc["revision"],
            "bindings": bindings,
            "doc": doc,
        },
    )
    print("Opened", doc["name"])
    print("Share:", remote("link", name))
    return ws


def snapshot_workspace(name: str, state: Instance, current: JsonObject) -> Workspace:
    doc = copy.deepcopy(state["doc"])
    known = {s["id"]: s for s in surfaces(doc["layout"])}
    known.update(state.get("pending_surfaces", {}))
    panes = {p["id"]: p for p in current["panes"]}
    live = [s for p in current["panes"] for s in p["surfaces"] if s.get("title") != "VPS Workspaces · Link"]
    counts = Counter(state["bindings"].get(s["id"]) for s in live)
    resolved = {s["id"]: known[state["bindings"][s["id"]]] for s in live if state["bindings"].get(s["id"]) in known}
    refresh = [
        s
        for s in live
        if s["type"] == "terminal" and (s["id"] not in resolved or counts[state["bindings"].get(s["id"])] > 1)
    ]
    if refresh:
        from vps_workspaces.persistence import discover

        discovered = discover(name, current)
        for s in refresh:
            if s["id"] in discovered:
                resolved[s["id"]] = discovered[s["id"]]
            elif s["id"] in resolved:
                raise ValueError(
                    "Cannot identify terminals with duplicate bindings; waiting for live session discovery"
                )
    used: set[str] = set()

    def convert(n: JsonObject) -> Layout:
        if "pane" not in n:
            return {
                "direction": n["direction"],
                "split": n["split"],
                "children": [convert(c) for c in n["children"]],
            }
        p = panes[n["pane"]["id"]]
        items: list[Surface] = []
        selected = 0
        visible = [s for s in p["surfaces"] if s.get("title") != "VPS Workspaces · Link"]
        for i, s in enumerate(visible):
            if s["type"] not in ("terminal", "browser"):
                raise ValueError("Only terminal and browser panes can be saved")
            old = resolved.get(s["id"])
            if s["type"] == "terminal" and old is None:
                raise ValueError(
                    "Unmanaged terminal: use `workspace.py add-terminal "
                    + name
                    + " <name>` to create a persistent shared terminal first."
                )
            item: Surface = copy.copy(old) if old else {"id": "browser-" + s["id"].lower()[:8], "type": "browser"}
            if item["id"] in used:
                item["id"] = "view-" + uuid5(NAMESPACE_URL, state["workspace"] + "/" + s["id"]).hex
            used.add(item["id"])
            if s["type"] == "terminal":
                state.setdefault("pending_surfaces", {})[item["id"]] = copy.copy(item)
            item["title"] = s["title"]
            if s["type"] == "browser":
                item["url"] = s.get("url") or (old.get("url") if old else None) or "about:blank"
            items.append(item)
            state["bindings"][s["id"]] = item["id"]
            if s["id"] == p["selected_surface_id"]:
                selected = i
        return {"pane": {"surfaces": items, "selected": selected}}

    if not current.get("layout"):
        raise ValueError("cmux did not expose a complete split layout")
    doc["layout"] = convert(current["layout"])
    doc["name"] = current["title"]
    doc["revision"] = state["revision"]
    return doc


def save_state(name: str, state: Instance, current: JsonObject, keep_local: bool = False) -> Workspace:
    doc = snapshot_workspace(name, state, current)
    if keep_local:
        doc["revision"] = remote("get", name)["revision"]
    saved = remote("save", doc=doc)
    state["revision"] = saved["revision"]
    state["doc"] = saved
    state.pop("pending_surfaces", None)
    state.pop("autosave_error", None)
    store_instance(name, state)
    return saved


def save_workspace(name: str, keep_local: bool = False) -> None:
    with (STATE / "autosave.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((STATE / (name + ".json")).read_text())
        saved = save_state(name, state, tree(state["workspace"]), keep_local)
    print("Saved revision", saved["revision"])
    print("Share:", remote("link", name))


def add_terminal(name: str, label: str) -> None:
    checked_id(label)
    state = json.loads((STATE / (name + ".json")).read_text())
    doc = remote("get", name)
    if doc["revision"] != state["revision"]:
        raise ValueError("Open the latest workspace first")
    if any(s["id"] == label for s in surfaces(doc["layout"])):
        raise ValueError("That terminal already exists")
    s = remote("prepare-terminal", name, label, str(state["revision"]))
    result = cmux(
        "new-pane",
        "--type",
        "terminal",
        "--workspace",
        state["workspace"],
        "--direction",
        "right",
        "--command",
        attach_command(name, s),
    )
    surface_id = ident(result, "surface")
    if not surface_id:
        raise RuntimeError("cmux did not return the terminal identity; saved workspace was not changed")
    state["bindings"][surface_id] = label

    state.setdefault("pending_surfaces", {})[label] = s
    store(name, state)
    save_workspace(name)


def current_name() -> str:
    if sys.platform != "darwin":
        from vps_workspaces.remote import current_name as remote_name

        return remote_name()
    wid = os.environ.get("CMUX_WORKSPACE_ID")
    if not wid:
        raise ValueError("Run inside a managed cmux workspace, or supply its name")
    path = STATE / "instances" / (wid + ".json")
    if not path.exists():
        raise ValueError("This is a local workspace; create a shared one with the New VPS Workspace action")
    return checked_id(json.loads(path.read_text())["registry_name"])


def show_link(name: str | None, copy_link: bool = False, palette: bool = False) -> None:
    if palette:
        print("\033]0;VPS Workspaces · Link\007", end="", flush=True)
    name = checked_id(name) if name else current_name()
    if sys.platform == "darwin":
        url = remote("link", name)
    else:
        from vps_workspaces.registry import WorkspaceRegistry

        url = WorkspaceRegistry(pathlib.Path.home() / ".local/share/vps-workspaces").sharing_link(name)
    if copy_link:
        if sys.platform == "darwin":
            subprocess.run(["/usr/bin/pbcopy"], input=url, text=True, check=True)
        else:
            encoded = base64.b64encode(url.encode()).decode()
            print("\033]52;c;" + encoded + "\007", end="", flush=True)
    print(url, flush=True)
    if palette:
        time.sleep(1)
        wid, sid = os.environ.get("CMUX_WORKSPACE_ID"), os.environ.get("CMUX_SURFACE_ID")
        if wid and sid:
            cli = CLI if sys.platform == "darwin" else str(pathlib.Path.home() / ".cmux/bin/cmux")
            subprocess.run(
                [cli, "rpc", "surface.close", json.dumps({"workspace_id": wid, "surface_id": sid})],
                check=True,
            )


def main() -> None:

    p = argparse.ArgumentParser(
        description="Persistent cmux workspaces with HAPI and a browser IDE.",
        epilog="Administration: install {server,ide,hapi,backups,cmux,mac-access}; doctor --json; hapi; backup; diagnose; verify-native. See docs/MAINTENANCE.md.",
    )
    p.add_argument(
        "action",
        choices=[
            "open",
            "new",
            "save",
            "list",
            "link",
            "add-terminal",
            "check",
            "hapi-link",
            "keep-local",
            "autosave-status",
        ],
    )
    p.add_argument("name", nargs="?")
    p.add_argument("label", nargs="?")
    p.add_argument("--title")
    p.add_argument("--cwd", default="~/Coding")
    p.add_argument("--copy", action="store_true")
    p.add_argument("--palette", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--launcher", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    try:
        if a.action == "list":
            for d in remote("list"):
                print(d["id"], d["name"], "https://" + d["host"])
        elif a.action == "autosave-status":
            path = STATE / "autosave-status.json"
            print(path.read_text() if path.exists() else "Autosave has not started in cmux yet.")
        elif a.action == "keep-local":
            save_workspace(checked_id(a.name), keep_local=True)
        elif a.action == "hapi-link":
            print(remote("hapi-link"))
        elif a.action == "link":
            show_link(a.name, a.copy, a.palette)
        elif a.action == "new":
            name = checked_id(a.name or input("Workspace name (lowercase, hyphens): ").strip())
            remote("create", name, a.title or name.replace("-", " ").title(), a.cwd)
            open_workspace(name)
            if a.launcher and os.environ.get("CMUX_WORKSPACE_ID"):
                cmux("close-workspace", "--workspace", os.environ["CMUX_WORKSPACE_ID"])
        elif a.action == "open":
            cmux("ping")
            open_workspace(checked_id(a.name))
        elif a.action == "save":
            save_workspace(checked_id(a.name))
        elif a.action == "add-terminal":
            add_terminal(checked_id(a.name), checked_id(a.label))
        elif a.action == "check":
            state = json.loads((STATE / (a.name + ".json")).read_text())
            out = {"tree": tree(state["workspace"])}
            for sid, name in state["bindings"].items():
                try:
                    out[name] = cmux(
                        "read-screen",
                        "--workspace",
                        state["workspace"],
                        "--surface",
                        sid,
                        "--lines",
                        "15",
                    )
                except RuntimeError:
                    pass
            store(a.name + "-check", out)
            print("Checks saved in", STATE)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, subprocess.SubprocessError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
