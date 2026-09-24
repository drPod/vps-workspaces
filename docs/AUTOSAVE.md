# Native workspace autosave

Source `shell-integration.zsh` from the Mac's `~/.zshrc`. The installed setup does this automatically for new local cmux shells. For an already-open shell, source it once:

```sh
source ~/Coding/vps-workspaces/shell-integration.zsh
```

The watcher polls cmux once per second and saves after a layout change has settled for two seconds. It records splits/proportions, tabs/selection, browser URLs, workspace names, managed terminal identities and HAPI bindings. It ignores changing terminal/page titles and tiny split-ratio noise. It does not save browser cookies/forms/scroll positions, unsaved editor buffers or running process memory.

It runs as a descendant of the local cmux shell to respect cmux's control-access setting. If that shell closes, a later local cmux prompt starts a replacement. While no authorized watcher is running, changes are not automatically saved. The next watcher compares the current layout with the saved definition. This is native cmux autosave; code-server layout changes are not exported back.

Every opened native copy has its own tracked revision. Merely opening two copies is safe. If both edit, the first save wins and the other pauses rather than overwriting the newer version. A Mac notification and `autosave-status` show the conflict; a local draft preserves the observed layout under `~/.local/state/vps-workspaces/autosave-drafts/`.

```sh
python3 ~/Coding/vps-workspaces/workspace.py autosave-status
# Keep the VPS version by reopening it:
python3 ~/Coding/vps-workspaces/workspace.py open outreach
# Explicitly replace the VPS layout with the currently tracked local copy:
python3 ~/Coding/vps-workspaces/workspace.py keep-local outreach
# Manual save remains available:
python3 ~/Coding/vps-workspaces/workspace.py save outreach
```

`keep-local` is an explicit conflict resolution: it fetches the latest revision and still uses the server's revision check, so a further simultaneous save is rejected. For the same workspace open multiple times, the manual command targets the most recently opened tracked copy. Close an obsolete copy when choosing a winner.

Unmanaged terminal panes pause saving because they have no persistent VPS identity. Use `workspace.py add-terminal` for those. New browser panes can be saved directly. Conversation history is saved by Codex/HAPI independently of layout autosave. Save files normally in your editor; Git commits remain a separate action.
