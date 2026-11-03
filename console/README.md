# The Loop Console — page source

`loop_console.html` is the web console (SPEC §8): a wrapper over
`metis-loop repl`, published as a claude.ai artifact. The artifact URL
lives in the operator's notes; capabilities are `db` + `user` (no model
in the page, nor behind it: the console's LLM seats are retired,
loop-workspace; the pi loop formalizes in the same workspace).

The page is written for the Artifact publish skeleton: no
doctype/html/head of its own — `<title>` and `<style>` first, content,
one `<script>`. Publish with the Artifact tool against the existing
URL so the db (collections `surprise`, `candidates`, `intents`,
`sessions`, and the `meta/catalogs` doc — CONSOLE.md §5; the old
`catalogs` mirror is retired) and open views carry over.

The shell — the top bar (`#band`), the tool panels (`.dock`) with the
strip that toggles them, the splitter and the colour tokens — is not in
this file: it is `console/lib/shell.css` + `console/lib/shell.js`, this
repo's own copy (shell-copy s-7c739dd7: independent repos keep copies,
never a dependency for look and feel; the metis-agent console keeps its
own copy of the same files). The page links them relative (`lib/…`): the
gateway and `dev_serve.py` serve them at `/lib/` (`loop/shell_lib.py`);
an artifact publish passes them as files
(`files: {"lib/shell.css": "console/lib/shell.css", "lib/shell.js": "console/lib/shell.js"}`).

**No voice navigation** (voice-nav-removal s-90621b2c; the user, 2026-10-24: one voice
paradigm, the dialog with the agent and the game; the web UI stays web). console-nav's TALK
dock, its navigation agent (`console-nav.sh`, `domains/ui`, `domains/repl`), `lib/nav.js`,
`lib/ui-port.js` and the fsttm-web copies it imported are removed. Since loop-workspace the
CLAUDE dock is gone too: the console has no chat. The docks keep the keyboard and the mouse.

Contract with the loop (SPEC §6): the page renders records/candidates/
catalogs read-only, writes ONLY candidate decisions (approve/reject)
and `intents` docs (viewer-typed REPL lines); a loop session drains
intents exclusively through `loop.repl.run_intent` and posts results.

Layout and contract: docs/CONSOLE.md (two dialogs over one REPL — the
state debugger left; the chat it describes is retired). The page renders
ONLY from structured postings: the band from `sessions/{sid}.ctx`,
the stream from each intent's `json` (beats from `run`/`step`
`fired`, rules/measure/proof from ctx). The serving side is
`loop/console_serve.py`, drained by a Claude session (skills/
metis-loop, "Serving the console").

Local testing: `python console/dev_serve.py --demo` serves the page
behind a dev shim (`claude.use("db"/"user")` over fetch to an
in-memory store, drained in-process by console_serve — the real
kernel). `?nodb` / `?guest` open it with that capability absent. The shim is
dev-only and never part of the published page.

## The standing backend: `metis-loop console-serve` (CONSOLE-WS.md)

For live work run the gateway on your host — no drain, no db:

    pip install -e '.[console]'          # websockets
    metis-loop console-serve             # personal: http://127.0.0.1:8770/
    metis-loop console-serve --mode shared --bind 0.0.0.0 --token T

It serves this same page with `window.LOOP_GATEWAY` set and a
`claude.use` shim that resolves null; the page then talks over ONE
WebSocket (`/ws`) — open/attach, intents, postings, session frames
(busy, queued), stop — and renders exactly as before. No mode runs a
model: `narrate`/`formalize`/`llm` and chat frames are refused in both,
naming the pi loop. **personal** = the operator's own host, with the
workspace channels (`trace`, `surprise`, `bundle`, `loop`: WORKSPACE.md §3);
**shared** = the REPL only, with a URL token, per-IP session cap and a
rate limit. Sessions, postings and
history live in MEMORY only (D4: nothing a visitor types or runs is
written to disk); `{source, name}` opens a catalog from text, compiled
in memory (§4a).

**The workspace panels** (loop-workspace step 4, docs/WORKSPACE.md §6): in personal mode the page
mounts the loop SDK's five widgets as docks, each over one of the backend's channels:
- **LOOP** (`loop`): who holds the workspace, the spend, start/stop of a pi loop as the backend's child
  (rpc mode), the chat with it, the gate's plan with confirm/refuse, the budget line past half the
  budget, the journal.
- **SURPRISES** (`surprise`): open · taken · ruled, and the drop dialog, from the open session or from
  a tick marked in TRACE.
- **RULINGS** (`surprise`): the verdict with when the candidate is first enabled and how often it fires,
  the goldens moved, lint, the readings absent, the spend, the pack and the document.
- **TRACE** (`trace`): the runs in `.metis/traces/`, the Tick table at k, step and jump, the declared
  trace verbs, and "mark here".
- **BUNDLE** (`bundle`): the composition, its image, STALE with why, and the session's reload.

A session opened here writes its trace (`.metis/traces/<session>/`), so a surprise dropped from it
replays.

This console with these panels is the pi loop's one frontend (WORKSPACE.md §6.1), on every
workspace: run it in `metis-catalog`, in `metis-worlds/road` (beside the road page, which stays the
road's own UI and the world's host), or in any DIR. Nothing of it is copied into another page.

Config — the metis dot file's `[console]` table (flags override):

    [console]
    port = 8770
    bind = "127.0.0.1"
    mode = "personal"            # or "shared"
    token = ""                   # shared: required as ?token=… when set
    max_sessions = 16
    max_sessions_per_ip = 4      # shared mode
    max_run_steps = 500          # `run N` is clamped above this
    idle_secs = 1800             # idle sessions reset (epoch + 1)
    rate_per_min = 120           # shared mode, per address

The retired seats' keys (`agent*`, `narrate*`, `formalize_*`, `brain`,
`openrouter_*`, `max_usd`, `artifact_url`) are ignored, and the start line
names any your dot file still has.

The artifact (same page, published) stays the SHARED window — demos and
approvals from any device — over its db drain; that is the secondary
transport.
