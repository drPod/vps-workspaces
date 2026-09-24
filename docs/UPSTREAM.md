# Upstream research and attribution

Checked September 23, 2026 (Pacific time). PR status can change; these are research observations, not promises that an upstream feature has shipped.

| cmux PR | Status when checked | Relevance |
|---|---|---|
| [#8116](https://github.com/manaflow-ai/cmux/pull/8116) — persist remote runtime session state | Closed, unmerged | Revisioned server-authoritative snapshots; atomic persistence; restored layouts/browser metadata. Inspired our explicit save with optimistic revision checks. The PR's discovery/selection work was incomplete. |
| [#9861](https://github.com/manaflow-ai/cmux/pull/9861) — browser beside remote tmux mirrors | Open, unmerged | Separates one native browser from the mirrored tmux tree. Shows why browser panes cannot simply become tmux panes. We use ordinary SSH workspaces instead of depending on this patch. |
| [#12706](https://github.com/manaflow-ai/cmux/pull/12706) — Connected Workspaces sync | Open, unmerged | Central snapshots and revisions with a web dashboard. Uses cmux cloud infrastructure and describes unfinished native publisher call sites. |
| [#8417](https://github.com/manaflow-ai/cmux/pull/8417) — authenticated multiplayer workspace sharing | Open, unmerged | Shared split layouts and live terminal input through a web client. Mac/cloud-oriented; not adopted as a self-hosted VPS terminal backend. |
| [#11514](https://github.com/manaflow-ai/cmux/pull/11514) — web bridge for live Mac sessions | Open, unmerged | Reuses cmux's web frontend and adds scoped browser grants. Requires the Mac runtime, whereas our shared terminals must survive the Mac disconnecting. |

## Source inspected

cmux source checkout: `be3855bb2d06c7ede52b01de2200f94be1ce1a68`. Installed app used for integration: **0.64.25 (106), b685a275c**. We verified available APIs against the running app, rather than assuming all checkout features were released.

- [Remote tmux environment propagation](https://github.com/manaflow-ai/cmux/blob/be3855bb2d06c7ede52b01de2200f94be1ce1a68/Sources/RemoteTmuxControlConnection%2BCommands.swift): refresh session-scoped metadata at attach/reconnect. The beta intentionally does not publish a Mac socket path where no reverse relay exists.
- [Live workspace tree](https://github.com/manaflow-ai/cmux/blob/be3855bb2d06c7ede52b01de2200f94be1ce1a68/Sources/TerminalController%2BControlSystemContext.swift): nested split direction/ratio and pane references. This project consumes the existing API representation.
- [Layout data definitions](https://github.com/manaflow-ai/cmux/blob/be3855bb2d06c7ede52b01de2200f94be1ce1a68/Sources/CmuxConfig.swift): binary splits and panes containing surfaces.
- [Remote relay policy](https://github.com/manaflow-ai/cmux/blob/be3855bb2d06c7ede52b01de2200f94be1ce1a68/Packages/macOS/CmuxRemoteWorkspace/Sources/CmuxRemoteWorkspace/Relay/RemoteRelayCommandPolicy.swift): remote requests have an explicit allowlist and ownership checks. The tested installation rejects `browser.snapshot` and `browser.url.get`. Our adapter does not override that policy.
- [ttyd's documented tmux sharing](https://github.com/tsl0922/ttyd/wiki/Example-Usage) and [HTTP implementation](https://github.com/tsl0922/ttyd/blob/main/src/http.c): reuse the terminal client and protocol unchanged. Installed Ubuntu ttyd: **1.7.4**.
- [Session Deck](https://github.com/JesseProjects-LLC/session-deck/tree/f04c33f3a67bbf7321109b8b4176434280cb7cc4): inspected its terminal attach service and recursive split-pane component. Its separate workspace database/UI is not imported into this project.
- [Split.js 1.6.5](https://github.com/nathancahill/split): the actual vendored dependency for web resizing. Its upstream MIT license is preserved in `static/SPLIT-LICENSE.txt`.
- [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy): existing TLS termination and Unix-socket upstream support.
- [aiohttp](https://docs.aiohttp.org/en/stable/): HTTP/WebSocket transport library, installed as a dependency.

No cmux, Session Deck, or PR source files are copied into this repository. Their API contracts and architectural patterns informed the adapter. We reuse ttyd/Caddy as programs, aiohttp as a dependency, and the unmodified Split.js distribution with its license.

## Reused IDE extension code

The browser IDE integration reuses [Microsoft VS Code Simple Browser](https://github.com/microsoft/vscode/tree/97452d795c704de960ead42638244f1e104319c7/extensions/simple-browser) and adapts terminal handling from [Workspace Layout](https://github.com/lostintangent/workspace-layout/tree/5ea20e7cd19e57bb000ceaf80237d63ac7b6034a). Both licenses, exact references, and modifications are recorded in [the extension notice](../ide-extension/NOTICE.md). VS Code provides the complete workbench; this project does not implement its terminal renderer, tabs, splitters, editor, or preview HTML.

Workspace Layout was not installed unchanged: its source disposes all existing terminals during reset, supports one browser URL, and does not import cmux's split tree. Our adaptation preserves existing terminals. Terminal Keeper and Restore Terminals were also considered for terminal initialization, but do not by themselves import the mixed terminal/browser layout.

## HAPI and backups

- [HAPI](https://github.com/tiann/hapi), official npm package `@twsxtd/hapi@0.30.7`, AGPL-3.0-only: deployed as the complete separate application. Workspace code calls its CLI/API; its implementation is not copied into this MIT repository. See [HAPI](HAPI.md) and [source research](SHARED-AGENT-RESEARCH.md).
- [rsnapshot](https://github.com/rsnapshot/rsnapshot), GPL: installed as a separate standard backup tool. It owns rsync snapshot creation, hard-link reuse and retention. Our scripts supply deployment configuration and SQLite online-backup preparation.
- systemd's `systemd-socket-proxyd` bridges the existing Caddy Unix-socket mount to HAPI's loopback listener. No custom HAPI HTTP/WebSocket proxy was written.
