# metis-loop

[![ci](https://github.com/metis-lang-dev/metis-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/metis-lang-dev/metis-loop/actions/workflows/ci.yml)

**A loop starts in a directory, and that directory is the catalog and the
workspace**, as `cd DIR && claude` makes DIR the project:

```sh
cd DIR && metis-loop           # the human loop's console over DIR (./run.sh: the same, in the background)
cd DIR && metis-agentic-loop   # pi's loop over DIR
METIS_CATALOG=DIR metis-loop   # the same, started elsewhere
```

DIR's `domains/<name>/` packages are the catalog; an empty DIR is an empty
catalog (the console's `new` writes the first domain); the loop's processes
run in DIR; the loops' own state goes in `DIR/.metis/` (git-ignored when DIR
is a checkout). `cd metis-catalog && metis-loop` serves the catalog's own
domains. Nothing is found "beside this checkout".

## Your brain

The console's LLM seats (formalize, narrate, the agent chat) run on one brain,
chosen when it starts (`loop/brain.py`):

```sh
cd DIR && metis-loop --brain claude                               # your Claude subscription
cd DIR && metis-loop --brain openrouter                           # an OpenRouter key: deepseek/deepseek-v4-pro
cd DIR && metis-loop --brain openrouter:qwen/qwen3-235b-a22b-2507 # another OpenRouter model
cd DIR && metis-loop --brain ollama                               # the dot file's [llm] endpoint (local)
BRAIN=openrouter ./run.sh                                         # the same, in the background
```

| brain | needs | formalize | narrate | agent chat |
|---|---|---|---|---|
| `claude` | `pip install 'metis-loop[agent]'` (the Agent SDK, with its `claude` CLI) and your `claude` login | `formalize_model` (claude-haiku-4-5) | `narrate_model` (claude-haiku-4-5) | yes |
| `openrouter[:MODEL]` | `export OPENROUTER_API_KEY=…` (from the environment only, never a file) | MODEL, else `openrouter_model` | `openrouter_narrate_model` (deepseek/deepseek-v4-flash) | needs claude |
| `ollama` | the kernel's `[llm] endpoint` (Ollama by default) | that endpoint | that endpoint | needs claude |

Without `--brain` it is `[console] brain` in the metis dot file, else `claude`
when the Agent SDK is installed, else `openrouter` when `OPENROUTER_API_KEY`
is set, else `ollama` (so a key in your environment makes OpenRouter the
default); the start line says which, with its models. `:llm X` in a session
moves both of its seats to X. A brain
named and not available refuses at startup with the fix. On OpenRouter every
call goes only to providers that keep no prompts; formalize has reasoning off
and 2048 tokens, narrate `[console] narrate_reasoning` ("low": with it off,
narration invented events) and 4096 tokens; each call and its cost (OpenRouter's own figure) goes in
`DIR/.metis/formalize-calls.jsonl`, and a session stops calling once it has
spent `[console] max_usd` (1.00 USD). A shared instance (`--mode shared`)
serves no LLM seat on any brain.

The explanation / formalization loop for metis catalogs:

    surprise records → mined text → formalize (LLM) → gated candidate
    extension → repair loop → human-approved catalog change

and the reverse reading, explanation: MAP event read-back and
surprise narratives over a running catalog.

**The loop kernel lives in metispy as `metis.loop`** (user decision
2026-10-01: one kernel REPL — the metis shell; every UI a wrapper).
Interactive: `metis FILE.llp`, where the loop verbs are plain
commands (`gate`, `accept`, `mine`, `narrate`, ...). The JSON wire
for wrappers: `metis --json FILE.llp`. This repo is the wrappers —
the web console (console/), the Claude Code skill (skills/), the
`metis-loop` CLI — the console backend itself (bare `metis-loop`
serves; the shell is `metis`, the old batch verbs merged into the
kernel REPL) — plus `loop.*`
compatibility shims re-exporting `metis.loop.*`.

**The voice / dialog UI is fsttm-web** (metis-lang-dev/fsttm-web), served by metis-agent: `apps/nina-web` is retired (agent-framework, 2026-10-12).

**The spec lives in ONE file: [docs/SPEC.md](docs/SPEC.md)** — the
kernel-as-REPL architecture, the verbs, extension vs revision, the
consistency ladder, transports, the debug sidecar, and the
invariants. Built: the REPL + CLI, the Claude Code plugin
(`skills/metis-loop`), and the web Loop Console.

**Experiments live in metis-catalog.** The loop's concluded experiments
(the RDDL shelf, bridge-torch, wolf-goat-cabbage, hanoi, the port-plugin
fixtures, the pantry and meadow demos) moved on 2026-10-11 to sit next
to the domains they produced, each with a README of what formalization
taught. See the "Experiments" section of the metis-catalog README. This
repo keeps only the loop machinery.

**The loop SDK (`sdk/`)** installs from its tag (catalog access, the
catalog widget, the model adapters, the TypeScript face):
`pip install "metis-loop-sdk @ git+https://github.com/metis-lang-dev/metis-loop@sdk-vX.Y.Z#subdirectory=sdk"`,
after metispy (on PyPI) and metis-catalog (not on PyPI yet: its checkout
or git URL). Its consumers are metis-agent and
metis-agentic-loop; [sdk/README.md](sdk/README.md) has the install and the
release (a tag `sdk-vX.Y.Z`). The human loop itself is not published.

## License

Apache License 2.0 (see `LICENSE`, `NOTICE`).
