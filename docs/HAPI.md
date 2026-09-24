# HAPI, cmux and code-server

The upstream HAPI 0.30.7 application is installed separately, without copying its AGPL implementation into this MIT repository. Its Hub provides the full Web/PWA app and native-app API; its Runner starts background-owned Codex sessions. Caddy serves HTTPS through systemd's Unix-socket proxy. HAPI keeps its own authentication.

## Everyday use

- Open the HAPI app to start sessions, send messages, review tool activity and answer approvals/questions. The application uses the configured VPS agent credentials.
- The **HAPI Sessions** button in code-server opens the app. From your Mac, `python3 ~/Coding/vps-workspaces/workspace.py hapi-link` prints the authenticated owner link. This is an owner-wide HAPI link, distinct from a workspace sharing link.
- Use HAPI Settings' companion pairing for native clients. The native applications are upstream software; this integration does not install or sign an iOS/Android app on your phone.
- On the VPS, `~/.local/bin/hapi resume <hapi-session-id>` attaches the official Codex terminal frontend. Each frontend owns its own terminal dimensions; the shared agent engine runs once.
- A saved terminal with `hapi_session` opens this same attachment in cmux, code-server and the fallback ttyd page. Other terminals continue to use tmux.
- Exiting an attached frontend detaches it. Runner-owned sessions remain running without a viewer. Archiving a session in HAPI ends it; reopening resumes saved history. A VPS reboot ends processes, so reopening resumes rather than restoring process memory.

## Installation

On the existing supported Linux amd64 VPS deployment:

```sh
python3 install-hapi.py --host hapi.example.com
```

This installs the pinned official npm package and configures `hapi-hub.service`, `hapi-runner.service`, `hapi-proxy.socket` and a separate Caddy route. Secrets remain under `~/.local/share/vps-workspaces/hapi/`, with private permissions. No relay provider or Telegram account is required. Runner browsing/spawning is restricted to `~/Coding`.

## Connect a saved pane

Run these on the VPS, using IDs from your saved workspace and HAPI:

```sh
python3 ~/.local/share/vps-workspaces/app/hapi-workspace.py list
python3 ~/.local/share/vps-workspaces/app/hapi-workspace.py bind demo agent HAPI_SESSION_ID
# Or create a new Runner-owned Codex session for an idle saved terminal:
python3 ~/.local/share/vps-workspaces/app/hapi-workspace.py new demo agent
```

Then reopen the saved workspace on the Mac or reload code-server. Binding refuses to replace a terminal with a running program. The registry revision changes, so an older native workspace's autosave will pause if it attempts to overwrite the new binding.

## Existing conversations

HAPI cannot hot-migrate a legacy Codex process. Exit the old agent normally first. From its VPS shell, run:

```sh
python3 ~/.local/share/vps-workspaces/app/hapi-workspace.py migrate demo agent NATIVE_CODEX_THREAD_ID
```

The importer starts the ordinary upstream HAPI wrapper in a systemd-owned execution and records the HAPI session ID after it becomes active. Subsequent cold resumes use HAPI's Runner. It does not kill the original agent. The default permission is `default`; use `--permission read-only` or `--permission yolo` only when desired. HAPI rejects some native profile/worktree flags and concurrent rewind; see its [shared-session boundaries](https://hapi.run/docs/guide/codex-shared-sessions).

## Verification and limits

On the installed package with VPS Codex 0.156.1:

- Real web message/response, simultaneous official terminals at 140×42 and 80×24, independent resize to 100×36, and detach with no viewers passed.
- Runner restart and Hub restart preserved the existing agent. Cold resume restored the same native conversation and history after the Runner re-registered its RPC handlers. Immediately resuming during Hub reconnection can return a temporary RPC-not-registered error; retry after the Runner is online.
- Actual code-server displayed the Codex conversation and both app/report previews; reload retained three tabs after cleaning up restored preview tabs. Two browser clients, resizing, sharing and unauthenticated rejection passed.
- Stock upstream full-stack tests are **not** all passing in this environment: Mac primary-exit timeout, Linux per-root shell-identity timeout. These failures are recorded rather than hidden; production validation uses Runner-owned executions and the installed package.
- Remote cmux browser automation remains denied by cmux's existing relay policy. Ordinary native cmux controls and browser views are unchanged.
- The original Outreach agent was not automatically stopped or migrated. New HAPI sessions and the integration-check workspace use the new path.
