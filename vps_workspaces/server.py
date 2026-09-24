from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import pathlib
import time
from urllib.parse import urlencode, urlsplit, urlunsplit

from aiohttp import web

from vps_workspaces.contracts import Access, Surface, Workspace
from vps_workspaces.model import browser_host, local_browser, surfaces
from vps_workspaces.registry import WorkspaceRegistry
from vps_workspaces.sharing import share_key, share_url

ROOT = pathlib.Path.home() / ".local/share/vps-workspaces"
STATIC = pathlib.Path(__file__).parent / "static"
COOKIE = "vws_access"


def resolve(host: str) -> tuple[Workspace, Surface | None]:
    for d in WorkspaceRegistry(ROOT).documents():
        if d["host"] == host:
            return d, None
        for s in surfaces(d["layout"]):
            if s["type"] == "browser" and local_browser(s) and browser_host(d, s) == host:
                return d, s
    raise web.HTTPNotFound()


def token(key: str, name: str, expires: int) -> str:
    body = f"{name}:{expires}"
    return body + ":" + hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()


def authorized(req: web.Request, access: Access, doc: Workspace) -> bool:
    raw = req.cookies.get(COOKIE, "")
    try:
        name, expiry, _ = raw.split(":")
        return (
            name == doc["id"]
            and int(expiry) > time.time()
            and hmac.compare_digest(raw, token(access["key"], name, int(expiry)))
        )
    except (ValueError, TypeError):
        return False


def entry_page() -> web.FileResponse:
    return web.FileResponse(
        STATIC / "entry.html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
        },
    )


async def handle(req: web.Request) -> web.StreamResponse:
    doc, browser = resolve(req.host.lower())
    access = json.loads((ROOT / "access.json").read_text())
    if req.path == "/join" and browser is None:
        if req.method != "POST":
            raise web.HTTPMethodNotAllowed(req.method, ["POST"])
        if req.headers.get("Origin") != "https://" + doc["host"]:
            raise web.HTTPForbidden()
        try:
            data = await req.json()
        except (ValueError, UnicodeDecodeError):
            raise web.HTTPBadRequest(text="Expected a JSON sharing key.") from None
        supplied = data.get("key") if isinstance(data, dict) else None
        if not isinstance(supplied, str) or not hmac.compare_digest(
            supplied.encode(), share_key(access, doc["id"]).encode()
        ):
            raise web.HTTPUnauthorized(text="This sharing link is not valid.")
        response = web.json_response(
            {
                "ok": True,
                "next": "/ide/",
            },
            headers={"Cache-Control": "no-store"},
        )
        response.set_cookie(
            COOKIE,
            token(access["key"], doc["id"], int(time.time()) + 86400),
            domain=doc["host"],
            secure=True,
            httponly=True,
            samesite="Lax",
            max_age=86400,
        )
        return response
    if browser is None and req.path in ("/entry.js", "/style.css"):
        return web.FileResponse(STATIC / req.path[1:], headers={"Cache-Control": "no-store"})
    if not authorized(req, access, doc):
        if browser is None and req.path in ("/", "/login") and req.method == "GET":
            return entry_page()
        raise web.HTTPUnauthorized(text="Open the original workspace sharing link to join.")
    if browser is None and req.path == "/login":
        raise web.HTTPFound("/")
    if req.path == "/auth":
        if (
            req.headers.get("X-VWS-Upgrade", "").lower() == "websocket"
            and req.headers.get("Origin") != "https://" + req.host
        ):
            raise web.HTTPForbidden(text="Origin mismatch")
        if browser is None:
            ide_path = ROOT / (doc["id"] + ".ide")
            if not ide_path.exists():
                raise web.HTTPNotFound(text="IDE is not installed for this workspace")
            original = req.headers.get("X-Forwarded-Uri", "")
            if original in ("/ide", "/ide/"):
                config = json.loads(ide_path.read_text())
                raise web.HTTPFound("/ide/?" + urlencode({"workspace": config["workspace"]}))
        return web.Response(status=204)
    if browser:
        raise web.HTTPNotFound()
    ide_path = ROOT / (doc["id"] + ".ide")
    if req.path == "/share-link":
        return web.json_response({"url": share_url(access, doc)}, headers={"Cache-Control": "no-store"})
    if req.path == "/" and ide_path.exists():
        return entry_page()
    if req.path == "/workspace.json":
        public = json.loads(json.dumps(doc))
        if ide_path.exists():
            public["ide_url"] = "/ide/"
        for s in surfaces(public["layout"]):
            if s["type"] == "browser" and local_browser(s):
                u = urlsplit(s["url"])
                s["web_url"] = urlunsplit(("https", browser_host(doc, s), u.path, u.query, u.fragment))
            elif s["type"] == "browser":
                s["web_url"] = s["url"]
        return web.json_response(public, headers={"Cache-Control": "no-store"})
    files = {
        "/": "entry.html",
        "/style.css": "style.css",
    }
    if req.path not in files:
        raise web.HTTPNotFound()
    return web.FileResponse(
        STATIC / files[req.path],
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src https: 'self'; frame-ancestors 'none'; base-uri 'none'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def make_app() -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)
    app.router.add_route("*", "/{path:.*}", handle)
    return app


def main() -> None:
    os.umask(0o077)

    async def serve() -> None:
        runner = web.AppRunner(make_app(), access_log=None)
        await runner.setup()
        sock = pathlib.Path.home() / "deploy/www/vps-workspaces.sock"
        sock.unlink(missing_ok=True)
        await web.UnixSite(runner, str(sock)).start()
        sock.chmod(0o600)
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    asyncio.run(serve())


if __name__ == "__main__":
    main()
