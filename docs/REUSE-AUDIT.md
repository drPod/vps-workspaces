# Custom-code audit

September 23, 2026. This distinguishes actual reuse from custom integration. Using an upstream library does not make the surrounding application upstream code.

| Area | Actual implementation | Assessment |
|---|---|---|
| Browser IDE | Unmodified code-server workbench | Keep. No custom editor, terminal renderer, tabs, or splitters. |
| Agent sharing | Complete upstream HAPI Hub/Runner/CLI | Keep. HAPI owns Codex execution, shared history, permissions, and frontend attachments. |
| Native UI / ordinary terminals | cmux and tmux | Keep. Native pane reconstruction is custom integration. |
| HTTPS | Existing Caddy deployment | Keep; use more of its built-in proxy capability. |
| HTTP/WebSocket forwarding | Caddy `reverse_proxy` + `forward_auth` | Replaced and deployed. Removed custom forwarding and ttyd process management. `caddy_routes.py` generates configuration; systemd provides the host-loopback socket bridge. |
| Workspace sharing authentication | Custom fragment-key exchange, signed cookies and scope checks | Custom security-sensitive application behavior. Preserve existing protection until a replacement provides the same passwordless, workspace-scoped links. Caddy `forward_auth` delegates authentication; it does not itself provide this identity/link model. |
| Old browser workspace | Removed | Deleted its HTML, JavaScript, Split.js and terminal-process manager. `/classic/` redirects to code-server. |
| IDE extension | Vendored Microsoft Simple Browser; adapted Workspace Layout terminal helper; custom layout conversion, lifecycle handling, sharing/HAPI commands | Keep the cmux-specific mapping. Review lifecycle workarounds against upstream behavior; do not describe the whole extension as an existing third-party extension. |
| Workspace registry | Custom JSON schema, optimistic revisions, SSH CLI | Actual product-specific glue. Existing cmux PRs informed it; their code is not reused. No verified drop-in replacement found in the earlier source review. |
| Native autosave | Custom polling, debounce, conflict pausing, recovery drafts | Actual product-specific glue, not a built-in cmux feature. A generic filesystem watcher does not replace reading live cmux state. Prefer an upstream layout event API if the installed version supports it. |
| cmux route refresh | Custom small command wrapper | Needed to load fresh Mac connection metadata in old agent processes. It forwards to cmux's relay and preserves its policy. |
| HAPI installation | Custom `install-hapi.py` and temporary Mac installer | Over-customized provisioning. Prefer official package installation, HAPI settings/auth, and Runner commands. Standard systemd/launchd definitions may still be needed for login/boot supervision. |
| Backups | Upstream rsnapshot/rsync plus custom SQLite preparation and schedule orchestration | Snapshot copying and hard-link retention are upstream. SQLite preparation adds a real consistency requirement. Reduce custom scheduling; this code exposed first-run retention and remote-only rsync-option bugs. |
| New terminal conversations | Upstream HAPI, selected by a small interactive shell function | Deployed on Mac and VPS. Fresh `codex` sessions were verified with real replies in the shared HAPI app. This is shared access on the owning machine, not native database merging or execution migration. Desktop-app sessions, scripts and explicit native bypasses are outside this integration. |

## Changes made during this audit

- Removed the new `install-hapi-mac.py` before publication.
- Replaced the generated Mac HAPI shell wrapper with a link to the upstream executable.
- Put Hub connection settings in HAPI's own settings file and used `hapi runner start --workspace-root` successfully.
- Preserved the original Outreach HAPI migration and verified its history in the app.
- Corrected backup rsync options so the remote lock wrapper applies only to the remote source, retaining the shared exclude list.
- Corrected first-run retention ordering: longer tiers wait until their source tier exists, so a new installation can publish its first hourly snapshot.

## Completed follow-up and retained code

- Replaced and deployed the proxy; verified code-server WebSockets, both previews, two viewers, reload, authentication and cross-origin rejection. A real Caddy echo upstream confirmed workspace credentials are stripped while application cookies survive.
- Removed the classic frontend and related process manager. Kept only the small link-entry page.
- Verified new shell-launched conversations from both machines in HAPI, normal exit, and Mac cold resume with the same native thread.
- Kept the per-workspace link exchange: neither Caddy proxying nor HAPI's owner-wide login provides the same scoped capability-link contract. It remains custom security-sensitive code with tests.
- Kept the bounded VPS installers as deployment configuration generators for this existing container/systemd arrangement. The upstream apps remain unmodified. Future portability work should separate templates rather than introduce another service manager.
- Kept SQLite online-copy preparation and its short rsnapshot invocation wrapper: the real regression tests now cover first-run publication and multiple sources. It does not implement a backup format, delta transfer or hard-link retention engine.
- Kept cmux layout translation, autosave conflict checks and connection metadata refresh as project-specific behavior. No verified upstream drop-in was found for that complete workflow.

The audit is complete for the current implementation. This is not a claim that no custom code remains, or that arbitrary native Codex stores can safely be merged.

## Sources checked

- [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy): HTTP, WebSockets, Unix sockets, header manipulation.
- [Caddy forward auth](https://caddyserver.com/docs/caddyfile/directives/forward_auth): delegation to an authentication service.
- [HAPI installation](https://hapi.run/docs/guide/installation): supported package installation and CLI/Hub/Runner roles.
- [HAPI shared Codex sessions](https://hapi.run/docs/guide/codex-shared-sessions): ownership, resume, remote access and unsupported features.
- [Existing source attribution](UPSTREAM.md) and [extension notice](../ide-extension/NOTICE.md): exact upstream code reuse versus inspiration.

## September 24 refactor

The integration now lives in `vps_workspaces/`, behind `workspace.py` and the stable SSH
`remote.py` entry point. Shared JSON writes and registry access have single implementations.
Python annotations and TypeScript checks run in CI; Zod validates extension input.

cmux actions use its native configuration schema and new-tab command target. Its standalone
settings editor preserves JSONC; the vendored compatibility change detects whether the
installed validator accepts `--scope`. No replacement configuration parser was written.
The Python SDK in cmux-tui was inspected, but its prefixed resource IDs/protocol are not a
verified replacement for the installed macOS control CLI. This adapter keeps the official CLI.

Clipboard requests use macOS `pbcopy` or the terminal's native OSC 52 support. There is no
clipboard daemon, tunnel, Clipaste dependency or custom clipboard synchronization service.


Development now follows the early Orchard/Sixtyfive pattern: uv owns the project environment
and lockfile; concise typed modules use the standard library and upstream libraries directly.
The Ruff rule set matches Sixtyfive's current E3/B/I/C4/PIE/PERF/DTZ/FAST extensions and
spacing exceptions. Vendor directories retain their upstream style and license notices.
See https://docs.astral.sh/uv/guides/projects/ for the dependency/lockfile workflow.
