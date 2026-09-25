from __future__ import annotations

import importlib
import sys

COMMANDS = {
    "persistence": "persistence",
    "doctor": "doctor",
    "serve": "server",
    "autosave": "autosave",
    "backup": "backup",
    "hapi": "hapi",
    "relay": "relay",
    "diagnose": "diagnostics",
    "verify-native": "verify",
}
INSTALLERS = {
    "resources": "resources",
    "server": "server",
    "ide": "ide",
    "hapi": "hapi",
    "backups": "backups",
    "mac-access": "mac_access",
    "cmux": "cmux",
}


def main() -> None:
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
