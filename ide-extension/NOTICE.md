The application UI is code-server / VS Code. This extension only translates saved cmux layouts and attaches existing tmux sessions.

`vendor/simple-browser/src/` is Microsoft VS Code Simple Browser source (with a title setter added for distinct preview tabs) from commit 97452d795c704de960ead42638244f1e104319c7, under its included MIT license. `media/` contains the corresponding compiled preview assets distributed with code-server 4.138.0 / Code 1.138.0 (Microsoft copyright, MIT). These are reused to allow multiple preview instances; the upstream SimpleBrowserManager normally maintains a single active preview. No custom preview HTML or pane framework is introduced.

Source: https://github.com/microsoft/vscode/tree/97452d795c704de960ead42638244f1e104319c7/extensions/simple-browser

`vendor/workspace-layout/` is adapted from Jonathan Carter's MIT-licensed Workspace Layout extension, commit 5ea20e7cd19e57bb000ceaf80237d63ac7b6034a. Changes: preserve existing terminals, reuse matching named instances, and preserve focus. The cmux tree conversion and reading the VPS registry are project-specific integration.

https://github.com/lostintangent/workspace-layout/tree/5ea20e7cd19e57bb000ceaf80237d63ac7b6034a

Adapter lifecycle handling records the tmux client PID returned by VS Code and detaches only that viewer's client on extension-host deactivation. This does not terminate or recreate tmux sessions.
