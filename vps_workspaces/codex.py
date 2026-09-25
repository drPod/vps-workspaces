from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from uuid import UUID

from vps_workspaces.contracts import JsonObject

if TYPE_CHECKING:
    from typing import Self


def checked_thread(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected a Codex thread UUID")
    return str(UUID(value))


def binary() -> str:
    command = shutil.which("codex")
    if command is None:
        raise RuntimeError("Install the official Codex CLI first")
    return command


def start() -> str:
    result = subprocess.run(
        [binary(), "app-server", "daemon", "start"], check=True, capture_output=True, text=True, timeout=90
    )
    info = json.loads(result.stdout.strip().splitlines()[-1])
    return str(Path(info["socketPath"]).resolve())


class Client:
    def __init__(self, socket: str) -> None:
        import aiohttp

        self.http = aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=socket))
        self.number = 0

    async def __aenter__(self) -> Self:
        try:
            self.ws = await self.http.ws_connect("http://localhost/", max_msg_size=64 * 1024 * 1024)
            await self.call("initialize", {"clientInfo": {"name": "vps_workspaces", "version": "0.1.0"}})
            await self.ws.send_json({"method": "initialized"})
        except BaseException:
            if hasattr(self, "ws"):
                await self.ws.close()
            await self.http.close()
            raise
        return self

    async def __aexit__(self, *args: object) -> None:
        try:
            await self.ws.close()
        finally:
            await self.http.close()

    async def call(self, method: str, params: JsonObject) -> JsonObject:
        self.number += 1
        await self.ws.send_json({"id": self.number, "method": method, "params": params})
        while True:
            message = await self.ws.receive_json(timeout=60)
            if message.get("id") == self.number and "method" not in message:
                if "error" in message:
                    raise RuntimeError(message["error"]["message"])
                return message["result"]


def request(method: str, params: JsonObject) -> JsonObject:
    async def run() -> JsonObject:
        async with Client(socket) as client:
            return await client.call(method, params)

    socket = start()
    return asyncio.run(run())


def create(directory: str, name: str) -> str:
    cwd = str(Path(directory).expanduser().resolve())

    async def run() -> str:
        async with Client(socket) as client:
            result = await client.call("thread/start", {"cwd": cwd})
            thread = checked_thread(result["thread"]["id"])
            # Naming materializes the otherwise lazy thread before the viewer connects.
            await client.call("thread/name/set", {"threadId": thread, "name": name})
            return thread

    socket = start()
    return asyncio.run(run())


def attach(thread: str) -> NoReturn:
    thread = checked_thread(thread)
    endpoint = "unix://" + start()
    command = binary()
    os.execv(command, [command, "--remote", endpoint, "resume", thread])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["list", "attach", "start"])
    parser.add_argument("thread", nargs="?")
    args = parser.parse_args()
    if args.action == "attach":
        attach(checked_thread(args.thread))
    elif args.action == "start":
        print(start())
    else:
        for thread in request("thread/list", {"limit": 100})["data"]:
            print(thread["id"], thread.get("name") or thread.get("preview", ""))
