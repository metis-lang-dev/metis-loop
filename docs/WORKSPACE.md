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
printed. narrate and llm behave the same in every console mode (the user, 2026-11-05: "there no
remote/local backend… repl narration is in metis host config. for narration from pi loop we have model on
openrouter"): repl-llm's shared-mode rules were reverted (two-terminals s-065d46d5 step 1).

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
| ~~SURPRISES~~ | surprise | gone (console-voice step 1; its file loop-ui 2.4): `/surprises` lists, the REPL's `drop`/`mark` and the CHAT's `/drop`/`/mark` drop |
| RULINGS | surprise, trace | a ruling document rendered: verdict, evidence rows (goldens held / moved by name, cases, fired diff, lint rows, reads-absent, inert), the model's words, spend |
| LOOP | loop | the pi loop's state (lock, mode, model, budget, spent), start/stop in rpc mode, the chat (say), the journal stream, the pending gate's plan with confirm/refuse |

"To replay the rules and see what is going on in the pi loop": TRACE is the replay, LOOP is the feedback,
RULINGS is why.

**Amended by [CHAT.md](CHAT.md) (loop-chat, the user's verdict after loop-test, 2026-11-03):** the tester sees two
panels, CHAT (LOOP's chat with its state as the header line, the gate, the ruling and STALE as cards) and
SURPRISES (since gone: console-voice); TRACE, RULINGS and BUNDLE are the developer's, behind the band's "developer"
switch; a host page embeds the served page as an iframe with `?panels=chat`.

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

## 10. Two terminals: the REPL in one, the pi loop in another (two-terminals s-065d46d5)

The user, 2026-11-05: "generally, i can run repl in one terminal and pi loop in another and do same flow like an
ui. then ui is just wrapper which we can attach to domain demo world for tester to assess and interrogate." The
console's flow is the two terminals' flow, over the same functions (metispy `metis.catalog.workspace`,
`metis.session_trace`; metis-loop `loop.chat`), in the same workspace directory (the one holding `.metis/` or a
bundle):

```
terminal 1 — the REPL                              terminal 2 — the pi loop
cd WS && metis domains/hier/grasp_domain.llp       cd WS && pi/loop.sh        (MODEL: the dot file's [llm] loop)
  (a member's unit: serves grasp/grasp.llp)          /status   /surprises      (0 USD, printed in the TUI)
llp> llm loop ollama qwen3:4b                        loop.sh: MODEL=ollama/qwen3:4b budget=none USD
                                                       formalize=ollama:qwen3:4b skills=metis-language,…
llp> do +take(other)                                 /take                    (the model's turn)
llp> run 4                                           /ruling   /replay   /why ATOM at K   /diff
llp> drop begin should not start a take …            /mark RUN K WORDS        (a trace's tick, dropped)
llp> surprises    llp> status                        /rebuild  /lint  /budget USD  /stop  /help
```

- **The REPL finds the workspace** (`metis.catalog.workspace.find`: `$METIS_CATALOG`, else the nearest of the cwd and
  its parents holding `.metis/` or a bundle; never the home, the temp directory or `/`). In one it writes its trace
  to `.metis/traces/repl-<id>/` with the console's writer (`metis.session_trace.SessionTrace`, `live:
  metis-loop-console`: the judge replays it member alone, as a console session's), and its intro says so: `workspace
  .: bundle alfworld v-8c989f738dd7 BUILT · 0 open surprise(s) · trace .metis/traces/repl-…`. Its verbs: `drop
  WORDS` (the last tick, the words' first sentence the reading), `mark K WORDS` / `mark K0..K1 WORDS` (a tick or a
  window of its trace), both `ws.drop_surprise`; `surprises`; `status` (the same two lines as pi's `/status`). Out
  of a workspace the intro says there is none and the verbs say how to get one.
- **What `metis ARG` serves** (`metis.catalog.serve_target`): a member's unit (`grasp_domain.llp`, which alone lacks
  the tick protocol its member includes) → the program that includes it (several includers: refused, naming them);
  a package name (`metis grasp`) → its program; a package directory; `metis` alone in a package → its program (it
  was a blank scratch world).
- **The cwd joins the catalog's places** (`metis.catalog.places()` with no root given: after the root, when it is
  another directory): under `$METIS_CATALOG` a package or an include where the person stands resolves; the root
  still wins a name in both. metisc's own include rule is unchanged (the bundle's `make` runs in its directory).
- **pi's own commands** are the chat's table (`loop/chat_tools.json` → `pi.registerCommand` in
  metis-workspace.ts): the workspace's answers run `python -m loop.chat --root DIR "/…"` at 0 USD and print in the
  TUI (the model never sees them); `/take [ID]` says "take the next surprise" (or "take surprise ID") as the console
  does; `/budget USD` sets this session's budget; `/stop` releases the lock and ends pi. `/drop` and `/reload` are
  the REPL's (the CLI says so; pi's built-in `/reload` keeps its name). The `chat_*` tools the model has are
  unchanged.
- **The console** is a wrapper over the same functions: its REPL session's trace is the same class. In personal mode
  its REPL pane is the REPL's own command line (loop-ui s-bb07923c): the gateway attaches the workspace and the
  session's trace to the session's shell, so `drop`, `mark`, `surprises` and `status` answer as terminal 1's do (a
  shared-mode visitor's shell has none attached and keeps the wire's whitelist). Opening a member's unit serves its
  includer, as `metis UNIT` does, and the session frame says so (`served`).
- **One command path** (loop-ui 2.2): the console's CHAT `/drop` and `/mark K WORDS` are its session's REPL verbs (the
  line goes to the REPL pane, as typed there); `/mark RUN K WORDS`, `/lint` and `/rebuild` are `loop.chat`'s terminal
  answers, pi's own; the STALE/BUILT card's [reload] says `/reload`. pi's `bundle_build` tool is `/rebuild` (the
  bundle's Makefile, which finds metisc and the world's python as demo.sh does). **One spend count**: pi journals a
  `usage` row per model call (paid or local, TUI or rpc), and every face's line is metispy's `Workspace.spend()`:
  `0 USD, local (11 calls)` on a local model, else `0.0123 USD spent by pi's estimate (12 calls; …)`; the page's
  header reads the same.
- **The tester's first view:** the CHAT opens with "say what surprised you; /help for the commands", then `/status`
  and `/surprises` printed. `/mark RUN:MEMBER K WORDS` marks a tick of a trace of several members (the alfworld demo's
  run has six); without the member the refusal names them.
- **`/apply [ID]`** (loop-ui 2.3, the user: "the apply writes exactly what was judged"): an accepted ruling's pack
  merged onto its unit by the judge's own code (metispy `Workspace.apply_plan`: `metis.trace.apply_pack`; the unit the
  ruling records, else the surprise's, else the member's program), shown as the diff of that one file, written when the
  person confirms at the face's gate: pi's TUI dialog (`/apply`, no model turn), the console's CHAT card (confirm /
  refuse). The model's tool is `catalog_apply` (it decides when, never how), the same plan and gate; each writes F1's
  `applied` journal row. Refused unless accepted, and once applied. `catalog_edit` names a member's file as the loop
  prints it (root-relative, or a bare name its image.lock includes) and reaches the includes its last build names.
- **A drop records the unit** the person had open (`unit: domains/hier/grasp_domain.llp` when `metis
  domains/hier/grasp_domain.llp` serves grasp/grasp.llp), and `pack_propose` amends the surprise's unit when the model
  names none: the rule is in the unit, and the member's program alone refused the right pack ("the pack drops begin,
  which this unit does not have", loop-ui I1).

**The model setting (llm-config s-07a070ad; the user, 2026-11-05: "harmonize config for narration and formalization.
both path can be configured to ollama or openroute. thus we can test whenever we want on local models").** One
configuration for every seat, the dot file's `[llm]` (metispy `metis.loop.config`), one grammar
(`ollama:MODEL[@URL] | openrouter:MODEL | anthropic[:MODEL] | command:ARGV`):

```
[llm]
endpoint  = "ollama:gemma3:4b"     # the REPL's narrate          llp> llm ollama gemma3:4b
loop      = "ollama:phi4-mini"     # the pi loop's model         llp> llm loop ollama phi4-mini
formalize = "ollama:phi4-mini"     # the loop's formalize        llp> llm formalize …   (default: loop's)
```

`llm` alone shows the three, checked: the key in the environment for openrouter; for Ollama the server, the pulled
model and, for the loop, whether it can call tools (Ollama's capabilities: gemma3:4b cannot; phi4-mini and gemma4
can). `pi/loop.sh` with MODEL unset takes `[llm] loop` (`python -m metis.loop.llm pi loop`): `openrouter:M` is pi's
`openrouter/M` with the key and the budget as before; `ollama:M@URL` is pi's provider `ollama` over the server's
OpenAI-compatible `URL/v1`, written for the start into `DIR/.metis/pi-agent/models.json` (pi/agent/models.json with
the provider merged: the URL is the person's, so it is generated, never committed; only models.json, never pi's
auth.json), cost 0, no key, no budget. FORMALIZE_MODEL comes from `[llm] formalize`, else `[llm] loop` (an Ollama
one is metispy's own `ollama:` backend). MODEL (and FORMALIZE_MODEL) on the command line still win; with neither,
loop.sh refuses and says how to set it: there is no default anywhere. The console's loop start passes no MODEL
unless the page names one, so it starts the same model from the same file, and says which (`dot_model`). pi's own
`/model` is not the setting: the dot file is, so both terminals and the console agree.

A local model under pi needs, of the Ollama server and the model (taycann, 2026-11-04; qwen-loop s-75ecbab5 and
s-fae78b2f):

- **A context that holds pi's prompt**: a take's first call is ~5.8k tokens (the system prompt 1.4k, the 26 tools'
  schemas ~3.9k, the skills' listing 0.5k), ~20k by its eleventh. Ollama's `/v1` takes no `num_ctx` from pi, so it
  is the model's own `num_ctx`, else the server's `OLLAMA_CONTEXT_LENGTH` (an 8 GB GPU's default is 4096: the prompt
  is cut and the model never sees its tools). Run the server with `OLLAMA_CONTEXT_LENGTH=32768`. `llm loop` says what
  Ollama says, in one clause: `context 16384 (the model's num_ctx)`, `context 32768 (served now)` when the model is
  loaded, else the condition (`context: the server's OLLAMA_CONTEXT_LENGTH, pi needs 16384+`); the server's
  environment is not visible over HTTP. pi's contextWindow (`.metis/pi-agent/models.json`) is the served context,
  not the model's trained one (qwen3:4b: 262144 trained, 32768 served).
- **The system prompt as role `system`**: pi sends a thinking model's instructions as role `developer`, and Ollama's
  templates (qwen3, gemma4) drop that role, so the model never saw `loop-system.md` or its skills (3925 prompt
  tokens with or without them). The generated entry sets `compat.supportsDeveloperRole: false` (as
  pi/agent/models.json does for OpenRouter).
- **Thinking**: a thinking model's reasoning comes back in `/v1`'s own `reasoning` field: pi keeps it as thinking
  blocks, never the answer (its TUI shows them dim and italic, which reads like answer text: it is not). pi has no
  off for Ollama: `METIS_LOOP_THINKING=off` sends no `reasoning_effort` and the server thinks at its default
  (qwen3:4b's first call 3928 in / 287 out, against 408 at pi's `medium`); `reasoning_effort: none` makes qwen3:4b
  think in the answer text instead. The default for a local model is pi's own level.
- **Skills**: `METIS_LOOP_SKILLS=none` (or `loop.sh --no-skills`, or `NAME,NAME`) starts without them; the start
  line says which (`skills=none`). Their listing is 477 tokens of the first call (5765 against 5288); a SKILL.md
  costs only when read.
- **A model that makes tool calls**, and what each did on the same surprise (grasp, k 2: "begin should not start a
  take while the hand is full"):

| model (Ollama capabilities) | what it did under pi |
|---|---|
| gemma3:4b (completion, vision) | no go: it cannot call tools; `llm loop` says so before any start |
| phi4-mini 3.8B (completion, tools) | named `surprise_next` but wrote the call as JSON in its text: no tool call |
| **qwen3:4b** Q4_K_M (completion, tools, thinking) | one `/take`, no "go on": `workspace_context`, `surprise_next`, `trace_blame` (handsfree: nothing ever moved it), `trace_case` ×5 (the trace has no beat to make a case of), `pack_propose`: refused at the link (`begin [dyn] requires handsfree.` is not the language); its second pack got "ruled already: REFUSED", which it told the person as it stands. 11 calls in about 3.5 minutes on an 8 GB GPU, 0 USD |
| metis-gemma4-e4b 7.5B (completion, tools, thinking) | no go (the user, 2026-11-04): with its system prompt it wrote `call:surprise_next{}` as text; use qwen3:4b |

The interworking holds on a local model; the language is beyond a 4B one: its packs are refused at the link, never
accepted wrongly.
