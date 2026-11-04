# The workspace — one root, one bundle, one backend, one pi loop

Design for the refactoring the user asked for on 2026-11-03 (subject loop-workspace): the human loop's
console becomes a frontend over the pi loop, and the two meet in a WORKSPACE. In the user's words: "redesign
the metis loop like a front end directly over the pi loop and make components from that loop UI pluggable,
for example, in the road web UI"; "there are few moving parts we have to unite by workspace: 1. the catalog
and the package/bundle we are working on; 2. the pi loop, starting in the same root on the same bundle;
3. the backend: REPL, editor, trace, surprise handling, inherited from the human loop"; "the pi loop can be
started separately from the backend any time; it needs a socket adaptor to talk to the UI; backend and pi
loop communicate through the workspace: if the backend drops a surprise trace, the pi loop can pick it up;
if the pi loop fixes a package, the backend can reload it"; "the workspace is formalized through the SDK
API, same as the catalog: a .metis dir with context; one workspace, one active pi loop, one human loop
backend (later the road backend)"; "drop Ollama: gemma4 is the agent's and can narrate traces if need be".

Scope of this design: the human loop (REPL) and the pi loop's web wrapper in ONE workspace. The next
subject puts road-agent and the pi loop's wrapper in the road workspace (metis-worlds/road), which is a
workspace already (its `.metis/road/` holds the page's run today).

## 1. What is what today (the parts to unite)

| part | where | state it keeps | wire |
|---|---|---|---|
| the catalog | `DIR/domains/<name>/` (metis.catalog: root, index, plan/confirm/refuse, state = `DIR/.metis/`) | `.metis/records/`, `sessions/`, `seed/` | none: a library |
| the bundle | `DIR/domains/composition.yaml` + `build/<name>.build` + the image (`metisc build .`, spec/17 §7; the road: `road/domains/`) | `build/`, `image.golden` | none: files |
| the human loop's backend | `loop/gateway.py` + `console_serve.py`: REPL sessions over the kernel wire, the EDITOR's gated edit of the file on disk (workspace-files), records sink, the gate (plan/confirm), the LLM seats formalize/narrate/agent chat on `loop/brain.py` (claude -p, OpenRouter, Ollama) | memory only (D4) | ONE WebSocket `/ws`, channels `repl`, `meta`, `chat`, gate ops |
| the console | `console/loop_console.html` + `console/lib/shell.*` + the SDK's catalog widget | browser | the gateway's socket |
| the pi loop | `pi/loop.sh`: pi (TUI or `--mode rpc`) with `metis-domain.ts` (domain_open/clock/ports/world/episodes) and `metis-repl.ts` (REPL tools, catalog_new/edit/take at pi's confirm); the brain on Ollama (`pi/ollama/`, `models.json`) | `.metis/seed/`, pi's own session files | pi's RPC mode over stdio, or nothing (the TUI) |
| the policy driver + the pack verb | `pi/policy/driver.py` (phases, the ask), `propose.sh --pack` (the judge: gate cascade, goldens, cases, fired diff, lint rows, the ruling document) | `RUN/records/`, `RUN/state/journal.jsonl`, `RUN/cost.jsonl`, the ruling .md | none: files and a command line |
| the trace | metispy `metis.trace`: Segments writer (`TRACE/segments`, `checkpoints/k<k>.json`), replay/case/blame/count/families/holds/diff/outcomes/fired/timeline | a trace dir per run | none: a command line |

The disconnect the user feels is literal: the console's socket reaches the human loop's seats, the pi loop
and the judge have no socket, and the three keep their state in three shapes.

## 2. The workspace

A workspace is a directory DIR, as `cd DIR && claude` makes DIR the project (cwd-root s-ddac2cbf). It IS
the catalog (`DIR/domains/`), it holds at most one bundle (`DIR/domains/composition.yaml`; the REPL still
serves one package at a time for individual work), and the loops' state is `DIR/.metis/`. Nothing is found
beside a checkout. `metis-catalog`, `metis-worlds/road`, `metis-worlds/alfworld` and an empty directory are
workspaces.

### 2.1 The SDK face: `metis.catalog.workspace` (metispy, beside `metis.catalog`)

```
ws = workspace(DIR=None)          # DIR or metis.catalog.root(): one object, no daemon
ws.root, ws.state                 # DIR, DIR/.metis/ (metis.catalog.state: made, git-ignored)
ws.bundle()                       # {name, composition, members, image: <hash>, build: <path or None>, stale: bool}
                                  #   from composition.yaml + build/<name>.build; stale = a member's source or
                                  #   directives newer than the build record (the same test `metisc build` makes)
ws.context()                      # the text a brain is given first: DIR/README.md, the composition's comment,
                                  #   each member's domain.yaml line, the patterns catalog's path (never its text)
ws.traces(), ws.trace(run)        # .metis/traces/<run>/ (the Segments layout as it is)
ws.surprises(status=None)         # .metis/surprises/*.json, each with its status (§2.2)
ws.drop_surprise(rec)             # the backend's write (§2.2): returns the id
ws.take_surprise(id) / ws.rule(id, ruling_path, verdict)   # the pi loop's writes
ws.rulings()                      # .metis/rulings/<id>.md (+ .json: verdict, pack, moved goldens, lint rows)
ws.loops()                        # {pi: lock or None, backend: lock or None} (§2.3)
ws.lock(kind, **fields) / ws.unlock(kind)
ws.events(since=0)                # .metis/loop/journal.jsonl rows after SINCE (every writer appends; the UI tails)
ws.cost()                         # .metis/cost.jsonl summed, by brain
```

A TypeScript face `sdk/ts/workspace.ts` with the same names, generated or hand-kept at parity with a test
that reads both (loop-parity's rule: the loop's policy lives once; here the workspace's layout lives once,
in one `LAYOUT` table both faces read).

### 2.2 The `.metis/` layout (the contract between the parts)

```
.metis/
  loop/
    pi.json          the pi loop's lock: {pid, started, mode: tui|rpc, cwd, model, socket?}   (one per workspace)
    backend.json     the backend's lock: {pid, started, port}                                  (one per workspace)
    journal.jsonl    every part appends: {ts, who: backend|pi|judge|world, kind, ...}: the UI's feed
  surprises/
    <id>.json        {id, ts, who, member, trace: "traces/<run>", k, k0?, window?: [k_start, k_end],
                      reading | atoms, words?: the person's text, status: open}
    <id>.taken       written by the pi loop when it starts on it ({pid, ts}); removed on a ruling
  rulings/
    <id>.md          the pack verb's document (propose.py document(): verdict, evidence, the model's words)
    <id>.json        {verdict, pack: "packs/<id>.llp", moved: [...], lint: [...], reads_absent: [...], spent}
  packs/<id>.llp     the candidate pack judged (applied only through the gate: catalog_edit)
  traces/<run>/      the Segments writer's dirs (header, segments, checkpoints), one per run
  records/, sessions/, seed/, seed.json      as today (metis.catalog.state)
  cost.jsonl         one line per paid call: {ts, who, model, cost, usage_before} (the existing cost log, one file)
  <world>/           a world runner's run dir, untouched (the road's run.json, journal.jsonl, log.jsonl, work/)
```

Rules: every file is written whole then renamed (no partial reads); ids are `YYYYMMDDTHHMMSS-<6 hex>`; a
status is a file's existence (`.taken`, a ruling), never a field edited in place; the journal is the only
append-only file the UI tails, and it carries pointers (ids, paths), never bodies.

### 2.3 One active pi loop, one backend

`ws.lock("pi")` writes `.metis/loop/pi.json` if none holds a live pid (a dead pid's lock is stale and is
taken over, with a journal line). A second `loop.sh` in the same DIR refuses with the lock's line and the
pid. The same for the backend's port lock. The road page is NOT a backend of the road workspace and takes no
lock: it is the world's host (metis-agent's service over `road/web`), which writes the run's trace and marks
into the road's `.metis/`; the one frontend of the pi loop (§6.1) started in `metis-worlds/road` is the
backend there. The one-TraCI-client rule is SUMO's own, not the workspace's.

### 2.4 How the parts meet: files and a watch, never a socket between them

- The backend drops a surprise (§4) → `surprises/<id>.json` + a journal line. The pi loop, when it runs,
  watches `surprises/` (its `surprise_next` tool, or the watch in rpc mode pushing "a surprise waits" into
  its turn) and takes it. Nothing runs → the surprise waits; the UI shows it OPEN.
- The pi loop rules and, at the person's confirm, applies through the gate → the catalog changes →
  `metisc build .` runs where the bundle is the target (the pi loop's `bundle_build` tool, §5) → the image
  moves. The backend watches `build/<name>.build` and the members: `ws.bundle().stale` flips → the session
  shows STALE → the person reloads (the two-users ruling: STALE → reload). Nothing is pushed into a running
  REPL session.
- Both append to the journal; the UI tails it through the backend. The pi loop's own words in rpc mode go
  through the adaptor (§5.2) and are ALSO journaled, so a TUI run leaves the same trail as an rpc one.

Why files: the pi loop "can be started separately from the backend any time", so there is no process to
hold a socket open for it; files survive either side's absence, are the trace-replay subject's witness
already, and are what a person reads afterwards. The one socket is the browser's to the backend.

## 3. The backend (inherited from the human loop, with its brain removed)

`loop/gateway.py` stays the one standing process on one port, one multiplexed WebSocket, the Session
Manager, the modes (`personal`, `shared` with its caps) and the privacy rule for sessions (memory only).
Channels:

| channel | kept / new | frames (as the gateway's docstring lists them) |
|---|---|---|
| `repl` | KEPT | open/intent/stop/close/records/sink/new, `edit` (plan/confirm/refuse: the EDITOR's save, one gated edit of the file on disk; workspace-files s-9ea4cfa4), the gate ops propose/confirm/refuse; the working copy's work/recompile/save/refuse and the open from TEXT are retired |
| `meta` | KEPT | manifest, catalogs, readme, domains (the CATALOG widget) |
| `chat` | RETIRED | the agent seat on claude -p (the brain seats go: formalize, narrate, agent chat; `loop/brain.py`, `loop/ollama.py`, `loop/llm.py`, `loop/narrate.py`, `loop/agent_service.py` leave with their console panels) |
| `trace` | NEW | `{type:"list"}` → the workspace's traces; `{type:"open", run}` → header, checkpoints, k range; `{type:"tick", run, member, k}` → the Tick table (counts, fired, made; `metis.trace.timeline`); `{type:"verb", name, args, req}` → one of the trace verbs as a declared tool (§3.1) |
| `surprise` | NEW | `{type:"list"}`; `{type:"drop", session?, run, k, window?, atoms?, words}` → `ws.drop_surprise` (from a REPL session: its served program and member, its trace if the session writes one; from a trace: the window); `{type:"get", id}` → the record + its ruling |
| `bundle` | NEW | `{type:"state"}` → `ws.bundle()`; `{type:"reload", session}` → the session re-opened on the rebuilt image (the gate's STALE → reload) ; a `{ch:"bundle", type:"stale"}` push when the watch flips |
| `loop` | NEW | `{type:"state"}` → `ws.loops()`, cost; `{type:"events", since}` → journal rows, then pushed as they come; `{type:"start", mode:"rpc", model, budget}` / `{type:"stop"}` → the pi loop as the backend's child in rpc mode (§5.2), refused when a lock holds; `{type:"say", text}` → the person's turn to the rpc child; `{type:"confirm"|"refuse", token}` → the child's pending gate (the same plan/confirm the gate already has) |

**narrate and llm RETURNED to the REPL (the user, 2026-11-04: "dropping ollama was mistake… people working on
single llp file losing this feature"; repl-llm s-7311fa1b).** The `chat` row stays retired and `formalize` alone
stays the pi loop's (the gateway refuses it in every mode). `narrate` and `llm` are the REPL's own again, in the
console and in the terminal, on the REPL's model (metispy `metis.loop.llm`): `llm ollama phi3 [URL]`, `llm
openrouter deepseek/deepseek-v4.1-flash-1017`, `llm URL MODEL`, `llm anthropic [MODEL]`, saved as `[llm] endpoint`
in the config dot file, so the next REPL starts on it; no default. Every paid request carries the token cap
(`[llm] max_tokens`, 1024), and each OpenRouter call appends a row to `~/.config/metis/cost.jsonl`. The key is
read from `OPENROUTER_API_KEY` only; `metis FILE.llp` says on its intro line whether it is set, never its value.
The gateway loads the person's private key file (`METIS_OPENROUTER_ENV`, default
`~/.config/metis/openrouter.env`, mode 600/400) into its own environment at start, parsed, never sourced, never
printed. In `shared` mode `llm` only shows the model (it is the operator's, and D4 writes nothing a visitor
types), and `narrate` is served on a local backend only (ollama, command): on openrouter or anthropic it
answers "narrate: a paid model is not served in shared mode; the operator sets a local one with llm" and
makes no call. There is no per-visitor cap: a cap on the operator's key is still the operator's money.

The REPL session gains a trace writer: `open` with `trace: true` writes `.metis/traces/<session>/` through
the Segments writer (the py Live's code path from trace-replay), so a surprise dropped from a session points
at a trace the pi loop can replay. Without it, a dropped surprise carries the session's atoms only and the
ruling says so (no replay, the gate cascade and the goldens still run).

### 3.1 The verbs as declared tools, once

`metis.trace`'s verbs (replay, case, blame, count, families, holds, diff, outcomes, fired, timeline, sort
when it lands) and `metis.lint` get ONE declaration table (`metis/trace_tools.json`, generated from their
argparse definitions by a script, checked by a test as `tools.json` is for the REPL's T): the backend's
`trace` channel serves exactly those, the pi loop's extension (§5.1) exposes exactly those. Nothing is hand-written for a UI that the verb does not declare (LOOP-AGENT.md's
parity rule, extended from the REPL to the trace).

## 4. The surprise, from where it is seen to where it is ruled

1. **Seen in the REPL** (a kernel `surprise` on the wire, `metis.loop.watch`): the session turns
   observe-only as today; the console's SURPRISES panel offers "drop to the loop" with the record's reading,
   the session's k and, when the session writes a trace, the trace. The person adds words. → `surprises/`.
2. **Seen in a trace** (the TRACE panel, or later a road mark): the person picks k or a window on the tick
   table and writes what should have happened (the command kind, the atoms: `expect.out` / `expect.after`
   as `metis.trace case` writes them). → `surprises/` with `window`.
3. **Taken by the pi loop**: `surprise_next` returns the oldest open record with its context: the member's
   unit text, the trace's k window as the Tick table, the person's words, the ruling of any earlier surprise
   on the same member. The loop drafts a case (`metis.trace case`) and a pack, judges it (`pack_propose` =
   propose.py: gate cascade, goldens with the family's skips, the cases, the fired diff, the lint rows, the
   moved-golden lines, reads-absent; the model's words only with a budget), writes `rulings/<id>`.
4. **Applied** only through `catalog_edit` at the person's confirm (pi's confirm in the TUI; the `loop`
   channel's confirm frame in rpc mode) → the catalog → the bundle rebuilt → STALE in the backend → reload.
5. **Narrated** when wanted: the agent's gemma4 (metis-agent) narrates a trace window over the agent's
   wire when the agent runs beside the workspace (the road, later). The backend keeps no narrator. "We will
   see by situation how to wire it": the design reserves `{ch:"trace", type:"narrate"}` and leaves it
   unimplemented.

## 5. The pi loop in the workspace

### 5.1 Tools (the extensions)

`metis-domain.ts` and `metis-repl.ts` stay. A third extension `metis-workspace.ts` adds, over the SDK's
TypeScript face: `workspace_context` (ws.context + bundle state), `surprise_next` / `surprise_list`,
`trace_*` (every verb of §3.1, one tool each, generated from the declaration table at load),
`pack_propose` (propose.py through `propose.sh`, the ruling path returned), `bundle_build` (`metisc build .`
in the workspace, the image hash before and after), `journal` (append a line: the loop's own progress, in
words, for the UI). `catalog_new/edit/take` keep the gate. pi's built-in edit stays off.

The pi loop works on the BUNDLE: `domain_open` opens the composition's members as one (the composition's
root), the REPL tools serve one member for a question. The seeded start (`--seed`) is unchanged.

### 5.2 The socket adaptor: pi's RPC mode, bridged by the backend

pi has `--mode rpc` (JSON over stdio). The backend starts `loop.sh --mode rpc` as a child when the console
asks (`loop` start) and bridges: the person's `say` → pi's user turn; pi's assistant text, tool calls and
results → journal rows (`who: pi`) and `loop` pushes; pi's confirm request → a `{ch:"loop", type:"gate",
plan, token}` frame, answered by confirm/refuse. The TUI and the rpc child are the same loop with the same
files; "the pi loop on the console with its own TUI and the backend is like the remote control in Claude
Code": the console is the remote, the TUI the local seat, either one at a time (the lock).

### 5.3 The brain: Ollama out

`pi/ollama/` (Modelfile, the E4B pull), `models.json`'s Ollama entry and `loop.sh`'s `MODEL=ollama/…`
default go. The pi loop's providers: OpenRouter through the key file in the environment (cap per request,
`--budget` required, the cost log to `.metis/cost.jsonl`) and the person's Claude subscription where pi
supports it. metispy's kernel `[llm] endpoint` stays an OpenAI-compatible endpoint with no Ollama default
and no Ollama words in its hints; `metis.loop.ollama` is renamed for what it is or folded into
`metis.loop.llm`. The gemma4 GGUFs stay metis-agent's (the agent and its narrator).

## 6. The console: panels as widgets

`console/loop_console.html` keeps the shell (`console/lib/shell.*`) and the CATALOG widget pattern (the
SDK's `web/catalog/`): every new panel is a widget under `sdk/metis_loop_sdk/widget/<name>/` (`<name>.js`,
`<name>.css`, served by the gateway as `/sdk/<name>/…`) of this console, the pi loop's one frontend (§6.1).
The panels, each over one channel:

| panel | over | shows / does |
|---|---|---|
| CATALOG | meta | as today |
| REPL, EDITOR | repl | sessions, intents; the EDITOR edits the file on disk, save = one gated edit (diff + findings, confirm) |
| BUNDLE | bundle | name, members, image hash, build time, STALE with the reload button |
| TRACE | trace | the runs; a run's k range with checkpoints; the Tick table at k (counts, fired rules, made atoms), step ±1, jump; the verbs as buttons with their declared args; "mark here" → a surprise draft |
| SURPRISES | surprise | the records with status open / taken / ruled, the drop dialog (k, window, atoms, words), each ruled one linking its ruling |
| RULINGS | surprise, trace | a ruling document rendered: verdict, evidence rows (goldens held / moved by name, cases, fired diff, lint rows, reads-absent, inert), the model's words, spend |
| LOOP | loop | the pi loop's state (lock, mode, model, budget, spent), start/stop in rpc mode, the chat (say), the journal stream, the pending gate's plan with confirm/refuse |

"To replay the rules and see what is going on in the pi loop": TRACE is the replay, LOOP is the feedback,
RULINGS is why.

**Amended by [CHAT.md](CHAT.md) (loop-chat, the user's verdict after loop-test, 2026-11-03):** the tester sees two
panels, CHAT (LOOP's chat with its state as the header line, the gate, the ruling and STALE as cards) and
SURPRISES; TRACE, RULINGS and BUNDLE are the developer's, behind the band's "developer" switch; a host page
embeds the served page as an iframe with `?panels=chat,surprises`.

### 6.1 The pi loop's frontend is shared (the user, 2026-11-03)

This console with its five panels is the ONE frontend of the pi loop, on every workspace: `run.sh` started
in `metis-catalog`, in `metis-worlds/road`, in any DIR of §2.1. It is not copied into the road page or any
other consumer page, and no loop code moves for it: `loop/workspace_ch.py`, `loop/pi_rpc.py` and
`web/workspace/` stay metis-loop's, the SDK carries the widgets for this console alone, metis-agent's
service gets no workspace frames. The road page stays the road's own UI. On the road the two run side by
side on the same workspace (`metis-worlds/road/.metis/`): the road page as the world's host, writing; the
pi frontend as the pi loop's, reading. They meet through the files and the watch (§2.4), never a socket.

What the road owes the shared frontend (the next subject, road-agent; the road's code only, no pi code):
1. one trace dir per run, `road/.metis/traces/<scenario>-<seed>-<started>/` (today `ROOT/.run/trace`,
   overwritten by every run), so TRACE lists the runs;
2. the run's marks beside its trace, `marks.jsonl` in the run dir, each row in the trace's k (on the road
   k = log tick + 1; the writer shifts, nothing downstream computes it); TRACE lists a run's marks and
   "mark here" from a mark fills the drop dialog with the window;
3. the run's config pointer in the run dir (`run.json`: `config`), so `ws.bundle()` and the judge replay
   the run's composition with the run's config;
4. in metispy's face, `ws.keep_window(run, k0, k1, name)`: the segments and checkpoints that hold a window
   copied under `traces/<run>-<name>/` before the surprise is written, called by the frontend's drop from a
   window, so a marked window outlives the writer's ring.

## 7. Retired, kept, moved

- Retired: the human loop's LLM seats (`loop/brain.py`, `llm.py`, `narrate.py`, `agent_service.py`,
  `ollama.py`, the `chat` channel, the console's formalize/narrate/agent panels, `--brain` on `metis-loop`),
  `pi/ollama/`, the Ollama model entries. The formalize step of the human loop (a surprise → a candidate by
  claude -p) is the pi loop's now: the backend drops, the loop formalizes.
- Retired (workspace-files s-9ea4cfa4, the user 2026-11-03: the workspace owns the file): the console's
  working copy (IndexedDB, the gateway's memory), the floating editors over it, the open from TEXT
  (`SourceRepl`, `{source, name, extensions}`, `MAX_SOURCE`), recompile and the copy's save gate, the
  SessionTrace of an in-memory session. The EDITOR edits the file through one gated edit (§6, LOOP.md).
- Kept: the gateway, the Session Manager, the modes, the gate (metis.gate, once), the REPL and editor
  panels, the catalog widget, `metis.loop.watch`, `pi/policy` (the driver stays the world-runner's loop; its
  RUN dir may move under `.metis/runs/` later, not in this subject).
- Moved: `propose.py`'s document into `.metis/rulings/`; the T declarations pattern to the trace verbs.

## 8. Steps (pascal implements, the user tests the loop UI, the architect reviews and merges)

| step | lands | accept |
|---|---|---|
| 1 | metispy `metis.catalog.workspace` + `sdk/ts/workspace.ts` + the LAYOUT table + locks + `trace_tools.json` generator; docs | unit tests on an empty DIR and on `metis-worlds/road` (its `.metis/road/` untouched); a second lock refused; parity test py/ts on the layout; the declaration table equal to the verbs' argparse |
| 2 | the backend's `trace`, `surprise`, `bundle`, `loop` channels; the session trace writer; the brain seats retired | gateway tests per frame; a surprise dropped from a REPL session and from a trace appear in `surprises/`; STALE flips on `metisc build`; `metis-loop --brain` gone |
| 3 | `metis-workspace.ts`; Ollama out; the rpc bridge | the pi loop in the TUI takes a dropped surprise, rules it (0 USD with a script brain; one paid round at the user's word, cap 0.50 USD), applies at confirm, the bundle rebuilds; the same over rpc from the console; CI `pi` jobs green without Ollama |
| 4 | the five widgets and the console over them | the flows of §4 (1), (2), (4) driven in the user's Chrome on `metis-catalog` as the workspace (the dog or kitchen bundle) and on `metis-worlds/road` with a committed trace: this is the user's test of the switch |
| 5 | report: what the road owes the shared frontend (§6.1: the run's trace dir, marks in k, the config pointer, `keep_window`), nothing of the loop moved | the next subject's brief |

Rules: 0 USD except the one paid round in step 3; MemoryMax 6G on every child; no sim runs; branches with
CI green, the architect merges (metispy first, then metis-loop); one file per agent per step on the subject.

## 9. Decisions taken here, for the user to overrule

1. Files and a watch between the backend and the pi loop, never a socket (§2.4).
2. pi's own RPC mode is the socket adaptor, bridged by the backend; no second server for the loop (§5.2).
3. The human loop's formalize/narrate/chat seats are retired; formalize is the pi loop's (§4.5, §7).
   narrate and llm returned to the REPL on the user's word, 2026-11-04, Ollama with them (§3).
4. The policy driver stays as it is (the world-runner's loop); only the pack verb's output moves into the
   workspace. Unifying the driver's RUN dir with `.metis/` is a later step.
5. Widgets live in the loop SDK for this console alone (§6.1): the frontend is shared, not copied.
