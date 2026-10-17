"""metis_loop_sdk — the loop SDK (metis-loop/sdk; loop-sdk s-9aabd5a0).

The code that has to stay the same in every consumer, and nothing else:
  catalog  catalog access: the one root fallback, the domains, their
           intents, the one validated write (apply), the catalog widget
           (catalog-sdk s-bc1718e3)
  models   the model adapters: claude -p (command, seat, chat endpoint)
           and ollama (think-off command, the GPU probe)

Each has a JSON CLI for non-Python consumers (`python -m metis_loop_sdk.<m>`).

The direction of dependency: this package imports metis_catalog and metispy
and nothing else of ours — never metis-loop's `loop`, `metis_agent` or the
agentic loop (tests/test_direction.py; CI installs it alone)."""

__version__ = "0.1.0"
