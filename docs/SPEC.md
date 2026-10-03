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
Both boundaries speak through ONE configurable endpoint (loop/llm.py:
ollama[:MODEL] | anthropic[:MODEL] | command:ARGV; `:llm` sets it,
page intents may never name a command). The narrate boundary is the
`:narrate` verb (loop/narrate.py): one seeded trace rendered in its
Foata beats + final state + %% docs, prompt-bound to the concurrency
doctrine — within a beat only simultaneity language (same-beat events
are independent; their order carries no information), across beats
causal language licensed by the rules, threads told with explicit
rewinds, repetitions aggregated. The same boundary is mounted in the
metispy shell (`llm` / `narrate`, soft dependency on this package):
`narrate` tells the interactive session itself; `narrate SEED` a
sampled trace.

## 2. The kernel is a REPL; every UI is a wrapper

Lean/Coq architecture — and since 2026-10-01 (user decision) the one
kernel REPL is THE METIS SHELL (`metis FILE.llp`, metispy): the loop
merged into it as plain commands (metis.loop.verbs — text/llp/load/
formalize/gate/revise/accept/mine/sink/records/record/replay/show/
export, llm/narrate), because the shell was already the runtime
session and the loop's judgements were already metispy's. The WORLD
is the served catalog (+ accepted packs; `accept` RE-SERVES the
merged catalog live — new key, new events, counts carry over);
tabula rasa = serve a blank catalog and `revise` it. The JSON-lines
wire is `metis --json FILE.llp` (one `{op, arg}` per line, one JSON
result per line; metis.loop.wire, which also owns the intent
policy). This repo is now the WRAPPERS: the web console, the Claude
Code skill, the `metis-loop` CLI bindings (admit/formalize/replay),
and compatibility shims (`loop.*` re-exports `metis.loop.*`).
Wrappers hold
NO semantics:

| wrapper | binding |
| --- | --- |
| CLI verbs (`admit`, `formalize`, `replay`) | batch calls of the same core |
| Claude Code plugin (`skills/metis-loop`) | the session drives the REPL; it is the formalizer seat |
| web console (the Loop Console artifact) | db documents in/out; a loop session executes |
| editor panels (later) | the JSON wire |

