# Independent Codex terminal views

Research date: 2026-09-23. Initial candidate evaluation below; the complete HAPI app has since been deployed and tested with Runner-owned sessions. See [current integration and verification](HAPI.md). The original Outreach conversation still awaits its normal stop/resume handoff.

## Existing implementation

[HAPI](https://github.com/tiann/hapi) provides shared Codex sessions using one app-server and multiple official Codex terminal frontends, alongside web/native clients. Its [shared-session guide](https://hapi.run/docs/guide/codex-shared-sessions) describes lifecycle, reconnect and ownership handling.

Inspected revision: `97cf69bb5989e64569514a58de959e7c5f06e693`.

- `cli/src/codex/shared/frontend.ts`: attaches with the runtime's exact Codex executable, `--remote`, and `resume <threadId>`. Each attachment is a separate terminal UI process; it does not attach viewers to one tmux screen.
- `cli/src/codex/shared/runtime.ts`: starts the shared app-server, owns its lifecycle, and exposes the shared protocol gateway.
- `cli/src/codex/shared/launch.ts`: checks version and rejects unsupported launch settings explicitly.
- `cli/src/codex/shared/frontend.integration.test.ts`: tests actual Codex terminal processes, HAPI Runner/Hub, web events and a local mock Responses endpoint.

Read-only checks confirmed the VPS has Codex 0.156.1 and exposes `--remote` for Unix-socket or WebSocket app-server connections. HAPI documents a minimum of 0.154.0.

## Fit for our workspace

Keep code-server and cmux as the user interfaces. Each agent pane can run its own official terminal frontend connected to the same VPS agent engine. This should let Codex render at each pane's dimensions while sharing conversation state. It does not provide independent rendering for arbitrary programs inside a shared shell; ordinary terminal surfaces still use tmux.

Prefer a Runner-owned execution so closing a viewer does not end the engine. HAPI's terminal-owned launch ends when its original terminal exits; secondary attachments only detach. Reuse the existing HAPI implementation as a separate application. It is AGPL-3.0; no HAPI implementation source has been copied into this MIT repository.

## Migration and remaining checks

A live legacy session cannot be hot-migrated by HAPI. Prepare and validate the new path first, then stop the old conversation normally and resume its native thread once. Do not start a second engine for the active thread.

Before deployment, verify different-sized simultaneous frontends, resize behavior, disconnect/reconnect, Runner-owned lifetime, our authenticated gateway, and saved layout import. HAPI also rejects profile flags and has concurrent-session restrictions on rewind and some launch options; preserve required settings explicitly and check compatibility.

## Isolated verification

Used the upstream integration tests with installed Mac Codex 0.155.1, temporary homes, a loopback test Hub and a local mock Responses API. No production credentials or agent threads were used.

- All four tests in `runtime.integration.test.ts` passed.
- Parameterized the upstream test-only Python PTY driver to start the primary at 140×42 and a secondary at 80×24. Shared history, secondary detach and continued engine liveness assertions passed. This establishes differently sized attachments, but is not a visual reflow or dynamic-resize acceptance test.
- The full frontend test subsequently timed out waiting for the original terminal process to exit. Rerunning the unchanged upstream frontend test reproduced the same timeout; it is not specific to our PTY-size variation. Later recovery assertions were not reached. Do not describe the complete lifecycle suite as passing or this candidate as deployment-ready.

Command: `HAPI_RUN_SHARED_CODEX_TESTS=1 bun run --cwd cli test -- src/codex/shared/runtime.integration.test.ts src/codex/shared/frontend.integration.test.ts`.
