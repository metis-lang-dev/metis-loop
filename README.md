# metis-loop

[![ci](https://github.com/metis-lang-dev/metis-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/metis-lang-dev/metis-loop/actions/workflows/ci.yml)

The explanation / formalization loop for metis catalogs:

    surprise records → mined text → formalize (LLM) → gated candidate
    pack → repair loop → human-approved catalog change

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
