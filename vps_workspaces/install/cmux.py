from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from vps_workspaces.workspace import CLI


def main() -> None:
    if sys.platform != "darwin":
        raise ValueError("Install cmux actions on the Mac")
    root = Path(__file__).resolve().parents[2]
    script = root / "workspace.py"
    command = "python3 " + shlex.quote(str(script))
    copy_command = (
        'case "$(uname -s)" in Darwin) ' + command + " link --copy --palette ;; "
        '*) python3 "$HOME/.local/share/vps-workspaces/app/workspace.py" link --copy --palette ;; esac'
    )
    config = Path.home() / ".config/cmux/cmux.json"
    if config.exists():
        backup = config.with_name("cmux.json." + time.strftime("%Y%m%dT%H%M%S") + ".bak")
        shutil.copy2(config, backup)
    actions = {
        "vps-copy-link": {
            "type": "command",
            "title": "Copy Browser Workspace Link",
            "subtitle": "Copy this VPS workspace’s browser link",
            "command": copy_command,
            "target": "newTabInCurrentPane",
            "icon": {"type": "symbol", "name": "link"},
        },
        "vps-new-workspace": {
            "type": "workspace",
            "title": "New VPS Workspace",
            "workspace": {
                "name": "New VPS workspace",
                "cwd": str(Path.home()),
                "layout": {
                    "pane": {
                        "surfaces": [
                            {
                                "type": "terminal",
                                "command": command + " new --launcher",
                                "focus": True,
                            }
                        ]
                    }
                },
            },
            "icon": {"type": "symbol", "name": "network"},
        },
    }
    env = dict(os.environ, CMUX_CLI_BIN=CLI)
    editor = [sys.executable, str(root / "vendor/cmux-settings/cmux-settings")]
    for key, action in actions.items():
        subprocess.run([*editor, "set", "actions." + key, json.dumps(action)], env=env, check=True)
    subprocess.run([*editor, "validate"], env=env, check=True)
    print("Installed: Copy Browser Workspace Link; New VPS Workspace")
    result = subprocess.run([CLI, "reload-config"], check=False, capture_output=True, text=True)
    if result.returncode:
        print("Press Cmd+Shift+, inside cmux to reload its configuration.")
