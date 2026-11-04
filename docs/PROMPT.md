# The pi loop's prompt — what the model is given, and where each kind of knowledge lives

loop-prompt (the architect, 2026-11-04; the user's observation: the pi loop degrades on deepseek under the
output and context caps, and the long tail of the context is where inference fails). This document is the
ruling and the brief: §1 what was measured, §2 where each kind of knowledge goes, §3 the tool sets, §4 the
budgets a turn must respect, §5 the steps. The prompt itself is `pi/prompts/loop-system.md` (v2 drafted
beside it as `loop-system.v2.md` until step 2 switches the launcher).

## 1. What sits in the context (measured on the dog drive, 2026-11-03 20:00, v4 pro, thinking high)

Session `metis-catalog/.metis/sessions/2026-11-03T19-59-10-994Z_…jsonl`: 26 messages, 88 KB of message
text, 9 model calls, 0.0276 USD.

| what | bytes | where in the context |
|---|---|---|
| three assistant turns that are **thinking only** (no words, no tool call: the 2048-token cap spent) | 15.9 K + 15.5 K + 15.8 K | the tail: deepseek's compat replays `reasoning_content` on every later request, so each dead turn stays |
| `surprise_next` result: the record + the WHOLE member program (dog.llp) + the primer + earlier rulings | 14.2 K | the tail at the moment the pack is written; alfworld's hier member with its family units would be 66 K, cut at the 40 K cap |
| one more thinking block before a tool call | 6.1 K | tail |
| `workspace_context` result (README up to 4000 + bundle + loops + surprises) | 4.1 K | head |
| the system prompt `loop-system.md` | 8.4 K | head |
| the tool declarations: repl 12, domain 5 + 12 + one per intent verb, workspace 6, trace 11, chat 15 (≈ 60 tools) | ≈ 25 K (estimated from the three declaration files + the extension strings) | head |
| every other tool result (trace_blame, trace_count, trace_fired, trace_replay) | 0.2–1.3 K each | tail |

What is NOT in pi's context: the pattern catalog (`pi/policy/skills/patterns`, 130 KB), `hierarchy.md`,
`skills/metis-loop/SKILL.md` (16 KB). pi runs with `--no-skills --no-context-files` (pi.sh); those files
are the Claude Code seat's and the policy driver's. So the degradation is not the skill files in the tail:
it is (a) dead reasoning replayed, 48 KB of the 88 KB, right before the generation point; (b) whole-program
dumps in one tool result; (c) the rule-writing primer and the loop's procedure arriving as tool results
(the tail) instead of standing in the system prompt (the head, cached, read once). The output cap (2048)
turns every long reasoning into a dead turn, and every dead turn into more tail.

Thinking off by default (30bf6fa, L1) removes (a) for the next drive, and it is kept. The rest is this
subject.

## 2. Where each kind of knowledge lives (the ruling)

The user's proposal, taken: ONE system prompt that defines the language, the loop's mechanics, and shows
the moves as worked examples; nothing domain-specific in it; patterns that are a tool invocation are the
tool, not prose. Precisely:

