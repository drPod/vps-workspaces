# code-server workspace

The same sharing URL now opens a full VS Code workbench for workspaces with the IDE enabled. Native cmux remains another client of the same tmux sessions. Open the link in an ordinary browser or in a cmux browser pane.

## Use

- Open the complete sharing link. No separate code-server password is required.
- The file explorer shows the saved terminal working directories. Terminals and browser previews occupy the imported editor groups.
- Use normal VS Code tab dragging, splitting, maximizing, search, and file editing.
- Run **VPS Workspaces: Open Saved cmux Layout** from the command palette to reimport the latest saved layout.
- Run **VPS Workspaces: Copy Sharing Link** to share the complete link.
- Reload reimports the saved cmux layout. IDE rearrangements are not written back to cmux.
- `/classic/` keeps the original ttyd-based page available.

Browser views are independent. Shared terminals still accept input from every attached client. Closing a terminal tab disconnects its tmux attachment; it does not start or stop the agent inside tmux. VS Code may hold a disconnected browser's terminal attachment for the configured reconnection grace period.

## Install on the VPS

First install the base gateway and save a workspace as described in INSTALL.md. This initial installer pins Linux amd64 code-server 4.138.0. For other platforms use an appropriate official release and adapt the binary path.

```sh
mkdir -p ~/.local/lib
curl -fL https://github.com/coder/code-server/releases/download/v4.138.0/code-server-4.138.0-linux-amd64.tar.gz -o /tmp/code-server.tar.gz
tar -xzf /tmp/code-server.tar.gz -C ~/.local/lib
python3 ~/.local/share/vps-workspaces/app/install-ide.py demo
systemctl --user restart vps-workspaces.service
```

The installer creates `vps-ide-demo.service`, private files under `~/.local/share/vps-workspaces/ide/demo`, and a `demo.ide` gateway marker. It does not change the saved cmux layout or restart tmux. The installer is safe to rerun; restart the IDE service explicitly if changing its generated configuration.

code-server listens only on a mode-600 Unix socket. `--auth none` is used behind the existing authenticated gateway, not on a public port. Both HTTP and WebSocket paths require the workspace cookie. Its generic port proxy is disabled because preview routing is already provided by the workspace gateway.

## Build the adapter

The built bundle is committed for deployment. Rebuild after changing extension source:

```sh
cd ide-extension
npm ci --ignore-scripts
npm test
npm run build
```

The small adapter uses existing extension source; see NOTICE.md in that directory. The remaining custom integration is saved-layout translation, stable tmux identities, and sharing-link access. No separate frontend framework is introduced.

## Revert the web entry

Remove only the workspace's `.ide` marker to return its sharing link to the original web page. Stop its `vps-ide-<name>.service` to release the IDE processes. The tmux agent is independent and continues running.
