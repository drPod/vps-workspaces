# Non-interactive Codex Bash commands only; host and interactive shells are unchanged.
if [[ -n ${BASH_EXECUTION_STRING:-} && -z ${VWS_TOOL_CGROUP:-} ]]; then
    export VWS_TOOL_CGROUP=1
    unset BASH_ENV
    vws_shell_mode=-c
    shopt -q login_shell && vws_shell_mode=-lc
    exec /bin/bash "$AGENTCG_WRAPPER" "$vws_shell_mode" "$BASH_EXECUTION_STRING" "$0" "$@"
fi