| knowledge | lives in | not in |
|---|---|---|
| the language: rule form, `$` read / bare consume, `*`, `-o`, `()`, `%%` doc, stages, layers, `pred`, `type`, `catalog`/`extends`/`include`, `now` command rules, the pack shape | system prompt **§1 The language** (one page, from spec/00 §1–2 and §5a) | `surprise_next`'s primer (removed: the prompt has it) |
| the loop's mechanics: workspace, surprise → window → case → pack → `pack_propose` → ruling → `catalog_edit` at the person's approval → `bundle_build` → `/reload`; the verdict is the gate's; the chat's conduct and intents | system prompt **§2 The loop** | the tool descriptions (they say what a tool returns, not when to call it) |
| the loop's moves (patterns `6-loop.md`: Blame first, Replay never rerun, Read the refusal, Mechanical verdict model's words, Not this package's, Own facts judged) | §2 as one-line rules, each one sentence | the pattern catalog's text (never loaded into pi) |
| worked examples: three REAL rulings, each as `surprise → blame rows → pack → verdict card` in ≤ 2 KB: one missing rule (the world did what no rule says), one missing premise (a rule fired when the person says it must not), one *explain* with no pack | system prompt **§3 Three surprises, ruled** (opus extracts them from the alfworld drive's rulings and the dog's; copied verbatim, never written from memory) | — |
| the standalone catalog loop (formalize / new / intents / exercise / take: the seed task) | `prompts/seed-task.md` only, loaded with the task when `loop.sh` seeds; the system prompt keeps one paragraph naming it | the workspace prompt's body (today's steps 1–8 are two thirds of it and are forbidden in a workspace) |
| tool-invocation patterns (status, replay, why, diff, ruling, rebuild, reload, lint, budget) | the `/commands` and the `chat_*` tools (CHAT.md §2), their one-line descriptions | prose in the prompt (the prompt names the intent and the tool, nothing more) |
| domain knowledge (the road's norms, a world's conventions, ALFWorld's verbs) | the workspace's `README.md` (`workspace_context`, cut at 4000 characters) and each member's `%%` doc lines (in the program `surprise_next` gives) | the system prompt, ever: the prompt is the same on every workspace |
| the member's program and its units | `surprise_next`: the member's OWN program in full; each included unit as its **signature** (its `pred` lines and every rule's name with its `%%` line, no bodies), with the path, so a pack that amends it names `unit=` | the full text of the family's units (25 KB on alfworld) |
| the pattern catalog, `hierarchy.md`, SKILL.md | the Claude Code seat (file tools) and `policy/rewrite.py` | pi |

## 3. The tool sets, by mode

pi declares ≈ 60 tools because the two loops share one process. In a workspace the standalone tools
(`repl_text`, `repl_formalize`, `repl_revise`, `repl_gate`, `repl_show`, `catalog_new`, `domain_open`,
`domain_*`, `intent_*`) are forbidden for a surprise and the prompt spends a paragraph saying so. The
extensions register by mode instead:

- **workspace mode** (`loop.sh` over a DIR with a bundle, no seed): `workspace_context`, `surprise_list`,
  `surprise_next`, `pack_propose`, `bundle_build`, `journal`, the 11 trace tools, `catalog_edit`,
  and the chat's answering tools (`chat_status`, `chat_surprises`, `chat_replay`, `chat_why`,
  `chat_diff`, `chat_ruling`, `chat_lint`): ≈ 27 tools;
- **seed mode** (`loop.sh --seed`): today's set minus the workspace tools.

The mode is one environment variable the launcher sets (`METIS_LOOP_MODE=workspace|seed`); each extension
reads it at registration. Nothing else changes in the extensions.

## 4. The budgets a turn must respect (measured by the drive, step 3)

| item | cap |
|---|---|
| the system prompt with its three examples | ≤ 20 KB |
| `workspace_context` | ≤ 5 KB (README 4000 stays) |
| `surprise_next` | ≤ 12 KB on alfworld's hier bundle (the own program + signatures); the 40 K cap stays as the hard stop |
| any other tool result | ≤ 8 KB; a longer one says "cut at N characters, narrow the window" |
| dead turns (no words, no tool call) in a drive of three surprises | 0 |
| `requiresReasoningContentOnAssistantMessages` replay | with thinking off, nothing; with thinking low (step 3's second run), the replay is measured per turn and reported |

The drive's report carries the context size per model call (characters sent, from pi's session file), the
dead turns, and the spend: three surprises on alfworld, thinking off, cap 0.50 USD; then the same three
with `METIS_LOOP_THINKING=low` and `maxTokens` 4096 for that run only (models.json override), cap 0.50 USD,
to say whether a little reasoning helps once the tail is clean. The user picks the default from the two
numbers; nothing is switched by the implementer.

## 5. The steps

1. **opus**: tool sets by mode (§3) and `surprise_next`'s signature view (§2, last rows); the primer line
   gone from the tool result; the workspace tests updated (`pi/test/workspace.test.ts`: the mode's tool
   list, the signature of alfworld's iface unit); 0 USD; CI green on a branch.
2. **opus**: the prompt v2 wired: `loop-system.v2.md` becomes `loop-system.md` with §3 filled from three
   real rulings (the alfworld drive's `rulings/<id>.md` + `packs/<id>.llp` and the chat's cards; quoted,
   trimmed to the rows the example needs, never rewritten); `seed-task.md` carries the standalone steps the
   prompt dropped; a test asserts the prompt's size and that every tool it names is registered in its mode.
3. **opus**: the two drives of §4 on metis-worlds/alfworld's bundle; the report with the table of §4 filled
   and the spend (two caps of 0.50 USD).
4. **nina** reviews 1–3 (the signature view against `metisc`'s own include resolution; the examples against
   the rulings they quote).
5. the user drives the chat (CHAT.md §3) on the new prompt; then loop-chat step 5 (the iframe) proceeds.
