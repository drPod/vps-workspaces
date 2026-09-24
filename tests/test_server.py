import hashlib
import json
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch
from aiohttp.test_utils import TestClient, TestServer
import server
from model import validate


class AccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.doc = {
            "id": "demo",
            "name": "Demo",
            "host": "demo.example.test",
            "layout": {
                "pane": {
                    "surfaces": [
                        {"id": "shell", "type": "terminal", "session": "demo-shell"}
                    ]
                }
            },
        }
        (self.root / "demo.json").write_text(json.dumps(self.doc))
        self.access = {
            "key": "test-only-secret",
            "salt": "00" * 16,
            "password_hash": hashlib.scrypt(
                b"correct", salt=bytes(16), n=16384, r=8, p=1
            ).hex(),
        }
        (self.root / "access.json").write_text(json.dumps(self.access))
        self.patch = patch.object(server, "ROOT", self.root)
        self.patch.start()
        self.client = TestClient(TestServer(server.make_app()))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.patch.stop()
        self.tmp.cleanup()

    def headers(self, name="demo", expiry=None):
        value = server.token(self.access["key"], name, expiry or int(time.time()) + 60)
        return {"Host": "demo.example.test", "Cookie": server.COOKIE + "=" + value}

    async def test_terminal_requires_auth_before_starting_ttyd(self):
        for path in ("/", "/workspace.json", "/terminal/shell/", "/terminal/shell/ws"):
            r = await self.client.get(
                path, headers={"Host": "demo.example.test"}, allow_redirects=False
            )
            self.assertEqual(r.status, 302)
        self.assertEqual(self.client.app["ttyd"], {})

    async def test_valid_cookie_can_read_only_its_workspace(self):
        r = await self.client.get("/workspace.json", headers=self.headers())
        self.assertEqual(r.status, 200)
        self.assertEqual(
            (await r.json())["layout"]["pane"]["surfaces"][0]["web_url"],
            "/terminal/shell/",
        )
        for h in (
            self.headers("other"),
            self.headers(expiry=int(time.time()) - 1),
            {"Host": "demo.example.test", "Cookie": "vws_access=demo:9999999999:fake"},
        ):
            r = await self.client.get(
                "/workspace.json", headers=h, allow_redirects=False
            )
            self.assertEqual(r.status, 302)

    async def test_login_requires_same_origin_and_sets_secure_cookie(self):
        r = await self.client.post(
            "/login",
            headers={"Host": "demo.example.test", "Origin": "https://evil.test"},
            data={"password": "correct"},
        )
        self.assertEqual(r.status, 403)
        r = await self.client.post(
            "/login",
            headers={
                "Host": "demo.example.test",
                "Origin": "https://demo.example.test",
            },
            data={"password": "correct"},
            allow_redirects=False,
        )
        self.assertEqual(r.status, 302)
        cookie = r.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("Domain=demo.example.test", cookie)

    async def test_unknown_host_and_terminal_are_not_proxied(self):
        r = await self.client.get("/", headers={"Host": "evil.test"})
        self.assertEqual(r.status, 404)
        r = await self.client.get("/terminal/other/", headers=self.headers())
        self.assertEqual(r.status, 404)

    async def test_cross_origin_websocket_is_rejected(self):
        # Validate before reaching ttyd; a fake client proves no upstream request.
        class NoUpstream:
            def ws_connect(self, *a, **kw):
                raise AssertionError("Must reject before upstream connection")

        from aiohttp.test_utils import make_mocked_request

        req = make_mocked_request(
            "GET",
            "/ws",
            headers={
                "Host": "demo.example.test",
                "Upgrade": "websocket",
                "Origin": "https://evil.test",
            },
        )
        with self.assertRaises(server.web.HTTPForbidden):
            await server.proxy(req, NoUpstream(), "http://localhost/ws", self.doc, True)


class ValidationTests(unittest.TestCase):
    def test_rejects_command_injection_ids_and_unsafe_urls(self):
        for session in ("foo;id", "../escape", "-option", "x\ncommand"):
            with self.assertRaises(ValueError):
                validate(
                    {
                        "id": "demo",
                        "name": "Demo",
                        "layout": {
                            "pane": {
                                "surfaces": [
                                    {
                                        "id": "term",
                                        "type": "terminal",
                                        "session": session,
                                    }
                                ]
                            }
                        },
                    }
                )
        for url in (
            "file:///etc/passwd",
            "javascript:alert(1)",
            "https://user:password@example.test",
        ):
            with self.assertRaises(ValueError):
                validate(
                    {
                        "id": "demo",
                        "name": "Demo",
                        "layout": {
                            "pane": {
                                "surfaces": [
                                    {"id": "browser", "type": "browser", "url": url}
                                ]
                            }
                        },
                    }
                )


if __name__ == "__main__":
    unittest.main()
