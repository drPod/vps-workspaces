#!/usr/bin/env python3
"""Run on a Mac inside cmux. Explicit Save/Open for VPS-backed native workspaces."""

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
from model import checked_id, surfaces, validate

CLI = "/Applications/cmux.app/Contents/Resources/bin/cmux"
STATE = pathlib.Path.home() / ".local/state/vps-workspaces"
STATE.mkdir(parents=True, exist_ok=True)
REMOTE = ".local/share/vps-workspaces/app/remote.py"
SSH_HOST = os.environ.get("VWS_SSH_HOST", "myvps")


def cmux(*args):
    p = subprocess.run(
        [CLI, "--json", "--id-format", "uuids", *args], capture_output=True, text=True
    )
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    try:
        return json.loads(p.stdout)
    except ValueError:
        return p.stdout.strip()


def remote(action, *args, doc=None):
    p = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            SSH_HOST,
            shlex.join(["python3", REMOTE, action, *args]),
        ],
        input=json.dumps(doc) if doc is not None else None,
        capture_output=True,
        text=True,
    )
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return json.loads(p.stdout)


def tree(workspace):
    d = cmux("tree", "--all")
    for w in d["windows"]:
        for ws in w["workspaces"]:
            if ws["id"] == workspace:
                return ws
    raise ValueError("Workspace is no longer open")


def ident(value, kind):
    if isinstance(value, dict):
        if kind + "_id" in value:
            return value[kind + "_id"]
        for v in value.values():
            found = ident(v, kind)
            if found:
                return found
    return None


def attach_command(name, s):
    return "python3 ~/" + REMOTE + " " + shlex.join(["attach", name, s["id"]])


def store(name, value):
    p = STATE / (name + ".json")
    p.write_text(json.dumps(value, indent=2))
    p.chmod(0o600)


def open_workspace(name):
    doc = remote("get", name)
    validate(doc)
    remote("ensure", name)
    # A real cmux SSH workspace installs the normal relay and browser proxy.
    first = next(surfaces(doc["layout"]))
    if first["type"] != "terminal":
        raise ValueError(
            "The first pane must start with a terminal for native SSH bootstrap"
        )
    created = cmux(
        "ssh", SSH_HOST, "--name", doc["name"], "--command", attach_command(name, first)
    )
    ws = ident(created, "workspace")
    if not ws:
        raise RuntimeError("No workspace returned by cmux")
    time.sleep(1)
    initial = tree(ws)["panes"][0]
    bindings = {}
    pane_bindings = {}

    def add_surface(s, pane):
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
        args += (
            ["--url", s["url"]]
            if s["type"] == "browser"
            else ["--command", attach_command(name, s)]
        )
        return ident(cmux(*args), "surface")

    def leaf(node, pane, surface):
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

    def walk(node, pane, surface):
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
        # cmux's pane.resize reports exact old/new divider positions. Calibrate
        # its pixel step before nesting further splits, preserving the saved ratio.
        target = node.get("split", 0.5)
        if abs(target - 0.5) > 0.001:
            flag = "-R" if direction == "right" else "-D"
            calibration = cmux(
                "resize-pane", "--workspace", ws, "--pane", pane, flag, "--amount", "1"
            )
            old = calibration.get("old_divider_position")
            new = calibration.get("new_divider_position")
            if old is None or new is None:
                raise RuntimeError(
                    "cmux cannot report split sizing; workspace remains open for inspection"
                )
            delta = new - old
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

    walk(doc["layout"], initial["id"], initial["surfaces"][0]["id"])
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
    print("Share: https://" + doc["host"])
    return ws


def save_workspace(name):
    state = json.loads((STATE / (name + ".json")).read_text())
    doc = state["doc"]
    current = tree(state["workspace"])
    known = {s["id"]: s for s in surfaces(doc["layout"])}
    panes = {p["id"]: p for p in current["panes"]}

    def convert(n):
        if "pane" not in n:
            return {
                "direction": n["direction"],
                "split": n["split"],
                "children": [convert(c) for c in n["children"]],
            }
        p = panes[n["pane"]["id"]]
        items = []
        selected = 0
        for i, s in enumerate(p["surfaces"]):
            old = known.get(state["bindings"].get(s["id"]))
            if s["type"] == "terminal" and old is None:
                raise ValueError(
                    "Unmanaged terminal: use `workspace.py add-terminal "
                    + name
                    + " <name>` to create a persistent shared terminal first."
                )
            item = (
                dict(old)
                if old
                else {"id": "browser-" + s["id"].lower()[:8], "type": "browser"}
            )
            item["title"] = s["title"]
            if s["type"] == "browser":
                item["url"] = s["url"]
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
    saved = remote("save", doc=doc)
    state["revision"] = saved["revision"]
    state["doc"] = saved
    store(name, state)
    print("Saved revision", saved["revision"], "— https://" + saved["host"])


def add_terminal(name, label):
    checked_id(label)
    state = json.loads((STATE / (name + ".json")).read_text())
    doc = remote("get", name)
    if doc["revision"] != state["revision"]:
        raise ValueError("Open the latest workspace first")
    if any(s["id"] == label for s in surfaces(doc["layout"])):
        raise ValueError("That terminal already exists")
    session = checked_id((name + "-" + label)[:48])
    s = {
        "id": label,
        "type": "terminal",
        "title": label,
        "session": session,
        "cwd": "~/Coding",
    }
    doc["layout"] = {
        "direction": "horizontal",
        "split": 0.5,
        "children": [doc["layout"], {"pane": {"surfaces": [s]}}],
    }
    saved = remote("save", doc=doc)
    remote("ensure", name)
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
    state["bindings"][ident(result, "surface")] = label
    state["doc"] = saved
    state["revision"] = saved["revision"]
    store(name, state)
    save_workspace(name)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "action", choices=["open", "save", "list", "link", "add-terminal", "check"]
    )
    p.add_argument("name", nargs="?")
    p.add_argument("label", nargs="?")
    a = p.parse_args()
    try:
        if a.action == "list":
            for d in remote("list"):
                print(d["id"], d["name"], "https://" + d["host"])
        elif a.action == "link":
            print("https://" + remote("get", a.name)["host"])
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
    except Exception as e:
        sys.exit(str(e))
