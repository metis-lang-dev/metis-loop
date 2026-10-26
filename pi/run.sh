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
#   --brain   openrouter/<model> (the key from $OPENROUTER_API_KEY, else ~/.config/metis/openrouter.env; --budget is required and the key's
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
# the OpenRouter key: the environment, else ~/.config/metis/openrouter.env (the one place the paid runs
# have always used: `OPENROUTER_API_KEY=…`, mode 600) sourced into the environment — never in argv or a log
ENVFILE="$HOME/.config/metis/openrouter.env"
if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -r "$ENVFILE" ]; then set -a; . "$ENVFILE"; set +a; fi
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
# the world's venv: ALFWorld's (.worlds/alf, its games in ALFWORLD_DATA), ScienceWorld's (.worlds/sw: the simulator's jar on the
# system java) or MiniHack's (.worlds/mh: NetHack's learning environment; the levels are generated in the driver's process)
case "$WORLD" in
  scienceworld) PY="${METIS_POLICY_PY:-$PKGS/.worlds/sw/bin/python}"; [ "$FAMILY" = pick_and_place_simple ] && FAMILY=conductivity && ARGS+=(--family conductivity) ;;
  minihack) PY="${METIS_POLICY_PY:-$PKGS/.worlds/mh/bin/python}"; [ "$FAMILY" = pick_and_place_simple ] && FAMILY=room && ARGS+=(--family room) ;;
  *) PY="${METIS_POLICY_PY:-$PKGS/.worlds/alf/bin/python}"; export ALFWORLD_DATA="${ALFWORLD_DATA:-$PKGS/.worlds/alfworld-data}" ;;
esac
[ -x "$PY" ] || { echo "run.sh: no python at $PY (METIS_POLICY_PY: the world's venv with metispy: .worlds/alf for alfworld, .worlds/sw for scienceworld, .worlds/mh for minihack)" >&2; exit 1; }
# the driver imports the loop SDK (the brain's model adapters) and the world's modules from that venv: both installed
# there, editable (the world's own setup.sh installs the world), never put on a path
"$PY" -c "import metis_loop_sdk" 2>/dev/null || { echo "run.sh: $PY lacks the loop SDK: $PY -m pip install -e $(cd "$HERE/.." && pwd)/sdk" >&2; exit 1; }
RUN="${RUN:-$PWD/policy-run-$WORLD-$FAMILY}"
if [ ${#ANSWER[@]} -gt 0 ]; then
  exec "$PY" -m metis.gate --state "$RUN/state" --policy experimental answer "${ANSWER[0]}" <<<"${ANSWER[1]}"
fi
# the memory cap: 6G for every world (the user's standing rule: a run that hits it is a finding, never a
# raised cap); swap off so the cap is the cap
CAP=()
command -v systemd-run >/dev/null && CAP=(systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0)
cd "$HERE"
exec "${CAP[@]}" nice "$PY" -m policy.driver --run "$RUN" "${ARGS[@]}"
