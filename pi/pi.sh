#!/usr/bin/env bash
# pi.sh — pi as the agentic loop's host: the pinned node and pi, this
# directory's agent config (models.json: pi's built-in OpenRouter capped at
# 8192 output tokens with data_collection=deny; a key only from the environment,
# never in a file here; no OAuth), no startup network, of pi's built-in tools only
# read, no context files, prompt templates or MCP, the three metis extensions and
# the skills under skills/ (docs/LOOP-AGENT.md; loop-prompt, docs/PROMPT.md §2). The TUI in regular mode: the apply gate's diff can be taller
# than the terminal, and fullscreen then hides its Yes/No; regular leaves it in the
# terminal's scrollback (a later --tui-mode fullscreen overrides).
#   pi.sh [pi args...]      e.g. --mode rpc, --model openrouter/deepseek/deepseek-v4-pro
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HERE/node/bin:$PATH" PI_CODING_AGENT_DIR="${PI_CODING_AGENT_DIR:-$HERE/agent}" \
       PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
# not installed in this checkout (the architect's F4: exit 127 from a shared checkout without pi): say the fix
[ -x "$HERE/node_modules/.bin/pi" ] && [ -x "$HERE/node/bin/node" ] || {
  echo "pi.sh: pi is not installed in $HERE (no node_modules/.bin/pi or node/bin/node): run $HERE/setup.sh once" >&2; exit 127; }
"$HERE/setup.sh" --link                              # extensions/sdk: the loop SDK's TypeScript face, as installed
# the skills (loop-prompt, PROMPT.md §2): each directory under skills/ by --skill (loaded under --no-skills; pi lists
# their name, description and path in the system prompt, and the model reads a SKILL.md with read when its task
# matches). --tools +read adds pi's read and nothing else of its own (bash, edit, write stay off); metis-workspace
# keeps read to the skills and the workspace (readRefusal)
SKILLS=()
for d in "$HERE"/skills/*/; do [ -f "$d/SKILL.md" ] && SKILLS+=(--skill "${d%/}"); done
exec "$HERE/node_modules/.bin/pi" --no-builtin-tools --tools +read --no-context-files --no-skills "${SKILLS[@]}" \
  --no-prompt-templates --no-mcp --no-approve --no-extensions --tui-mode regular \
  -e "$HERE/extensions/metis-repl.ts" -e "$HERE/extensions/metis-domain.ts" -e "$HERE/extensions/metis-workspace.ts" \
  --session-dir "${PI_LOOP_SESSIONS:-$HERE/agent/sessions}" "$@"
