# Automatic tool resource isolation

This adapter reuses [AgentCgroup's Bash wrapper](https://github.com/eunomia-bpf/agentcgroup),
pinned at `551ca1689b7d2d30db6b8a8613414750103cc68b`. The original, adapted source,
GPL-2.0 license, and change list are in [vendor/agentcgroup](../vendor/agentcgroup/NOTICE.md).

Codex's `shell_environment_policy.set.BASH_ENV` invokes the adapter before noninteractive
Bash tool commands. It puts the command and its descendants into a separate cgroup, while
keeping the supervising agent outside that cgroup. It does not replace `/bin/bash`, add
an MCP server, or change interactive login shells.

## Install

Requires Linux cgroup v2, systemd 254+ with user delegation, and the official Codex CLI.
From this checkout, after `uv sync --locked`:

```sh
uv run python workspace.py install resources
```

The installer preserves the existing Codex TOML settings and backs up that file before
changing it. It refuses to overwrite an unrelated BASH_ENV adapter. Start a new Codex
thread to load the settings; a running engine may retain its previous environment.
The installer does not restart agents. The current Mac does not need this Linux adapter.

`vws-agent-tools.service` delegates a subtree under `agent-jobs.slice`. Its supervisor
uses negligible resources; systemd owns startup and teardown. Existing slice configuration
is preserved. The supplied defaults are:

| Budget | Default |
|---|---|
| Per command | 768 MiB, 128 processes |
| `AGENT_RESOURCE_HINT=memory:low` | 256 MiB |
| `AGENT_RESOURCE_HINT=memory:medium` | 768 MiB |
| `AGENT_RESOURCE_HINT=memory:high` | 1 GiB |
| All isolated jobs combined | 1 GiB memory.high, 1.5 GiB memory.max, 1.5 CPU cores, 256 processes |

Set a resource hint in the invoking process environment before Bash starts. A variable
assignment inside an already-running command cannot change its cgroup budget. Large builds
may need an explicitly configured systemd job; use [RESOURCE-LIMITS.md](RESOURCE-LIMITS.md).

Per-command memory uses a hard cap. A lower per-command `memory.high` made over-budget
allocations spend too long reclaiming in the live test. Aggregate `memory.high` still
provides backpressure across concurrent jobs. On a cgroup OOM, the wrapper reports the
limit and measured peak to the agent. If assignment fails, the command does not run.

Metrics contain PID, duration, exit status, peak bytes and OOM count; no command text or
environment values. They live in `~/.local/state/vps-workspaces/resources/tools.jsonl`.
When logrotate is installed, an hourly user timer rotates at 1 MiB and retains two archives.
Background children remain in the same budget; a populated cgroup is never removed to
let them escape. Empty groups normally disappear as commands finish.

## Kernel choice and coverage

The deployed adapter uses **ordinary cgroup v2**, tested on Ubuntu's 6.8 kernel. It does
not run AgentCgroup's eBPF scheduler, process monitor, or adaptive memory daemon. The full
upstream CPU scheduler needs sched_ext (6.12+); its memory controller also requires
`memcg_bpf_ops` patches. Installing a newer distribution kernel alone does not establish
support for that controller. No kernel upgrade or reboot is required for this adapter.

This is protection from accidental resource exhaustion, not a security boundary. It
covers Bash commands receiving Codex's configured environment, including `-lc` and `-c`.
It does not automatically cap non-Bash execution, a separately managed Docker container,
remote SSH work, or work submitted to another daemon. Those need their own service or
container limits. Agents run under the same trusted Unix account and can bypass limits.

## Verify and recover

```sh
systemctl --user status vws-agent-tools.service
systemctl --user show agent-jobs.slice -p MemoryHigh -p MemoryMax -p CPUQuotaPerSecUSec
```

Ask a disposable Codex conversation to run `cat /proc/self/cgroup`; its shell should report
`vws-agent-tools.service/tool_…`. The agent engine itself must remain outside that group.
On this installation, a real native Codex call passed that check. Login/non-login shell,
stdio, exit status, and a 320 MiB allocation against a 256 MiB limit passed live tests.
The over-budget command exited 137; the supervisor reported the OOM and cleaned up.

For opt-in live regression tests, set `VWS_TEST_CGROUP` to an otherwise idle delegated
subtree with cpu, memory and pids enabled, then run `test_resources.py`. Normal unit test
runs skip the live allocation tests.

To disable: remove only `BASH_ENV`, `AGENTCG_WRAPPER`, `AGENTCG_ROOT`, and `AGENTCG_LOG`
from Codex's `[shell_environment_policy.set]` table, preserving other settings. New threads
then stop using the adapter. Do not stop `vws-agent-tools.service` until its jobs have
finished: stopping the service kills its contained jobs. The private installation runbook
records deployment and rollback state.
