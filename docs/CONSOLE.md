# CONSOLE — the Loop Console redesign (two dialogs over one REPL)

**Status: ACCEPTED 2026-10-05 (user review); D1–D5 resolved in §D,
with the user's amendments folded in: NO TABS (gdb-wrapper flow,
§2), multi-session backend on metis-catalog (§5a), self-reload +
shortcuts (§2a). Implementation is iterative with the opus seat —
"start and refine".** Supersedes the current
`console/loop_console.html` layout; the SPEC §6 transport contract
is kept with the one amendment stated in §6 below.

Guiding principle (user): the REPL was grown deliberately until its
command set covers every aspect of LLP execution — findings (spec
08), graph / why / causes / ctx-grade `list` (spec 09). The console
REUSES that information to build a comprehensive environment; it
never computes semantics of its own. The design reference is
Pwndbg, as a principle rather than a look: **when the program stops,
show the important state immediately — never make the user ask
questions whose answers are already known.** The command line is the
control surface; the page sections are the information surface.
Not an IDE, not a chat app: a state inspector. No catalog layout, no
source editing — catalogs are loaded and changed through the REPL
(`load`, `revise`, `accept`), exactly as in a terminal.

## 1. Layout

One page, dark, dense, monospace, no cards; a thin splitter between
two panels, and a persistent CONTEXT BAND across the top.

    ┌──────────────────────────────────────────────────────────────┐
    │ CATALOG three-pigs  KEY 1e3be62…  STAGE go  BEAT 3  QUIESCENT│
    │ TOKENS pig ●●  brickhouse ●  wolf ●        ENABLED 1 of 6    │
    ├───────────────────────────────┬──────────────────────────────┤
    │  METIS (the debugger)         │  CLAUDE (the interpreter)    │
    │  …sections…                   │  …chat…                      │
    │  llp> _                       │  > _                         │
    └───────────────────────────────┴──────────────────────────────┘

The band re-renders from the `ctx` wire op (§4) after every executed
intent, whichever panel issued it. Color semantics (the only color
on the page): green fireable/certified · purple rests-on/proof ·
yellow waiting/stochastic · red spent/failed · cyan current beat ·
gray inactive/pruned.

## 2. The left panel — the debugger

- **Transcript grouped by BEAT, not by line.** Fired events render
  as beat blocks (cyan rule name; `consume → produce` with counts),
  from the `graph` op's beats — a beat is the instruction boundary,
  and events sharing one are causally independent; the rendering
  must make that impossible to misread. Typed `llp>` lines and
  non-event output interleave as plain transcript. Stage episodes
  (links) draw as labeled horizontal rules between beat groups.
- **RULES section** — `list`'s marks become first-class visual
  states, 1:1: `*` FIREABLE (green) · `◂ #k` RESTS-ON (purple,
  occurrence refs clickable into the trace) · `·` FIRED, no longer
  matters (gray) · `? atom ← maker` WAITING (yellow) · `– no atom`
  SPENT (red). The cross-stage `rests on` block renders beneath.
