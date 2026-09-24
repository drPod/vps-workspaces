# Verification

## Verified in the live initial deployment

- Installed cmux **0.64.25 (106)** exposes the full tree and browser URLs.
- Native Open produced a terminal on the left and two working native browser panes on the right, matching the existing workspace.
- Caddy serves the workspace over valid HTTPS; unauthenticated page and terminal requests redirect to login.
- A real Chromium browser logged in, loaded the report and app in distinct iframe origins, and connected to ttyd.
- Keyboard input from the web terminal appeared in the same named tmux session used by native cmux.
- No browser page errors in that smoke test.
- Six automated tests cover authentication and validation boundaries.
- Native Save/Open reconstructed a second client workspace with the same split tree and two URLs (revision 2).
- The original agent was stopped normally and resumed inside the managed tmux terminal. Verified a single Codex conversation process with native/web access to its session.

## Not yet claimed

- A physical second Mac has not been exercised. The native verification script reconstructs a separate client workspace on the same Mac; it is not evidence of a physical two-machine test.
- The installed cmux SSH relay rejects browser snapshot and URL-read requests (`remote_relay_denied`). Refreshing connection metadata does not grant these commands. Full agent-driven native browser automation from the VPS is **not implemented** by this adapter.
- Arbitrary websites may reject iframes. Only the tested report/app are verified.
- Existing agents outside tmux require a deliberate stop/resume. The launcher does not terminate or duplicate them.

## Current scope limits

- Initially the first saved pane must begin with a terminal for ordinary cmux SSH bootstrap.
- Workspace files support terminal/browser tabs; unsupported pane kinds and unmanaged terminals fail explicitly.
- Explicit saves use revision checks; there is no live layout synchronization.
- Browser navigation after opening is independent. Only an explicit native Save updates portable URLs.
- App proxy support currently covers localhost origins, root-relative assets, HTTP requests and WebSockets. Site-specific cookie-domain/redirect behavior may need adaptation.
- VPS reboot does not preserve agent processes. Missing managed shells are recreated on native Open; agents are resumed manually.
- Most recent Mac attachment wins the routing context for supported cmux relay commands.
- Shared-terminal collaborators can type simultaneously; there is no input arbitration or read-only role.

## Reproduce checks

```sh
python3 -m unittest discover -s tests -v
```

Run `verify-native.py` in a local cmux terminal after opening the initial Outreach workspace. It performs Save/Open and checks topology and URLs without closing existing workspaces. Private results are written outside the repository.
