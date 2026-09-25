# AgentCgroup

Source: https://github.com/eunomia-bpf/agentcgroup
Commit: `551ca1689b7d2d30db6b8a8613414750103cc68b`
License: GPL-2.0; see LICENSE.

`bash_wrapper.upstream.sh` is the unmodified upstream `agentcg/bash_wrapper.sh`.
`bash_wrapper.sh` adapts that wrapper for a systemd-delegated subtree on an existing VPS.
It preserves per-command cgroups, resource hints and memory feedback, with these changes:

- Supports Codex's login-shell invocation as well as `bash -c`.
- Keeps the supervisor outside the command's cgroup so it can report an OOM.
- Uses hard memory/PID limits and fails closed if assignment fails.
- Avoids changing host bash; a full-access Codex BASH_ENV adapter invokes it.
- Records counters, never command text or environment values.
- Leaves surviving background processes inside the same aggregate budget.

The adapter uses ordinary cgroup v2; it does not claim to deploy the paper's eBPF
scheduler or patched-kernel memory controller. The optional upstream BPF components
are not installed. No upstream Python daemon is running.

Paper: Zheng et al., *AgentCgroup: Understanding and Controlling OS Resources of AI Agents*
(2026), https://arxiv.org/abs/2602.09345.
