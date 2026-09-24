# Custom-code audit

September 23, 2026. This distinguishes actual reuse from custom integration. Using an upstream library does not make the surrounding application upstream code.

| Area | Actual implementation | Assessment |
|---|---|---|
| Browser IDE | Unmodified code-server workbench | Keep. No custom editor, terminal renderer, tabs, or splitters. |
| Agent sharing | Complete upstream HAPI Hub/Runner/CLI | Keep. HAPI owns Codex execution, shared history, permissions, and frontend attachments. |
| Native UI / ordinary terminals | cmux and tmux | Keep. Native pane reconstruction is custom integration. |
| HTTPS | Existing Caddy deployment | Keep; use more of its built-in proxy capability. |
| HTTP/WebSocket forwarding | Custom `server.py:proxy`, built on aiohttp | Strong replacement candidate. Caddy already implements this. An aiohttp dependency is not reuse of a complete proxy. |
| Workspace sharing authentication | Custom fragment-key exchange, signed cookies and scope checks | Custom security-sensitive application behavior. Preserve existing protection until a replacement provides the same passwordless, workspace-scoped links. Caddy `forward_auth` delegates authentication; it does not itself provide this identity/link model. |
| Old browser workspace | Custom `static/app.js`, HTML/CSS, upstream Split.js and ttyd | Superseded by code-server. Candidate for removal with `/classic/` and its ttyd process manager, after confirming fallback is no longer needed. |
| IDE extension | Vendored Microsoft Simple Browser; adapted Workspace Layout terminal helper; custom layout conversion, lifecycle handling, sharing/HAPI commands | Keep the cmux-specific mapping. Review lifecycle workarounds against upstream behavior; do not describe the whole extension as an existing third-party extension. |
| Workspace registry | Custom JSON schema, optimistic revisions, SSH CLI | Actual product-specific glue. Existing cmux PRs informed it; their code is not reused. No verified drop-in replacement found in the earlier source review. |
| Native autosave | Custom polling, debounce, conflict pausing, recovery drafts | Actual product-specific glue, not a built-in cmux feature. A generic filesystem watcher does not replace reading live cmux state. Prefer an upstream layout event API if the installed version supports it. |
| cmux route refresh | Custom small command wrapper | Needed to load fresh Mac connection metadata in old agent processes. It forwards to cmux's relay and preserves its policy. |
| HAPI installation | Custom `install-hapi.py` and temporary Mac installer | Over-customized provisioning. Prefer official package installation, HAPI settings/auth, and Runner commands. Standard systemd/launchd definitions may still be needed for login/boot supervision. |
| Backups | Upstream rsnapshot/rsync plus custom SQLite preparation and schedule orchestration | Snapshot copying and hard-link retention are upstream. SQLite preparation adds a real consistency requirement. Reduce custom scheduling; this code exposed first-run retention and remote-only rsync-option bugs. |
| New conversation sync | Not completed | Do not claim that connecting two Runners syncs native Codex stores. HAPI offers shared access to wrapped sessions; it does not automatically adopt arbitrary already-running native agents or migrate execution between machines. |

## Changes made during this audit

- Removed the new `install-hapi-mac.py` before publication.
- Replaced the generated Mac HAPI shell wrapper with a link to the upstream executable.
- Put Hub connection settings in HAPI's own settings file and used `hapi runner start --workspace-root` successfully.
- Preserved the original Outreach HAPI migration and verified its history in the app.
- Corrected backup rsync options so the remote lock wrapper applies only to the remote source, retaining the shared exclude list.
- Corrected first-run retention ordering: longer tiers wait until their source tier exists, so a new installation can publish its first hourly snapshot.

## Replacement order

1. Finish verifying backup publication and the existing migrated workspace.
2. Use upstream HAPI configuration and documented startup behavior on both machines.
3. Replace the generic HTTP/WebSocket transport with Caddy, preserving authentication, cookies, app subdomains and code-server WebSockets in integration tests.
4. Retire the superseded classic UI and ttyd fallback if no remaining use requires them.
5. Finish the new-conversation workflow using supported upstream session behavior. Do not introduce a homegrown live SQLite merger or pretend history file copying transfers a live process.

The last three are identified work, not completed replacements. Do not remove security checks or working routes merely to lower the line count.

## Sources checked

- [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy): HTTP, WebSockets, Unix sockets, header manipulation.
- [Caddy forward auth](https://caddyserver.com/docs/caddyfile/directives/forward_auth): delegation to an authentication service.
- [HAPI installation](https://hapi.run/docs/guide/installation): supported package installation and CLI/Hub/Runner roles.
- [HAPI shared Codex sessions](https://hapi.run/docs/guide/codex-shared-sessions): ownership, resume, remote access and unsupported features.
- [Existing source attribution](UPSTREAM.md) and [extension notice](../ide-extension/NOTICE.md): exact upstream code reuse versus inspiration.
