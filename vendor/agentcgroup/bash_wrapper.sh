#!/bin/bash
# Adapted from AgentCgroup; GPL-2.0. See NOTICE.md and LICENSE.
set -u

case "${1:-}" in
    -c|-lc) ;;
    *) exec /bin/bash "$@" ;;
esac

root="${AGENTCG_ROOT:?Missing delegated cgroup root}"
log="${AGENTCG_LOG:?Missing private metrics path}"
group="$root/tool_$$_${RANDOM}"
max=805306368
hint="${AGENT_RESOURCE_HINT:-}"
case "$hint" in
    memory:low) max=268435456 ;;
    memory:medium|'') ;;
    memory:high) max=1073741824 ;;
    *) echo '[Resource] Use memory:low, memory:medium, or memory:high.' >&2; exit 125 ;;
esac

fail() {
    echo '[Resource] Could not enforce the command budget; command was not started.' >&2
    rmdir "$group" 2>/dev/null || true
    exit 125
}

mkdir "$group" || fail
printf '%s' "$max" > "$group/memory.max" || fail
printf '1' > "$group/memory.oom.group" || fail
printf '128' > "$group/pids.max" || fail
start=$SECONDS
(
    printf '%s' "$BASHPID" > "$group/cgroup.procs" || exit 125
    exec /bin/bash "$@"
)
status=$?
read -r peak < "$group/memory.peak"
killed=0
while read -r key value; do
    [[ "$key" == oom_kill ]] && killed=$value
done < "$group/memory.events"
if (( killed > 0 )); then
    printf '[Resource] Command exceeded its %s MiB memory budget (peak %s MiB).\n' \
        "$((max / 1048576))" "$((peak / 1048576))" >&2
    echo '[Resource] Reduce parallelism or split the job; the agent is still running.' >&2
fi
printf '{"pid":%d,"exit":%d,"seconds":%d,"peak_bytes":%d,"oom_kills":%d}\n' \
    "$$" "$status" "$((SECONDS - start))" "$peak" "$killed" >> "$log"
rmdir "$group" 2>/dev/null || true
exit "$status"
