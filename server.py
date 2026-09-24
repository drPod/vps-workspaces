#!/usr/bin/env python3
"""Authenticated layout adapter. ttyd supplies the complete terminal client/PTY protocol."""

import asyncio
import hashlib
import hmac
import json
import os
import pathlib
import time
from urllib.parse import urlsplit, urlunsplit, urlencode
from aiohttp import (
    web,
    ClientSession,
    ClientTimeout,
    UnixConnector,
    WSMsgType,
    DummyCookieJar,
)
from model import surfaces, origin, browser_host, local_browser
from sharing import share_key, share_url

ROOT = pathlib.Path.home() / ".local/share/vps-workspaces"
STATIC = pathlib.Path(__file__).parent / "static"
COOKIE = "vws_access"
HOP = {
    "connection",
    "upgrade",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "content-length",
    "host",
    "authorization",
}


def resolve(host):
    for p in ROOT.glob("*.json"):
        if p.name in ("access.json", "settings.json"):
            continue
        d = json.loads(p.read_text())
        if "layout" not in d:
            continue
        if d["host"] == host:
            return d, None
        for s in surfaces(d["layout"]):
            if (
                s["type"] == "browser"
                and local_browser(s)
                and browser_host(d, s) == host
            ):
                return d, s
    raise web.HTTPNotFound()


def token(key, name, expires):
    body = f"{name}:{expires}"
    return (
        body + ":" + hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    )


def authorized(req, access, doc):
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


def entry_page():
    return web.FileResponse(
        STATIC / "entry.html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
        },
    )


async def startup(app):
    app["http"] = ClientSession(
        auto_decompress=False,
        cookie_jar=DummyCookieJar(),
        timeout=ClientTimeout(total=None, sock_connect=10),
    )
    app["ttyd"] = {}
    app["ide_clients"] = {}
    app["terminal_lock"] = asyncio.Lock()


async def cleanup(app):
    for p, client in app["ttyd"].values():
        if p.returncode is None:
            p.terminate()
        await p.wait()
        await client.close()
    for client in app["ide_clients"].values():
        await client.close()
    await app["http"].close()


