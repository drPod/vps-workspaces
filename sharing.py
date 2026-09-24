"""Stable per-workspace capability links, derived from the private installation key."""

import hashlib
import hmac


def share_key(access, workspace):
    return hmac.new(
        access["key"].encode(), ("share-link:" + workspace).encode(), hashlib.sha256
    ).hexdigest()


def share_url(access, doc):
    return "https://" + doc["host"] + "/#key=" + share_key(access, doc["id"])
