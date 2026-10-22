# repl — the loop console's REPL as a domain

What a REPL command needs, what it changes, what it refuses, as rules. The navigation
agent (metis-agent, Gemma E2B — the NAVIGATION brain) types the person's words into one
command; **the host is a websocket client of the loop gateway** (metis-loop
`loop/gateway.py`): a fired rule's event is the frame the page would send, and the
gateway's answers come back as reports. TELL hands the person's words to the
FORMALIZATION brain (the console's `claude -p` or OpenRouter, brain-choice) through the
console's chat; the navigation agent never formalizes. APPLY only shows the plan (the
`repl/save` frame without a token): applying is the person's click.

| file | what |
|---|---|
| `repl.llp` | the session's state as complementary pairs (`idle`/`busy`, `loaded`/`unloaded`, `ran`/`fresh`, `dirty`/`clean`, `chat_seat`/`no_chat_seat`), the tasks (`loading`, `running`, `narrating`, `applying`, `telling`) and the gateway's reports that end them, every refusal with its `%%` reason; the embedded case: "run" with nothing loaded is refused |
| `intent.yaml` | the card: LOAD(package), RUN(n), STEP, UNDO, RESET, NARRATE, RECORDS, APPLY, STOP, TELL(text), HELP, UNKNOWN; the slots ride in the payload |
| `intent/repl-corpus.tsv` | 73 rows, 10 handovers and the navigator's commands as UNKNOWN here |
| `repl_host.py` | the gateway client (the implementer's) |

| event | the frame the host sends | the report it turns the answer into |
|---|---|---|
| `load` / `load_switch` | `repl/open {llp: <package's program>}` (the package from the payload, resolved on the gateway's `meta/domains`) | `+opened` on the `session` frame; `+absent` when the name is in no domains frame |
| `run` / `step` | `repl/intent {cmd: ":run n"}` (n from the payload, default 50) / `":step"` | `+stopped` on the posting's `done`; `+run_refused` on `refused` |
| `undo` / `reset` | `repl/intent ":undo"` / `":reset"` | — (immediate; the host keeps `ran`/`fresh` from the postings) |
| `narrate` | `repl/intent ":narrate"` | `+narrated` / `+narrate_refused` |
| `records` | `repl/records` | — (the dock lists them) |
| `apply` | `repl/work` (the copy) then `repl/save` **without a token** | `+plan_shown` on the plan frame; `+nothing_to_apply` on an empty plan |
| `stop_*` | `repl/stop` | — |
| `tell` | `chat/say {text}` (the payload) | `+told`; `+tell_refused` on a chat error |

The host keeps the pairs current from the gateway's frames: `session.busy` → `busy`/`idle`,
a session open → `loaded`, `source.certified != checkout` → `dirty`, the manifest's
`chat_unavailable` → `no_chat_seat`. A line the gateway refused that a rule accepted (or
the reverse) is a surprise: the console's formalization disagrees with the console.

The sensor (`observe()`, when no request is in flight) reads the console as it is, never as the
program expects (console-nav step 2 F7, the architect's ruling):

| the console | `observe()` reads | against a program that believes `loaded`, `ran` |
|---|---|---|
| the page's session, open | `loaded` | agrees |
| the session gone: `repl/error gone` for it, or a `repl/session` with status closed (the console closed or dropped it) | `unloaded` | a surprise record on `loaded`: the program has no rule for a console that dropped its session (the record drives that rule) |
| the session restarted: a `repl/session` with a new epoch (the idle recycle, a recompile); the same session id, the package still loaded | `loaded`, `fresh` (until a run or step of it is posted: `ran`; a reset: `fresh`) | a surprise record on `ran`: the kernel is at its start again |
| no restart seen yet, or an undo since | `loaded` only (`ran`/`fresh` are the program's own) | — |

The person sees "unloaded" only when the session is really gone.
