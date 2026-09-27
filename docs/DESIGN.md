# metis-loop — shape proposal (decision deferred)

2026-09-27. The loop's *content* is settled by stage 45 and the
formalization contract (metis docs/rewrite/07-formalization.md); its
*deployment shape* is not. This note fixes what is shape-independent,
lists the candidate shapes, and names the evidence that will decide.

## What the loop IS, in any shape

A pipeline of pure stages over data, with exactly two heavyweight
dependencies (the LLM and the metispy gate harness), both behind
seams:

    SurpriseSource ──► miner ──► text (%% doc, the APPROVED UNIT)
                                   │
                          Formalizer (LLM seam)
                                   │  .llp candidate
                          Gates: admit_text_pack (metispy)
                          parse / roundtrip / containment /
                          class-F / EXACT measure-diff / MAP read-back
                                   │  findings
                          repair loop (findings → Formalizer, ≤N)
                                   │
                          Approval artifact: text + pack +
                          measure-diff + certificate → human

Interfaces to hold stable from day one:

- **SurpriseSource** — reads surprise records (metis kernel/record.py
  wire; the chariot `wayplan_surprise` sink rows are the first real
  corpus). File/dir first; anything streaming is an adapter.
- **Formalizer** — `(vocabulary context, task text, findings so far)
  → llp source`. Backends: Claude Code / Opus 5.5 first (establish
  the ceiling), then any OpenAI-compatible HTTP endpoint (Ollama,
  llama.cpp) for the local-model experiments. One function, no
  framework.
- **Gates** — metispy's `admit_text_pack` verbatim. The loop never
  reimplements semantics; it orchestrates the harness.
- **Sink** — the approval artifact. Approved base edits / packs flow
  to metis-catalog as ordinary reviewed commits; the loop never
  writes a catalog directly.

Explanation is the same machinery read backwards (MAP read-back,
per-tick likelihood narratives over the runtime surprise op) and
belongs in this repo as a second consumer of the same interfaces —
not a separate system.

## Candidate shapes

**A. CLI (`metis-loop run`, batch offline).** Thin wrapper over the
core; mines a records file, emits approval artifacts. Cheapest to
build, testable in CI against the stage-45 benchmark. *Build this
first regardless — every other shape wraps it.*

**B. Claude Code plugin.** A skill packaging the loop
conversationally: the agent is the Formalizer, the gates run through
the CLI, the human approval IS the conversation. First real
deployment (per the plan: strong model first, Opus 5.5). Cheap
because it is mostly prompt + the CLI.

**C. Service.** A daemon watching the surprise sink, proposing packs
into a review queue. Right shape iff the loop proves mostly-automatic
(low repair counts, rare human edits). Do not build before the
metrics exist.

**D. Runtime library (behavior-interpreter embedding).** The
explanation half embedded next to the C++ runtime (narrating
decisions, scoring surprises in-process); formalization stays
offline — text as the approved unit rules out closed-loop catalog
self-modification in the vehicle BY DESIGN (07-formalization).
So D is only ever the *explanation* shape, never the formalize shape.

**E. Editor/LSP code action** ("formalize this text"). Sugar over
the CLI once B stabilizes the prompt shape.

## Proposal

Hexagonal: **the loop is a library (core/) with the four seams
above; A is its first binding, B its first deployment.** Defer C/D/E.
The decision inputs to collect from running B on real soak rows:

1. repair-loop iteration count and gate pass-rate per model class
   (Opus 5.5 ceiling vs local floor) — decides whether C is viable;
2. how often the human edits the TEXT vs the PACK — decides how
   interactive the approval must be (B/E vs C);
3. latency and context size of the gate cascade per candidate —
   decides whether explanation needs D or stays offline tooling.

Language: python (it orchestrates metispy and talks HTTP; there is
no compiler-grade component here). If a runtime explanation library
(D) materializes, its in-process half lands in metis-lang/runtime as
ordinary headers, not here.
