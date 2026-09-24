# Keeping agent jobs from starving the VPS

The September 24 freeze was a host-wide OOM event: an unbounded Python guide parse used about
3.3 GiB alongside existing services. It ran inside the HAPI agent's service cgroup. The kernel
killed that Python child; the interactive session slowed during memory reclaim. Jellyfin was
already limited separately. Container limits do not cover arbitrary host-side helper commands.

This is an established cloud-development pattern. [Coder](https://coder.com/docs) manages
agent/development workspaces with resource-limited templates and dev containers.
[OpenHands](https://github.com/OpenHands/docs/blob/main/openhands/usage/architecture/runtime.mdx)
separates agent control from an action-execution container. The underlying enforcement is
[Linux cgroup v2](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html).

For this existing systemd/HAPI installation, use native systemd units rather than adding a
second workspace platform or writing a monitoring daemon. Keep expensive jobs separate from
the HAPI process and SSH. The installed user slice `agent-jobs.slice` has a 1 GiB soft threshold,
1.5 GiB aggregate hard limit, 150% CPU quota (1.5 cores), CPU weight 20, and 256-task limit.
It is defined in `~/.config/systemd/user/agent-jobs.slice`; the reusable template is in Watch Link's
`deploy/systemd/agent-jobs.slice`. An individual job should have a lower suitable limit:

```sh
systemd-run --user --slice=agent-jobs.slice --wait --pipe --collect \
  --working-directory="$PWD" \
  -p MemoryHigh=512M -p MemoryMax=768M -p CPUQuota=100% \
  /usr/bin/python3 your_job.py
```

Use absolute executable paths. Service environment/cwd may differ from the interactive shell;
pass necessary environment explicitly, without logging credentials. For an interactive command
use a scope where appropriate; for background work use a service and read its journal.

`MemoryHigh` throttles/reclaims; `MemoryMax` is the hard boundary. The aggregate slice prevents
several individually capped jobs from exceeding its combined budget. A disposable 64 MiB unit
was tested with a 128 MiB allocation: that process was killed and the interactive session
remained available. Guide processing subsequently ran under a 256 MiB cap using about 15 MiB.

These controls apply **only to jobs launched into the slice**. They are not universal protection.
A Docker CLI command asks the separate Docker daemon to do work; limiting the CLI does not limit
that daemon or its containers. Give containers their own limits. Don't set a small hard limit on
the entire user/HAPI service: that can kill the conversation along with its child jobs.

Swap (2–4 GiB) is an optional burst cushion, not an alternative to these limits. No swap was added
as part of this change. systemd-oomd is another established pressure-response tool, but enabling
it on an undifferentiated user session risks killing the entire session; it was not enabled.
Idle application cleanup or more RAM helps sustained demand but is not required for this fix.

Use `systemctl --user show UNIT -p MemoryPeak -p MemoryMax -p Result`, `systemd-cgtop`, `free -h`,
and kernel OOM logs to diagnose. Prefer streaming large files and avoid unnecessary parallelism.
