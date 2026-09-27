# metis-loop

The explanation / formalization loop for metis catalogs:

    surprise records → mined text → formalize (LLM) → gated candidate
    pack → repair loop → human-approved catalog change

and the reverse reading, explanation: MAP event read-back and
surprise narratives over a running catalog.

**The deployment shape is deliberately undecided** — library for a
runtime behavior interpreter, offline service, or editor tooling.
See `docs/DESIGN.md` for the candidate shapes, what the loop is
regardless of shape, and the criteria that will pick one.

Status: provisioned; no code yet. First experiment target: a Claude
Code plugin driving the loop with a strong model (Opus 5.5) against
the stage-45 gate harness (`metispy` `admit_text_pack`) and the real
soak surprise rows.
