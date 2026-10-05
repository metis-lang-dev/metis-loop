# The Loop Console — page source

`loop_console.html` is the web console (SPEC §8): a wrapper over
`metis-loop repl`, published as a claude.ai artifact. The artifact URL
lives in the operator's notes; capabilities are `db` + `user` (no model
integration in the page — the only LLM in the loop is the REPL's
ollama backend).

The page is written for the Artifact publish skeleton: no
doctype/html/head of its own — `<title>` and `<style>` first, content,
one `<script>`. Publish with the Artifact tool against the existing
URL so the db (collections `surprise`, `candidates`, `intents`,
`sessions`, and the `meta/catalogs` doc — CONSOLE.md §5; the old
`catalogs` mirror is retired) and open views carry over.

Contract with the loop (SPEC §6): the page renders records/candidates/
catalogs read-only, writes ONLY candidate decisions (approve/reject)
and `intents` docs (viewer-typed REPL lines); a loop session drains
intents exclusively through `loop.repl.run_intent` and posts results.

Layout and contract: docs/CONSOLE.md (two dialogs over one REPL — the
state debugger left, the chat right from step 3). The page renders
ONLY from structured postings: the band from `sessions/{sid}.ctx`,
the stream from each intent's `json` (beats from `run`/`step`
`fired`, rules/measure/proof from ctx). The serving side is
`loop/console_serve.py`, drained by a Claude session (skills/
metis-loop, "Serving the console").

Local testing: `python console/dev_serve.py --demo` serves the page
behind a dev shim (`claude.use("db"/"user")` over fetch to an
in-memory store, drained in-process by console_serve — the real
kernel). `?nodb` / `?guest` open it with that capability absent;
`?mocksample` gives the chat a CANNED stand-in (no model) that runs
the REPL lines in a message through the page's `repl` tool —
`=deny` / `=rate` simulate not_granted / rate_limited. The real-model
pass happens on the published artifact. The shim is dev-only and
never part of the published page.

## The standing backend: `metis-loop console-serve` (CONSOLE-WS.md)

For live work run the gateway on your host — no drain, no db:

    pip install -e '.[console]'          # websockets
    metis-loop console-serve             # personal: http://127.0.0.1:8770/
    metis-loop console-serve --mode shared --bind 0.0.0.0 --token T

It serves this same page with `window.LOOP_GATEWAY` set and a
`claude.use` shim that resolves null; the page then talks over ONE
WebSocket (`/ws`) — open/attach, intents, postings, session frames
(busy, queued), stop — and renders exactly as before. The mode
manifest decides the chat pane and the LLM seats: **personal** = the
operator's own host (REPL + its LLM seats; agent chat lands in step 2),
**shared** = REPL only — `narrate`/`formalize`/`llm` and chat frames are
refused (they would run on the operator's credentials), with a URL
token, per-IP session cap and a rate limit. Sessions, postings and
history live in MEMORY only (D4: nothing a visitor types or runs is
written to disk); `{source, name}` opens a catalog from text, compiled
in memory (§4a).

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
    artifact_url = ""            # where the chat pointer sends shared users

The artifact (same page, published) stays the SHARED window — demos,
approvals from any device, `sample` chat billed to the viewer — over
its db drain; that is the secondary transport.