- **Click a rule = the inspector** (Pwndbg's disassemble): premises,
  conclusion, linear effect (−/+ lines), weight, class, status,
  its `%% doc`, source line, fired occurrences. Read-only.
- **Lenses — NO TABS (user).** The page follows the gdb-wrapper
  (Pwndbg) terminal design: one scrolling stream in which context
  SECTIONS render inline after each step — DERIVATION (the beat
  blocks), PROOF (program_key, run_key, canonical state), MEASURE
  (enabled tier with normalized p's; `query`/`map`/`marginals`
  results where issued) — exactly as Pwndbg prints its context
  blocks at every stop. `ctx proof` / `ctx measure` (and the
  shortcut chips, §2a) choose which sections print; runtime updates
  are WATCHED, not fetched: every backend posting re-renders the
  band and appends to the stream live (db onSnapshot).
- **NARRATOR** — a section, never a chat: endpoint/model status
  line (the `llm` op), a [narrate] action, the prose below, marked
  "certified trace only". The LLM here is the REPL's backend.
- **FINDINGS** — the `findings` op, one line per diagnostic,
  expandable to the full slice (spec 08 D4).
- **GRAPH** — [graph] fetches the `graph` op's JSON and offers the
  .dot/.json for download (§D3: in-page SVG drawing is v2).
- The `llp>` line at the bottom queues an intent exactly as today;
  arrow-key history; the transcript shows every intent whoever
  issued it (viewer or the chat's Claude, marked — the dialog is
  always visible on both sides).

### 2a. Shortcuts, self-reload, reset (user extras)

- **Shortcut chips** above the prompt: one-click senders for the
  frequent lines — `run` `step` `events` `ctx` `graph` `why`
  `findings` `narrate` — each queues the intent exactly as typing
  it would (same pipeline, same transcript mark).
- **Self-reload on backend change**: each session doc carries an
  `epoch` (bumped by the backend on reload/accept/new key). The page
  watches it; on a bump it clears the stream, re-pulls `ctx`, and
  banners what changed ("reloaded: NEW key …", as the REPL prints).
- **Reset**: a [reset] affordance queues the `reset` intent; the
  backend may also recycle an idle session to keep it clean — the
  epoch bump makes that visible instead of silent.

## 3. The right panel — the Claude chat

Built on the artifact `sample` capability (in-page Claude,
viewer-consented, viewer-billed), `cache: false`, turns kept by the
page; `db` + `user` as today.

- **System preamble** (embedded in the page source, versioned with
  it): (a) the REPL skill — the command set and how to read each
  section's output, generated from the REPL's `_HELP` plus this
  spec's contract; (b) the formalization skill — the loop doctrine:
  mined text → candidate LLP → `gate` cascade → repair from
  DIAGNOSTICS (never full source, spec 08 D5) → the HUMAN approves;
  the gate stays (SPEC §10).
- **One tool**: `repl {line}` — executes through the SAME intents
  pipeline and whitelist as the left prompt (`run_intent`, SPEC §6),
  returning the structured JSON result. No second channel: what
  Claude does is what the viewer could type, it appears in the left
  transcript marked `claude>`, and the context band updates — the
  chat REINTERPRETS the machine, it never bypasses it.
- The chat answers in language, citing sections ("fired in BEAT 4;
  see RULES: blow_brick is waiting on brickhouse"). It may run
  multi-step investigations (why/causes/query) and summarize.
- **No approval authority**: `accept` and candidate approval are
  not in the whitelist; the buttons in the candidates view remain
  the only approve path, and they act as the signed-in viewer
  (`user`).
- Intents carry `actor`: the viewer's `user.id()` or `"claude"`.

## 4. Kernel/wire additions (metispy; small, no new semantics)

- **`ctx`** — new wire op AND REPL command (terminal parity; the
  Pwndbg `context`): one aggregate JSON reusing existing internals —
  `{catalog, key, stage, status: running|quiescent|done, fired,
  beat, episode, counts, enabled: [{name, w, p}], rules: [{name,
  state: fireable|rests_on|fired_pruned|waiting|spent, detail}],
  last_event, rests_on_stages}`. Exactly `list`'s analysis plus the
  header facts, as data; the text `ctx` renders the same block the
  context band shows. Sections selectable: `ctx tokens|rules|trace`.
- `run_intent`'s whitelist admits the read-only ops it does not yet
  carry (`ctx`, `graph`, `why`, `causes`, `findings`); still never
  `accept`, paths, or backend commands.
- Result docs carry `{json}` beside the text rendering, so sections
  render from data, not from scraped text.

## 5. db contract (delta)

Collections `surprise`, `candidates`, `intents` unchanged in role.
`intents` docs gain `actor` and `session`; result postings gain
`json`. The `catalogs` mirror collection is RETIRED (§5a): the
backend reads metis-catalog directly.

### 5a. Backend: metis-catalog direct, multiple sessions (user, D4)

- The serving loop session works DIRECTLY on the metis-catalog
  checkout: `load <name>` resolves against the repo's domains (the
  REPL's existing file loading; no db mirror to resync). Approved
  candidates keep becoming metis-catalog commits (SPEC §6).
- The backend keeps **multiple REPL sessions** — one per open
  console window: a `sessions` collection ({id, llp, key, epoch,
  stage, status, opened_by, ts}); a window joins or creates one; the
  bus already runs N `metis --json` interpreters over one named pipe
  (SPEC §6), so a session maps to one interpreter. Intents route by
  `session`; every posting names its session; the band renders the
  window's own session only.

## 6. SPEC §6 amendment

The clause "the console holds NO model integration of its own" is
amended to: the console's chat panel is an in-page Claude (`sample`)
acting purely as PRESENTATION and CONTROL through the intent
whitelist; the loop's own LLM seats (formalize, narrate) remain the
REPL's backend, and no model anywhere holds approval authority.

## 7. Non-goals

Source/catalog editing panels; SaaS styling, cards, icons; the
narrator as a chat; page-side execution of any semantics; graphviz
or server-side rendering (v2 may draw the graph JSON as in-page
SVG); multi-catalog dashboards.

## §D — decisions (resolved in review, 2026-10-05)

- **D1 — RESOLVED: intents.** One executor, one whitelist, dialog
  visible on both sides.
- **D2 — RESOLVED: kernel `ctx`** (wire op + REPL command).
- **D3 — RESOLVED: v1 cut as proposed** (graph drawing is v2;
  [graph] offers .dot/.json).
- **D4 — RESOLVED, amended (user)**: the backend works DIRECTLY on
  the metis-catalog repo (no db catalog mirror) and keeps MULTIPLE
  REPL sessions so several console windows can be open — §5a.
  Republish to the existing artifact URL (db carries over); the
  page is reviewed in-repo, published by the architect seat.
- **D5 — RESOLVED: steps as proposed**, run iteratively with the
  opus seat ("start and refine"): 1 kernel `ctx` + whitelist +
  result `json` (+tests); 2 page: band + beat-grouped stream +
  rules/inspector + inline lens sections + shortcuts/self-reload/
  reset + sessions plumbing (no chat yet); 3 chat panel (sample +
  preamble skills + `repl` tool + actor marks); 4 findings/narrator/
  graph sections, polish, publish + functional pass. The interface
  is TESTED WITH THE CHROME TOOLS by the implementer (drive the
  page, click the chips, type intents, verify the live re-render)
  before each step's report.
