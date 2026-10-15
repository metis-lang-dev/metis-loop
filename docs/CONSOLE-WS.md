# CONSOLE-WS — the Loop Console v2 (one backend, real transport)

**Status: ACCEPTED 2026-10-05 (user review); D1–D5 resolved in §D.** Builds on
CONSOLE.md (v1, shipped as artifact v8); v1's page rendering, kernel
ops and ConsoleServer are REUSED, its artifact-db transport is
RETIRED as the primary channel (the artifact surface itself is kept,
§6).

Origin: v1's structural gap, hit by the user on first contact —
"where is the backend from session?" The artifact db is reachable
only by the page or a Claude session's tools, so serving means a
Claude session babysitting a drain loop; intents answer in seconds
to never, and automated windows suspend inbound delivery entirely.
v2 gives the console what it always implied: a standing backend on
the operator's host, WebSocket push, and the agent in the backend
where its tools are function calls.

    ┌──────────── Browser (one page) ─────────────┐
    │  debugger pane          │  Claude chat pane │
    └──────────────┬──────────┴─────────┬─────────┘
                   └── one WebSocket ───┘
                             │
    ┌────────────── metis-loop console-serve ─────────────────┐
    │  Gateway (WS router, mode manifest, optional token)     │
    │    ├── Session Manager  == ConsoleServer (sid -> Repl)  │
    │    └── Agent Service (Claude Agent SDK, personal mode)  │
    │           └── tools -> the wire-op module, in process   │
    └──────────────────────────────────────────────────────────┘

## 1. Gateway and wire

`metis-loop console-serve` (new CLI verb): serves the page over HTTP
and ONE WebSocket per browser window, multiplexed by channel —
grown from `console/dev_serve.py`, which is already this shape.
Messages (JSON, one per frame):

    {ch:"repl",  type:"intent",  session, cmd, actor}        (page->gw)
    {ch:"repl",  type:"posting", session, id, status, result,
                 json, epoch}                                 (gw->page)
    {ch:"repl",  type:"session", session, ...ctx fields}      (gw->page)
    {ch:"chat",  type:"say", text}            (page->gw, personal mode)
    {ch:"chat",  type:"token"|"tool"|"done"|"error", ...}     (gw->page)
    {ch:"meta",  type:"manifest", modes...; type:"catalogs", names}

The posting payload is `intent_posting`'s dict verbatim (CONSOLE §4)
— the page's renderers do not change. The whitelist is enforced
gateway-side with the SAME `parse_intent`; `accept` and paths stay
structurally absent. Config: the metis dot file gains `[console]`
(port, bind, mode, token?, session caps).

## 2. Session Manager

`ConsoleServer` as-is: one in-process `Repl` per console session,
open/serve/close, epoch bumps, catalog names from the metis-catalog
checkout. v2 additions: per-session COMMAND QUEUE (one command runs
at a time; the page shows "running… [stop]" and disables Run — stop
interrupts the running command, and in agent mode the agent loop
too); caps from `[console]`: max sessions, max steps per `run`, idle
session recycling (epoch bump says so). Subprocess isolation
(`metis --json` per session over the bus) stays the drop-in upgrade
if a session ever needs killing harder than Python allows.

## 3. Agent Service (personal mode only)

The chat pane's Claude moves into the backend: Python
`claude-agent-sdk`, authenticated by the OPERATOR's `claude login`
(Pro/Max) — the key/login never reaches the browser.

- System prompt = v1's PREAMBLE (REPL skill + formalization skill),
  promoted to a real system slot and PROMPT-CACHED.
