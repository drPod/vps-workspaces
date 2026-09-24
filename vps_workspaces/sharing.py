from __future__ import annotations

import hashlib
import hmac

from vps_workspaces.contracts import Access, Workspace


def share_key(access: Access, workspace: str) -> str:
    return hmac.new(access["key"].encode(), ("share-link:" + workspace).encode(), hashlib.sha256).hexdigest()


def share_url(access: Access, doc: Workspace) -> str:
    return "https://" + doc["host"] + "/#key=" + share_key(access, doc["id"])
