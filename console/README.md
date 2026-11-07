# The Loop Console — page source

`loop_console.html` is the web console (SPEC §8): a wrapper over the two terminals (the REPL and the pi loop,
loop-ui s-bb07923c), served by the gateway, `metis-loop console-serve`, its ONLY backend (loop-ui 2.4, the
user, 2026-11-05: the claude.ai artifact published and drained by a Claude session, its db and
`dev_serve.py` are gone). No model in the page, nor behind it: the pi loop formalizes in the same workspace.

The page has no doctype/html/head of its own — `<title>` and `<style>` first, content, its scripts: the
gateway wraps it (`loop/gateway.py` page(), with `window.LOOP_GATEWAY`).

The shell — the top bar (`#band`), the tool panels (`.dock`) with the
strip that toggles them, the splitter and the colour tokens — is not in
this file: it is `console/lib/shell.css` + `console/lib/shell.js`, this
repo's own copy (shell-copy s-7c739dd7: independent repos keep copies,
never a dependency for look and feel; the metis-agent console keeps its
own copy of the same files). The page links them relative (`lib/…`): the
gateway serves them at `/lib/` (`loop/shell_lib.py`).

**No voice navigation** (voice-nav-removal s-90621b2c; the user, 2026-10-24: one voice
paradigm, the dialog with the agent and the game; the web UI stays web). console-nav's TALK
dock, its navigation agent (`console-nav.sh`, `domains/ui`, `domains/repl`), `lib/nav.js`,
`lib/ui-port.js` and the fsttm-web copies it imported are removed. Since loop-workspace the
CLAUDE dock is gone too: the console has no chat. The docks keep the keyboard and the mouse.

**The voice** (console-voice s-dc1f184c; the user, 2026-11-05): fsttm-web's voice widget in the
band (mic on F9, pi's words spoken by its voice switch on Shift+8, the narrator on F8) and the dialog's own part (the floor, barge-in,
attention, the floor / state / events cards) in the DIALOG dock, the last dock. What the mic hears
is said in the CHAT as the person's line (`you · heard`): a `/` line is the backend's, anything
else pi's; pi's words are spoken on the dialog's floor. fsttm-web is served at `/lib/` from the
installed `fsttm_web` package, behind the shell (`loop/shell_lib.py`), never copied; without the
package the page has no voice and says so in the browser's console.

Contract with the loop (SPEC §6): the page renders the catalogs read-only and sends ONLY REPL lines (`repl
intent` frames, viewer-typed); the gateway runs them exclusively through `run_intent` (the whitelist; in personal
mode with the workspace verbs, loop-ui 2.1) and posts results. **No CANDIDATES, RECORDS or SURPRISES docks** (console-voice step 1; the user, 2026-11-05: "too many useless
panels ... we have /surprises for same info"): the candidates' approve/reject (formalize left the console), the
JSONL sink records (the pre-workspace loop's) and the surprises list with its drop dialog are gone. In the CHAT:
- `/surprises [open|taken|ruled]` lists the workspace's surprises (`.metis/surprises/`);
- `/drop WORDS` drops the open session's last tick as a surprise with these words: its REPL's `drop` (loop-ui 2.2);
- `/mark [K | K0..K1] WORDS` its REPL's `mark`; `/mark RUN K WORDS` a trace's tick, dropped at once as the
  terminal's `/mark` does. TRACE's "mark here" (developer) puts `/mark RUN K ` in the CHAT's
  input for the words.

Layout and contract: docs/CONSOLE.md (two dialogs over one REPL — the
state debugger left; the chat it describes is retired). The page renders
ONLY from structured postings: the band from the session frame's ctx,
the stream from each posting's `json` (beats from `run`/`step`
`fired`, rules/measure/proof from ctx). The serving side is
`loop/console_serve.py`, called by the gateway.

## The standing backend: `metis-loop console-serve` (CONSOLE-WS.md)

Run the gateway on your host:

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
written to disk). A session opens a checkout program (`{llp}`); the
workspace owns the file (workspace-files s-9ea4cfa4): the EDITOR (the
band's **edit**, the REPL's `edit RULE`, a file's row on CATALOG) edits
the session's program and extensions as they are on disk, and **save**
is one gated edit — the diff and the gate's findings (metisc's
diagnostics, the lint) in the dialog, then confirm writes the file and
the session re-opens (epoch + 1). Nothing is kept in the browser. A
visitor's view (shared mode) reads only.

**The workspace panels** (loop-workspace step 4, docs/WORKSPACE.md §6; reduced by loop-chat step 1,
docs/CHAT.md §1): in personal mode the page mounts the loop SDK's widgets as docks, each over the backend's
channels. The tester's one is open by default:
- **CHAT** (`loop`, with `bundle` and `surprise` for its cards): the header line (the bundle's name, image,
  BUILT/STALE; the pi child, or the lock of a pi loop elsewhere; the spend of the session's budget), the chat
  with the pi loop (a line said with no child starts one first: the options' model and budget, else
  loop.sh's), the gate's plan as a card with confirm/refuse, a ruling as a card (verdict, first enabled,
  firings, goldens moved, lint, spend, show pack / show document), STALE as a notice with [rebuild] [reload],
  the journal behind its chip.

The developer's three, behind the band's **developer** switch (hidden by default, per viewer):
- **RULINGS** (`surprise`): the verdict with when the candidate is first enabled and how often it fires,
  the goldens moved, lint, the readings absent, the spend, the pack and the document.
- **TRACE** (`trace`): the runs in `.metis/traces/`, the Tick table at k, step and jump, the declared
  trace verbs, and "mark here".
- **BUNDLE** (`bundle`): the composition, its image, STALE with why, and the session's reload.

On a workspace CATALOG starts folded (the strip shows the docks); the layout is kept per
viewer (`loopconsole.docks.v5`). **Embedding:** `/?panels=chat` (with `&token=` when the gateway
has one) mounts only the named docks, across the whole page, with no band, REPL or strip: a host page (the
road's) shows it as an iframe of the served URL, never a copy of its code.

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

A shared window (demos, visitors) is the same gateway in `--mode shared`.
