#!/usr/bin/env bash
# loop.sh — the agentic loop (docs/LOOP-AGENT.md): pi with the three
# metis extensions over a catalog (the workspace's: docs/WORKSPACE.md §5), on MODEL (default deepseek v4 pro, the user's choice).
#
# A loop starts in a directory, and that directory is the catalog and the workspace
# (cwd-root s-ddac2cbf), as `cd DIR && claude` makes DIR the project: DIR's domain
# packages are the catalog (an empty DIR is an empty catalog: the first catalog_new
# writes DIR/domains/<name>/), pi runs in DIR, and the loop's own state goes in
# DIR/.metis/ (the loop SDK's catalog.state(): records/, sessions/, seed/, seed.json;
# git-ignored when DIR is a checkout).
#
#   cd DIR && loop.sh [pi args...]       the loop over DIR
#   cd DIR && loop.sh --seed PATH.llp|PKG_DIR [--name NAME] [--episodes N] [pi args...]
#                                        a seeded start: the REPL serves an existing program
#                                        (a copy in DIR/.metis/seed/), and pi's first message asks
#                                        the model to make it DIR's domain NAME (default: the file's
#                                        stem, - as _) through catalog_new program=served — its rules
#                                        unchanged — then exercise it and, when the person asks,
#                                        catalog_take it (prompts/seed-task.md). A DIR is seeded once:
#                                        the same --seed again goes on with it.
#                                        --episodes N: the n of the task's domain_episodes (an RDDL
#                                        world's measure; default 20), in the task from its first
#                                        message, so the model never runs another n before the person's
#                                        PKG_DIR, a domain package (its manifest, program, included
#                                        files, host): copied whole into DIR/.metis/seed/domains/NAME/,
#                                        its program served there; program=served takes the package into
#                                        DIR, every file at the gate
#   --into DIR2 (or METIS_LOOP_TAKE_INTO=DIR2)
#                                        the catalog catalog_take takes a finished domain into (gated,
#                                        never a commit); none named: catalog_take refuses
#   METIS_CATALOG=DIR loop.sh …          the same, started elsewhere
#
#   MODEL=<pi provider>/<id> for one start; unset: the dot file's [llm] loop (llm-config: ONE configuration for
#         every seat, metispy metis.loop.config; the REPL's `llm loop ollama phi4-mini` or `llm loop openrouter
#         deepseek/deepseek-v4.1-flash-1017` writes it); neither: refused (no default). openrouter/<id>: its key
#         OPENROUTER_API_KEY from the environment, else read from METIS_OPENROUTER_ENV (default
#         ~/.config/metis/openrouter.env, only when private: mode 600), agent/models.json caps and routes it, and a
#         budget. ollama/<id> ([llm] loop = "ollama:ID[@URL]"; MODEL=ollama/ID: METIS_OLLAMA_URL, else
#         http://127.0.0.1:11434): pi's provider over the server's /v1 in DIR/.metis/pi-agent/ (loop/pi_models.py),
#         no key, 0 USD, no budget needed; a model that cannot call tools cannot run the loop (`llm` says so)
#   --budget USD (or METIS_LOOP_BUDGET=USD): the session's spend cap on a paid model (openrouter/*),
#         default 1.00; past it the workspace extension refuses further model turns, journals
#         `budget` and releases the lock (no kill). A paid MODEL with an empty budget is refused.
#   FORMALIZE_MODEL=the model the kernel's formalize drafts with: openrouter/<id> (the loop
#         SDK's OpenAI-compatible command face, reasoning off, 2048 tokens, data_collection
#         deny; its calls and their cost in $METIS_LOOP_RECORDS/formalize-calls.jsonl),
#         ollama/<id> (metispy's own ollama backend, 0 USD), or claude[/<id>] (the SDK's
#         claude -p command face, the person's own login). Default: the dot file's [llm]
#         formalize, else its [llm] loop; else MODEL's when MODEL is openrouter/* or ollama/*,
#         thinking suffix dropped; otherwise none, and the kernel's formalize says how to set one
#   METIS_LOOP_LLP=<file.llp>  the program the REPL starts on (default: a blank world; demo.sh
#              starts on the plant, so formalize sees a known world's vocabulary)
#   pi args: e.g. --mode rpc (a client is the person), or none (pi's TUI)
#   --help (first): this text; nothing starts, no key read
#   METIS_LOOP_PI=<cmd>  run it in pi.sh's place, with pi.sh's arguments (the tests' stand-in)
#   METIS_LOOP_TOOLS=workspace|seed|all  the tool set (default: seed with --seed or no bundle in DIR, else workspace)
set -euo pipefail
case "${1:-}" in                      # loop.sh's own help: the header above (pascal, loop-test); pi's is pi.sh --help
  -h|--help) sed -n '2,/^set -euo/{/^#/s/^# \{0,1\}//p}' "$0"; exit 0 ;;
