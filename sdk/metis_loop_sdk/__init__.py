"""metis_loop_sdk — the loop SDK (metis-loop/sdk; loop-sdk s-9aabd5a0).

The code that has to stay the same in every consumer, and nothing else:
  web      the catalog widget the consoles serve and the TypeScript face
           (the catalog itself is metispy's metis.catalog, the gate
           metis.gate: the SDK's shims went at 0.1.14)
  models   the model adapters: claude -p (command, seat, chat endpoint)
           and ollama (think-off command, the GPU probe)

Each has a JSON CLI for non-Python consumers (`python -m metis_loop_sdk.<m>`).

The direction of dependency: this package imports metispy and nothing else
of ours — never metis-loop's `loop`, `metis_agent` or the
agentic loop (tests/test_direction.py; CI installs it alone)."""

__version__ = "0.2.0"
