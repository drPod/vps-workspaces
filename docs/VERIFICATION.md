# Verification

## Verified in the live initial deployment

- Installed cmux **0.64.25 (106)** exposes the full tree and browser URLs.
- Native Open produced a terminal on the left and two working native browser panes on the right, matching the existing workspace.
- Caddy serves the workspace over valid HTTPS; the full sharing link joins without a password. Requests for terminal or workspace data without an access cookie are rejected.
- A real Chromium browser joined, loaded the report and app in distinct iframe origins, and connected to ttyd.
- Keyboard input from the web terminal appeared in the same named tmux session used by native cmux.
- No browser page errors in that smoke test.
- Passwordless link entry, copying the full link, a second isolated viewer, and rejection of an invalid cookie passed a live Chromium check.
- Fourteen Python tests and four extension layout/URL tests cover authentication, validation, terminal reservation, and failed-publication recovery.
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

Run `workspace.py verify-native` in a local cmux terminal after opening the initial Outreach workspace. It performs Save/Open and checks topology and URLs without closing existing workspaces. Private results are written outside the repository.

## code-server integration verification

Code-server 4.138.0 / Code 1.138.0 was exercised in real Chromium at 1600×1000, 1440×900, and 1280×850. The same Outreach agent was visible beside two loaded app previews in three editor groups. Reload restored exactly three tabs. Two isolated browsers joined through the same passwordless link; closing one left the other working. Copy Sharing Link produced the original capability URL. Requests to `/ide/` without the workspace cookie returned 401. No page JavaScript errors were observed.

Screenshots were inspected locally and are not published because they contain workspace content. The pinned code-server build requests two missing optional `vsda` browser assets (404); the terminal, extension host, editor workbench, and previews still connected successfully. Native cmux's terminal process was not restarted. Actual terminal input in the live agent was intentionally not injected during the IDE smoke test.

Not yet exercised: IDE file-editing collaboration/conflict handling, arbitrary third-party extensions, two different physical Macs, or bidirectional synchronization of IDE layout changes back into cmux.

## HAPI, autosave and backups follow-up

- 24 Python tests and 4 extension tests pass, including conflict rejection across two locally edited workspace copies, refusal to bind over a running agent, and SQLite backup with committed WAL data. GitHub CI passed commit `1b69206`.
- Installed HAPI package: real web message/response, two official terminal sizes, independent resize, secondary/last-viewer detach, supervised Runner PID replacement without stopping the agent, Hub reconnect, and cold resume of the same native thread/history passed.
- HAPI code-server workspace: actual Codex output plus two live previews, three tabs after reload, two isolated viewers, resize and unauthenticated rejection passed. Existing Outreach repeated the browser checks successfully.
- Native autosave: user sourced the shell hook inside cmux; the watcher reported Outreach as watched before the user quit cmux; new local cmux shells start it again. Multi-copy conflict behavior is covered by tests; a physical second Mac was not available.
- VPS rsnapshot: first snapshot complete. Copied HAPI and Codex-history database snapshots to disposable restore locations and passed SQLite quick checks; restored Outreach JSON validated. The unrelated pre-existing `gradient-hackathon/data/swarmci.db` is corrupt and preserved as raw files with a recorded warning.
- Mac rsnapshot: first full snapshot published. Both local project files and the VPS workspace are present; 42 SQLite copies passed restore quick checks from the published snapshot. Homebrew Python and GNU rsync are required on this Mac. A real rsnapshot regression check verifies first-run publication, multiple source folders, and preservation of the prior version after a second snapshot.

- Original Outreach handoff: user authorized the idle native process to exit; HAPI resumed the same native thread. Its latest conversation messages were verified in the app. The existing IDE link passed reload, two viewers, both previews, sharing-link copying, and unauthenticated rejection again.

## Caddy transport and new-session follow-up

- 26 Python tests pass; the new auth tests cover Caddy's auth subrequest contract and preview scopes.
- Deployed Caddy `reverse_proxy`/`forward_auth`: Outreach passed real Chromium reload, exactly three tabs, two browser viewers, both actual previews, share-link copy, unauthenticated rejection and no page errors. Live HTTP checks rejected cross-origin/missing-origin WebSocket requests for the IDE and previews. A temporary echo upstream verified credential stripping and preservation of application cookies.
- Retired terminal route returns 404; `/classic/` redirects to the IDE. Layout-only saves skip unchanged Caddy routes.
- New `codex` sessions launched through fresh Mac zsh and VPS bash registered in HAPI. Native prompts received the expected replies, and both saved transcripts were inspected in Chromium. Both terminals exited normally; the Mac session cold-resumed through its Runner with the same native identity. Disposable verification sessions were archived afterward.
- This does not provide native database merging, automatic migration of a running agent, or automatic HAPI adoption of desktop-app/script/bypassed sessions.


## Package refactor verification (24 September 2026)

31 Python tests, strict mypy, the shared Ruff lint/format rules, six extension tests and
TypeScript checks passed. uv's locked environment was installed on Linux and macOS;
both uv and the dependency-free system-Python CLI help ran on the Mac.

Real Chromium opened the existing shared workspace with one terminal group and two browser
tabs in the other group. Saved tab order was retained; report and Post Studio loaded with
no page errors. Every HAPI engine kept its pre-deployment PID. Native autosave recovered
from a verified metadata-only revision conflict and saved the combined browser pane.

The Mac palette configuration validates and is installed. The replacement Mac autosave worker is running and watching the open managed workspaces.
The user confirmed the browser-link action copied successfully from local cmux. A naming
collision with cmux's built-in native-link action was corrected by renaming this action to
Copy Browser Workspace Link. Reload/restart cmux to load the distinct label.


A newly created disposable workspace provisioned its IDE and HAPI session successfully.
Two independently sized Chromium contexts attached; closing the first and reloading the
second retained the original engine PID and exactly one terminal tab. The disposable
workspace was removed and its empty HAPI conversation archived afterward. All six regular
workspace routes passed anonymous rejection, authenticated IDE/preview access and foreign-
origin WebSocket rejection. Fresh Mac and VPS snapshots completed; the known unrelated
corrupt SwarmCI database remains preserved raw with a warning, not reported as verified.
