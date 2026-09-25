# Maintenance

## Find the installation

| Item | Location |
|---|---|
| Shared source checkout | Wherever you cloned this repository; this installation uses `~/Coding/vps-workspaces` |
| Installed VPS application | `~/.local/share/vps-workspaces/app` |
| VPS workspace registry and link key | `~/.local/share/vps-workspaces` |
| Mac layout bindings, autosave status and recovery drafts | `~/.local/state/vps-workspaces` |
| Backup configuration and completion records | `~/.local/state/vps-workspaces-backup` |
| User service definitions | `~/.config/systemd/user` on Linux |
| Native cmux actions | `~/.config/cmux/cmux.json` on the Mac |
| Private installation-specific runbook, if present | `~/.local/state/vps-workspaces/OPERATIONS.md` |

In this installation, Mutagen synchronizes `~/Coding` bidirectionally between the Mac
and VPS. Edits, moves and deletions can propagate; these are not independent checkouts.
Check synchronization status and conflicts before editing another machine's copy.
Mutagen source synchronization does not deploy the installed VPS application or merge running
process state. Do not copy private registry or Codex SQLite files into the source checkout.

## Everyday commands

Run native workspace commands in a **local Mac terminal inside cmux**:

```sh
python3 workspace.py new my-project --cwd '~/Coding/my-project'
python3 workspace.py open my-project
python3 workspace.py link my-project --copy
python3 workspace.py save my-project
python3 workspace.py autosave-status
```

`new` provisions the browser IDE and creates an official native Codex conversation. The
VPS directory must exist. It prints the sharing link after setup succeeds. `open` attaches
another viewer of the same thread. See [native Codex](CODEX.md) for daemon lifecycle,
legacy migration, and the distinction between shared tmux shells and native agent clients.

Install native palette actions with `python3 workspace.py install cmux` on the Mac:

- **New VPS Workspace** asks for a name and creates a managed workspace.
- **Copy Browser Workspace Link** copies the current managed workspace's link. cmux's native action
  opens a short-lived terminal tab; the command copies through macOS or native OSC 52 clipboard
  handling and closes only that helper tab. It never types a command into an agent prompt.
  Link lookup retains the initial relay identity after terminal recovery; new relay records
  also retain their owning workspace name, independently of the current pane layout.

Press Cmd+Shift+, to reload cmux configuration if installation was performed over SSH.
This installed-version integration has been source-checked; the deployment verification
record identifies any local palette tests still pending.
Browser workspaces open with the file sidebar collapsed; toggle it normally from VS Code when needed.

With `persistence install` enabled, ordinary new cmux workspaces become remote at their first
prompt. Existing running local processes are never forcibly migrated. See [autosave](AUTOSAVE.md).

## Diagnose a problem

```sh
python3 workspace.py doctor --json
python3 workspace.py codex list
systemctl --user status vps-workspaces.service
systemctl --user status vps-ide-my-project.service
journalctl --user -u vps-workspaces.service -n 50
journalctl --user -u vps-ide-my-project.service -n 50
```

`doctor` reports registry and service/socket health without printing link keys. An active
service is not a complete browser test: also open the actual link and verify its terminal
and preview content. On the Mac, `doctor` reports cmux access and saved autosave status.

| Symptom | Check / action |
|---|---|
| IDE unavailable | `python3 workspace.py install ide my-project` on the VPS; inspect its user service |
| Wrong preview app | Check the saved URL **and** the service owning that port on the VPS |
| Autosave conflict | Inspect `autosave-drafts`; reopen the latest workspace, or explicitly use `keep-local` after reviewing both layouts |
| Access denied from cmux | Run the command in a local cmux shell; SSH ancestry does not satisfy its access policy |
| Missing agent after reboot | Inspect `vws-codex.service`, then reopen the saved workspace to resume its native thread |
| Agent terminal vanished after SSH reconnect | From a local cmux shell, inspect `cmux ssh-session-list --all-workspaces` and use `cmux ssh-session-attach --session-id ID --workspace WORKSPACE` to reattach the existing PTY |
| Linux sandbox namespace failure | Check the installed distribution's AppArmor bubblewrap profile; preserve global restrictions |

Do not use `keep-local` merely to silence an error. Browser storage and draft text are not
part of layout autosave. The backup configuration is authoritative for snapshot locations.

Autosave discovers managed native Codex clients and tmux shells, including native SSH sessions reattached under
new surface IDs. It registers new remote workspaces automatically. Terminal removals save after
ten seconds with a recovery copy; transient connection errors retry before notifying. Genuine
revision conflicts retain drafts and never overwrite another viewer. The Mac launchd worker is
`com.drpod.vps-workspaces-autosave`; its log and status are in the Mac state directory.

## Update or roll back

1. Read `AGENTS.md`, inspect the working tree, and run the development checks.
2. Back up the installed app, affected registry documents, Caddy site and service definitions.
3. Copy only the application files into the installed VPS app. Exclude `.git`, environments,
   dependency caches and private artifacts. Keep the source checkout separate.
4. In the installed app, run `UV_PROJECT_ENVIRONMENT=../venv uv sync --locked --no-dev`.
   Re-run the relevant installer after changing unit definitions, then reload systemd.
5. Restart the gateway only for gateway changes. Reload a browser window for extension changes.
   IDE restarts disconnect viewers; they should not stop shared agent engines or tmux sessions.
6. Verify unauthenticated requests are rejected, a valid sharing link opens its IDE, previews
   serve the right apps, and existing agents still have the same session identities.
7. To roll back, restore the affected app/config backup, reload systemd and Caddy as needed,
   and restart only the services changed by the deployment.

Changes under `vps_workspaces/` need the same package on both source and installed copies.
`workspace.py` and `remote.py` are intentionally small, stable entry points.

## Reconfigure or extend

- Set `VWS_SSH_HOST` on the Mac to choose its VPS SSH alias.
- `install server --base-domain ...` sets the domain for **new** workspace records; changing
  existing public hostnames requires editing their registry records and rebuilding Caddy routes.
- `install ide NAME` is idempotent and preserves existing VS Code settings.
- `install backups ROLE` retains the configured snapshot location and additional SQLite roots.
- `codex list` lists native conversations. Legacy HAPI migration needs an idle old engine;
  follow [native Codex](CODEX.md) and the private installation runbook.
- Prefer native Caddy, systemd, rsnapshot, Codex and cmux features over another custom service.
  Record upstream versions, links, licenses and adaptations in the relevant NOTICE/docs.

The current backend expects Linux systemd, the documented rootless Caddy arrangement,
and the pinned Linux amd64 code-server release and official Codex daemon. It is not a universal installer.
Workspace capability links grant a terminal under the VPS user; they are intended for
trusted collaborators, not isolation between untrusted users.

## Move or retire a server

Follow the [migration and retirement checklist](MIGRATION.md) before cancelling a host.
It covers state outside the source checkout, final database exports, external routes and
verification with the old server offline. Keep the actual recovery report private.

## Optional media stack

See [media services](MEDIA.md) for the independent Compose stack, private access, storage,
VPN verification and playback. Media runtime state belongs outside the synced checkout.
