# Automatic persistence

With the base cmux/VPS installation complete, run `python3 workspace.py persistence install`
on both machines. The Mac must allow cmux **Automation** socket access: launchd cannot use
“processes started inside cmux only.” The installer does not weaken or change that setting.

On the Mac, the installer enables a launchd autosave worker and sources the zsh integration.
A normal new local cmux workspace becomes a native SSH workspace on the configured VPS at
its first shell prompt. New remote bash terminals attach to individual upstream tmux sessions
before accepting input. Existing HAPI agents are discovered and registered without spawning
another engine. Set `VWS_LOCAL=1` for a shell that should deliberately stay local.

Native cmux owns SSH reconnect and app-session restoration. The VPS owns tmux shells, HAPI
conversations and revisioned workspace definitions. Closing a viewer or sleeping the Mac leaves
VPS processes running. Closing a workspace keeps its saved definition; `workspace.py open NAME`
reopens it, including browser tabs. cmux's normal app relaunch restores its open SSH workspaces.
After a VPS reboot, shells can be recreated and HAPI can resume conversations; arbitrary process
memory is not checkpointed.

The worker saves splits, proportions, tab order, selected tabs, URLs, workspace names and
terminal identities after two seconds of stability. Removing terminal tabs settles for ten
seconds before saving; the previous definition is kept in `autosave-drafts/*-before-removal.json`.
Closing a tab removes its view, not its VPS session. This avoids notifications for intentional
layout edits while preserving recovery data. Incomplete snapshots and unknown running processes
are never replaced with invented empty shells.

Connection failures retry automatically, with a notification after a minute of continuous
failure. Two viewers making conflicting layout changes still pause rather than overwrite each
other. Autosave status distinguishes a retry from a conflict:

```sh
python3 workspace.py autosave-status
python3 workspace.py open NAME
python3 workspace.py save NAME
python3 workspace.py keep-local NAME
```

Use `keep-local` only after reviewing a conflict. It fetches the latest revision and still uses
the server's optimistic revision check. Each native viewer has a separate tracked revision.

Browser cookies, forms, localStorage, scroll positions and unsaved editor buffers are not part
of the portable layout. Native cmux may retain its own browser state locally. Save project files
normally; Git commits are separate. Codex/HAPI save conversations independently. code-server
opens the saved native layout; its subsequent rearrangements remain local to that browser viewer.

Runtime maps, recovery drafts and links live outside Git. See [maintenance](MAINTENANCE.md).
