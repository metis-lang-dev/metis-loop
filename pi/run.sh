#!/usr/bin/env bash
# run.sh — the loop's POLICY over a world (loop-policy step 2; docs/POLICY.md, policy/driver.py):
# explore / exploit / refactor through metis.gate's experimental policy, disengaging with an ask.
#
#   run.sh --world alfworld --family pick_and_place_simple [--phase explore|exploit|refactor]
#   run.sh --world scienceworld --family conductivity …        (the second world: metis-worlds/scienceworld)
#          --brain openrouter/<model> --budget USD [--run DIR] [--discovery N] [--gate-games N] [--set KEY=N …]
#   run.sh --run DIR --answer TOKEN 'a note'        the person's answer to the ask (or JSON: {"kind": "budget", "proposals": 10})
#   run.sh --run DIR --resume [--brain …]           re-engage from the snapshot with the answer in context
#
#   --brain   openrouter/<model> (the key from $OPENROUTER_API_KEY only; --budget is required and the key's
#             own usage is the meter), claude[/<model>] (the operator's login), script:<file> (no model)
#   --run     the run's directory (default: ./policy-run-<world>-<family>): its catalog (the base the loop
#             builds), records, the gate's state and journal, the cost log, the brain's prompts
#   METIS_POLICY_PY  the python (default: the workspace's .worlds/alf venv: ALFWorld, metispy)
#   ALFWORLD_DATA    the games (default: the workspace's .worlds/alfworld-data)
#   METISC           metis-lang's metisc (default: the workspace's build): the gate checks a person's .llp edit with it
#   Every run is a child in a memory-capped scope (systemd-run --user, MemoryMax=6G) when systemd-run is there.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKGS="$HERE"                                          # the workspace: the first parent with .worlds/ (a worktree sits deeper)
while [ "$PKGS" != / ] && [ ! -d "$PKGS/.worlds" ]; do PKGS="$(dirname "$PKGS")"; done
[ -n "${METISC:-}" ] || [ ! -x "$PKGS/metis-lang/src/metisc" ] || export METISC="$PKGS/metis-lang/src/metisc"   # the gate checks a .llp edit with it
WORLD=alfworld FAMILY=pick_and_place_simple RUN="" ANSWER=() ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --world) WORLD="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --family) FAMILY="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --run) RUN="$2"; shift 2 ;;
    --answer) ANSWER=("$2" "$3"); shift 3 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
# the world's venv: ALFWorld's (.worlds/alf, its games in ALFWORLD_DATA) or ScienceWorld's (.worlds/sw: the simulator's jar on the system java)
case "$WORLD" in
  scienceworld) PY="${METIS_POLICY_PY:-$PKGS/.worlds/sw/bin/python}"; [ "$FAMILY" = pick_and_place_simple ] && FAMILY=conductivity && ARGS+=(--family conductivity) ;;
  *) PY="${METIS_POLICY_PY:-$PKGS/.worlds/alf/bin/python}"; export ALFWORLD_DATA="${ALFWORLD_DATA:-$PKGS/.worlds/alfworld-data}" ;;
esac
[ -x "$PY" ] || { echo "run.sh: no python at $PY (METIS_POLICY_PY: the world's venv with metispy: .worlds/alf for alfworld, .worlds/sw for scienceworld)" >&2; exit 1; }
RUN="${RUN:-$PWD/policy-run-$WORLD-$FAMILY}"
if [ ${#ANSWER[@]} -gt 0 ]; then
  exec "$PY" -m metis.gate --state "$RUN/state" --policy experimental answer "${ANSWER[0]}" <<<"${ANSWER[1]}"
fi
CAP=()
command -v systemd-run >/dev/null && CAP=(systemd-run --user --scope -q -p MemoryMax=6G)
cd "$HERE"
exec "${CAP[@]}" nice "$PY" -m policy.driver --run "$RUN" "${ARGS[@]}"
