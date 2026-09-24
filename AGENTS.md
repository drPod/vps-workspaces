# Working on VPS Workspaces

## Start here

Read [README.md](README.md), then [docs/MAINTENANCE.md](docs/MAINTENANCE.md).
This repository integrates upstream cmux, HAPI, tmux, code-server and Caddy.
It does not implement a terminal emulator, an IDE, or a browser engine.

Run `python3 workspace.py --help` for the main CLI and
`python3 workspace.py doctor --json` for the local installation's health report.
Run Mac workspace commands in a local cmux terminal; SSH access alone does not
satisfy cmux's “processes started inside cmux only” policy.

## Code map

| Location | Responsibility |
|---|---|
| `workspace.py` | Main CLI entry point |
| `remote.py` | Stable SSH entry point; delegates to the package |
| `vps_workspaces/cli.py` | Command dispatch |
| `vps_workspaces/workspace.py` | Native cmux layouts and link actions |
| `vps_workspaces/remote.py`, `registry.py` | VPS registry, provisioning and terminal attachment |
| `vps_workspaces/contracts.py`, `model.py` | Types and runtime document validation |
| `vps_workspaces/autosave.py` | Native layout snapshots, debounce and conflicts |
| `vps_workspaces/hapi.py`, `hapi_bridge.py` | HAPI binding and official CLI attachment |
| `vps_workspaces/server.py`, `sharing.py`, `caddy_routes.py` | Link authentication and Caddy configuration |
| `vps_workspaces/ide.py`, `ide-extension/` | code-server setup and VS Code layout adapter |
| `vps_workspaces/backup.py`, `install/` | SQLite preparation and standard service installers |
| `vendor/`, `ide-extension/vendor/` | Attributed upstream code; preserve notices and licenses |
| `tests/` | Python regression and integration checks |

## Working rules

- Reuse upstream commands, libraries and configuration before adding custom machinery.
  Record the actual reuse and any compatibility changes in the relevant NOTICE or docs.
- Use `uv` and the committed lockfile; `.venv` is machine-local, never synchronized.
  Match the 120-column Ruff rules in pyproject.toml (shared with Sixtyfive). Keep helpers
  compact and direct; introduce an object only when it owns meaningful state.
- Type project-owned code. Use objects where they group real state or responsibilities.
  Keep comments and docstrings only for non-obvious constraints. Preserve upstream attribution.
- Never overwrite unrelated working-tree edits or publish runtime files, credentials,
  capability links, relay tokens, session databases or personal job configurations.
- The source checkout and installed VPS app are separate. Editing the checkout does not
  deploy it. In this installation, `~/Coding` is synchronized bidirectionally between
  the Mac and VPS by Mutagen, including this checkout. Edits, moves and deletions can
  propagate. Check synchronization status and conflicts before modifying both copies.
- Back up affected runtime configuration before deployment. Validate Caddy before reloading.
  Restart only affected services, and keep a concrete rollback path.
- Do not stop a HAPI-owned agent to refresh an IDE or native viewer. A viewer attachment
  and the shared agent are different processes. Never run concurrent copies of a migrated thread.
- Preserve optimistic revision checks and recovery drafts. Do not “fix” a save conflict by
  silently forcing a revision or replacing another viewer's state.
- Layouts save URLs and proportions, not browser cookies, forms, localStorage or drafts.
  A matching localhost port on two machines does not establish that they serve the same app.
- A sharing link grants a code-server terminal under the VPS user. It is for trusted
  collaborators; it is not isolation from other files or processes owned by that user.
- Keep backups unencrypted unless the user changes that requirement. Preserve configured
  backup locations and extra sources when reinstalling or updating.

## Checks

Use `uv sync --locked`, then run:

```sh
uv run mypy
uv run ruff check
uv run ruff format --check
uv run python -m unittest discover -s tests -v
cd ide-extension
npm ci --ignore-scripts
npm test
```

The extension bundle is committed. Rebuild it when its source changes. Test new behavior
with focused regressions; use a disposable workspace for lifecycle or deployment checks.
After deployment, verify actual sharing-link authentication, IDE access, preview identity,
existing agent continuity and Mac behavior. Report unverified steps explicitly.

## Local installation details

The public repository is the reusable implementation. When present, read
`~/.local/state/vps-workspaces/OPERATIONS.md` for this machine's private deployment map,
current workspace ownership, service names and recovery notes. Do not publish that file.

## Optional media

The media stack and invitation launcher moved to [drPod/watch-link](https://github.com/drPod/watch-link).
Read that repository's AGENTS.md for media work. [docs/MEDIA.md](docs/MEDIA.md) keeps the handoff
and backup relationship. The private deployment remains `~/deploy/media-stack`; credentials
and media stay outside either checkout. Gluetun owns the VPN firewall.
