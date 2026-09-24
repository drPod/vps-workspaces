#!/usr/bin/env python3
"""Save and reconstruct a second native client; records private verification evidence."""

import json
import sys
from workspace import save_workspace, open_workspace, tree, store, STATE
from model import surfaces

name = sys.argv[1] if len(sys.argv) > 1 else "outreach"
save_workspace(name)
expected = json.loads((STATE / (name + ".json")).read_text())["doc"]
ws = open_workspace(name)
actual = tree(ws)


def shape(n):
    if "pane" in n:
        return "pane"
    return [n["direction"], round(n["split"], 2), *[shape(c) for c in n["children"]]]


assert shape(actual["layout"]) == shape(expected["layout"]), "Split layout differs"
urls = [
    s["url"] for p in actual["panes"] for s in p["surfaces"] if s["type"] == "browser"
]
assert sorted(urls) == sorted(
    s["url"] for s in surfaces(expected["layout"]) if s["type"] == "browser"
)
store(
    name + "-verification",
    {
        "passed": True,
        "workspace": ws,
        "revision": expected["revision"],
        "layout": shape(actual["layout"]),
        "browser_count": len(urls),
    },
)
print("PASS: saved layout and URLs restored into a second native cmux workspace.")