esac
case " $* " in
  *" --mode rpc "*) ;;                # rpc: stdin IS the protocol (the backend's child, person.py): kept
  *) [ -t 0 ] || exec </dev/null ;;   # no terminal: pi must not sit reading a stdin nobody will close
esac
HERE="$(cd "$(dirname "$0")" && pwd)"
PKGS="$(cd "$HERE/../.." && pwd)"                      # the workspace: its .venv, metis-agent (defaults only)
AGENT="${METIS_AGENT:-$PKGS/metis-agent}"           # the domain agent's checkout
for a in "$@"; do
  [ "$a" != --scratch ] || { echo "loop.sh: --scratch is gone: cd DIR && loop.sh (DIR is the catalog; cwd-root s-ddac2cbf)" >&2; exit 2; }
done
# the loop SDK's python (metis_loop_sdk: the catalog's root and state, the model adapters)
SDK_PY="${METIS_LOOP_SDK_PY:-$PKGS/.venv/bin/python}"
"$SDK_PY" -c "import metis_loop_sdk.models, metis.catalog" 2>/dev/null || {
  echo "no loop SDK in $SDK_PY: pip install metis-loop-sdk (its sdk-vX.Y.Z tag), or set METIS_LOOP_SDK_PY" >&2; exit 1; }
sdk() { "$SDK_PY" -m metis.catalog --root "$DIR" "$@" --json; }
field() { "$SDK_PY" -c 'import json,sys; o=json.load(sys.stdin); print(o.get(sys.argv[1]) or "", end="")' "$1"; }
TASK=()
SEED="" NAME="" EPISODES="" INTO="${METIS_LOOP_TAKE_INTO:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --seed) SEED="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --episodes) EPISODES="$2"; shift 2 ;;
    --into) INTO="$2"; shift 2 ;;
    --budget) METIS_LOOP_BUDGET="$2"; shift 2 ;;
    *) break ;;
  esac
done
for a in "$@"; do                                    # loop.sh's own options come first: one after pi's would reach pi
  case "$a" in --seed|--episodes|--into|--budget)     # (--name is pi's too)
    echo "loop.sh: $a after pi's arguments: give loop.sh's options first (loop.sh $a … --mode rpc)" >&2; exit 2 ;;
  esac
done
DIR="${METIS_CATALOG:-$PWD}"
[ -d "$DIR" ] || { echo "loop.sh: no directory $DIR (METIS_CATALOG)" >&2; exit 1; }
DIR="$(cd "$DIR" && pwd)"
if [ -n "$INTO" ]; then
  [ -d "$INTO" ] || { echo "loop.sh: --into $INTO: no such directory (the catalog catalog_take takes a domain into)" >&2; exit 1; }
  INTO="$(cd "$INTO" && pwd)"
  [ "$INTO" != "$DIR" ] || { echo "loop.sh: --into $INTO is the catalog the loop runs in" >&2; exit 1; }
fi
if [ -n "$EPISODES" ] && ! { [[ "$EPISODES" =~ ^[1-9][0-9]*$ ]] && [ "$EPISODES" -le 50 ]; }; then
  echo "loop.sh: --episodes $EPISODES: 1-50 (domain_episodes' n)" >&2; exit 1
fi
if [ -z "$SEED" ] && { [ -n "$NAME" ] || [ -n "$EPISODES" ]; }; then
  echo "loop.sh: --name and --episodes go with --seed" >&2; exit 1
