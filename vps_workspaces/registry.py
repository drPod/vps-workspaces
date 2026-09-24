from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vps_workspaces.contracts import Access, Workspace
from vps_workspaces.model import checked_id, validate
from vps_workspaces.sharing import share_url
from vps_workspaces.storage import read_json


@dataclass(frozen=True)
class WorkspaceRegistry:
    root: Path

    def load(self, name: str) -> Workspace:
        doc = validate(read_json(self.root / (checked_id(name) + ".json")))
        if doc["id"] != name:
            raise ValueError("Workspace ID does not match its file name")
        return doc

    def documents(self) -> list[Workspace]:
        result: list[Workspace] = []
        for path in sorted(self.root.glob("*.json")):
            if path.stem in {"access", "settings"}:
                continue
            value = read_json(path)
            if isinstance(value, dict) and "layout" in value:
                result.append(self.load(path.stem))
        return result

    def sharing_link(self, name: str) -> str:
        access: Access = read_json(self.root / "access.json")
        return share_url(access, self.load(name))
