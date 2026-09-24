#!/usr/bin/env python3
"""Refresh cmux's per-attachment routing for an already-running tmux agent."""

import json
import os
import pathlib
import sys

root = pathlib.Path.home() / ".local/share/vps-workspaces"
session = os.environ.get("VWS_SESSION", "")
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
