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
skill, the `metis-loop` CLI (console-serve + repl delegation), the
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
3. **Formalize**: YOU write the candidate `.llp` pack over the base
   vocabulary (`llp <<EOF` or `load FILE.llp`; packs consume base
   atoms, never produce them — containment admission enforces it;
   new vocabulary only for new observations). Numbers from data:
   prior-mode measures, no invented weights — notching fits them
   later. (`formalize` drafts via the llm endpoint instead; the
   gate treats both the same.)
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
   console (or in chat). On `status: approved`: commit text + pack
   to metis-catalog (packs/, with the text as the commit body),
   re-run the catalog gates (`ci/check.sh`), and replay the record
   corpus against the merged catalog — the record's likelihood must
   become positive (`fixed: true`); report the new trace. On
   `rejected`: record why, stop.

Never bypass a gate, never edit the harness to make a candidate
pass, never write catalog files for an unapproved candidate.

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
working directly on the metis-catalog checkout (no catalog mirror).

    from loop.console_serve import ConsoleServer
    srv = ConsoleServer()          # $METIS_CATALOG or ../metis-catalog

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
