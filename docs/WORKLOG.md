# Implementation log

## 2026-09-23

1. Reconstructed the agreed requirements from the full conversation: native Mac panes, VPS-owned persistent terminals, explicit Save/Open, independent browsers at saved URLs, and an embedded web view per workspace.
2. Inspected cmux Remote tmux source, its session-environment propagation, layout representation, CLI creation commands, and remote relay authorization. Also inspected ttyd and Session Deck before choosing the smaller adapter.
3. Queried the installed cmux 0.64.25 from an authorized local cmux terminal. Confirmed the live API exposes nested split ratios and current browser URLs. Kept the existing socket access policy.
4. Added SSH-only revisioned workspace storage, a dedicated tmux server, native Open/Save scripts, and a session-local cmux routing wrapper.
5. Installed packaged ttyd, disabled its default listener, and used per-session private sockets instead. Integrated HTTPS through the already-running Caddy container without replacing its sites.
6. Added the small split-tree webpage using upstream Split.js and ttyd's unmodified client. Local app origins get authenticated subdomains, preserving root-relative resources.
7. Confirmed the native three-pane workspace through live execution and a user screenshot. Confirmed both actual report/app pages render in browser iframes.
8. Browser testing caught GET requests being forwarded with an unnecessary chunked body; fixed forwarding to send a body only when the incoming request has one. Retest verified terminal input reaches the shared tmux shell.
9. Tested remote browser commands explicitly. The installed cmux relay denied `browser.snapshot` and `browser.url.get`. Recorded this as a capability gap, not a solved feature; did not bypass the relay's policy.
10. Added tests for authentication, expiry/tampering, workspace isolation, unknown upstream rejection, WebSocket origins, and invalid session IDs/URLs. Prepared native Save/Open verification and a public repository with upstream PR references.

11. Native Save/Open verification passed with a second cmux workspace. User completed the stop/resume handoff; verified the intended agent is now running inside the managed terminal.

12. Replaced the password screen with per-workspace capability links at the user’s request. Added a same-origin link exchange, secure session cookies, and a Copy sharing link button. The key stays out of HTTP request URLs and is removed before loading iframes.

13. Changed Add Terminal to reserve the tmux identity first, then publish the actual native layout only after pane creation. Added failure/retry tests and Caddy rollback coverage.
14. Confirmed that Session Deck contributes no source or frontend dependency; retain its link only as research provenance. Live passwordless sharing passed in two isolated Chromium browser contexts.

15. Compared complete frontend applications after feedback on the custom web page. Recorded source-level findings for code-server/VS Code, JupyterLab, Wave Terminal, and the archived Cloud9 SDK in FRONTEND-RESEARCH.md. Recommended evaluating code-server as a complete application; no replacement has been deployed.

16. User selected a full browser IDE, preferring Zed if available. Checked Zed's supported platforms and remote-development model; no supported browser-hosted edition found. Installed code-server 4.138.0 on the VPS.
17. After user steering, inspected existing Workspace Layout, Restore Terminals, Terminal Keeper, and Microsoft browser-preview implementations before continuing the integration. Adapted Workspace Layout's terminal code and reused Microsoft's preview view/assets with licenses.
18. Enabled code-server behind the existing passwordless gateway and private Unix socket. Imported Outreach as three VS Code editor groups without restarting its tmux agent. Verified reload, resizing, two viewers, copied links, and unauthenticated rejection. Native cmux access remains available.

19. User identified tmux padding dots in a larger IDE pane. Changed managed windows from smallest-client sizing to latest-active-client sizing. This uses tmux itself; terminal rendering remains VS Code. A shared PTY still has one size at a time.

20. Investigated independent per-viewer Codex rendering through HAPI shared sessions. Inspected its official-TUI attachment and runtime source, confirmed installed Codex remote support, and ran isolated mock-model integration tests. Protocol tests passed and differently sized secondary attachment/detach worked; the full lifecycle test exposed a primary-terminal exit timeout. Recorded findings and migration constraints in [shared-agent research](SHARED-AGENT-RESEARCH.md). Production remains unchanged.

21. Installed the complete official HAPI 0.30.7 package, Hub and supervised Runner behind Caddy using systemd's socket proxy. Added narrow workspace/session binding and import commands, independent native/IDE/fallback terminal attachment, and an IDE HAPI-app button. The original Outreach agent remains untouched pending its normal stop/resume handoff.
22. Verified real HAPI web messaging, two native terminal sizes and independent resize, disconnect with no viewers, Runner/Hub restarts, and cold resume of a disposable conversation. Verified the actual code-server terminal with both previews and fixed duplicate restored preview tabs. Raised the VPS inotify limits after the second IDE exposed file-watcher exhaustion.
23. Added debounced native cmux autosave, per-instance state, conflict rejection, local recovery drafts and a Mac shell startup hook. User sourced the hook inside cmux; confirmed the running watcher sees Outreach. Manual Save and explicit keep-local conflict resolution remain available.
24. At the user's request, configured ordinary unencrypted rsnapshot backups on VPS and Mac. No encrypted backup repository was created. SQLite online backups precede snapshots; restore checks passed for HAPI, Codex history and Outreach layout on the VPS. Preserved raw files for an already-corrupt unrelated project database. Mac initial transfer and storage relocation are verified separately before declaring the backup rollout complete.

