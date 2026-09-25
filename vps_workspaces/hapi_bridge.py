from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import NoReturn
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from vps_workspaces.contracts import HapiConfig, HapiSession, JsonObject, Surface

ROOT = Path.home() / ".local/share/vps-workspaces"
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def checked_session(value: object) -> str:
    if not isinstance(value, str) or not SESSION_ID.fullmatch(value):
        raise ValueError("Invalid HAPI session ID")
    return value


def config() -> HapiConfig:
    return json.loads((ROOT / "hapi/install.json").read_text())


class Hapi:
    def __init__(self, timeout: float = 90) -> None:
        self.timeout = timeout
        self.config = config()
        self.base = self.config.get("api_url") or f"http://127.0.0.1:{self.config['port']}"
        self.token = None
        self.token = self.request("/api/auth", {"accessToken": self.config["token"]})["token"]

    def request(self, path: str, data: JsonObject | None = None, method: str | None = None) -> JsonObject:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(
            self.base + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read().decode()[:500]
            raise RuntimeError(f"HAPI returned HTTP {error.code}: {detail}") from None

    def session(self, sid: str) -> HapiSession:
        return self.request("/api/sessions/" + checked_session(sid))["session"]

    def ready(self, sid: str) -> HapiSession:
        session = self.session(sid)
        if (session.get("metadata") or {}).get("flavor") != "codex":
            raise ValueError("Independent terminal attachment currently requires a Codex session")
        if not session.get("active"):
            for attempt in range(20):
                try:
                    result = self.request("/api/sessions/" + sid + "/resume", {})
                    break
                except RuntimeError as error:
                    if "RPC handler not registered" not in str(error) or attempt == 19:
                        raise
                    time.sleep(0.5)
            if result.get("type") != "success":
                raise RuntimeError("HAPI could not resume this session")
            for _ in range(100):
                session = self.session(sid)
                if session.get("active"):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("HAPI session did not become active")
        return session

    def create(self, directory: str, name: str, permission: str = "default") -> str:
        machines = self.request("/api/machines")["machines"]
        local = [m for m in machines if m.get("active") and m.get("metadata", {}).get("host") == os.uname().nodename]
        if len(local) != 1:
            raise RuntimeError("Expected one online HAPI Runner on this VPS")
        result = self.request(
            "/api/machines/" + local[0]["id"] + "/spawn",
            {
                "directory": str(Path(directory).expanduser().resolve()),
                "agent": "codex",
                "permissionMode": permission,
            },
        )
        if result.get("type") != "success":
            raise RuntimeError("HAPI spawn failed: " + json.dumps(result))
        sid = checked_session(result["sessionId"])
        self.request("/api/sessions/" + sid, {"name": name}, method="PATCH")
        return sid


def link(sid: str | None = None) -> str:
    c = config()

    path = "/sessions/" + checked_session(sid) if sid else "/"
    return "https://" + c["host"] + path + "?" + urlencode({"token": c["token"]})


def attach(sid: str) -> NoReturn:
    Hapi().ready(checked_session(sid))

    wrapper = str(Path.home() / ".local/bin/hapi")
    os.execv(wrapper, [wrapper, "resume", sid])


def assert_shell(surface: Surface) -> None:
    p = subprocess.run(
        [
            "/usr/bin/tmux",
            "-L",
            "vps-workspaces",
            "list-panes",
            "-t",
            "=" + surface["session"],
            "-F",
            "#{pane_current_command}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if p.returncode == 0 and any(cmd not in ("bash", "zsh", "sh", "fish") for cmd in p.stdout.splitlines()):
        raise ValueError(
            "This terminal still has a running program. Exit the old agent normally before binding or migrating; it will not be stopped automatically."
        )