fi
PACKAGE=""
if [ -n "$SEED" ]; then
  if [ -d "$SEED" ]; then                                             # a domain package, as it is
    [ -f "$SEED/domain.yaml" ] || { echo "loop.sh: --seed $SEED: a directory seed is a domain package (its domain.yaml)" >&2; exit 1; }
    PACKAGE=1; base="$(basename "$SEED")"
  else
    [ -f "$SEED" ] || { echo "loop.sh: --seed $SEED: no such file" >&2; exit 1; }
    base="$(basename "$SEED" .llp)"
  fi
  NAME="${NAME:-${base//-/_}}"
  [[ "$NAME" =~ ^[a-z][a-z0-9_]*$ ]] || { echo "loop.sh: the domain name '$NAME': lowercase letters, digits, _ (give --name NAME)" >&2; exit 1; }
  case "$SEED" in */domains/*) REL="domains/${SEED#*/domains/}" ;; *) REL="$SEED" ;; esac   # catalog-relative inside a catalog
  WANT="{\"seed\": \"$REL\", \"name\": \"$NAME\"${PACKAGE:+, \"package\": true}}"
fi
ST="$(sdk state | field state)"                    # DIR/.metis/: made, and git-ignored in a checkout
if [ -n "$SEED" ]; then
  if [ -f "$ST/seed.json" ]; then
    [ "$(cat "$ST/seed.json")" = "$WANT" ] || { echo "loop.sh: $DIR was seeded otherwise ($(cat "$ST/seed.json")): seed a new DIR" >&2; exit 1; }
  else
    if sdk get "$NAME" > /dev/null 2>&1; then
      echo "loop.sh: $DIR has a domain $NAME already: --name another, or start without --seed" >&2; exit 1
    fi
    if [ -n "$PACKAGE" ]; then                                        # the package, a catalog of its own outside DIR's
      mkdir -p "$ST/seed/domains/$NAME"
      (cd "$SEED" && tar --exclude=./build --exclude=./records --exclude=__pycache__ -cf - .) | (cd "$ST/seed/domains/$NAME" && tar -xf -)
    else                                                              # the seed, served from a copy outside the catalog
      mkdir -p "$ST/seed" && cp "$SEED" "$ST/seed/$NAME.llp"
    fi
    printf '%s' "$WANT" > "$ST/seed.json"
  fi
  if [ -n "$PACKAGE" ]; then                                          # its program where it is, so its includes resolve
    METIS_LOOP_LLP="$("$SDK_PY" -m metis.catalog --root "$ST/seed" get "$NAME" --json | field program)" || true
    [ -n "$METIS_LOOP_LLP" ] || { echo "loop.sh: --seed $SEED: its domain.yaml names no program the loop SDK reads" >&2; exit 1; }
    export METIS_LOOP_LLP
  else
    export METIS_LOOP_LLP="$ST/seed/$NAME.llp"
  fi
  # pi's first message: the seeded task (a client over --mode rpc sends it itself: DIR/.metis/seed/task.md)
  t="$(cat "$HERE/prompts/seed-task.md")"; t="${t//"{{SEED}}"/"$REL"}"; t="${t//"{{NAME}}"/"$NAME"}"   # no sed: any path
  t="${t//"{{EPISODES}}"/"${EPISODES:-20}"}"
  printf '%s\n' "$t" > "$ST/seed/task.md"
  case " $* " in *" --mode "*) ;; *) TASK=("$(cat "$ST/seed/task.md")") ;; esac
fi
export METIS_CATALOG="$DIR" METIS_LOOP_RECORDS="$ST/records" PI_LOOP_SESSIONS="$ST/sessions" METIS_LOOP_RUN="$ST"
# catalog_take's target: only the one named (--into, METIS_LOOP_TAKE_INTO), never a default
export METIS_LOOP_TAKE_INTO="$INTO"
# an RDDL world's host imports tools/rddl_host.py, which it looks for above its own directory;
# a DIR without tools/ (any DIR, a seed under .metis/) gets the installed metis-catalog's
TOOLS="$("$SDK_PY" -m metis.catalog installed --json | field tools)"
export PYTHONPATH="$TOOLS${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$ST/records" "$ST/sessions"
cd "$DIR"                                           # the workspace: pi and the tools it runs, in DIR
# the model (llm-config s-07a070ad): MODEL as given wins; else the dot file's [llm] loop (metispy metis.loop.llm: ONE
# configuration for every seat, set in the REPL with `llm loop WORDS`); no default: unset is refused, saying how
seat() {                                          # the seat's JSON; refused (2) when unset or on a metispy without the seats
  local o; o="$(PYTHONPATH="$HERE/..${PYTHONPATH:+:$PYTHONPATH}" "$SDK_PY" -m metis.loop.llm pi "$1")" || return 2
  [ -n "$o" ] || { echo "loop.sh: this metispy has no [llm] seats (python -m metis.loop.llm pi: llm-config)" >&2; return 2; }
  printf '%s' "$o"; }
