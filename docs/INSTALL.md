# Install

## Prerequisites

- macOS with cmux installed at `/Applications/cmux.app`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) on both machines for Python 3.12 and locked dependencies.
  Existing Mac commands also work with system Python 3.9 because those entry points use the standard library.
- Linux VPS with SSH keys, Python 3.12, tmux, systemd user services, and a `~/Coding` directory.
- DNS resolving the workspace domain and its subdomains to the VPS, with ports 80/443 reachable for Caddy's automatic TLS certificates. Explicit hostnames are generated, so a wildcard TLS certificate is not required.
- Existing rootless Docker Caddy deployment: container `caddy`, `~/deploy/caddy/sites` mounted at `/etc/caddy/sites` and imported by `/etc/caddy/Caddyfile`, `~/deploy/www` mounted at `/srv`. Caddy must run as the same host user through rootless Docker to read the private Unix socket. Adapt these paths in `vps_workspaces/remote.py` and `vps_workspaces/server.py` for other installations.

The initial adapter intentionally builds on an existing reverse proxy instead of taking over ports 80/443 or replacing server configuration.

## VPS setup

Install terminal persistence and Python support:

```sh
sudo apt-get install tmux
mkdir -p ~/.local/share/vps-workspaces/app ~/Coding
```

Copy this repository into `~/.local/share/vps-workspaces/app` on the VPS, excluding `.git`, `.venv`, and private artifacts. Then:

```sh
cd ~/.local/share/vps-workspaces/app
UV_PROJECT_ENVIRONMENT=../venv uv sync --locked --no-dev
python3 ~/.local/share/vps-workspaces/app/workspace.py install server --base-domain workspaces.example.com
```

For user services to survive logout, enable lingering for your VPS account if not already enabled:

```sh
sudo loginctl enable-linger "$USER"
```

Configure SSH liveness on the VPS so abandoned connections release cmux's reverse
ports after sleep or a network change. On Ubuntu with `sshd_config.d` enabled:

```sh
sudo install -m 644 deploy/ssh/40-workspace-liveness.conf /etc/ssh/sshd_config.d/
sudo sshd -t && sudo systemctl reload ssh
sudo sshd -T | rg clientalive
```

Back up an existing file at that path before replacing it. The effective settings
must be `clientaliveinterval 10` and `clientalivecountmax 2`; an earlier directive
or a `Match` block can override them. This leaves margin under cmux's 60-second
relay readiness deadline. Reloading applies to new SSH connections only. Let
existing transports reconnect naturally; exiting a shared master interrupts
every viewer using it, even though persistent remote agents survive.

Install [code-server](IDE.md) and [HAPI](HAPI.md) before creating HAPI-backed workspaces.
For the default new-workspace flow, create a VPS project directory and run `workspace.py new`
from a local Mac cmux shell after completing Mac setup.

Alternatively, import the example layout (edit its preview URL and working directory first):

```sh
python3 ~/.local/share/vps-workspaces/app/remote.py save < examples/demo.json
python3 ~/.local/share/vps-workspaces/app/remote.py prepare demo
```

This validates/reloads Caddy after adding explicit workspace and app hostnames. No existing sites are overwritten. Retrieve the complete private sharing URL with `python3 ~/.local/share/vps-workspaces/app/remote.py link demo`. No password is required.

## Mac setup

Configure a working SSH alias (`myvps` by default). Include `ServerAliveInterval 15`,
`ServerAliveCountMax 3`, and `ConnectTimeout 15` in that host's SSH configuration,
including any separate administrative alias. Keep existing identity and host-key
settings. Client checks detect a lost server; the server checks above reclaim
abandoned reverse ports. Neither replaces the other. The `install mac-access`
tunnel already specifies its own liveness checks and disables multiplexing.

Leave `ControlMaster`, `ControlPath`, and `ControlPersist` unset on the cmux host
alias so cmux can manage and recover its own shared connection. If administrative
SSH uses multiplexing, give its separate alias a different `ControlPath`.
cmux deliberately does not reap user-managed sockets. Existing workspaces may
retain their saved options; do not interrupt them just to apply this change.

From a **local** terminal in cmux, in this repository:

```sh
uv sync --locked
uv run workspace.py install cmux
python3 workspace.py open demo
```

The new native workspace has the saved panes; start your agent inside its terminal. Opening the same saved workspace on another Mac attaches to the same tmux process. To use a different SSH alias:

```sh
VWS_SSH_HOST=devbox python3 workspace.py open demo
```

The shell integration below saves pane arrangement, tab order, selected tabs and browser
URLs automatically after a short debounce. Manual save is also available:

```sh
python3 workspace.py save demo
```

Run `python3 workspace.py persistence install` on the VPS and Mac to make ordinary new workspaces and bash terminal tabs persistent automatically. The Mac requires cmux Automation socket access. `add-terminal` remains available for explicitly named terminals. Browser panes use ordinary cmux controls.

## Share

Run `python3 workspace.py link demo` and open the complete HTTPS URL. Anyone with that link joins automatically. The link remains stable across saves. Use **VPS Workspaces: Copy Sharing Link** in the IDE command palette to share it again; the address bar no longer contains the access key after joining. Browser pages must allow iframe embedding. An agent started outside the managed tmux session must be stopped/resumed there deliberately.

## Uninstall

Stop/disable `vps-workspaces.service`, remove only `~/deploy/caddy/sites/vps-workspaces.caddy`, then validate/reload Caddy. Keep the private state directory for recovery until you no longer need it. tmux terminals are independent; detach them normally and stop them only when their work is finished.

Code-server is required for the browser workspace. Caddy forwards IDE and preview traffic directly, using `forward_auth` against the sharing-link service. Preview localhost ports are bridged into the existing `/srv` mount by standard systemd socket proxies.


## Source checkout versus installed application

Clone the public repository on the Mac and copy it to the VPS installed-app directory.
If you synchronize the checkout with Mutagen, both machines already see source changes;
keep the VPS installed application separate so changes are reviewed before becoming live.
Exclude `.git`, `.venv`, `node_modules`, caches and private artifacts from deployments.
The committed extension bundle does not require Node dependencies on the deployed runtime.

The persistence installer sources the shell integrations and installs the Mac launchd worker.
See [autosave](AUTOSAVE.md) and [maintenance](MAINTENANCE.md) for behavior and verification.
Optional VPS-to-Mac administration uses `workspace.py install mac-access` on the Mac;
it is not required to open a workspace or copy its link.
