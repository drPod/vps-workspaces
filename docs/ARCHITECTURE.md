# Architecture

## Ownership

The VPS registry owns saved workspace definitions. Explicit Save captures the live `cmux tree` response, replaces Mac-specific surface identities with stable terminal/browser IDs, and writes a revisioned JSON document over SSH. Server-side writes are serialized and reject stale revisions. Open fetches the latest definition and uses an ordinary `cmux ssh` workspace plus native pane commands to rebuild the layout.

A terminal belongs to a named session on the dedicated tmux server `tmux -L vps-workspaces`. Each terminal has its own session, rather than treating tmux's internal splits as cmux's layout. code-server terminals and native cmux attach to these same sessions. Closing a viewer disconnects a client, not the session. tmux uses the most recently active client size (`window-size latest`), so the terminal fits the viewer currently using it. Other viewers may see padding or clipping because a single shared terminal process has one size.

Ordinary tmux shells do not start coding agents automatically. HAPI-bound surfaces use HAPI to attach or resume the saved conversation. After a reboot, opening from the Mac recreates missing shells; the user resumes the desired agent conversation. Restarting the sharing service does not restart tmux.

## Browser pages

Native cmux owns the Mac browser panes and its ordinary SSH proxy. Web viewers receive independent iframes. The initial adapter maps localhost/127.0.0.1/::1 app origins to separate HTTPS subdomains under the workspace hostname. Keeping each app at the root of its own origin preserves absolute asset paths and separates app scripts from the terminal's origin. External HTTP(S) pages are embedded directly and must permit embedding; there is no browser stream or iframe-restriction bypass.

The IDE uses the saved split tree. Resizing in the web UI affects only that viewer; publishing layout changes is an explicit Mac Save. Reload the saved layout to see a newer revision.

## Native relay routing

Each Mac attachment records that session's cmux relay context in a private `.route` file. A session-local `cmux` wrapper reads it afresh for each invocation. This addresses stale process environments without attempting to modify an already-running agent's environment. The most recent Mac attachment becomes the route for supported cmux commands.

This is not an expansion of cmux's permissions. The installed app rejects remote browser snapshot/URL commands. Local Mac browser automation remains cmux's own capability; remote agent browser automation is a known gap. No socket access mode is changed.

## Authentication and networking

Caddy terminates HTTPS and performs HTTP/WebSocket forwarding directly. Its `forward_auth` calls the small aiohttp sharing-link service through a private Unix socket. That service checks a signed, expiring workspace cookie before Caddy forwards IDE or preview traffic. Standard systemd socket proxies connect host-only preview listeners to the existing Caddy container mount. A stable 256-bit per-workspace link key is derived from the installation secret. It travels in the URL fragment (not HTTP request URLs or access logs), is exchanged for a session cookie, and is removed from visible history before loading child frames. Secrets and relay records are outside the source tree with restrictive permissions.

Link exchange requires a matching Origin and sets Secure/HttpOnly/SameSite cookies. WebSocket upgrades require an exact Origin match. Workspace credentials are stripped before proxying to apps. The web API has no shell-command, arbitrary upstream, workspace-write, or session-creation endpoint.

This first version uses possession of the complete sharing link as access authorization; it does not provide individual accounts, read-only viewer roles, audit trails, or per-person revocation. Anyone with a workspace link can control its terminal as the shared Unix user. This is a trusted-collaborator tool, not tenant isolation. Installation-key rotation affects new HTTP connections; already-open WebSockets must be disconnected separately.

## Browser IDE

An enabled workspace has its own code-server systemd service, private Unix socket, user-data directory, and generated `.code-workspace` file. Caddy authenticates `/ide/` HTTP and WebSocket requests through `forward_auth`, then forwards directly to that socket. code-server has no public listener; its own password prompt and generic port proxy are disabled. The existing allowlisted app subdomains remain the preview destinations.

The extension adapts Workspace Layout's terminal construction and directly reuses Microsoft's Simple Browser view and assets. The custom part translates cmux's binary split tree into VS Code editor groups and resolves saved surface identities. Microsoft preview tabs get distinct titles. Existing terminals are preserved, and no coding agent is launched.

The IDE's layout is initially imported on window activation. Later VS Code rearrangements are viewer-local; native Save remains the publisher of the portable layout. Reload imports that saved layout again. The browser is a separate view of the same tmux processes and app URLs, not an embedded instance of the native cmux UI.

code-server retains disconnected clients for a 60-second reconnection grace period; a newly attached viewer can temporarily become the most recently active size until another viewer interacts. The adapter detaches only its own recorded tmux client PIDs when its extension host deactivates. After that the browser can reconnect by opening a fresh view onto the still-running tmux session.

Layout-only autosaves do not reload Caddy when the rendered routes are unchanged. Code-server is the sole workspace frontend; `/classic/` redirects to it.
