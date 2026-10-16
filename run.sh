#!/usr/bin/env bash
# metis-loop — start the loop console (the gateway over the metis-catalog
# checkout: one kernel REPL per page, the CATALOG panel, the agent seat) in
# the background and print its URL.
#
#   ./run.sh            start (installs the catalog's loader into the venv if missing)
#   ./run.sh stop       stop it
#   ./run.sh status     running or not, the URL
#   ./run.sh log        follow the gateway's log
#
#   VENV=../.venv  PORT=8770  BIND=127.0.0.1  MODE=personal|shared  TOKEN=…
#   METIS_CATALOG=<checkout>   (default: the sibling ../metis-catalog)
#
# The python is the workspace venv (perotheia-packages/.venv: metispy,
# metis-loop[console] editable) unless VENV says otherwise. The catalog's
# loader (metis_catalog, a sibling checkout, not on PyPI) is pip-installed
# editable on first start — the CATALOG panel reads it. The page's shell
# (console/lib/shell.css + shell.js) is this repo's own copy, served at /lib/.
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
CATALOG="${METIS_CATALOG:-$(cd "$ROOT/.." && pwd)/metis-catalog}"

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
  rm -f "$PID"; exit 0 ;;
status)
  if running; then echo "running (pid $(cat "$PID")) — $URL"; else echo "not running"; fi
  exit 0 ;;
log)
  exec tail -f "$LOG" ;;
start) ;;
*) echo "usage: $0 [start|stop|status|log]" >&2; exit 2 ;;
esac

if running; then echo "already running (pid $(cat "$PID")) — $URL"; exit 0; fi

[ -x "$PY" ] || { echo "no venv at $VENV (set VENV; python3 -m venv ../.venv && ../.venv/bin/pip install -e ../metispy -e '.[console]')" >&2; exit 1; }
[ -d "$CATALOG/domains" ] || { echo "no metis-catalog checkout at $CATALOG (set METIS_CATALOG)" >&2; exit 1; }
"$PY" -c "import metis, loop" 2>/dev/null || { echo "the venv at $VENV lacks metispy / metis-loop: $VENV/bin/pip install -e ../metispy -e '$ROOT[console]'" >&2; exit 1; }
"$PY" -c "import websockets" 2>/dev/null || { echo "installing metis-loop[console] into $VENV …"; "$VENV/bin/pip" install -q -e "$ROOT[console]"; }
if ! "$PY" -c "import metis_catalog" 2>/dev/null; then
  echo "installing the catalog's loader (pip install -e $CATALOG) into $VENV …"
  "$VENV/bin/pip" install -q -e "$CATALOG"
fi

mkdir -p "$RUN"
[ -s "$LOG" ] && mv "$LOG" "$RUN/gateway-$(date -r "$LOG" +%Y%m%d-%H%M%S).log"
cd "$ROOT"
METIS_CATALOG="$CATALOG" nohup "$PY" -m loop.cli --port "$PORT" --bind "$BIND" --mode "$MODE" ${TOKEN:+--token "$TOKEN"} >"$LOG" 2>&1 &
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
  ./run.sh stop · ./run.sh log · ./run.sh status
MSG
