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
kernel). `?nodb` / `?guest` open it with that capability absent. The
shim is dev-only and never part of the published page.
