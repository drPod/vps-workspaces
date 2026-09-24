# Complete application frontend research

Research date: 2026-09-23. This is an evaluation, not a claim that a replacement has been installed or tested against Outreach.

## Requirements

Use an existing, thoughtfully implemented application rather than write another pane shell. Maintenance and popularity are supporting evidence, not selection gates. Preserve native cmux access and existing VPS tmux agents. Browser viewers need terminals and app/report previews together, usable focus, resizing, tabs and reconnection. Keep complete-link entry without a password prompt.

## Findings

### code-server / VS Code: strongest candidate for whole-application reuse

- Application: https://github.com/coder/code-server (MIT). Release checked: v4.138.0, published 2026-09-19.
- VS Code already supports terminals as editor tabs, including arbitrary editor-group splits: https://code.visualstudio.com/docs/terminal/basics#_terminals-in-editor-area
- Inspected `src/vs/workbench/contrib/terminal/browser/terminalEditor.ts` in microsoft/vscode: terminal instances attach/detach from the view; focus updates active terminal state; visibility is propagated; layout dimensions are retained and applied when a terminal is attached. These are interaction/lifecycle behaviors missing from a minimal iframe shell.
- Inspected `extensions/simple-browser/src/simpleBrowserView.ts`: existing preview webview, retained hidden context, view-column placement, and iframe rendering. This remains subject to ordinary website embedding restrictions. Do not assume desktop VS Code's newer integrated browser is available in code-server.
- code-server documents port proxies and integration with an external authentication proxy: https://coder.com/docs/code-server/guide
- Proposed reuse: run the existing application; terminal profiles attach the current named tmux sessions; a narrow extension translates our saved tree into editor groups and opens previews. Configure away unwanted IDE chrome rather than fork the workbench.
- Not yet verified: multiple preview instances, two simultaneous browser clients, exact saved-layout reconstruction, cookie/proxy behavior behind our link gateway, and closing terminals without terminating the underlying agent. The existing Simple Browser implementation has panel-management semantics that must be tested before promising two concurrent previews.
- Tradeoff: users get a VS Code workbench, not a terminal-first cmux clone. It introduces a larger server process and IDE features.

### JupyterLab: credible complete web-workspace alternative

- Application: https://github.com/jupyterlab/jupyterlab (BSD-3-Clause).
- Full application with movable terminal/document tabs and saved workspaces: https://jupyterlab.readthedocs.io/en/stable/user/interface.html
- Inspected `packages/terminal/src/widget.ts`: buffers output before xterm initialization, defers sizing until visible/attached/ready, refits after showing, and handles terminal focus and keyboard behavior explicitly.
- Server-backed terminals survive closing their view: https://jupyterlab.readthedocs.io/en/stable/user/terminal.html
- Its URL documentation explicitly says one named workspace should be open in only one browser tab at a time. Simultaneous viewers require distinct cloned layouts, even if their terminals attach the same tmux sessions: https://jupyterlab.readthedocs.io/en/stable/user/urls.html
- App previews require additional integration (for example Jupyter Server Proxy plus a preview extension). A complete terminal-and-two-preview workflow has not been tested.
- Tradeoff: notebook/scientific-computing UI and extra preview integration. Do not imply that using the underlying Lumino library alone reuses the finished application.

### Wave Terminal: closest product interaction reference, not a drop-in web application

- Application: https://github.com/wavetermdev/waveterm (Apache-2.0).
- Existing terminal/browser/editor blocks, drag-and-drop, and block maximization closely match the desired interaction model.
- Inspected `frontend/app/view/webview/webview.tsx` and `webviewenv.ts`: browser rendering depends on Electron WebviewTag and Electron APIs for preload, focus, navigation, and storage. Its browser view cannot simply be hosted in a normal browser.
- Useful as an implementation/design reference; extracting its UI requires a port and would put us back in substantial custom frontend work.

### Cloud9 SDK: relevant older application, unsuitable default for code reuse here

- https://github.com/c9/core is archived, but age itself is not the rejection reason.
- The repository's top-level LICENSE is a non-commercial SDK agreement with explicit restrictions, rather than a permissive license for this public project's intended reuse: https://github.com/c9/core/blob/master/LICENSE
- Do not copy its implementation into our MIT repository. Its published product tour is still a useful interaction reference: https://docs.aws.amazon.com/cloud9/latest/user-guide/tour-ide.html

## Recommendation and acceptance criteria

Evaluate code-server as the first complete replacement candidate. This recommendation is based on existing application behavior and inspected source, not a claim that integration is already complete. Keep the current service available until a separate candidate passes:

1. Existing tmux agent visible without starting a second agent process.
2. Report and application open together beside the terminal.
3. Focus, copy/paste, resizing, tab moves, and maximize/restore work in the browser.
4. Two isolated browser clients can attach, reload, and disconnect independently.
5. Native cmux remains attached to the same tmux session.
6. Passwordless link entry protects both HTTP and WebSocket routes.
7. Saved layouts reopen and visual screenshots are reviewed at practical viewport sizes.

No upstream source was copied and no live service was replaced during this research.

Source heads checked at the end of inspection (moving branches may advance): microsoft/vscode `97452d795c704de960ead42638244f1e104319c7`; jupyterlab/jupyterlab `b524d0acddd7c8320c476d05f7c5e0199c512916`; wavetermdev/waveterm `a4447c1563b2df285ab89e76c82f91e1a1a49c1e`.

## Follow-up: independent agent views

The code-server integration is now deployed; see [IDE setup](IDE.md). For independent terminal dimensions while sharing one Codex engine, see [shared-agent research](SHARED-AGENT-RESEARCH.md), including HAPI source inspection and isolated test results.