OLLAMA_ID="" OLLAMA_BASE=""
if [ -z "${MODEL:-}" ]; then
  seatj="$(seat loop)" || { echo "loop.sh: no model: set [llm] loop (the REPL's llm loop WORDS) or give MODEL=<provider>/<id>" >&2; exit 2; }
  MODEL="$(printf '%s' "$seatj" | field model)"
  if [ "$(printf '%s' "$seatj" | field backend)" = ollama ]; then
    OLLAMA_ID="$(printf '%s' "$seatj" | field id)" OLLAMA_BASE="$(printf '%s' "$seatj" | field base_url)"
  fi
  echo "loop.sh: MODEL from $(printf '%s' "$seatj" | field where) ($(printf '%s' "$seatj" | field spec))" >&2
fi
# an Ollama model: pi's provider `ollama` over the server's OpenAI-compatible /v1, in an agent directory generated
# for this start (DIR/.metis/pi-agent/: pi/agent/models.json with the provider merged; loop/pi_models.py says
# why); no key, cost 0, no budget needed. MODEL=ollama/M given: the server is METIS_OLLAMA_URL, else 127.0.0.1:11434
case "$MODEL" in
  ollama/*)
    OLLAMA_ID="${OLLAMA_ID:-${MODEL#ollama/}}"
    case "$OLLAMA_ID" in *:off|*:minimal|*:low|*:medium|*:high|*:xhigh|*:max) OLLAMA_ID="${OLLAMA_ID%:*}" ;; esac
    OLLAMA_BASE="${OLLAMA_BASE:-${METIS_OLLAMA_URL:-http://127.0.0.1:11434}/v1}"
    PI_CODING_AGENT_DIR="$(PYTHONPATH="$HERE/..${PYTHONPATH:+:$PYTHONPATH}" "$SDK_PY" -m loop.pi_models ollama-agent \
      --state "$ST" --id "$OLLAMA_ID" --base-url "$OLLAMA_BASE")" || { echo "loop.sh: the Ollama agent directory was not written" >&2; exit 1; }
    export PI_CODING_AGENT_DIR ;;
esac
# the kernel's formalize (FORMALIZE_MODEL given wins): the dot file's [llm] formalize, default its [llm] loop; else, as
# before, an openrouter MODEL's own; an Ollama one is metispy's own ollama: backend (FORMALIZE_SPEC), no face, no key
FORMALIZE_SPEC=""
if [ -z "${FORMALIZE_MODEL:-}" ] && fj="$(seat formalize 2>/dev/null)"; then
  case "$(printf '%s' "$fj" | field backend)" in
    openrouter) FORMALIZE_MODEL="$(printf '%s' "$fj" | field model)" ;;
    *) FORMALIZE_SPEC="$(printf '%s' "$fj" | field spec)" ;;
  esac
fi
case "${FORMALIZE_MODEL:-}" in
  ollama/*) FORMALIZE_SPEC="ollama:${FORMALIZE_MODEL#ollama/}@${METIS_OLLAMA_URL:-http://127.0.0.1:11434}"; FORMALIZE_MODEL="" ;;
esac
if [ -z "${FORMALIZE_MODEL:-}" ] && [ -z "$FORMALIZE_SPEC" ] && [ -n "$OLLAMA_ID" ]; then
  FORMALIZE_SPEC="ollama:$OLLAMA_ID@${OLLAMA_BASE%/v1}"            # the loop's own model, formalize's default
fi
# METIS_LOOP_THINKING=off|minimal|low|medium|high|xhigh|max: pi's thinking suffix on a MODEL without one of its own
# (the console's chat sets off when its options say "no thinking"); unset or on: pi's default level for the model.
# Reasoning stays on by default (loop-prompt, PROMPT.md §2: the output cap is 8192, agent/models.json)
case "${METIS_LOOP_THINKING:-}" in
  ""|on) ;;
  off|minimal|low|medium|high|xhigh|max)
    case "$MODEL" in
      *:off|*:minimal|*:low|*:medium|*:high|*:xhigh|*:max) ;;
      *) MODEL="$MODEL:$METIS_LOOP_THINKING" ;;
    esac ;;
  *) echo "loop.sh: METIS_LOOP_THINKING=$METIS_LOOP_THINKING: off | minimal | low | medium | high | xhigh | max (unset: pi's default)" >&2; exit 2 ;;
esac
# a paid model runs with a budget (1 USD by default: a session of v4 pro at 8192 tokens a request spends
# cents a turn, so 1 USD bounds a runaway session well inside a paid round's limit); empty: refused
# the key: the environment's; unset, the person's key file (the architect's F5: a start from the chat got no key),
# read only when it is the person's own and private (mode 600 or 400), into the environment, never printed
KEYFILE="${METIS_OPENROUTER_ENV-$HOME/.config/metis/openrouter.env}"
case "$MODEL${FORMALIZE_MODEL:-}" in
  *openrouter/*)
    if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -n "$KEYFILE" ] && [ -f "$KEYFILE" ] && [ -O "$KEYFILE" ]; then
      case "$(stat -c %a "$KEYFILE" 2>/dev/null)" in
        600|400)
          # PARSED, never sourced (nina's review: sourcing runs the file, and bash's error for a bare-key line
          # prints the key, which the backend journals): the last OPENROUTER_API_KEY= line only (export and
          # spaces around = allowed), quotes stripped, the value's first word; nothing else of the file is read
          { set +x; } 2>/dev/null
          _k="$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}OPENROUTER_API_KEY[[:space:]]*=[[:space:]]*//p' "$KEYFILE" | tail -n 1 | tr -d '\r')"
          case "$_k" in \"*) _k="${_k#\"}"; _k="${_k%%\"*}" ;; \'*) _k="${_k#\'}"; _k="${_k%%\'*}" ;; esac
          _k="${_k%%[[:space:]]*}"
          if [ -n "$_k" ]; then export OPENROUTER_API_KEY="$_k"; echo "loop.sh: OPENROUTER_API_KEY from $KEYFILE" >&2
          else echo "loop.sh: $KEYFILE has no OPENROUTER_API_KEY= line: not read" >&2; fi
          unset _k ;;
        *) echo "loop.sh: $KEYFILE is not private (chmod 600 it): not read" >&2 ;;
      esac
    fi ;;
