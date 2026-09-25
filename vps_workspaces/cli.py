from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

COMMANDS = {
    "persistence": "persistence",
    "doctor": "doctor",
    "serve": "server",
    "autosave": "autosave",
    "backup": "backup",
    "codex": "codex",
    "hapi": "hapi",
    "relay": "relay",
    "diagnose": "diagnostics",
    "verify-native": "verify",
}
INSTALLERS = {
    "resources": "resources",
    "server": "server",
    "ide": "ide",
    "codex": "codex",
    "hapi": "hapi",
    "backups": "backups",
    "mac-access": "mac_access",
    "cmux": "cmux",
}


def environment() -> None:
    if sys.platform == "linux" and sys.prefix == sys.base_prefix:
        root = Path(__file__).resolve().parents[1]
        for directory in (root / ".venv", root.parent / "venv"):
            python = directory / "bin/python"
            if python.exists():
                os.execv(str(python), [str(python), *sys.argv])


def main() -> None:
    environment()
    args = sys.argv[1:]
    try:
        if args and args[0] == "install":
            if len(args) < 2 or args[1] not in INSTALLERS:
                raise ValueError("Choose an installer: " + ", ".join(INSTALLERS))
            module = "install." + INSTALLERS[args[1]]
            sys.argv = [sys.argv[0], *args[2:]]
        elif args and args[0] in COMMANDS:
            module = COMMANDS[args[0]]
            sys.argv = [sys.argv[0], *args[1:]]
        else:
            module = "workspace"
        importlib.import_module("vps_workspaces." + module).main()
    except (ValueError, RuntimeError, OSError) as error:
        sys.exit(str(error))
