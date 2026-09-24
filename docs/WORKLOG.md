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
