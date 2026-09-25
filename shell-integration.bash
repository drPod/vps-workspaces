_vws_persistent_shell() {
    [[ -n "$CMUX_WORKSPACE_ID" && -n "$CMUX_SURFACE_ID" && -z "$TMUX" && -z "$VWS_SESSION" ]] || return
    [[ -z "$VWS_LOCAL" ]] || return
    exec python3 "$HOME/.local/share/vps-workspaces/app/workspace.py" persistence shell
}
if [[ $- == *i* && -z "$CMUX_INITIAL_COMMAND_FILE" && "${PROMPT_COMMAND[*]}" != *"_vws_persistent_shell"* ]]; then
    case "$(declare -p PROMPT_COMMAND 2>/dev/null)" in
        "declare -a"*) PROMPT_COMMAND=(_vws_persistent_shell "${PROMPT_COMMAND[@]}") ;;
        *) PROMPT_COMMAND="_vws_persistent_shell${PROMPT_COMMAND:+; $PROMPT_COMMAND}" ;;
    esac
fi
