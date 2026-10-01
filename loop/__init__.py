"""metis-loop — WRAPPERS over the one kernel REPL (the metis
shell): the web console (console/), the Claude Code skill (skills/),
and the `metis-loop` CLI bindings (admit/formalize/replay). The loop
kernel itself lives in metispy as `metis.loop` (core seams, the LLM
endpoint, the narrate boundary, the shell verbs, the intent wire);
this package re-exports the core API for compatibility."""
from metis.loop.core import (FormalizeResult, admit,  # noqa: F401
                             formalize_loop, load_records,
                             render_prompt, replay)

__all__ = ["FormalizeResult", "admit", "formalize_loop",
           "load_records", "render_prompt", "replay"]
