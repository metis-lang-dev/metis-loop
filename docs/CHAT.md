# The tester's interface: CHAT + SURPRISES

The user's verdict after the loop-test on pascal (2026-11-03): five panels are too much for an embedded
agent console, and too hard on a tester. The frontend of the pi loop (WORKSPACE.md §6.1: one, shared,
served by the loop's gateway on every workspace) is reduced to TWO panels, and the loop is driven as a
chat. This document amends WORKSPACE.md §6; it is the brief of loop-chat.

## 1. Two panels

| panel | why it stays | what it absorbs |
|---|---|---|
| **CHAT** | the standard interface of the tester: say what to do, read what the loop did | LOOP's state line (lock, child, model, spend of budget) as the chat's header; the gate's plan as a chat card with **confirm / refuse**; a ruling as a chat card (verdict, first enabled, firings, goldens moved, lint, spend, "show pack", "show document"); BUNDLE's STALE as a chat notice with **[rebuild] [reload]**; TRACE's replay as the reply to `/replay` (the Tick table rows, in the chat) |
| **SURPRISES** | the visible connection through the workspace between the REPL (or the road game) and the pi loop: what is open, taken, ruled | the drop dialog (from the session, from a mark, from `/mark`); a ruled one opens its card in the chat |

TRACE, RULINGS and BUNDLE do not go away: they are the developer's docks, hidden by default, shown by a
"developer" switch in the band. The CATALOG, REPL and EDITOR panels stay as they are (the human loop's
tools, personal mode). The dock key becomes v5 (the person's v4 layout is not kept).

**Embedding** (the road catalog, later): the two-panel console is the gateway's page; a host page embeds it
as an iframe of the served URL with `?panels=chat` (SURPRISES went: console-voice step 1), never a copy of its code (§6.1). The
workspace is the host page's root; the gateway serves it there. Nothing of the loop moves.

## 2. Two kinds of lines in the chat

A line the tester types is one of two kinds, told apart by its first character:

**`/command`: the backend's, deterministic, 0 USD.** The gateway answers from the workspace face and the
trace verbs, no model turn. The pi loop need not be running for them. Each is one declared verb:

| command | does | answers with |
|---|---|---|
| `/status` | the workspace: bundle (name, image, BUILT/STALE), locks, child, spend, open surprises | the header line, refreshed |
| `/surprises` | the records by status | the list (the SURPRISES panel scrolls to it) |
| `/take` | starts the pi loop if it is not running and says "take the next surprise" to it | pi's words |
| `/replay [RUN] [K0..K1 \| K]` | `metis.trace fired`/`timeline` of the window (default: the last surprise's) | the Tick table rows in the chat: fired rules, made atoms, per k |
| `/why ATOM [at K]` | `metis.trace blame` | the rule chain that made the atom |
| `/diff` | the last ruling's fired diff and goldens moved | the rows |
| `/ruling [ID]` | the ruling card (default: the last) | the card, with "show pack", "show document" |
| `/mark [K \| K0..K1] WORDS` | a surprise draft from the open session's trace (or `/mark RUN K …` from a run); `keep_window` for a window | the SURPRISES panel's dialog, prefilled |
| `/drop WORDS` | the session's last tick as a surprise with these words | the record's id |
| `/rebuild` | `make` / `metisc build` of the bundle | the build line (image, reused, compiled, errors) |
| `/reload` | the session re-opened from the rebuilt catalog | the session line (epoch) |
| `/lint [MEMBER]` | `metis.lint` with the member's manifest | the rows |
| `/budget USD` | the session budget for the next start | the line |
| `/stop` | stops the pi child | the child's exit |
| `/help` | the table above, from the declarations | |

The verbs come from ONE declaration table (the trace verbs are already metispy's `metis/trace_tools.json`;
the chat's are metis-loop's `loop/chat_tools.json`, generated from the backend's argparse the same way:
`loop/chat.py` `parser()`, `python tools/gen_chat_tools.py [--check]`, a test that the file equals the argparse;
loop-chat step 2). A command the table does not declare is answered "no such command; /help". The chat offers
completion on `/` (the `loop commands` frame: the table). A `/` line never starts pi and costs nothing; `/take` is the
one command that starts it (and says "take the next surprise" to it). `/help` also says the REPL's intervention:
`do +atom` (a bare `+atom` line is refused).

**Anything else: the pi loop's, a model turn, paid within the session budget.** The text goes to the child
as `say`; without a child the chat starts one first (the default model, the `/budget` or loop.sh's 1 USD)
and says so. The loop's conduct in the chat is a section of `pi/prompts/loop-system.md` ("The chat"):

- answer in a few lines; a ruling is reported in the card's fields, never retold;
- the **intents** it understands, each a fixed tool path, named in the prompt so the tester's words land:
  - *take / next*: `surprise_next` → case → pack → `pack_propose` → say the verdict (today's path);
  - *explain [the surprise \| k]*: `trace_fired` + `trace_blame` on the window → three lines: what the
    program did at k, what the world did, which rule's premise was missing; NO pack;
  - *why did it <verb> at k*: `trace_blame` on the atom → the chain in words;
  - *propose / fix*: the pack for the last explanation, judged (`pack_propose`), not applied;
  - *apply*: the accepted pack through `catalog_edit` at the gate, then `bundle_build` — the gate card;
  - *replay / recompile / rebuild / reload / status*: the loop runs the `/command` itself (the backend's
    verbs are tools of the extension too: `chat_tools.json`), so the tester need not know the slash;
  - *narrate [k0..k1]*: the window in prose from the Tick table (the loop's own words; the agent's gemma4
    narration stays reserved, WORKSPACE.md §4.5);
  - *compare [ruling A] [ruling B]*: the two packs' fired diffs side by side;
  - *undo*: `git checkout` of the last applied file through `catalog_edit`'s gate (the apply is a commit
    in the person's tree; undo is its reverse, shown as a diff);
  - *what changed*: the journal since the last take, in words.
- every tool reply past half the budget carries the budget line (as today); past the budget the loop
  refuses with the line, and the chat says "budget spent: /budget N to continue".
- **As landed (loop-chat step 3):** the prompt's "## The chat" (pi/prompts/loop-system.md) makes every turn end with
  a line of words and carries a take through `pack_propose` in one turn; the read-only commands are the loop's
  tools `chat_status`, `chat_surprises`, `chat_replay`, `chat_why`, `chat_diff`, `chat_ruling` (loop/chat.py
  `READ`, the same answers as the slash, through `python -m loop.chat --root DIR LINE`); a turn that still ends
  without words shows "pi ended its turn without words (N tool calls)" (the backend marks it); the chat's input
  answers /commands while another pi loop (the TUI) holds the workspace; an acceptance with nothing enabled reads
  "accepted (inert)" in the card and in `/ruling`.

## 3. What the tester sees, in order (the acceptance)

1. `cd metis-worlds/road && ../../metis-loop/run.sh` → CHAT (header: `road · v-… BUILT · pi: none · 0 of 1 USD`)
   and SURPRISES (empty) and nothing else.
2. The road game drops a mark (the page, road-traces) or the tester types `/mark 412..430 it braked late
   behind the lead car` → SURPRISES shows it open.
3. `take` (or `/take`) → the loop's lines: "taking 2026…-a1b2c3 on planner, window 412..430", the ruling
   card: `accepted · first enabled k 413 brake_late · 3 firings in 3 rows · goldens held · 0.02 USD`.
4. `explain` → three lines, no pack. `why did it accel at 414` → the chain.
5. `apply` → the gate card with the diff → **confirm** → "applied, rebuilt v-…, reload?" → `/reload`.
6. `/replay 412..430` → the rows, now with the new rule firing at 413.
7. `/status` → the header; `/stop`.

## 4. Steps (loop-chat)

| step | who | lands | accept |
|---|---|---|---|
| 1 | opus | the console reduced: CHAT + SURPRISES default, the three docks behind "developer", the header line, the gate/ruling/STALE cards in the chat, `?panels=` | the user's test on the road, chat only (today's `say`, no commands yet) |
| 2 | nina | the backend's `/commands`: `chat_tools.json` generated, the `say` frame routed by its first character, `/help` from the table, completion | each command answered from a committed road trace at 0 USD; tests per command |
| 3 | opus | the loop's chat conduct: the prompt section, the intents, the backend verbs as extension tools, the budget line | one paid round on the road at cap 0.50 USD: take, explain, why, apply, replay, status as a tester would type them |
| 4 | — | the user's test | the acceptance of §3 |
| 5 | pascal | the iframe embedding tried on the road page (`?panels=chat,surprises`), no copy | the road page shows the chat beside the game, the mark lands in SURPRISES |

Rules as loop-workspace's: 0 USD except the named paid rounds; the key from the environment; MemoryMax 6G;
no sim runs (the road trace is committed; the road page is the user's); branches with CI green, the
architect merges; one file per agent per step; WORKSPACE.md §6 gets a pointer to this file.
