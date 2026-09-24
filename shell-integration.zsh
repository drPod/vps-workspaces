# Source from ~/.zshrc. The worker must remain a descendant of a local cmux shell.
_vws_autosave_start() {
  [[ -n "$CMUX_SOCKET_PATH" && -z "$SSH_CONNECTION" ]] || return
  if [[ -n "$_VWS_AUTOSAVE_PID" ]] && kill -0 "$_VWS_AUTOSAVE_PID" 2>/dev/null; then
    return
  fi
  local vws_root="${VWS_LOCAL_ROOT:-$HOME/Coding/vps-workspaces}"
  [[ -f "$vws_root/autosave.py" ]] || return
  mkdir -p "$HOME/.local/state/vps-workspaces"
  (umask 077; exec python3 "$vws_root/autosave.py") >> "$HOME/.local/state/vps-workspaces/autosave.log" 2>&1 &!
  _VWS_AUTOSAVE_PID=$!
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd _vws_autosave_start
_vws_autosave_start