async def terminal(app, session):
    async with app["terminal_lock"]:
        entry = app["ttyd"].get(session)
        if entry and entry[0].returncode is None:
            return entry[1]
        if entry:
            await entry[1].close()
        socket = ROOT / (session + ".sock")
        socket.unlink(missing_ok=True)
        p = await asyncio.create_subprocess_exec(
            "/usr/bin/ttyd",
            "-i",
            str(socket),
            "-W",
            "-t",
            "fontSize=14",
            "-t",
            "disableLeaveAlert=true",
            "/usr/bin/tmux",
            "-L",
            "vps-workspaces",
            "-u",
            "attach-session",
            "-t",
            "=" + session,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(100):
            if socket.exists():
                break
            if p.returncode is not None:
                raise web.HTTPBadGateway(text="Terminal service failed to start")
            await asyncio.sleep(0.03)
        else:
            p.terminate()
            await p.wait()
            raise web.HTTPBadGateway(text="Terminal service timeout")
        client = ClientSession(
            connector=UnixConnector(path=str(socket)),
            cookie_jar=DummyCookieJar(),
            auto_decompress=False,
            timeout=ClientTimeout(total=None, sock_connect=10),
        )
        app["ttyd"][session] = (p, client)
        return client


async def proxy(req, client, target, doc, terminal_view=False, prefix=""):
    headers = {
        k: v
        for k, v in req.headers.items()
        if k.lower() not in HOP
        and k.lower()
        not in (
            "cookie",
            "origin",
            "referer",
            "x-forwarded-for",
            "x-forwarded-host",
            "x-forwarded-proto",
        )
    }
    # Keep app cookies, but never pass the workspace access credential upstream.
    cookies = {k: v for k, v in req.cookies.items() if k != COOKIE}
    if prefix:
        headers["X-Forwarded-Host"] = req.host
        headers["X-Forwarded-Proto"] = "https"
    if req.headers.get("Origin"):
        headers["Origin"] = req.headers["Origin"] if prefix else origin(target)
    if req.headers.get("Upgrade", "").lower() == "websocket":
        if req.headers.get("Origin") != "https://" + req.host:
            raise web.HTTPForbidden(text="Origin mismatch")
        protocols = [
            s.strip()
            for s in req.headers.get("Sec-WebSocket-Protocol", "").split(",")
            if s.strip()
        ]
        for k in list(headers):
            if k.lower().startswith("sec-websocket-"):
                headers.pop(k)
        async with client.ws_connect(
            target,
            headers=headers,
            protocols=protocols,
            autoping=True,
            max_msg_size=16 * 1024 * 1024,
        ) as upstream:
            ws = web.WebSocketResponse(
                protocols=[upstream.protocol] if upstream.protocol else [],
                max_msg_size=16 * 1024 * 1024,
            )
            await ws.prepare(req)

            async def pump(src, dst):
                async for msg in src:
                    if msg.type == WSMsgType.TEXT:
                        await dst.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await dst.send_bytes(msg.data)
                    elif msg.type in (
                        WSMsgType.CLOSE,
                        WSMsgType.CLOSED,
                        WSMsgType.ERROR,
                    ):
                        break

            tasks = [
                asyncio.create_task(pump(ws, upstream)),
                asyncio.create_task(pump(upstream, ws)),
            ]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await ws.close()
            return ws
    async with client.request(
        req.method,
        target,
        headers=headers,
        cookies=cookies,
        data=req.content.iter_chunked(65536) if req.can_read_body else None,
        allow_redirects=False,
    ) as upstream:
        result = web.StreamResponse(status=upstream.status)
        for key, value in upstream.headers.items():
            if key.lower() in HOP or key.lower() == "set-cookie":
                continue
            if key.lower() == "location" and value.startswith(origin(target) + "/"):
                value = "https://" + req.host + prefix + value[len(origin(target)) :]
            elif (
                key.lower() == "location"
                and prefix
                and value.startswith("/")
                and not value.startswith("//")
            ):
                value = prefix + value
            result.headers.add(key, value)
        # Preserve host-only app cookies on the dedicated app subdomain.
        for value in upstream.headers.getall("Set-Cookie", []):
            if not value.lower().startswith(COOKIE + "="):
                result.headers.add("Set-Cookie", value)
        result.headers["Cache-Control"] = "no-store"
        if terminal_view:
            result.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        await result.prepare(req)
        async for block in upstream.content.iter_chunked(65536):
            await result.write(block)
        return result


async def handle(req):
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
            raise web.HTTPBadRequest(text="Expected a JSON sharing key.")
        supplied = data.get("key") if isinstance(data, dict) else None
        if not isinstance(supplied, str) or not hmac.compare_digest(
            supplied.encode(), share_key(access, doc["id"]).encode()
        ):
            raise web.HTTPUnauthorized(text="This sharing link is not valid.")
        response = web.json_response(
            {
                "ok": True,
                "next": "/ide/" if (ROOT / (doc["id"] + ".ide")).exists() else "/",
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
        return web.FileResponse(
            STATIC / req.path[1:], headers={"Cache-Control": "no-store"}
        )
    if not authorized(req, access, doc):
        if browser is None and req.path in ("/", "/login") and req.method == "GET":
            return entry_page()
        raise web.HTTPUnauthorized(
            text="Open the original workspace sharing link to join."
        )
    if browser is None and req.path == "/login":
        raise web.HTTPFound("/")
    if browser:
        return await proxy(
            req, req.app["http"], origin(browser["url"]) + req.rel_url.raw_path_qs, doc
        )
    ide_path = ROOT / (doc["id"] + ".ide")
    if req.path == "/ide":
        raise web.HTTPFound("/ide/")
    if req.path.startswith("/ide/"):
        if not ide_path.exists():
            raise web.HTTPNotFound(text="IDE is not installed for this workspace")
        config = json.loads(ide_path.read_text())
        if req.path == "/ide/" and not req.query_string:
            raise web.HTTPFound(
                "/ide/?" + urlencode({"workspace": config["workspace"]})
            )
        if doc["id"] not in req.app["ide_clients"]:
            req.app["ide_clients"][doc["id"]] = ClientSession(
                connector=UnixConnector(path=config["socket"]),
                cookie_jar=DummyCookieJar(),
                auto_decompress=False,
                timeout=ClientTimeout(total=None, sock_connect=10),
            )
        target = "http://localhost/" + req.rel_url.raw_path_qs[len("/ide/") :]
        return await proxy(
            req, req.app["ide_clients"][doc["id"]], target, doc, prefix="/ide"
        )
    if req.path.startswith("/terminal/"):
        parts = req.path.split("/", 3)
        if len(parts) < 4:
            raise web.HTTPNotFound()
        s = next(
            (
                s
                for s in surfaces(doc["layout"])
                if s["id"] == parts[2] and s["type"] == "terminal"
            ),
            None,
        )
        if s is None:
            raise web.HTTPNotFound()
        client = await terminal(req.app, s["session"])
        suffix = "/" + parts[3] + ("?" + req.query_string if req.query_string else "")
        return await proxy(req, client, "http://localhost" + suffix, doc, True)
    if req.path == "/share-link":
        return web.json_response(
            {"url": share_url(access, doc)}, headers={"Cache-Control": "no-store"}
        )
    if req.path == "/" and ide_path.exists():
        return entry_page()
    if req.path == "/workspace.json":
        public = json.loads(json.dumps(doc))
        if ide_path.exists():
            public["ide_url"] = "/ide/"
        for s in surfaces(public["layout"]):
            if s["type"] == "terminal":
                s["web_url"] = "/terminal/" + s["id"] + "/"
            elif local_browser(s):
                u = urlsplit(s["url"])
                s["web_url"] = urlunsplit(
                    ("https", browser_host(doc, s), u.path, u.query, u.fragment)
                )
            else:
                s["web_url"] = s["url"]
        return web.json_response(public, headers={"Cache-Control": "no-store"})
    files = {
        "/": "index.html",
        "/classic/": "index.html",
        "/app.js": "app.js",
        "/style.css": "style.css",
        "/split.min.js": "split.min.js",
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


def make_app():
    app = web.Application(client_max_size=1024 * 1024)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    app.router.add_route("*", "/{path:.*}", handle)
    return app


if __name__ == "__main__":
    os.umask(0o077)

    async def main():
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

    asyncio.run(main())
