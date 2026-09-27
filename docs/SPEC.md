# The metis loop — specification

One file, authoritative for this repo. Supersedes the earlier
DESIGN.md (folded in) and every scattered fragment; the language and
gate semantics it leans on stay owned by metis-lang (specs) and
metispy (07-formalization, learning.md) — this file cites, never
restates, them.

## 1. What the loop is

The improvement cycle of a metis world, with text as the approved
unit and the exact measure as the instrument:

    surprise record -> replay/explain -> mined TEXT -> formalize ->
    candidate .llp -> GATES -> repair (findings feed back) ->
    human approval -> catalog commit -> recompile -> replay corpus

and read backwards, EXPLANATION: which rule fires, why this
decision, narrated from certified material (MAP derivation +
per-candidate marginals + the rules' own %% docs), never generated
from thin air. The LLM sits at exactly two text boundaries —
formalize in, narrate out — and never inside the semantics.

## 2. The kernel is a REPL; every UI is a wrapper

Lean/Coq architecture. `metis-loop repl` holds the session state —
WORLD (accepted catalog; tabula rasa starts empty), TEXT, CANDIDATE,
REPORT, scene (init/steps/seed) — behind one dispatcher spoken two
ways: the interactive prompt and the JSON-lines wire (`repl --json`,
one `{op, arg}` per line, one JSON result per line). Wrappers hold
NO semantics:

| wrapper | binding |
| --- | --- |
| CLI verbs (`admit`, `formalize`, `replay`) | batch calls of the same core |
| Claude Code plugin (`skills/metis-loop`) | the session drives the REPL; it is the formalizer seat |
| web console (the Loop Console artifact) | db documents in/out; a loop session executes |
| editor panels (later) | the JSON wire |

## 3. REPL verbs (the protocol)

    :text  :llp                 the approved unit; the candidate source
    :formalize CMD...           draft via a backend command (stdin: prompt,
                                stdout: LLP) — `claude -p --model opus`
                                and a local-model wrapper are interchangeable
    :gate                       EXTENSION: full cascade against the world
    :revise                     BASE EDIT: gate the candidate standalone;
                                the next :accept REPLACES the world
    :accept                     admitted candidate joins (or replaces) the world
    :init a=1,b=2  :steps N     the scene
    :trace [seed]               one synthetic trajectory (the seeded
                                reference sampler; 06-sampler-wire)
    :map                        the modal derivation (Viterbi), events
                                labeled stage/rule
    :marginals [atoms]          exact final marginals (the measure)
    :show :save                 state; world.llp + text.md out

## 4. Extension vs revision (the redefinition doctrine)

Two change classes, mechanically distinct, per the design finding of
2026-07-19 (metis TODO):

- **Extension** (`:gate` + `:accept`): a pack. Containment admission
  makes packs ONLY ADD: a pack may not produce OR consume a base
  atom unless the base namespace grants the right explicitly;
  base state is reachable read-only through `$`-persist premises.
  There is no redefinition through this path — a pack reusing a base
  rule's short name coexists (entry names are layer-qualified) and
  draws a discipline WARNING, because traces, MAP read-back and the
  debug sidecar identify events by short name.
- **Revision** (`:revise` + `:accept`): a base edit — the
  human-approved catalog diff. The world is REPLACED: the canonical
  key moves, accepted packs DROP (they were admitted against the old
  base and must be re-proposed), and the before/after exact measure
  diff on the current scene is the consistency instrument — it also
  surfaces the dropped packs (their vocabulary vanishes from the
  measure; their consumed triggers reappear).

## 5. Consistency: what the kernel admits and what catches the rest

The kernel admits any WELL-TYPED rules; "consistency" is not
classical non-contradiction — in linear logic rules are transitions
over resources, so conflicting rules are a RACE priced by the
measure, never an explosion. The layered checks, in order:

1. parse + `parse(pretty(a)) = a` roundtrip;
2. typecheck: namespace production/consumption rights, layers,
   stages (ill-typed, not lint-flagged);
3. containment admission (packs constrain, never enable);
4. proof-net certification (bpn: no ill-typed net ships);
5. class-F statics (factorizability; the exact counterexample quoted);
6. the SEMANTIC instruments — the only tier that catches
   plausible-but-wrong: exact measure diff vs base, MAP read-back,
   support size, and the stall discipline (a missing else-branch is
   a detectable Z < 1, never a silent bug);
7. after acceptance: the record corpus replay (every stored surprise
   record re-scored; an admitted fix must move its likelihood
   positive) and, per repo, the corpus gates (program_key identity,
   goldens).

## 6. Transport and state

- **Runtime -> loop**: surprise records (metispy kernel/record.py):
  small JSON — program_key + meta, tick init, observed outcome,
  horizon, verdict. Pointers, not traces: evaluation is
  deterministic, the loop re-derives everything via `recover()`.
  Carrier: a JSONL sink file; anything streaming is an adapter.
- **Console <-> loop**: the artifact db. Collections: `surprise`
  (records + explanation + mined_text + status: new/investigating/
  formalized/dismissed), `candidates` (llp, report fields, rounds,
  model, status: pending/regate/approved/rejected + decided_by/ts),
  `catalogs` (one doc per catalog .llp: name/path/group/kind/note/
  llp — read-only mirror of metis-catalog, resynced after commits).
  Console edits set `status: regate`; a loop session re-runs the
  cascade and posts the fresh report. Approvals are human, in the
  console or in chat — a loop session NEVER approves.
- **Loop -> catalog**: approved candidates become metis-catalog
  commits (the text is the commit body), then recompile + corpus
  replay.

## 7. Explanation from IR (the debug sidecar)

The IR wire is name-free; the determinism contract (metis-lang
01-ir-spec §0: site-candidate order = canonical event order) makes
rule identity DERIVABLE. `metispy ir_debug_lines()` emits it as
detached debug info — `D <site> <n> <rule-names...>` — keyed to the
artifact, never authoritative (a missing sidecar degrades to
indices, never wrong names). An interpreter joins artifact + sidecar
+ %% docs to answer "which rule fires and why" from the runtime
path; the gate: it must agree with the REPL's `:map` on the same
scene (verified: meadow, IR PARITY + marginal equality at 1e-12).

## 8. Deployment shapes (status)

- REPL kernel + CLI: BUILT (this repo).
- Claude Code plugin: BUILT (skills/metis-loop).
- Web console: BUILT (queue, gates, diffs, editor->regate, catalog
  browser, in-page analyst).
- Service (daemon watching sink + console): build when the metrics
  say the loop is mostly-automatic (repair counts, gate pass-rate,
  human-edit rate).
- In-runtime explanation lib: only ever the EXPLANATION half —
  text-as-approved-unit rules out closed-loop catalog
  self-modification in the vehicle BY DESIGN.

## 9. Invariants (never violated by any wrapper)

1. The harness verdict is the only authority; no wrapper reimplements
   semantics.
2. Text is the approved unit; every rule carries its %% doc.
3. Approval is human. A loop session never approves, never commits
   unapproved candidates, never edits the harness to make a
   candidate pass.
4. Numbers from data: candidates ship prior-mode measures; weights
   arrive by notching or through declared ports.
5. Packs only add; base edits go through :revise with the diff
   surfaced.
