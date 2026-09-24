# Architecture

## Ownership

The VPS registry owns saved workspace definitions. Explicit Save captures the live `cmux tree` response, replaces Mac-specific surface identities with stable terminal/browser IDs, and writes a revisioned JSON document over SSH. Server-side writes are serialized and reject stale revisions. Open fetches the latest definition and uses an ordinary `cmux ssh` workspace plus native pane commands to rebuild the layout.

A terminal belongs to a named session on the dedicated tmux server `tmux -L vps-workspaces`. Each terminal has its own session, rather than treating tmux's internal splits as cmux's layout. ttyd and native cmux attach to these same sessions. Closing a viewer disconnects a client, not the session. tmux uses the smallest attached client size, so narrower viewers can resize the common terminal.

The server does not start coding agents automatically. After a reboot, opening from the Mac recreates missing shells; the user resumes the desired agent conversation. Restarting the sharing service does not restart tmux.

## Browser pages

Native cmux owns the Mac browser panes and its ordinary SSH proxy. Web viewers receive independent iframes. The initial adapter maps localhost/127.0.0.1/::1 app origins to separate HTTPS subdomains under the workspace hostname. Keeping each app at the root of its own origin preserves absolute asset paths and separates app scripts from the terminal's origin. External HTTP(S) pages are embedded directly and must permit embedding; there is no browser stream or iframe-restriction bypass.

The web page uses the saved split tree. Resizing in the web UI affects only that viewer; publishing layout changes is an explicit Mac Save. Reload the saved layout to see a newer revision.

## Native relay routing

Each Mac attachment records that session's cmux relay context in a private `.route` file. A session-local `cmux` wrapper reads it afresh for each invocation. This addresses stale process environments without attempting to modify an already-running agent's environment. The most recent Mac attachment becomes the route for supported cmux commands.

This is not an expansion of cmux's permissions. The installed app rejects remote browser snapshot/URL commands. Local Mac browser automation remains cmux's own capability; remote agent browser automation is a known gap. No socket access mode is changed.

## Authentication and networking

Caddy terminates HTTPS and connects to an aiohttp Unix socket through an existing bind mount. ttyd uses separate private Unix sockets: no public ttyd listener. The web adapter checks a signed, expiring workspace cookie before serving the layout, terminal HTTP, terminal WebSockets, or local app proxies. Passwords are hashed with scrypt; secrets and relay records are outside the source tree with restrictive permissions.

Login requires a matching Origin, is rate-limited, and sets Secure/HttpOnly/SameSite cookies. WebSocket upgrades require an exact Origin match. Workspace credentials are stripped before proxying to apps. The web API has no shell-command, arbitrary upstream, workspace-write, or session-creation endpoint.

This first version has one shared deployment password and does not provide individual accounts, read-only viewer roles, audit trails, or per-person revocation. Anyone with the password can access a known workspace link and control its terminal as the shared Unix user. This is a trusted-collaborator tool, not tenant isolation. Password/key rotation affects new HTTP connections; already-open WebSockets must be disconnected separately.
