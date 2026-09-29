# The Loop Console — page source

`loop_console.html` is the web console (SPEC §8): a wrapper over
`metis-loop repl`, published as a claude.ai artifact. The artifact URL
lives in the operator's notes; capabilities are `db` + `user` (no model
integration in the page — the only LLM in the loop is the REPL's
ollama backend).

The page is written for the Artifact publish skeleton: no
doctype/html/head of its own — `<title>` and `<style>` first, content,
one `<script>`. Publish with the Artifact tool against the existing
URL so the db (collections `surprise`, `candidates`, `catalogs`,
`intents`) and open views carry over.

Contract with the loop (SPEC §6): the page renders records/candidates/
catalogs read-only, writes ONLY candidate decisions (approve/reject)
and `intents` docs (viewer-typed REPL lines); a loop session drains
intents exclusively through `loop.repl.run_intent` and posts results.
