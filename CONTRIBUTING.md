# Contributing

Start with [AGENTS.md](AGENTS.md) and [the development checks](README.md#development).
Keep changes focused on integrating upstream tools. Explain what remains custom and why.

For a bug report, include OS, cmux/code-server/HAPI versions, the command you ran, what you
expected and a redacted error or `doctor --json` result. Never include sharing-link keys,
relay credentials, HAPI tokens, environment files or conversation databases.

Changes to connection routing, session ownership, authentication or backup behavior need
focused regression coverage. Test lifecycle changes against a disposable workspace before
using a live agent. Preserve the licenses and notices of vendored code.