## 3. REPL verbs (the protocol)

    :sink FILE.jsonl            load surprise records (the runtime's sink)
    :records  :record [N]       list them; select one — its init/steps
                                become the scene, its mined_text the TEXT
    :mine [TEXT]                bare: the observed-vs-modeled gap; with
                                TEXT: set the approved unit + stamp the record
    :replay                     recover() the record against the world:
                                the explanation before a fix, the
                                verification after (`fixed` = likelihood
                                moved positive)
    :text  :llp                 the approved unit; the candidate source
    :formalize [BACKEND]        draft the candidate. Default: the local
                                model through the OLLAMA ADAPTER
                                (loop/ollama.py, stdlib urllib; $OLLAMA_HOST
                                / $OLLAMA_MODEL; `ollama:MODEL` picks one) —
                                no plugins in the path. Anything else is an
                                external command (stdin: prompt, stdout:
                                LLP); `python -m loop.ollama` is that same
                                adapter as a command
    :gate                       EXTENSION: full cascade against the world
    :revise                     BASE EDIT: gate the candidate standalone;
                                the next :accept REPLACES the world
    :accept                     admitted candidate joins (or replaces) the world
    :load FILE.llp              candidate from a file, includes spliced;
                                its '#'-directives (metis-lang spec §8)
                                seed the scene, and its leading comment
                                block the TEXT, where still unset
    :init a=1,b=2  :steps N  :seed N        the scene
    :trace [seed]               one synthetic trajectory (the seeded
                                reference sampler; 06-sampler-wire)
    :map                        the modal derivation (Viterbi), events
                                labeled stage/rule
    :marginals [atoms]          exact final marginals (the measure)
    :show :save :help           state; world.llp + text.md out; verbs

The interactive prompt wraps the same dispatcher with readline (line
editing, tab-completed verbs, history at $XDG_STATE_HOME/metis-loop/
history); piped stdin and the JSON wire stay byte-clean.

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
  console or in chat — a loop session NEVER approves. The console's
  REPL window queues `intents` docs ({cmd, record_id, status:
  queued}) — one REPL line each, typed by the viewer; a loop session
  drains them ONLY through `loop.repl.run_intent` (the single
  whitelist: drafting and instrument verbs; never :accept, file
  paths, or arbitrary backend commands) and posts {status:
  done|refused, result}. The console holds NO model integration of
  its own: the only LLM in the loop is the REPL's ollama backend.
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

- REPL kernel + CLI: BUILT (this repo) — and since the surprise /
  refinement verbs (:sink/:record/:mine/:replay) and the built-in
  Ollama backend landed, the REPL alone IS the loop: no plugin, no
  console, no external command required.
- Claude Code plugin: BUILT (skills/metis-loop) — OPTIONAL; a
  conversational seat over the same wire, never a dependency.
- Web console: A REPL WRAPPER (2026-09-29). The page follows the
  REPL verb by verb — :record (scene) / :replay (trace &
  explanation) / :mine (text) / :gate (report) / :accept
  (approve/reject, the page's only decision write) — plus a REPL
  window (viewer-typed commands queue as intents; results stream
  back) and a separate Δ-rules window when a module (pack candidate)
  is loaded. LLP sources render through the in-page colorizer
  (lexer's token classes). Sources are READ-ONLY everywhere (edits
  go file -> reload); the in-page editor, edit->regate path and the
  Claude analyst are gone — no model integration in the page.
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

## 10. Direction (the change vector)

Where this software is going — recorded 2026-10-03, updated as the
orientation moves. The orientation itself is fixed: metis is the
SLOW-THINKING (System-2) substrate for SMALL LLMs — the exact
measure, the gates and the certificates are the deliberate half;
the model halves stay at the two text boundaries (§1).

Staged, in order:

1. **Big-model formalization** (next step): put a frontier model
   (Opus) on the formalize-in boundary — probably NOT inside the
   metis loop process but in a conversational seat (Claude Code /
   coworker) driving the same REPL wire; the `:llm` endpoint seam
   (`anthropic:MODEL`) already carries it.
2. **Small-model narration**: the narrate-out boundary (`:narrate`)
   through the local small model — prove narration from certified
   material works at small scale.
3. **Integration**: once small-model narration holds, integrate the
   metis interpreter as the slow-thinking organ OF the small model
   itself — the interpreter inside the model's loop, not beside it.

THE GATE STAYS at every stage (user decision 2026-10-03): whatever
model sits at the formalize boundary, the cascade (§5) is the
semantics of working on surprise inside the loop — a stronger
formalizer changes the repair-round count, never the authority.

**Parallelism — two tiers** (user direction 2026-10-03):

1. *Inside one evaluation*: Theorem 4 / the Foata layers —
   independent sites and disjoint junction-tree branches evaluate
   concurrently; measure-preserving, already licensed; the
   layer-structure wire record stays deferred until an artifact
   outgrows ~ms queries (metis-lang spec-07 P3).
2. *Between interpreters*: MULTIPLE interpreters, each a full world
   with its own exact measure, coupled by message passing through a
   BLACKBOARD (the behavior-tree notion). The blackboard is each
   world's ENVIRONMENT, never shared state: values enter a world
   only through declared ports (input/weight/guard, `reads{}`
   contract) and leave through output ports — per-world exactness
   untouched, coupling = conditioning at declared boundaries, the
   same doctrine as `interactive`. Carriers already in hand: the
   theia actor runtime; `metis --json` as the per-interpreter wire.
   Honest limit: the ensemble has no joint measure — no certificate
   spans the blackboard; if one is ever needed, that is new
   semantics (composition across ports), not a deployment detail.
