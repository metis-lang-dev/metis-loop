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
