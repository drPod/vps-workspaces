# Retire the legacy HAPI shell function in shells that source this compatibility file.
unset -f codex 2>/dev/null || true
