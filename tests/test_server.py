import json
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch
from aiohttp.test_utils import TestClient, TestServer
import server
from model import validate
from sharing import share_key


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
        self.access = {"key": "test-only-secret"}
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

    async def test_protected_routes_require_auth(self):
        for path in (
            "/workspace.json",
            "/terminal/shell/",
            "/terminal/shell/ws",
            "/share-link",
            "/ide/",
            "/ide/stable-example",
        ):
            r = await self.client.get(
                path, headers={"Host": "demo.example.test"}, allow_redirects=False
            )
            self.assertEqual(r.status, 401)

    async def test_valid_cookie_can_read_only_its_workspace(self):
        r = await self.client.get("/workspace.json", headers=self.headers())
        self.assertEqual(r.status, 200)
        self.assertEqual((await r.json())["id"], "demo")
        for h in (
            self.headers("other"),
            self.headers(expiry=int(time.time()) - 1),
            {"Host": "demo.example.test", "Cookie": "vws_access=demo:9999999999:fake"},
        ):
            r = await self.client.get(
                "/workspace.json", headers=h, allow_redirects=False
            )
            self.assertEqual(r.status, 401)

    async def test_link_join_requires_same_origin_and_sets_secure_cookie(self):
        key = share_key(self.access, "demo")
        r = await self.client.post(
            "/join",
            headers={"Host": "demo.example.test", "Origin": "https://evil.test"},
            json={"key": key},
        )
        self.assertEqual(r.status, 403)
        r = await self.client.post(
            "/join",
            headers={
                "Host": "demo.example.test",
                "Origin": "https://demo.example.test",
            },
            json={"key": key},
        )
        self.assertEqual(r.status, 200)
        cookie = r.headers["Set-Cookie"]
        for attribute in ("HttpOnly", "Secure", "Domain=demo.example.test"):
            self.assertIn(attribute, cookie)

    async def test_wrong_or_other_workspace_link_cannot_join(self):
        for key in ("incorrect", share_key(self.access, "other"), "非ASCII", None):
            r = await self.client.post(
                "/join",
                headers={
                    "Host": "demo.example.test",
                    "Origin": "https://demo.example.test",
                },
                json={"key": key},
            )
            self.assertEqual(r.status, 401)

    async def test_entry_has_no_password_form_and_link_is_retrievable_after_join(self):
        r = await self.client.get("/", headers={"Host": "demo.example.test"})
        self.assertEqual(r.status, 200)
        self.assertNotIn('type="password"', await r.text())
        r = await self.client.get("/share-link", headers=self.headers())
        self.assertEqual(
            (await r.json())["url"],
            "https://demo.example.test/#key=" + share_key(self.access, "demo"),
        )

    async def test_unknown_host_and_terminal_are_not_proxied(self):
        r = await self.client.get("/", headers={"Host": "evil.test"})
        self.assertEqual(r.status, 404)
        r = await self.client.get("/terminal/other/", headers=self.headers())
        self.assertEqual(r.status, 404)

    async def test_ide_routes_require_installation_and_open_configured_workspace(self):
        r = await self.client.get(
            "/auth", headers=dict(self.headers(), **{"X-Forwarded-Uri": "/ide/"}), allow_redirects=False
        )
        self.assertEqual(r.status, 404)
        (self.root / "demo.ide").write_text(
            json.dumps(
                {
                    "workspace": "/private/demo.code-workspace",
                    "socket": "/private/ide.sock",
                }
            )
        )
        r = await self.client.get(
            "/auth", headers=dict(self.headers(), **{"X-Forwarded-Uri": "/ide/"}), allow_redirects=False
        )
        self.assertEqual(r.status, 302)
        self.assertEqual(
            r.headers["Location"], "/ide/?workspace=/private/demo.code-workspace"
        )

    async def test_cross_origin_websocket_is_rejected(self):
        headers = dict(self.headers(), **{"X-VWS-Upgrade": "websocket", "Origin": "https://evil.test"})
        r = await self.client.get("/auth", headers=headers)
        self.assertEqual(r.status, 403)

    async def test_preview_auth_is_scoped_and_accepts_same_origin_websocket(self):
        self.doc['layout']['pane']['surfaces'].append({'id': 'preview', 'type': 'browser', 'url': 'http://localhost:8765/'})
        (self.root / 'demo.json').write_text(json.dumps(self.doc))
        from model import browser_host
        host = browser_host(self.doc, self.doc['layout']['pane']['surfaces'][1])
        headers = dict(self.headers(), Host=host, Origin='https://' + host)
        headers['X-VWS-Upgrade'] = 'websocket'
        self.assertEqual((await self.client.get('/auth', headers=headers)).status, 204)
        headers['Cookie'] = self.headers('other')['Cookie']
        self.assertEqual((await self.client.get('/auth', headers=headers)).status, 401)


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
