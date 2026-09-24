# Source in interactive bash/zsh shells to use upstream HAPI for coding sessions.
# `command codex ...` always invokes the original CLI without HAPI.
codex() {
  case "${1-}" in
    agents|exec|e|review|login|logout|mcp|mcp-server|plugin|app-server|remote-control|app|completion|update|doctor|sandbox|debug|apply|a|queue|archive|delete|migrate-rollouts|unarchive|fork|cloud|exec-server|features|help|--help|-h|--version|-V|--remote)
      command codex "$@" ;;
    resume)
      shift
      if [ "$#" -eq 0 ]; then
        "$HOME/.local/bin/hapi" resume
      else
        "$HOME/.local/bin/hapi" codex resume "$@"
      fi ;;
    *) "$HOME/.local/bin/hapi" codex "$@" ;;
  esac
}
