"""metis-loop — the formalization/explanation loop over four seams:
SurpriseSource (JSONL records), Formalizer (an external command),
Gates (metispy admit_text_pack), Sink (the approval artifact).
Deployment shape stays open (docs/DESIGN.md); this package is the
core library + the CLI, which every shape wraps."""
from .core import (FormalizeResult, admit, formalize_loop, load_records,
                   render_prompt, replay)

__all__ = ["FormalizeResult", "admit", "formalize_loop", "load_records",
           "render_prompt", "replay"]
