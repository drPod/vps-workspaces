from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from urllib.parse import urlsplit

from vps_workspaces.contracts import Layout, Surface, Workspace

ID = re.compile(r"^[a-z][a-z0-9-]{0,47}$")


def checked_id(value: object) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("Use a lowercase name with letters, digits and hyphens (max 48).")
    return value


def surfaces(node: Layout) -> Iterator[Surface]:
    if "pane" in node:
        yield from node["pane"]["surfaces"]
    else:
        for child in node["children"]:
            yield from surfaces(child)


def validate(doc: Workspace) -> Workspace:
    if not isinstance(doc, dict):
        raise TypeError("Workspace must be an object")
    checked_id(doc.get("id"))
    if doc["id"] in ("access", "settings"):
        raise ValueError("That workspace name is reserved")
    if not isinstance(doc.get("name"), str) or not 1 <= len(doc["name"]) <= 200:
        raise ValueError("Invalid workspace name")
    seen = set()

    def walk(n: Layout, depth: int = 0) -> None:
        if not isinstance(n, dict):
            raise TypeError("Layout nodes must be objects")
        if depth > 16:
            raise ValueError("Layout too deep")
        if "pane" in n:
            pane = n["pane"]
            if not isinstance(pane, dict) or not isinstance(pane.get("surfaces"), list):
                raise ValueError("Pane surfaces must be a list")
            tabs = pane["surfaces"]
            if not tabs:
                raise ValueError("Empty pane")
            selected = pane.get("selected", 0)
            if type(selected) is not int or not 0 <= selected < len(tabs):
                raise ValueError("Selected tab is out of range")
            for s in tabs:
                if not isinstance(s, dict):
                    raise TypeError("Surface must be an object")
                checked_id(s.get("id"))
                if s["id"] in seen:
                    raise ValueError("Duplicate surface ID")
                seen.add(s["id"])
                if s["type"] == "terminal":
                    checked_id(s["session"])
                    if "codex_thread" in s:
                        from vps_workspaces.codex import checked_thread

                        checked_thread(s["codex_thread"])
                    if "hapi_session" in s:
                        from vps_workspaces.hapi_bridge import checked_session

                        checked_session(s["hapi_session"])
                elif s["type"] == "browser":
                    if s.get("url") == "about:blank":
                        continue
                    if not isinstance(s.get("url"), str) or any(c.isspace() for c in s["url"]):
                        raise ValueError("Browser URL must not contain whitespace")
                    u = urlsplit(s["url"])
                    _ = u.port
                    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
                        raise ValueError("Browser URL must be HTTP(S) without credentials")
                else:
                    raise ValueError("Only terminals and browsers can be shared")
        else:
            if (
                n.get("direction") not in ("horizontal", "vertical")
                or not isinstance(n.get("children"), list)
                or len(n["children"]) != 2
            ):
                raise ValueError("Invalid split")
            if not 0.1 <= float(n.get("split", 0.5)) <= 0.9:
                raise ValueError("Invalid split ratio")
            for c in n["children"]:
                walk(c, depth + 1)

    walk(doc["layout"])
    if len(seen) > 32:
        raise ValueError("Maximum 32 surfaces")
    return doc


def origin(url: str) -> str:
    u = urlsplit(url)
    return f"{u.scheme}://{u.netloc}"


def browser_host(doc: Workspace, s: Surface) -> str:
    return "b-" + hashlib.sha256(origin(s["url"]).encode()).hexdigest()[:10] + "." + doc["host"]


def local_browser(s: Surface) -> bool:
    return urlsplit(s["url"]).hostname in ("localhost", "127.0.0.1", "::1")
