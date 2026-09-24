"""Portable cmux split trees. No credentials or machine-local IDs in saved definitions."""

import hashlib
import re
from urllib.parse import urlsplit

ID = re.compile(r"^[a-z][a-z0-9-]{0,47}$")


def checked_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(
            "Use a lowercase name with letters, digits and hyphens (max 48)."
        )
    return value


def surfaces(node):
    if "pane" in node:
        yield from node["pane"]["surfaces"]
    else:
        for child in node["children"]:
            yield from surfaces(child)


def validate(doc):
    checked_id(doc["id"])
    if not isinstance(doc.get("name"), str) or len(doc["name"]) > 200:
        raise ValueError("Invalid workspace name")
    seen = set()

    def walk(n, depth=0):
        if depth > 16:
            raise ValueError("Layout too deep")
        if "pane" in n:
            tabs = n["pane"]["surfaces"]
            if not tabs:
                raise ValueError("Empty pane")
            for s in tabs:
                checked_id(s["id"])
                if s["id"] in seen:
                    raise ValueError("Duplicate surface ID")
                seen.add(s["id"])
                if s["type"] == "terminal":
                    checked_id(s["session"])
                elif s["type"] == "browser":
                    u = urlsplit(s["url"])
                    if (
                        u.scheme not in ("http", "https")
                        or not u.hostname
                        or u.username
                        or u.password
                    ):
                        raise ValueError(
                            "Browser URL must be HTTP(S) without credentials"
                        )
                else:
                    raise ValueError("Only terminals and browsers can be shared")
        else:
            if (
                n["direction"] not in ("horizontal", "vertical")
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


def origin(url):
    u = urlsplit(url)
    return f"{u.scheme}://{u.netloc}"


def browser_host(doc, s):
    return (
        "b-"
        + hashlib.sha256(origin(s["url"]).encode()).hexdigest()[:10]
        + "."
        + doc["host"]
    )


def local_browser(s):
    return urlsplit(s["url"]).hostname in ("localhost", "127.0.0.1", "::1")
