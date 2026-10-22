#!/usr/bin/env bash
# console-nav.sh — the loop console with its voice navigation (console-nav s-b923ebfe): the
# console over the catalog of the directory it runs in (cwd-root), and metis-agent's py service
# on Gemma E2B, local, serving this checkout's two console domains (domains/ui: the page's
# widgets and the focus; domains/repl: the REPL, its host a client of the console's gateway).
# The page (http://127.0.0.1:PORT/) talks to both: its dialog panel (the TALK dock) is the one
# input; the flip key (ctrl+space) moves it to the formalization agent's chat and back.
#
#   cd <a catalog, e.g. metis-catalog> && METIS_AGENT=<metis-agent checkout> <metis-loop>/console-nav.sh
#
# PORT (the console, default 8770), AGENT_ADDR (metis-agent, default 127.0.0.1:8395), MODEL (the
# E2B GGUF, default the metis-agent checkout's go/models/gemma4 Q4_K_M), AGENT_PY (default the
# checkout's py/.venv python), METISPY (a metispy checkout, when the agent's venv has none),
# METIS_LOOP (the console's command, default metis-loop on PATH). The rest of the arguments go to
# the console (--brain, --token, …). Everything the agent writes goes to .metis/console-nav/ here.
set -euo pipefail
LOOP=$(cd "$(dirname "$0")" && pwd)
: "${METIS_AGENT:?the metis-agent checkout (its py/ is run)}"
PORT=${PORT:-8770}
AGENT_ADDR=${AGENT_ADDR:-127.0.0.1:8395}
MODEL=${MODEL:-$METIS_AGENT/go/models/gemma4/gemma-4-E2B-it-Q4_K_M.gguf}
AGENT_PY=${AGENT_PY:-$METIS_AGENT/py/.venv/bin/python}
METIS_LOOP=${METIS_LOOP:-metis-loop}
CAT=$PWD
STATE=$CAT/.metis/console-nav
[ -f "$MODEL" ] || { echo "console-nav: no model at $MODEL (MODEL=…)" >&2; exit 1; }
mkdir -p "$STATE"
[ -f "$CAT/.metis/.gitignore" ] || echo '*' > "$CAT/.metis/.gitignore"
cat > "$STATE/agent.yaml" <<YAML
# written by console-nav.sh
model: $MODEL
template: gemma4
stop_words: [stop, halt, freeze, quiet]
v3:
    prompt: [../go/grammar/v3-orchestrator.txt]
    catalog: [ui, repl]
    loaded: [ui]
    n_ctx: 16384
    tick_ms: ${TICK_MS:-1000}
    journal: $STATE/journal.jsonl
domains:
    names: [ui, repl]
    case: live
    seed: 1
    clocks: [{domain: ui, n: 1}, {domain: repl, n: 1}]
    trace: true
    records: $STATE/records
    narrator_n_ctx: 8192
    seat_n_ctx: 8192
ws:
    addr: $AGENT_ADDR
YAML

# metis-agent: the console's domains from this checkout (METIS_CATALOG); the repl host reaches
# the console at METIS_LOOP_WS (the page's activate bindings carry its token and session)
(
  cd "$METIS_AGENT/py"
  export METIS_CATALOG=$LOOP METIS_LOOP_WS=ws://127.0.0.1:$PORT/ws
  export PYTHONPATH=$METIS_AGENT/py:$LOOP/sdk${METISPY:+:$METISPY}${PYTHONPATH:+:$PYTHONPATH}
  exec "$AGENT_PY" -m metis_agent.service --config "$STATE/agent.yaml" --addr "$AGENT_ADDR" --no-wait-viewer
) > "$STATE/agent.log" 2>&1 &
AGENT=$!
trap 'kill $AGENT 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 240); do                                    # the model loads first (tens of seconds)
  kill -0 $AGENT 2>/dev/null || { echo "console-nav: the agent stopped — $STATE/agent.log:" >&2; tail -20 "$STATE/agent.log" >&2; exit 1; }
  (exec 3<>"/dev/tcp/${AGENT_ADDR%:*}/${AGENT_ADDR##*:}") 2>/dev/null && break
  sleep 0.5
done
echo "metis-agent: ws://$AGENT_ADDR/ws (log $STATE/agent.log)"
"$METIS_LOOP" console-serve --port "$PORT" --metis-agent "ws://$AGENT_ADDR/ws" "$@"