- Tools = one module wrapping the wire ops for a FIXED session id
  (the window's): `repl(line)` as in v1, plus direct `ctx()` /
  `transcript(n)` readers so the model needn't spend a round asking.
  Results trimmed exactly as v1's `trimJson`; refusals throw.
- Each chat is BOUND to the pane's session; the live ctx line rides
  each turn as in v1.
- Caps: ≤10 tool calls per turn, per-command timeout, output
  truncation (first/last 200 lines). [stop] aborts the SDK turn.
- Chat history is server-held IN MEMORY per session (D4): reload
  restores both panes while the backend lives; a backend restart
  starts clean. Nothing a visitor types or runs is written to the
  operator's disk — deliberate, since shared instances serve people
  from the net and we do not keep their work.
- Later (v2.1, not launch): Suggest mode (code blocks with
  insert/run buttons) beside today's Agent mode; selection →
  "ask Claude"; VOICE on the chat pane — browser-side only, the
  text loop unchanged: Web Speech API (SpeechRecognition in,
  speechSynthesis out; Chrome/Edge; NOTE Chrome ships recognition
  audio to Google's servers — say so in the UI). The privacy
  upgrade, if ever wanted, is local STT/TTS on the personal host
  (faster-whisper + piper) over an added WS audio channel — fits
  the interception pattern, personal mode only (chat does not
  exist in shared mode, so voice has no shared-instance story).

## 4. Deployment modes and LLM seat routing (the user's conditions)

Anybody can start `metis-loop console-serve` on their host. The
gateway advertises a MODE MANIFEST and the page renders what exists
— nothing it cannot serve is shown as available.

| seat | terminal REPL | web personal (own host, own login) | web shared (one public-ish instance) |
|---|---|---|---|
| REPL sessions | the local shell | yes (multi) | yes (multi) — "replit without AI" |
| chat (agent) | — | Agent SDK, operator's Pro/Max | OFF (policy + resources) |
| formalize | `llm` endpoint as today — the subscription path is the existing `command:` backend (`command:claude -p …`) or ollama | Agent Service (SDK, diagnostics-only repair, spec 08 D5) | OFF |
| narrate | **ollama ONLY** (user condition: the terminal REPL narrates through ollama) | **Haiku PREFERRED** via the SDK (`claude-haiku-4-5`), ollama fallback when the SDK seat is absent | OFF (a nook cannot carry models) |

### 4a. Command interception and copy-on-write catalogs (user, 2026-10-05)

D3's pattern generalized: the gateway INTERCEPTS the commands whose
terminal semantics (local editors, local paths) mean nothing over
the web, and substitutes web-native ones. The kernel is untouched;
the terminal REPL keeps its behavior.

- **`edit [RULE]`** → a READ-ONLY, syntax-colored source viewer in
  the browser (popup or tab): the LLP colorizer (the v1 console's
  `hl()` token classes), scrolled to RULE's line with the rule
  flashed; AUTO-RELOADS when the session's catalog changes (epoch /
  key bump, or a COW re-send). No editor component — a plain
  rendered view; editing happens in the COW editor below.
- **Copy-on-write catalogs.** metis-catalog is READ-ONLY for every
  web user. "Fork" on a session pulls the resolved catalog's source
  (a read-only gateway fetch) into the BROWSER DB (IndexedDB,
  per-browser) where the user edits it (plain textarea with the
  colorizer as overlay — minimal decoration, no editor framework);
  the page re-opens the session FROM SOURCE: `open_session` accepts
  `{source: text, name}` beside `{llp: name}`, compiles in memory,
  and NOTHING touches the operator's disk (the D4 doctrine extended:
  visitors' catalogs are theirs, held client-side). Saving in the
  editor re-sends the source — the REPL reload semantics apply
  (state carries over, NEW-key banner, epoch bump), and the `edit`
  viewer auto-follows. New scripts = COW from a blank scratch
  catalog. Changes destined for the REAL metis-catalog still go the
  one road: candidate → gates → the operator approves → commit (the
  loop; never a web write).
- **`save`/`export`** → browser downloads of the session state /
  COW source (gateway returns the text; the page saves it), never
  server paths.
- On the ARTIFACT surface the COW copy's home is the viewer's
  private `data/users/<id>/` subtree (same ownership story,
  different store).

Policy line, enforced by the manifest and stated in the page: a
shared instance NEVER routes other people's chat, narration or
formalization through the operator's Pro/Max credentials (Anthropic
policy); AI for shared users lives on the artifact surface (§6),
where `sample` bills the VIEWER. Shared mode ships with an optional
access token + per-IP session caps + rate limits; "anyone on my LAN
/ with the token can run catalogs, nothing can spend my tokens."

## 5. Page changes

One page serves both transports: a WS client module replaces the
`claude.use("db")`/`sample` shims when the page is served by the
gateway (served flag), and the rendering core — band, beat blocks,
rule states, lenses, inspector, sections — is untouched. The chat
pane renders per manifest: agent chat (personal), or a one-line
pointer to the artifact console (shared), or hidden (terminal-only
hosts). Busy/stop state per §2. The `?mocksample`/`?missmod` dev
modes survive for page testing.

## 6. The artifact surface is KEPT

The published artifact (v8, same URL) remains the zero-install,
share-from-anywhere surface: demos, approvals from any device, and
the shared-users' Claude chat — `sample` is viewer-consented and
viewer-billed, which is exactly the policy-clean shape for people
who are not the operator. Its drain stays as documented (a Claude
session serving `ConsoleServer.drain`), explicitly labeled the
SECONDARY transport: the skill says "for live work, run
console-serve; the artifact is the shared window."

## 7. Security and limits

- No API key or login token in the browser, ever (SDK auth lives in
  the backend process).
- Shared mode: token (optional), per-IP session cap, per-session
  command queue, `run` step caps, rate limits; the whitelist is the
  same one — approval verbs and paths cannot arrive over the wire.
- Agent mode: tool-call cap per turn, interruptible, output
  truncation before the model sees it; agent usage draws the
  operator's subscription limits and the manifest shows a per-day
  soft cap.

## Implementation sketch

- metis-loop: `loop/gateway.py` (websockets or FastAPI; grown from
  dev_serve), `loop/agent_service.py` (claude-agent-sdk), the
  `console-serve` CLI verb, `[console]` config; console page: the
  WS client module + manifest rendering + busy/stop.