esac
case "$MODEL" in
  openrouter/*)
    [ -n "${OPENROUTER_API_KEY:-}" ] || { echo "loop.sh: MODEL=$MODEL needs OPENROUTER_API_KEY: the environment, or ${KEYFILE:-a key file} (mode 600)" >&2; exit 1; }
    METIS_LOOP_BUDGET="${METIS_LOOP_BUDGET-1.00}"
    [ -n "$METIS_LOOP_BUDGET" ] || { echo "loop.sh: MODEL=$MODEL is paid: give --budget USD (or METIS_LOOP_BUDGET)" >&2; exit 1; }
    awk -v b="$METIS_LOOP_BUDGET" 'BEGIN { exit !(b + 0 > 0) }' || { echo "loop.sh: --budget $METIS_LOOP_BUDGET: a positive number of USD" >&2; exit 1; } ;;
  *) METIS_LOOP_BUDGET="${METIS_LOOP_BUDGET-}" ;;
esac
export METIS_LOOP_BUDGET
echo "loop.sh: MODEL=$MODEL budget=${METIS_LOOP_BUDGET:-none} USD${FORMALIZE_SPEC:+ formalize=$FORMALIZE_SPEC}" >&2   # the first line (stderr: stdout is pi's, the rpc protocol in rpc mode)
case "$MODEL" in
  openrouter/*) [ -n "$FORMALIZE_SPEC" ] || FORMALIZE_MODEL="${FORMALIZE_MODEL:-$MODEL}" ;;
esac
FORMALIZE_MODEL="${FORMALIZE_MODEL:-}"
case "$FORMALIZE_MODEL" in                                       # pi's thinking suffix is pi's, not the model's
  *:off|*:minimal|*:low|*:medium|*:high|*:xhigh|*:max) FORMALIZE_MODEL="${FORMALIZE_MODEL%:*}" ;;
esac
# an RDDL world's host runs its gym under this python (tools/rddl_host.py: pyRDDLGym); a DIR
# has no .venv beside it and the domain agent's venv has no gym (rddl-worlds step 2, finding 1)
export METIS_RDDL_PY="${METIS_RDDL_PY:-$PKGS/.venv/bin/python}"
# the kernel's formalize on FORMALIZE_MODEL through its command: backend: the SDK's
# OpenAI-compatible face on OpenRouter (the key reaches it through the environment: pi's,
# then the REPL's), or its claude -p face; none named, no [llm] endpoint is written
CONF="${METIS_CONFIG:-$(mktemp -t metis-loop-XXXX.toml)}"
if grep -q -E "ollama/generate.py|ollama-command" "$CONF" 2>/dev/null; then   # an old config: that face is gone
  echo "loop.sh: $CONF names an Ollama face, which is gone: unset METIS_CONFIG (loop.sh writes one) or use" \
       "command:$SDK_PY -m metis_loop_sdk.models openai-command --base-url U --model M" >&2; exit 1
fi
if [ ! -s "$CONF" ]; then
  FACE=""
  case "$FORMALIZE_MODEL" in
    openrouter/*)
      : "${OPENROUTER_API_KEY:?formalize on $FORMALIZE_MODEL: OPENROUTER_API_KEY from the environment}"
      FACE="openai-command --base-url https://openrouter.ai/api/v1 --model ${FORMALIZE_MODEL#openrouter/}"
      FACE="$FACE${METIS_LOOP_RECORDS:+ --log $METIS_LOOP_RECORDS/formalize-calls.jsonl}" ;;
    claude)   FACE="claude-command" ;;
    claude/*) FACE="claude-command --model ${FORMALIZE_MODEL#claude/}" ;;
    "") ;;
    *) echo "loop.sh: FORMALIZE_MODEL=$FORMALIZE_MODEL: openrouter/<id> or claude[/<id>]" >&2; exit 1 ;;
  esac
  if [ -n "$FACE" ]; then printf '[llm]\nendpoint = "command:%s -m metis_loop_sdk.models %s"\n' "$SDK_PY" "$FACE" > "$CONF"
  elif [ -n "$FORMALIZE_SPEC" ]; then printf '[llm]\nendpoint = "%s"\n' "$FORMALIZE_SPEC" > "$CONF"; fi
fi
export METIS_CONFIG="$CONF"
export METIS_LOOP_METIS="${METIS_LOOP_METIS:-$PKGS/.venv/bin/metis}"
export METIS_LOOP_SDK_PY="$SDK_PY"                    # the extensions' catalog: the loop SDK's catalog CLI
export METIS_LOOP_AGENT_PY="${METIS_LOOP_AGENT_PY:-$AGENT/py/.venv/bin/python}"
export METIS_LOOP_AGENT_DIR="$AGENT/py"
# one pi loop per workspace (WORKSPACE.md §2.3): a live one's lock refuses this start; the extension
# (metis-workspace) takes the lock for pi's own pid, a dead holder's is taken over
held="$("$SDK_PY" -m metis.catalog.workspace --root "$DIR" loops --json | "$SDK_PY" -c '
import json, sys
p = json.load(sys.stdin).get("pi")
print("" if not p or p.get("alive") is False else "pid %s, started %s, mode %s" % (p.get("pid"), p.get("started"), p.get("mode")), end="")')"
[ -z "$held" ] || { echo "loop.sh: a pi loop runs in $DIR already ($held): one per workspace" >&2; exit 1; }
case " $* " in *" --mode rpc "*) export METIS_LOOP_MODE=rpc ;; *) export METIS_LOOP_MODE=tui ;; esac
# the tool set (loop-prompt, PROMPT.md §3; extensions/lib/toolset.ts): seed with --seed or a DIR without a bundle (the
# standalone catalog loop), workspace when DIR has one (the surprise loop); METIS_LOOP_TOOLS given is kept
if [ -z "${METIS_LOOP_TOOLS:-}" ]; then
  if [ -n "$SEED" ]; then METIS_LOOP_TOOLS=seed
  elif [ "$("$SDK_PY" -m metis.catalog.workspace --root "$DIR" bundle --json 2>/dev/null | head -c 4)" = null ]; then METIS_LOOP_TOOLS=seed
  else METIS_LOOP_TOOLS=workspace; fi
fi
export METIS_LOOP_TOOLS
export MODEL
exec "${METIS_LOOP_PI:-$HERE/pi.sh}" --model "$MODEL" --system-prompt "$HERE/prompts/loop-system.md" "$@" "${TASK[@]}"
