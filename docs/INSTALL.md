# Install

## Prerequisites

- macOS with cmux installed at `/Applications/cmux.app` and Python 3.10+.
- Linux VPS with SSH keys, Python 3.12, tmux, systemd user services, and a `~/Coding` directory.
- DNS resolving the workspace domain and its subdomains to the VPS, with ports 80/443 reachable for Caddy's automatic TLS certificates. Explicit hostnames are generated, so a wildcard TLS certificate is not required.
- Existing rootless Docker Caddy deployment: container `caddy`, `~/deploy/caddy/sites` mounted at `/etc/caddy/sites` and imported by `/etc/caddy/Caddyfile`, `~/deploy/www` mounted at `/srv`. Caddy must run as the same host user through rootless Docker to read the private Unix socket. Adapt these paths in `remote.py` and `server.py` for other installations.

The initial adapter intentionally builds on an existing reverse proxy instead of taking over ports 80/443 or replacing server configuration.

## VPS setup

Install terminal persistence and Python support:

```sh
sudo apt-get install tmux python3-venv
mkdir -p ~/.local/share/vps-workspaces/app ~/Coding
```

Copy this repository into `~/.local/share/vps-workspaces/app` on the VPS, excluding `.git`, `.venv`, and private artifacts. Then:

```sh
python3 -m venv ~/.local/share/vps-workspaces/venv
~/.local/share/vps-workspaces/venv/bin/pip install -r ~/.local/share/vps-workspaces/app/requirements.txt
python3 ~/.local/share/vps-workspaces/app/install-server.py --base-domain workspaces.example.com
```

For user services to survive logout, enable lingering for your VPS account if not already enabled:

```sh
sudo loginctl enable-linger "$USER"
```

Create the example workspace (edit its preview URL and working directory first):

```sh
python3 ~/.local/share/vps-workspaces/app/remote.py save < examples/demo.json
python3 ~/.local/share/vps-workspaces/app/remote.py ensure demo
```

This validates/reloads Caddy after adding explicit workspace and app hostnames. No existing sites are overwritten. Retrieve the complete private sharing URL with `python3 ~/.local/share/vps-workspaces/app/remote.py link demo`. No password is required.

## Mac setup

Configure a working SSH alias (`myvps` by default). From a **local** terminal in cmux, in this repository:

```sh
python3 workspace.py open demo
```

The new native workspace has the saved panes; start your agent inside its terminal. Opening the same saved workspace on another Mac attaches to the same tmux process. To use a different SSH alias:

```sh
VWS_SSH_HOST=devbox python3 workspace.py open demo
```

After rearranging panes or changing browser URLs:

```sh
python3 workspace.py save demo
```

Add terminal panes through `add-terminal` so they get persistent session identities. Save rejects unmanaged terminals rather than quietly publishing a different process. Browser panes can be added using ordinary cmux controls.

## Share

Run `python3 workspace.py link demo` and open the complete HTTPS URL. Anyone with that link joins automatically. The link remains stable across saves. Use **Copy sharing link** in the page to share it again; the address bar no longer contains the access key after joining. Browser pages must allow iframe embedding. An agent started outside the managed tmux session must be stopped/resumed there deliberately.

## Uninstall

Stop/disable `vps-workspaces.service`, remove only `~/deploy/caddy/sites/vps-workspaces.caddy`, then validate/reload Caddy. Keep the private state directory for recovery until you no longer need it. tmux terminals are independent; detach them normally and stop them only when their work is finished.

Code-server is required for the browser workspace. Caddy forwards IDE and preview traffic directly, using `forward_auth` against the sharing-link service. Preview localhost ports are bridged into the existing `/srv` mount by standard systemd socket proxies.
