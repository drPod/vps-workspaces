from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import tomlkit


def configure(path: Path, values: dict[str, str]) -> None:
    text = path.read_text() if path.exists() else ""
    doc = tomlkit.parse(text)
    policy = cast(dict[str, Any], doc.setdefault("shell_environment_policy", tomlkit.table()))
    env = cast(dict[str, Any], policy.setdefault("set", tomlkit.table()))
    current = env.get("BASH_ENV")
    if current and current != values["BASH_ENV"]:
        raise RuntimeError("Existing BASH_ENV needs to be reconciled before installing resource isolation")
    env.update(values)
    updated = tomlkit.dumps(doc)
    if updated == text:
        return
    if path.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        shutil.copy2(path, path.with_name(f"{path.name}.before-resources-{stamp}"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    args = parser.parse_args()
    if sys.platform != "linux":
        raise RuntimeError("Tool resource isolation requires Linux systemd and cgroup v2")
    source = Path(__file__).resolve().parents[2]
    target = Path.home() / ".local/share/vps-workspaces/resources"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("bash_wrapper.sh", "bash_wrapper.upstream.sh", "LICENSE", "NOTICE.md"):
        shutil.copy2(source / "vendor/agentcgroup" / name, target / name)
    shutil.copy2(source / "deploy/agent-tools-env.bash", target / "env.bash")
    units = Path.home() / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    if not (units / "agent-jobs.slice").exists():
        shutil.copy2(source / "deploy/systemd/agent-jobs.slice", units / "agent-jobs.slice")
    shutil.copy2(source / "deploy/systemd/vws-agent-tools.service", units / "vws-agent-tools.service")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "vws-agent-tools.service"], check=True)
    subprocess.run(["systemctl", "--user", "start", "vws-agent-tools.service"], check=True)
    group = subprocess.check_output(
        ["systemctl", "--user", "show", "vws-agent-tools.service", "-p", "ControlGroup", "--value"], text=True
    ).strip()
    root = Path("/sys/fs/cgroup" + group)
    if not {"cpu", "memory", "pids"}.issubset((root / "cgroup.subtree_control").read_text().split()):
        raise RuntimeError("Tool cgroup controllers are not enabled")
    state = Path.home() / ".local/state/vps-workspaces/resources"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.which("logrotate") or Path("/usr/sbin/logrotate").exists():
        (target / "logrotate.conf").write_text(f'''"{state}/tools.jsonl" {{
    size 1M
    rotate 2
    compress
    copytruncate
    missingok
    notifempty
}}
''')
        (units / "vws-agent-metrics.service").write_text(f"""[Service]
Type=oneshot
ExecStart=/usr/sbin/logrotate --state {state}/logrotate.state {target}/logrotate.conf
MemoryMax=64M
CPUQuota=10%
""")
        (units / "vws-agent-metrics.timer").write_text("""[Timer]
OnBootSec=10min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
""")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "vws-agent-metrics.timer"], check=True)
    configure(
        args.codex_home / "config.toml",
        {
            "BASH_ENV": str(target / "env.bash"),
            "AGENTCG_WRAPPER": str(target / "bash_wrapper.sh"),
            "AGENTCG_ROOT": str(root),
            "AGENTCG_LOG": str(state / "tools.jsonl"),
        },
    )
    print("AgentCgroup tool isolation configured. New Codex threads load the environment settings.")
