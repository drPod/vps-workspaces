# Native shared Codex

New workspaces use the official Codex app-server daemon and official terminal client,
tested with **Codex 0.157.0**. The server owns the conversation; each cmux or code-server
terminal runs `codex --remote unix://… resume THREAD_ID`. Clients have independent terminal
sizes and closing them does not end an active server turn. This integration does not add
a model proxy, MCP bridge, custom prompt, terminal renderer, or agent implementation.

Sources: [OpenAI app-server documentation](https://learn.chatgpt.com/docs/app-server),
[daemon management](https://github.com/openai/codex/blob/rust-v0.157.0/codex-rs/app-server-daemon/README.md).
HAPI v0.30.7's shared-engine implementation was inspected while planning the migration;
its engine, gateway and prompt bridge are not copied into the native path.

## Install and use

Install the official Codex CLI and authenticate normally. On the VPS:

```sh
python3 workspace.py install codex
python3 workspace.py codex list
```

The installer enables `vws-codex.service` to call upstream `codex app-server daemon start`
at boot. On macOS it installs an equivalent RunAtLoad launch agent, using the same upstream
command. Existing daemons are reused, not restarted. Automatic daemon updates are disabled
because an update can interrupt active work; update explicitly when conversations are idle.
The CLI and the managed daemon package have separate versions:

```sh
codex app-server daemon version
codex app-server daemon update
```

From a local Mac cmux shell, `workspace.py new NAME --cwd DIRECTORY` provisions the IDE,
creates and names a native thread, and saves its UUID in the terminal's `codex_thread` field.
Naming persists a new thread before another client resumes it. `open NAME` attaches viewers
without creating another agent. The existing sharing-link flow is unchanged.

`codex-shell.sh` now only removes the old HAPI shell function. New shells call the official
CLI directly. In an old idle shell, source this file to remove a function it already loaded.
The native daemon's Unix socket stays local; browser access goes through the authenticated
code-server terminal, not a public app-server listener.

A plain `codex` started inside an existing tmux shell still belongs to that shared shell's
terminal layout. Use a managed native thread binding to get independent Codex terminal
clients in different viewers. Do not infer a thread's identity from its title or cwd.

## Existing HAPI workspaces

The schema and legacy attachment adapters remain readable during migration. They are not
used for new workspaces. Migrate an existing workspace only after its HAPI-owned turn is
idle, preserving its native Codex thread UUID:

1. Back up the registry, Mac binding state, and HAPI/Codex databases with SQLite's backup API.
2. Inspect the owning app-server's `thread/read` status. Never start a second engine for the
   same thread while its old engine is running.
3. Stop the old owner normally, resume the same thread in the native daemon, and clear only
   the HAPI-injected developer instructions. Preserve any user-authored instructions.
4. Replace `hapi_session` with `codex_thread` using the normal revision check. Hold the Mac
   autosave lock while updating its matching baseline and replacing a viewer.
5. Open and verify a native client in the same pane before closing the old viewer. Preserve
   browser tabs, their URLs, pane sizes and tab order. Save the resulting layout normally.
6. Retire HAPI Hub/Runner and its routes only after every remaining owner has migrated.

Installation-specific identities and migration progress belong in the private operations
runbook, never in this repository. Legacy modules are compatibility code, not a reason to
reinstall HAPI when a native workspace needs repair.

## Verification and limits

A disposable native thread was attached to two independent clients. Both received the
same completed turn. A shell command continued while both clients were disconnected, and
a fresh client resumed its completed result. Real native TUI clients at 70×24 and 140×40
rendered independent layouts. Existing idle workspaces have been migrated using their
original thread UUIDs and native Mac viewers verified before old viewers were closed.

The daemon inherits the environment at startup; it does not provide per-client environment
isolation. The cmux relay adapter resolves `CODEX_THREAD_ID` through the saved registry and
reads the latest route each time. Files and other processes are still shared by Unix user.
Normal native Codex permissions, approvals, configuration and tools belong to Codex.
The optional [AgentCgroup adapter](AGENTCGROUP.md) caps supported Bash tool calls separately.

Closing a viewer is not a server shutdown. A VPS reboot or daemon restart interrupts running
commands; conversation history can be resumed afterward, but arbitrary processes are not
checkpointed. All threads currently share one native daemon failure domain. Avoid automatic
restarts or small hard memory caps on that daemon; cap expensive tool commands instead.
