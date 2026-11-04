# The pi loop's prompt and skills — what the model is given, and where each kind of knowledge lives

loop-prompt s-3591d53b (the architect, 2026-11-04; v2 after the user's correction). The user's two working
ideas, in their order: FIRST take out of the loop's material the domain-specific patterns and the patterns
that became a tool (a tool catalog is not a pattern); THEN use what remains as a multi-shot prompt of
examples, the anti-patterns among them as counter-examples. The system prompt is the ORIGINAL one (the
one tested in the first runs: `pi/prompts/loop-system.md` at 163f432, its shape and its wording),
enhanced with the tooling added since, the noise taken out. The detail goes into pi SKILLS, loaded on
demand. Reasoning stays ON: DeepSeek was kept over GLM for its chain of thought; the only measurement
is reasoning on against reasoning off, and the off run goes to another model.

§1 what was measured, §2 the ruling (prompt, skills, reasoning), §3 the skills' content, §4 the
measurement, §5 the steps. The prompt draft is `pi/prompts/loop-system.v2.md` beside the current one
until step 2 switches the launcher.

## 1. What sits in the context (measured on the dog drive, 2026-11-03 20:00, v4 pro, thinking high)

Session `metis-catalog/.metis/sessions/2026-11-03T19-59-10-994Z_…jsonl`: 26 messages, 88 KB, 9 model
calls, 0.0276 USD.

| what | bytes | where |
|---|---|---|
| three assistant turns that are thinking only (the 2048-token output cap spent before a word or a tool call) | 16 K each, 48 of 88 K | the tail: deepseek's compat replays `reasoning_content` on every later request |
| `surprise_next`: the record + the whole member program + the primer + earlier rulings | 14 K (alfworld's hier member with its family units would be 66 K, cut at 40 K) | the tail when the pack is written |
| `workspace_context` | 4 K | head |
| the system prompt | 8.4 K | head |
| ≈ 60 tool declarations (repl 12, domain 5 + 12 + intents, workspace 6, trace 11, chat 15) | ≈ 25 K | head |
| the other tool results | 0.2–1.3 K each | tail |

pi runs `--no-skills --no-context-files`: the pattern catalog (130 KB), `hierarchy.md` and SKILL.md never
entered pi's context. The dead turns are the 2048 output cap, not the reasoning: with the cap raised the
chain of thought ends in words. Step 1 (opus, d8f87c4, merged) already cut the tail: 25 tools in a
workspace (`METIS_LOOP_TOOLS=workspace|seed|all`), `surprise_next` gives the included units as signatures
(4–7 KB per alfworld member), `rule_text` reads a named rule whole, the primer is gone from the result.

## 2. The ruling

**The system prompt** is the original, enhanced. Its shape stays: one paragraph on what the loop is, the
loop in numbered order, the seeded start, the world without intents, the `catalog_edit` paragraph, the
rules line. What changes: step 5–6 (surprise, revise) become the workspace path (`surprise_next`, the
trace tools, `trace_case`, the pack, `pack_propose`, `catalog_edit` at the person's approval,
`bundle_build`, `/reload`); `catalog_apply` becomes `catalog_new` / `catalog_edit` / `catalog_take`; the
chat's conduct (words at every turn's end, a take in one turn, the intents as one line each) is kept, in
a third of today's space; `workspace_context` first, `journal` on a take and a ruling, `rule_text` to
read a rule before amending it. Target ≤ 7 KB. Nothing domain-specific; no pattern prose: a pattern that
is a tool is named by the tool only.

**pi skills**, native (pi implements the Agent Skills spec: `--skill DIR` loads one even under
`--no-skills`; pi puts each skill's name, description and path in the system prompt and the model reads
`SKILL.md` when the task matches, with the `read` tool). So `pi.sh` adds `--skill` for each directory
under `pi/skills/` and enables pi's built-in `read` only (`--tools read` beside the extensions' tools;
`bash`, `edit`, `write` stay off). The skills' descriptions are the invocation headers: each says what
the skill holds and when to load it (pi's rule: the description routes, 1024 characters at most). A
drive's report says which skills the model loaded and when.

**Reasoning** stays on for DeepSeek: `loop.sh`'s `:off` default (30bf6fa, L1) is reverted; the console's
options checkbox turns thinking OFF instead of on. The output cap moves from 2048 to 8192 in
`agent/models.json` (output at 1.2 USD/M: a full turn ≤ 0.01 USD). A turn that still ends without words
is reported by the chat's empty-turn line as today. The thinking level is pi's default for the model
(not forced high): `METIS_LOOP_THINKING=low|high` sets it for a drive.

**What leaves the loop's material** (the user's first idea): the road's patterns (`8-road.md`), the
plant's (`7-world.md`), the projection patterns written for the chair and the car (`1-projection.md`),
and every pattern whose Loop line is a verb (`lint`, `trace_*`, `family`/`invariant`, the chat's
commands). They stay in the pattern catalog for the Claude Code seat; pi never sees them. Domain words
reach pi only through the workspace README (`workspace_context`) and the members' `%%` lines.