- metispy: nothing new expected (the wire ops and ctx are done);
  narrate's seat spec gains the SDK endpoint kind only if §D3 lands
  it kernel-side rather than gateway-side.
- Tests: gateway protocol round-trip over a real socket; manifest
  gating (shared mode refuses chat/narrate/formalize frames);
  agent-tool module against 3lp with the cap enforced; page guards.

## §D — decisions (resolved in review, 2026-10-05)

- **D1 — RESOLVED: plain `websockets` + stdlib http** (dev_serve
  lineage; no framework).
- **D2 — RESOLVED: shared-mode token in the URL.**
- **D3 — RESOLVED: gateway substitutes the narrate seat with an
  SDK-backed endpoint.** Kernel untouched; the terminal narrates
  via ollama by construction.
- **D4 — RESOLVED: chat history in memory only.** The user's
  reasoning is privacy, recorded as doctrine: shared instances
  serve users from the net and WE DO NOT KEEP THEIR WORK — no
  visitor chat, session state or transcripts persisted to the
  operator's disk (§3).
- **Step-4 amendments (user, during the step, recorded post-hoc)**:
  §4a landed in the user's simplified form — the working copy lives
  in IndexedDB + gateway memory, extensions gate on top of it through the
  loop's own road (`accept` into THIS session only, never the wire),
  recompile = "certified local" or the old world kept; the agent
  gains source_read / source_edit / extension_create / recompile behind
  the same single-authority gate. UI amendments: CodeMirror 6 as
  floating editors from ONE vendored esbuild bundle (CDN double-
  loads @codemirror/state; artifact surface falls back to textarea),
  right-side TOOL PANELS (strip: Claude · Catalog · Candidates ·
  Records), clickable enabled events (queue `step <event>`), a CM
  chat input, and DICTATION (the v2.1 voice item pulled forward:
  Web Speech, feature-detected, the Chrome-audio-to-Google notice in
  its title; local Whisper-on-WebGPU a proposed follow-up).
  Doctrine correction found in the step: containment is NAMESPACE
  PRODUCE-RIGHTS — an extension writes what the base grants its layer; the
  preamble's "extensions never produce base atoms" overstated the gate
  and was corrected (the gate is the semantics; prompts follow it).
- **D5 — RESOLVED: steps as proposed, plus step 4 (user)** —
  1 gateway + session manager + page WS client (REPL-only, both
  modes; this alone is the nook deployment — and `open_session`
  accepts `{source}` from day one so §4a needs no API rework);
  2 Agent Service + chat pane over WS + caps/stop; 3 narrate-via-
  Haiku + in-memory history wiring + manifest polish + docs/skill;
  4 command interception + COW (§4a): the edit viewer, fork/editor
  over IndexedDB, save/export as downloads. The artifact-surface
  skill note lands with step 1.

## Implementation notes (steps 1–3, opus seat, 2026-10-07)

- **Gateway** `loop/gateway.py`: websockets on one port (`process_request`
  serves `/`, `/healthz`); session ids gateway-minted (bearer for
  re-attach); per-session asyncio queue + ONE worker thread; stop raises
  KeyboardInterrupt into that thread (tid lock-guarded) and cancels the
  queue — soft by nature (subprocess isolation stays the upgrade);
  `submit()` lets the agent queue a line and await its posting.
- **Session from source** (§4a, day one): `ConsoleServer.open_session
  ({source, name})` — a `Repl` subclass compiling the given text; no
  temp file; 256 KiB cap.
- **Agent Service** `loop/agent_service.py`: PREAMBLE read from the page
  (one source) + an addendum; one in-process MCP server per chat
  (repl via the session queue as `claude>`, ctx/transcript from cached
  state); `tools=[]`, strict MCP, `setting_sources=[]`,
  `--no-session-persistence` (verified: no transcript written after
  live turns); a `can_use_tool` gate is the ONLY authority — no
  `allowed_tools`, which auto-approves before the callback; the page
  cannot claim `actor: claude`.
- **Narrate seat** (D3) `loop/sdk_narrate.py`: the gateway points a
  personal session's LLM endpoint at it through the kernel's existing
  `command:` backend (pages can't set `command:` — whitelist); no
  tools, one turn, no persistence. Measured on 3lp: CLI-default
  thinking ~5k tokens/~50 s (faithful); thinking off ~4 s but fused
  separate beats and once invented events (3/3 wrong); budget 1024
  ~8–18 s and faithful → the default (`narrate_thinking`).
- **Tests** are hermetic (FakeClient over a real socket; SDK `query`
  monkeypatched); real turns are opt-in with `METIS_AGENT_LIVE=1`.
- **Tooling fact**: WebSocket push keeps flowing in a hidden/
  background browser window — unlike the artifact frame, whose
  inbound delivery is suspended there.

