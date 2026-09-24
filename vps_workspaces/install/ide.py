from __future__ import annotations

import sys
from pathlib import Path

from vps_workspaces.ide import ensure_ide
from vps_workspaces.registry import WorkspaceRegistry


def main() -> None:
    root = Path.home() / ".local/share/vps-workspaces"
    doc = WorkspaceRegistry(root).load(sys.argv[1])
    ensure_ide(root, doc)
    print("IDE enabled:", doc["id"])


if __name__ == "__main__":
    main()
