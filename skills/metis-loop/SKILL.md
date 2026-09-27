---
name: metis-loop
description: >
  Drive the metis formalization loop conversationally: read surprise
  records, mine the text description, write the candidate LLP pack,
  run it through the gate cascade, repair on findings, sync the
  console artifact, and turn approvals into metis-catalog commits.
  Use when the user mentions surprise records, formalizing observed
  behavior into rules, the loop console, or /metis-loop.
---

# The loop, driven by this session

You are the FORMALIZER seat of the metis loop (shape B of
docs/DESIGN.md). The gates are the authority, never you: every
candidate you write goes through `admit` and only the harness
verdict counts. The text is the approved unit — rules carry `%%`
docs quoting it.

Paths (adjust to the checkout): `metis-loop` (this repo, CLI
`python -m loop.cli` with metispy + metis-loop on PYTHONPATH),
`metispy` (the harness), `metis-lang` (metisc + corpus),
`metis-catalog` (where approved rules land). The console artifact
URL is in the project memory; sync it with the ArtifactData tool
(collections `surprise`, `candidates`; approvals arrive as
`status: approved` on candidate docs).

## The cycle

1. **Ingest**: load new records (JSONL sink or `surprise` docs with
   `status: new`). For each: `metis-loop replay` against the base
   catalog for the explanation; push likelihood/explanation to the
   record doc; set `status: investigating`.
2. **Mine**: write the `%%` text description of the unmodeled
   behavior from the record's observed-vs-modeled gap. Short,
   factual, quoting atoms. Store as `mined_text` on the record.
3. **Formalize**: YOU write the candidate `.llp` pack over the base
   vocabulary (packs consume base atoms, never produce them —
   containment admission enforces it; new vocabulary only for new
   observations). Numbers from data: prior-mode measures, no invented
   weights — notching fits them later.
4. **Gate**: `metis-loop admit TEXT.md CAND.llp --base BASE.llp
   --scenario a=1,b=2 --steps N`. On findings: repair and re-run,
   at most 4 rounds; every round's findings go in the candidate doc
   history. Push the final report (ok, findings, warnings, rules,
   classification, scenarios with measure diffs) as a `candidates`
   doc, `status: pending`.
5. **Approval**: never approve yourself. The human approves in the
   console (or in chat). On `status: approved`: commit text + pack
   to metis-catalog (packs/, with the text as the commit body),
   re-run the catalog gates (`ci/check.sh`), and replay the record
   corpus against the merged catalog (`metis-loop replay`) —
   the record's likelihood must become positive; report the new
   trace. On `rejected`: record why, stop.

Never bypass a gate, never edit the harness to make a candidate
pass, never write catalog files for an unapproved candidate.
