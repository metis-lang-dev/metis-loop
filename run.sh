#!/usr/bin/env bash
# metis-loop — start the loop console (the gateway over the catalog in the
# current directory: one kernel REPL per page, the CATALOG panel, the agent
# seat) in the background and print its URL. As `cd DIR && claude` makes DIR
# the project, `cd DIR && …/metis-loop/run.sh` makes DIR the catalog and the
# workspace (cwd-root s-ddac2cbf): its domains/<name>/ are the catalog, an
# empty DIR is an empty catalog (`new` writes the first domain), the gateway
# and its REPLs run in DIR.
#
#   cd DIR && …/run.sh   start, over DIR (cd metis-catalog first for the catalog's own)
#   …/run.sh stop        stop it (from anywhere)
#   …/run.sh status      running or not, the URL, the catalog it serves
#   …/run.sh log         follow the gateway's log
#
#   VENV=../.venv  PORT=8770  BIND=127.0.0.1  MODE=personal|shared  TOKEN=…
#   BRAIN=claude|openrouter[:MODEL]|ollama   the LLM seats' provider (loop/brain.py; default:
#                              [console] brain, else claude when here, else openrouter with
#                              OPENROUTER_API_KEY in the environment, else ollama)
#   METIS_CATALOG=<dir>        the catalog when it is not the current directory
#   METIS_AGENT_WS=<ws url>    the band's AGENT field: metis-agent's console wire
#                              (default ws://127.0.0.1:8395/ws in personal mode; empty: off)
#
# The python is the workspace venv (perotheia-packages/.venv: metispy,
# metis-loop[console] editable) unless VENV says otherwise; it has the
# catalog's loader (pip install metis-catalog, or -e a checkout). The loop
# SDK (./sdk, metis_loop_sdk: the CATALOG widget, the model adapters; the
# catalog itself is metispy's metis.catalog) is pip-installed editable on first start. The
# gateway's pid and log stay in this repo's .run/ (one console on the port),
# with the catalog it serves in .run/catalog. The page's
# shell (console/lib/shell.css + shell.js) is this repo's own copy, served at
# /lib/; the CATALOG widget is the SDK's, served at /sdk/catalog/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
PID="$RUN/gateway.pid"
LOG="$RUN/gateway.log"
VENV="${VENV:-$ROOT/../.venv}"
[ -d "$VENV" ] || VENV="$ROOT/.venv"
PY="$VENV/bin/python"
PORT="${PORT:-8770}"
BIND="${BIND:-127.0.0.1}"
MODE="${MODE:-personal}"
URL="http://$BIND:$PORT/${TOKEN:+?token=$TOKEN}"
CATALOG="${METIS_CATALOG:-$PWD}"
SERVED="$RUN/catalog"

running() { [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; }

case "${1:-start}" in
stop)
  if running; then
    p=$(cat "$PID"); kill "$p"
    for _ in $(seq 1 20); do kill -0 "$p" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$p" 2>/dev/null && { echo "still up after 10 s; kill -9 $p" >&2; kill -9 "$p"; }
    echo "stopped (pid $p)"
  else
    echo "not running"
  fi
  rm -f "$PID" "$SERVED"; exit 0 ;;
status)
  if running; then echo "running (pid $(cat "$PID")) — $URL — catalog: $(cat "$SERVED" 2>/dev/null)"; else echo "not running"; fi
  exit 0 ;;
log)
  exec tail -f "$LOG" ;;
start) ;;
*) echo "usage: $0 [start|stop|status|log]" >&2; exit 2 ;;
esac

[ -d "$CATALOG" ] || { echo "no directory $CATALOG (METIS_CATALOG)" >&2; exit 1; }
CATALOG="$(cd "$CATALOG" && pwd)"
if running; then
  was="$(cat "$SERVED" 2>/dev/null)"
  if [ "$was" = "$CATALOG" ]; then echo "already running (pid $(cat "$PID")) — $URL"; exit 0; fi
  echo "already running over $was (pid $(cat "$PID")) — $0 stop first to serve $CATALOG" >&2; exit 1
fi

[ -x "$PY" ] || { echo "no venv at $VENV (set VENV; python3 -m venv ../.venv && ../.venv/bin/pip install -e ../metispy -e '.[console]')" >&2; exit 1; }
"$PY" -c "import metis, loop" 2>/dev/null || { echo "the venv at $VENV lacks metispy / metis-loop: $VENV/bin/pip install -e ../metispy -e '$ROOT[console]'" >&2; exit 1; }
"$PY" -c "import websockets" 2>/dev/null || { echo "installing metis-loop[console] into $VENV …"; "$VENV/bin/pip" install -q -e "$ROOT[console]"; }
"$PY" -c "import metis_catalog" 2>/dev/null || {
  echo "the venv at $VENV lacks the catalog's loader: $VENV/bin/pip install metis-catalog (or -e a metis-catalog checkout)" >&2; exit 1; }
if ! "$PY" -c "import metis_loop_sdk.web" 2>/dev/null; then   # the catalog widget the console serves
  echo "installing the loop SDK (pip install -e $ROOT/sdk) into $VENV …"
  "$VENV/bin/pip" install -q -e "$ROOT/sdk"
fi

mkdir -p "$RUN"
[ -s "$LOG" ] && mv "$LOG" "$RUN/gateway-$(date -r "$LOG" +%Y%m%d-%H%M%S).log"
echo "$CATALOG" >"$SERVED"
cd "$CATALOG"                     # the workspace: the gateway and its REPLs run in the catalog
AGENT_WS="${METIS_AGENT_WS-ws://127.0.0.1:8395/ws}"; [ "$MODE" = personal ] || AGENT_WS=""
METIS_CATALOG="$CATALOG" nohup "$PY" -m loop.cli --port "$PORT" --bind "$BIND" --mode "$MODE" ${BRAIN:+--brain "$BRAIN"} ${TOKEN:+--token "$TOKEN"} ${AGENT_WS:+--metis-agent "$AGENT_WS"} >"$LOG" 2>&1 &
echo $! >"$PID"

for _ in $(seq 1 60); do
  if ! running; then echo "the gateway exited — see $LOG:" >&2; tail -20 "$LOG" >&2; rm -f "$PID"; exit 1; fi
  grep -q "^loop console" "$LOG" 2>/dev/null && break
  sleep 0.5
done
grep -q "^loop console" "$LOG" || { echo "not serving after 30 s — see $LOG" >&2; exit 1; }

cat <<MSG
metis-loop console is up (pid $(cat "$PID")): open $URL
  mode: $MODE · catalog: $CATALOG · log: $LOG
  $(grep -m1 "^brain:" "$LOG" || true)
  $0 stop · $0 log · $0 status
MSG
