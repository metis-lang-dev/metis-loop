#!/usr/bin/env bash
# propose.sh — a hand-written amendment judged on a trace, and a ruling (policy/propose.py): the gate cascade, the goldens and the cases, the fired diff on the composition's replay;
# no world, no agent run. Runs under metis-agent's python (the replay is the real Live's relay code; METIS_PROPOSE_PY), in the memory-capped scope. The catalog's environment is yours:
# METIS_CATALOG is set per root by the judgement, METIS_HOME stays as you give it (the road family). A paid brain's key from the environment only, never a file here.
#   propose.sh --pack FILE --member M --trace TRACE --root ROOT --config CONFIG --run DIR [--composition domains] [--case CASE ...] [--brain openrouter/<model> --budget USD]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKGS="$(cd "$HERE/../.." && pwd)"
PY="${METIS_PROPOSE_PY:-$PKGS/metis-agent/py/.venv/bin/python}"
[ -x "$PY" ] || { echo "propose.sh: no python at $PY (METIS_PROPOSE_PY: a venv with metispy and metis-agent)" >&2; exit 2; }
export PYTHONPATH="$HERE:$HERE/../sdk${PYTHONPATH:+:$PYTHONPATH}"
CAP=()
command -v systemd-run >/dev/null && CAP=(systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0)
exec "${CAP[@]}" nice "$PY" -m policy.propose "$@"