## 3. The skills (`pi/skills/<name>/SKILL.md`, each ≤ 8 KB, examples real and quoted)

| skill | description (the invocation header) | content |
|---|---|---|
| `metis-language` | The metis language: how a rule, a pack and a composition member are written. Load before writing or amending any rule. | §1 of the earlier draft: the rule form, `$` read / bare consume, `*`, `-o`, `()`, `%%` mandatory, stages and layers, `pred`/`type`/`catalog`/`extends`/`include`, `now` command rules, the pack shape (`stage S {}`, `pred`, `drop`, `unit=`); the tick protocol in six lines (hierarchy.md 11–14: want/grant/release, active/done, cancel, world-private); then the rule-writing anti-patterns as counter-examples, each one real rule quoted and the rule that replaced it: the faked class, absent means no, the clock in the rule, twin bodies / weight as priority, the self-clearing hold, a static that merely holds in the record |
| `surprise-ruling` | Ruling a dropped surprise on a trace: blame, case, the smallest pack, the gate's verdict. Load when a surprise is taken, explained or proposed. | the path as multi-shot: three REAL rulings quoted from the alfworld drive's `rulings/<id>.md` and `packs/<id>.llp` (a missing rule; a missing premise; an explain with no pack), each as record → blame rows → pack → verdict card, ≤ 2 KB; then the loop's anti-patterns as counter-examples with what the gate said: the ad hoc rule, the same rule in other words after a refusal, a rule tested by rerunning the agent, 'accepted' with nothing fired, the model's agree taken as the review, the whole reading judged, a rule of another member (Not this package's) |
| `seed-domain` | Making a seed program a catalog domain and exercising it (no workspace bundle). Load when the task names a seed. | the original prompt's steps 1–8 as they were tested, with `catalog_new`/`catalog_edit`/`catalog_take`; the world without intents (`domain_ports`, `domain_episodes`); seed-task.md's README rules |

Not a skill: the chat's conduct (always on, in the system prompt); the tool catalog (the declarations
are the catalog); the trace instruments (their descriptions say what they return).

## 4. The measurement: reasoning on vs off

Two drives of the same three alfworld surprises, the chat's §3 sequence of CHAT.md, cap 0.50 USD each:

| run | model | thinking | output cap |
|---|---|---|---|
| A | openrouter/deepseek/deepseek-v4-pro | on (pi's default level) | 8192 |
| B | the GLM the earlier profiling used (the user names the id; else `z-ai/glm-4.6`) | off | 8192 |

Reported per run: the verdicts (the chat's cards), dead turns (none expected), the skills loaded and
when, characters sent per model call (from pi's session file), the spend. Nothing is switched on the
numbers by the implementer: the user reads them.

## 5. The steps

1. **opus** (DONE, d8f87c4): tool sets, signatures, `rule_text`, the primer out.
2. **opus**: the system prompt from the original (`loop-system.v2.md` is the draft to finish, ≤ 7 KB;
   every tool it names registered in the workspace set); the three skills of §3 with their examples quoted
   from real rulings and real rules (never written from memory; each quote names its file); `pi.sh`
   `--skill` + `--tools read`; `loop.sh` thinking default reverted, console checkbox inverted; models.json
   8192; a test that the prompt's size holds, that every named tool exists, that each SKILL.md parses with
   a description; 0 USD, CI green.
3. **opus**: the two drives of §4 and the report (two caps of 0.50 USD).
4. **nina**: review of 2–3 (the quotes against their sources; the skills' loading seen in the session file).
5. the user drives the chat on the new prompt.
