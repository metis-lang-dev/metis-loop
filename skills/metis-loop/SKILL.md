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

You are the FORMALIZER seat of the metis loop (SPEC.md §1). The
gates are the authority, never you: every candidate you write goes
through `gate` and only the harness verdict counts. The text is the
approved unit — rules carry `%%` docs quoting it.

## The kernel is the metis shell

The loop lives in the kernel REPL (SPEC.md §2): `metis FILE.llp`
(metispy; `pip install -e .`, or the repo venv's `.venv/bin/metis`).
The WORLD is the served catalog; the loop verbs are plain shell
commands — `sink/records/record/replay/mine` (ingest), `text/llp/
load/formalize` (candidate), `gate/revise/accept` (admission; accept
RE-SERVES the merged world live), `show/export/save`, `llm/narrate`.
Scene setup is `#`-directive lines (`#init ATOM N`, `#steps N` —
metis-lang spec §8), typed live or carried by the file. The JSON
wire for programmatic driving is `metis --json FILE.llp`, one
`{op, arg}` per line. `docs/TUTORIAL.md` is the executed walkthrough.

This repo (metis-loop) is the WRAPPERS: the web console, this
skill, the `metis-loop` CLI (= the console backend; the shell is `metis`), the
`loop.*` shims. Wrappers hold no semantics.

**Run interactive shell sessions inside tmux** (e.g.
`tmux new-session -d -s metis '… metis FILE.llp'`, drive it with
`send-keys`, read with `capture-pane`) so the human can
`tmux attach -t metis` and watch the REPL live — the session is
also their window into the loop.

## The cycle

1. **Ingest**: load new records (`sink FILE.jsonl`, or `surprise`
   docs with `status: new` from the console). For each: `record N`
   (its init/steps become the scene), `replay` for the explanation;
   push likelihood/explanation to the record doc; set
   `status: investigating`.
2. **Mine**: `mine <text>` — the `%%` description of the unmodeled
   behavior, from the record's observed-vs-modeled gap. Short,
   factual, quoting atoms. It is stamped on the record as
   `mined_text`.

   **Investigate with the causal instruments (specs 09-11)** before
   writing a rule: `why [ATOM|K]` — what the state rests on (the
   structural cone); `whatif K do(~RULE|+ATOM|EVENT) query Y [@N]` —
   the counterfactual comparison (fact / with-do / by-chance);
   `necessity K [ATOM]` — was K needed for the outcome (PN with the
   Tian–Pearl verdict; inhibitors named); `fork K`/`back` to explore
   an alternative branch by hand. Answers state their tier (exact
   cone / sampled ± ci) and readout; trust the extremes, read
   mid-range PN against the by-chance column. These are
   session-local and on the console whitelist.
3. **Formalize**: YOU write the candidate `.llp` pack over the base
   vocabulary (`llp <<EOF` or `load FILE.llp`; a pack WRITES only what the
   base's namespaces grant its layer — the gate's containment check
   enforces the produce-rights; a base granting nothing means the
   pack only reads base atoms and produces its own; new vocabulary
   only for new observations). Numbers from data:
   prior-mode measures, no invented weights — notching fits them
   later. (`formalize` drafts via the llm endpoint instead; the
   gate treats both the same.)

   **Declarative over imperative — model the MECHANISM, not the
   ledger.** The smell: a quantity of the text evaluated at
   authoring time — per-value rule unrolling (`cost2`/`cost5`/
   `cost8` variants), enumerated `max`/`min` pair facts, token
   multiplicities (`wick * wick * ...`) encoding a number. That is
   computation frozen into rules; it also distorts the measure
   (consuming k tokens from a pool of C multiplies the event weight
   by the falling factorial C·(C−1)···(C−k+1) — ordered matchings,
   measured in the bridge-torch transcript). Instead, make the quantity a PATH the world walks
   and the rate DATA. Worked example (bridge-and-torch, metis-catalog
   domains/bridge_decl/bridge_decl.llp vs the
   imperative domains/bridge/bridge.llp; that package's README carries the findings): durations 1/2/5/8 became `bwd pace(person, mark)`
   facts over a `bwd step(mark, mark)` chain; the torch-party
   advances one mark per minute, each minute consuming ONE wick;
   each walker steps off at their own pace mark; "moves at the
   slower person's pace" is then EMERGENT — the torch lands when
   the last walker is off (both capacity planks back). Deterministic
   consequences ("would eat", "steps off") go in a settle stage
   where enabled rules MUST fire before quiescence (the wgc
   ferry/shore qui-tick; bridge extends it to board → stride →
   settle). Statement constraints become resource shapes: "holds
   two people" = two plank tokens, "the torch must be used" = the
   walk consumes the torch to a lamp-in-transit. Test of success:
   the puzzle's own question answered by the instruments (`query`
   > 0 / = 0 exact; goal-record `replay` derives the schedule), with
   every %%-quoted sentence mapping to ONE rule or ONE data relation.
4. **Gate**: `gate` for a pack, `revise` for a base edit. On
   findings: repair and re-run, at most 4 rounds; every round's
   findings go in the candidate doc history. Push the final report
   (ok, findings, warnings, rules, classification, scenarios with
   measure diffs) as a `candidates` doc, `status: pending`.
5. **Console edits**: a candidate with `status: regate` was edited
   by a human in the console. Its `llp` field is the new source:
   re-run the cascade on it exactly as in step 4 (the text stays
   the approved unit), push the fresh report, set
   `status: pending`. Console REPL intents (`intents` docs) are
   drained ONLY through `run_intent` — the whitelist; never
   `accept`, file paths, or arbitrary backend commands (see
   "Serving the console" below). The console artifact URL is in the
   project memory; sync with the ArtifactData tool (collections
   `surprise`, `candidates`; approvals arrive as `status: approved`).
6. **Approval**: never approve yourself. The human approves in the
   console (or in chat). On `status: approved`: commit text + the
   extension to its domain package in metis-catalog
   (`domains/<name>/extensions/`, with the text as the commit body),
   re-run the catalog gates (`ci/check.sh`), and replay the record
   corpus against the merged catalog — the record's likelihood must
   become positive (`fixed: true`); report the new trace. On
   `rejected`: record why, stop.

Never bypass a gate, never edit the harness to make a candidate
pass, never write catalog files for an unapproved candidate.

## Refinement on a trace: ONE package, no world rerun (trace-replay s-c111ff41, 2026-11-01)

The run is deterministic given what each member applied (spec 17 am.7): the TRACE is the
witness. When a deployment surprises (a failed card, the road's accounting, a watch's
record, the user naming a tick), refine like this, and never by rerunning the agent or the
bundle with its many domains:

1. **Take the trace, not the world.** The run's `.run/trace/` segment and its checkpoint
   (each session's counts, stage, RNG; the world's reference) up to the surprise. The pi
   driver writes its own (`clock: firing`).
2. **The surprise is a failing CASE of the package**: `metis.trace case --at k` writes
   `cases/surprise-<id>.yaml` in the package named (the stub's YAML with `expect.after`:
   what the world did; `rng`/`stage` at the window's start). It fails in the package's
   harness until a rule makes it pass.
3. **Replay the model alone**: `metis.trace replay` feeds the trace into the package's
   instance on the image; no host, no world, no model call. 0 divergences up to the
   surprise is the precondition; a divergence earlier is a toolchain or writer finding.
4. **Fix in the package named, and only there.** A candidate rule is judged by `fits`
   and the fired diff over the trace (exact up to its first differing output, open-loop
   after it: say so).
5. **Rerun the package's GOLDENS as the acceptance**: every case, the surprise case
   among them; a fix that breaks a golden is refused like a contradiction. A passed
   surprise case is committed as a golden: the loop grows the package's cases.
6. **A family package has two consumers** (the road family in the catalog: the road
   world and the wheelchair): the gate runs the family's goldens and every consumer's,
   on their images (spec/18 §5). A rule good for one consumer that breaks the other
   is refused at the source.

Derivation, never override: a consumer changes prices (ports), vocabulary (abstract
types), adds its own rules (packs), switches a family rule off (a token) or leaves a
unit out; it never rewrites a family rule (spec/18).

## Live work: run console-serve (docs/CONSOLE-WS.md)

For live work, start the standing backend and work in its page —
commands answer over one WebSocket in milliseconds, no drain to
babysit:

    pip install -e '.[agent]'      # websockets + claude-agent-sdk
    metis-loop console-serve       # personal: http://127.0.0.1:8770/

- **personal** (your host, your `claude login`): multi-session REPL;
  the chat pane is the Agent Service (claude-opus-5-5 by default) —
  it acts ONLY through three console tools (repl / ctx / transcript),
  no built-in tools, nothing persisted; `narrate` runs on
  claude-haiku-4-5 via the SDK (1024-token thinking budget — measured
  faithful at ~8-18 s; thinking off is fast but fuses beats);
  formalize keeps the kernel's `llm` endpoint.
- **shared** (`--mode shared --bind 0.0.0.0 --token T`): REPL only —
  chat/narrate/formalize/llm are refused (they would spend the
  operator's credentials); per-IP caps, rate limit; nothing a visitor
  does is written to disk.
- The terminal REPL is untouched: it narrates through ollama.
- Dev: `--mock-agent` gives the chat a canned client (never a model);
  `METIS_AGENT_LIVE=1 pytest -k live` runs the opt-in real turns.

The published artifact stays the SHARED window — demos, approvals from
any device, `sample` chat billed to the viewer; serve its db only when
someone is using that surface, as below.

## Serving the console (docs/CONSOLE.md §5a) — the artifact surface (secondary transport)

The console's db is reachable only by the page or by THIS session's
ArtifactData tool, so you are the backend: a drain loop over
`loop/console_serve.py`, one interpreter per open console window,
working directly on the catalog in the session's directory (no catalog mirror).

    from loop.console_serve import ConsoleServer
    srv = ConsoleServer()          # $METIS_CATALOG, else the cwd (cd metis-catalog first for its domains)

The whole drain is ONE pure call — you are glue, not logic:

1. At start (and after every catalog commit): write
   `srv.catalogs_doc()` (`{path: "meta/catalogs", data}`) with
   ArtifactData `set`.
2. Each pass: `list` the `sessions` collection and the `intents`
   collection (query `status == "queued"` is enough for intents), then
   `writes = srv.drain(sessions_rows, intents_rows)` and apply every
   `{path, data}` as an `update`, in order, as ONE `batch`. That pass
   binds `opening` sessions, re-binds live sessions this process has
   no interpreter for (after a restart, epoch + 1 so pages reset),
   and serves queued intents oldest first — each intent doc gets its
   posting (status done|refused|error, result, json, epoch, done_ts),
   each session doc its fresh `ctx` (what the band renders).
3. Repeat while windows are open; a quiet pass returns `[]`.
4. A session the page marks `closed` → `srv.close_session(sid)`.

The whitelist lives in `run_intent`: never execute an intent any
other way, never `accept`, never approve — `actor: "claude"` lines
(the page's chat, step 3) get exactly the same treatment as the
viewer's. Local dev without claude.ai: `python console/dev_serve.py
--demo` runs this same loop in-process behind a capability shim.
