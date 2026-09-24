#!/usr/bin/env python3
"""Authenticated layout adapter. ttyd supplies the complete terminal client/PTY protocol."""

import asyncio
import hashlib
import hmac
import html
import json
import os
import pathlib
import time
from urllib.parse import urlsplit, urlunsplit
from aiohttp import (
    web,
    ClientSession,
    ClientTimeout,
    UnixConnector,
    WSMsgType,
    DummyCookieJar,
)
from model import surfaces, origin, browser_host, local_browser

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


def login_page(doc, error=""):
    return web.Response(
        text="""<!doctype html><meta name="viewport" content="width=device-width"><title>Open workspace</title><style>body{font:16px system-ui;background:#10151d;color:#e9edf4;display:grid;place-items:center;height:90vh}form{width:320px}input,button{box-sizing:border-box;width:100%;padding:12px;margin:8px 0;border-radius:7px;border:1px solid #566}button{background:#b9e3bc;cursor:pointer}p{color:#c9a}</style><form method="post" action="/login"><h1>"""
        + html.escape(doc["name"])
        + '</h1><label>Workspace password<input type="password" name="password" autocomplete="current-password" required></label><button>Open workspace</button><p>'
        + html.escape(error)
        + "</p></form>",
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def startup(app):
    app["http"] = ClientSession(
        auto_decompress=False,
        cookie_jar=DummyCookieJar(),
        timeout=ClientTimeout(total=None, sock_connect=10),
    )
    app["ttyd"] = {}
    app["attempts"] = {}
    app["terminal_lock"] = asyncio.Lock()


async def cleanup(app):
    for p, client in app["ttyd"].values():
        if p.returncode is None:
            p.terminate()
        await p.wait()
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


async def proxy(req, client, target, doc, terminal_view=False):
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
    if req.headers.get("Origin"):
        headers["Origin"] = origin(target)
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
                value = "https://" + req.host + value[len(origin(target)) :]
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
    if req.path == "/login" and browser is None:
        if req.method == "POST":
            if req.headers.get("Origin") != "https://" + doc["host"]:
                raise web.HTTPForbidden()
            key = req.headers.get("X-Forwarded-For", "unknown").split(",")[0]
            now = time.time()
            attempts = req.app["attempts"]
            history = [x for x in attempts.get(key, []) if x > now - 60]
            if len(history) >= 10:
                raise web.HTTPTooManyRequests(text="Try again in a minute")
            history.append(now)
            attempts[key] = history
            if len(attempts) > 10000:
                attempts.clear()
            data = await req.post()
            given = str(data.get("password", ""))
            digest = await asyncio.to_thread(
                hashlib.scrypt,
                given.encode(),
                salt=bytes.fromhex(access["salt"]),
                n=16384,
                r=8,
                p=1,
            )
            if hmac.compare_digest(digest.hex(), access["password_hash"]):
                r = web.HTTPFound("/")
                r.set_cookie(
                    COOKIE,
                    token(access["key"], doc["id"], int(time.time()) + 86400),
                    domain=doc["host"],
                    secure=True,
                    httponly=True,
                    samesite="Lax",
                    max_age=86400,
                )
                return r
            return login_page(doc, "Incorrect password")
        return login_page(doc)
    if not authorized(req, access, doc):
        if req.headers.get("Upgrade"):
            raise web.HTTPUnauthorized()
        raise web.HTTPFound("https://" + doc["host"] + "/login")
    if browser:
        return await proxy(
            req, req.app["http"], origin(browser["url"]) + req.rel_url.raw_path_qs, doc
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
    if req.path == "/workspace.json":
        public = json.loads(json.dumps(doc))
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
