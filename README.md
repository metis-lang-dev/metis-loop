# metis-loop

The explanation / formalization loop for metis catalogs:

    surprise records → mined text → formalize (LLM) → gated candidate
    pack → repair loop → human-approved catalog change

and the reverse reading, explanation: MAP event read-back and
surprise narratives over a running catalog.

**The spec lives in ONE file: [docs/SPEC.md](docs/SPEC.md)** — the
kernel-as-REPL architecture, the verbs, extension vs revision, the
consistency ladder, transports, the debug sidecar, and the
invariants. Built: the REPL + CLI, the Claude Code plugin
(`skills/metis-loop`), and the web Loop Console.
