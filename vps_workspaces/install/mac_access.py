from __future__ import annotations

import os
import plistlib
import socket
import subprocess
import sys
import time
from functools import partial
from pathlib import Path

run = partial(subprocess.run, check=True)


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("Run this installer in a local Mac terminal.")
    home = Path.home()
    ssh = ["/usr/bin/ssh", "-o", "BatchMode=yes", "myvps"]
    key = subprocess.check_output(ssh + ["cat ~/.ssh/mac-backlink.pub"], text=True).strip()
    if not key.startswith("ssh-ed25519 ") or "\n" in key:
        raise SystemExit("Unexpected VPS public key; nothing installed.")
    try:
        with socket.create_connection(("127.0.0.1", 22), timeout=2):
            pass
    except OSError:
        print("Enabling macOS Remote Login; sudo may request your Mac password.", flush=True)
        result = subprocess.run(["sudo", "/usr/sbin/systemsetup", "-setremotelogin", "on"], check=False)
        try:
            with socket.create_connection(("127.0.0.1", 22), timeout=3):
                pass
        except OSError:
            raise SystemExit(
                "Turn on System Settings > General > Sharing > Remote Login, "
                "allow your Mac account, then rerun this command."
            ) from None

    directory = home / ".ssh"
    directory.mkdir(mode=0o700, exist_ok=True)
    authorized = directory / "authorized_keys"
    old = authorized.read_text() if authorized.exists() else ""
    if key.split()[1] not in old:
        with authorized.open("a") as f:
            f.write(
                ("\n" if old and not old.endswith("\n") else "") + "no-agent-forwarding,no-X11-forwarding " + key + "\n"
            )
    authorized.chmod(0o600)
    host_key = Path("/etc/ssh/ssh_host_ed25519_key.pub").read_text().split()
    pinned = "mac-backlink " + " ".join(host_key[:2]) + "\n"
    run([*ssh, "umask 077; cat > ~/.ssh/known_hosts_mac"], input=pinned, text=True)

    label = "com.drpod.vps-workspaces-mac-access"
    logs = home / "Library/Logs"
    logs.mkdir(parents=True, exist_ok=True)
    plist = home / "Library/LaunchAgents" / (label + ".plist")
    plist.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "Label": label,
        "ProgramArguments": [
            "/usr/bin/ssh",
            "-N",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "ControlMaster=no",
            "-o",
            "ControlPath=none",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "PermitLocalCommand=no",
            "-o",
            "RemoteCommand=none",
            "-R",
            "127.0.0.1:22022:127.0.0.1:22",
            "myvps",
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / (label + ".log")),
        "StandardErrorPath": str(logs / (label + ".log")),
    }
    domain = "gui/" + str(os.getuid())
    subprocess.run(
        ["launchctl", "bootout", domain + "/" + label],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    plist.write_bytes(plistlib.dumps(data))
    run(["launchctl", "bootstrap", domain, str(plist)])
    for _attempt in range(15):
        result = subprocess.run(ssh + ["ssh mac /usr/bin/whoami"], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            print("Verified VPS → Mac SSH access as " + result.stdout.strip())
            print("The VPS can now use: ssh mac")
            return
        time.sleep(2)
    raise SystemExit(
        "Tunnel installed, but login verification failed: "
        + result.stderr.strip()
        + "\nCheck Remote Login allows your account and see "
        + str(logs / (label + ".log"))
    )


if __name__ == "__main__":
    main()