25. Migrated the original idle Outreach conversation after explicit authorization, verified its native identity and latest HAPI history, and retested the existing IDE link.
26. Completed the first Mac snapshot and verified 42 restored SQLite copies plus local/VPS files. Fixed remote-only rsync options, first-run retention initialization, and selected GNU rsync after detecting incompatible multi-source deletion behavior in system openrsync. Verified with real two-snapshot regression coverage. Relocated the VPS snapshot store to the larger filesystem and removed the verified redundant copy.
27. Connected the Mac to the existing HAPI Hub. After user feedback, removed the custom Mac installer and wrapper, used upstream HAPI settings and Runner startup, and documented a repository-wide custom-code audit in REUSE-AUDIT.md. Automatic inclusion of all new Codex conversations and native-store synchronization remain unfinished; two registered Runners alone do not implement them.

28. Completed the reuse audit follow-up: replaced aiohttp transport with Caddy reverse_proxy/forward_auth, used standard systemd socket proxies for host-loopback previews, and deleted the classic frontend/ttyd manager. Verified live auth boundaries, credential stripping, previews, code-server WebSockets, reload and two viewers.
29. Configured fresh interactive Mac/VPS shells to delegate coding sessions to upstream HAPI, keeping native management commands available. Verified both machines' real prompts/replies in the shared app, normal exit and Mac cold resume. Documented that shared app access does not merge native databases or move execution between machines.


### 2026-09-24 — Correct migrated preview ownership

Outreach's port 8765 incorrectly served the sixtyfive Hex founder dashboard. Conversation provenance placed the dashboard with the product-analytics work. Among the open workspaces, Autumn user tiers is the closest match for product analytics and Hex work.

- Moved `preview-sixtyfive-hex.service` to loopback port 8787 using its existing `HEX_APP_PORT` option.
- Enabled stock Python HTTP serving of `ss-outreach/post-studio` on loopback port 8765 through `post-studio.service`.
- Corrected Outreach's saved preview title and added the founder dashboard to Autumn user tiers. Updated the integration fixture's analytics URL.
- Backed up affected workspace records and the original analytics unit before changing routing.
- Verified both applications respond and the authenticated public Outreach preview serves Post Studio.

Existing Mac panes need refreshing; adding the analytics pane requires loading the updated saved layout. VPS-to-Mac SSH is currently unavailable. Post Studio drafts remain in each browser's storage; serving the app on the VPS does not migrate browser drafts.

### 2026-09-24 — Typed package, upstream actions and deployment

- Organized the Python integration into a typed package with stable workspace.py/remote.py entry points, service templates and a documented code map.
- Adopted uv project dependencies and uv.lock; matched Sixtyfive's 120-column Ruff rules and checked every owned Python file, including tests.
- Used the upstream standalone cmux JSONC settings editor for native New VPS Workspace and Copy Workspace Link actions. Kept its license and documented the installed-version compatibility patch.
- Added Zod validation and strict TypeScript checks; retained attributed Simple Browser and Workspace Layout code.
- Fixed selected-tab restoration without reordering browser tabs, stale PID reuse during viewer cleanup, and IDE readiness checks against actual socket connections.
- Preserved backup destinations and extra database roots during installer updates. Added atomic JSON replacement and focused failure regressions.
- Backed up and deployed the package; updated both backup installations. All six HAPI engine PIDs remained unchanged.
- Resolved a title-only registry conflict by comparing baseline layout fingerprints, backing up bindings and advancing only metadata. Observed native autosave save the user's two-browser-tab pane automatically.
- Verified an actual browser session opens the IDE, correct tab groups, report and Post Studio with no page errors. The replacement Mac autosave worker is running and watching all three open managed workspaces. Native palette click/clipboard confirmation remains pending.
- Added contributor/agent instructions and a private installation runbook outside Git. Mutagen synchronization is documented explicitly; the source and installed app remain separate.

### Palette label correction

The user confirmed the browser-link action works, but reported two identically named commands.
Installed cmux source confirms its own Copy Workspace Link command copies a native navigation
link. Renamed this integration's action to **Copy Browser Workspace Link**; its action ID and
behavior are unchanged. The native command remains available.
