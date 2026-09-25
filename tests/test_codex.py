import tempfile
import unittest
from pathlib import Path

from aiohttp import web

from vps_workspaces.codex import Client, checked_thread


class NativeClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_notifications_and_server_requests_do_not_become_responses(self):
        async def handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for message in ws:
                incoming = message.json()
                if "id" not in incoming:
                    continue
                ident = incoming["id"]
                await ws.send_json({"method": "thread/status/changed", "params": {}})
                await ws.send_json({"id": ident, "method": "item/commandExecution/requestApproval", "params": {}})
                if incoming["method"] == "fail":
                    await ws.send_json({"id": ident, "error": {"message": "test error"}})
                else:
                    await ws.send_json({"id": ident, "result": {"ok": True}})
            return ws

        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            app = web.Application()
            app.router.add_get("/", handler)
            runner = web.AppRunner(app)
            await runner.setup()
            socket = str(Path(directory) / "test.sock")
            await web.UnixSite(runner, socket).start()
            try:
                async with Client(socket) as client:
                    self.assertEqual(await client.call("read", {}), {"ok": True})
                    with self.assertRaisesRegex(RuntimeError, "test error"):
                        await client.call("fail", {})
            finally:
                await runner.cleanup()

    def test_thread_binding_rejects_non_uuid_values(self):
        for value in ("../other", "--help", "", None):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                checked_thread(value)


if __name__ == "__main__":
    unittest.main()
