# The language in front of the model: deterministic retrieval for the pi loop (design, 2026-11-05)

**Status: DESIGN (the architect; the user: "go all in", 2026-11-05). For gpt-oss:20b on pascal's card first, qwen3:4b as the floor, DeepSeek v4 pro as the reference. 0 USD throughout: no embedding model, no fine-tune, no copied rule files; the examples come from the bundle in the workspace and the catalog it pins; the judge decides as before (the goldens rule). Spec 20 (metis-lang spec/20) decides WHICH help a record gets: the retrieval below serves the STRUCTURAL kind; an ontological record gets §4's other message.**

## 0. The evidence this answers

| run | model | what happened | the lack |
|---|---|---|---|
| qwen-loop-2 (opus, 2026-11-04) | qwen3:4b | 11 real tool calls after the developer-role fix; the pack refused at the link; `take_open [dyn] %% … requires handsfree.` English where the grammar wants atoms | the FORM of a rule |
| gpt-oss step 1 (pascal, 2026-11-05), medium | gpt-oss:20b | 17 calls in ~80 s, take → blame → fired → case → propose; the pack linked first try, accepted (inert: no case, F1) | nothing of the language; the plumbing (F1–F4) |
| the same, high | gpt-oss:20b | 28 calls, 3× the tokens, refused at the link: a `unit=` line inside the pack | the pack's envelope |
| the same, skills none | gpt-oss:20b | no stage block, a parse error, then 8 `catalog_edit` attempts, all refused | the shape of a pack, and a refusal that teaches nothing |

Not the domain: the form. A 20B model that is told the shape writes the language; a 4B model does not whatever it is told (the smoke tier). The narrator RAG result (metis-rag, E7/E8) holds here too: flat lexical retrieval over the names did the work and embeddings added nothing. So the design is deterministic retrieval at the two moments the model writes the language, and one refusal that reads as a correction.

## 1. Order of work: the plumbing first

No model finishes a surprise today, whatever it knows, because of four defects pascal's step 1 found. They land before any retrieval is measured:

| finding | defect | owner |
|---|---|---|
| F1 | `trace_case` on a REPL trace never beats (loop-chat F2: `case()` ignores step items): no case, no golden, every acceptance "inert" | opus (loop-chat s-f6c32d0c) |
| F2 | `pack_propose brain=none` is passed to the judge as `--brain none` and fails | pascal |
| F3 | a REFUSED ruling blocks the model's corrected second pack ("ruled already"); RULED: the refusal stays in rulings/ as history, the surprise goes back to `taken`, the second try is the brief's | pascal |
| F4 | the model reads `skills/X/SKILL.md` relative to the workspace (ENOENT): no skill body was ever read | pascal |
| F7 | `dot_model` null in the console start reply | pascal |

Measurement rule: the before number (§5) is taken on gpt-oss at medium with F1–F4 fixed and no retrieval; then the retrieval lands and the same drive runs again.

## 2. Layer 1: the right rules at propose time

**Where.** `surprise_next` (metis-workspace.ts). It already returns the record, the member's program, each included unit as its SIGNATURE (declarations, rule names with their `%%` lines) and the rulings of earlier surprises on the same member; `rule_text` gives one rule whole on request. The model gets names, not rules, and does not ask.

**Change.** `surprise_next` adds a section `examples:` with WHOLE RULES, verbatim from the member's units, chosen deterministically:

1. the surprise's atoms: the record's `atoms` when it has them, else the predicates `trace_blame` names on the record's window (the rules that last moved each atom and the atoms they read);
2. every rule of the member's units whose body or head mentions one of those predicates, scored by how many it mentions, the top 3 to 8 rules, whole, with their `%%` line and the stage they sit in;
3. one rule of the SAME SHAPE the pack will need when the record's reading names a command (a `[dyn]` rule of the same stage reading `$tick__grant`), so the envelope is in view;
4. one line of grammar, fixed text, under 40 words: a pack is `stage S { rules }`, `pred` lines, `drop NAME`; a rule is `name [dyn] : premises -o effects.`; `$` reads, `%%` is the person's line, no prose outside `%%`.

The section is capped at about 2 KB. Lexical, no model, no embeddings: the predicates are tokens of the atoms. This is the layer that fixes "wrote English", "no stage block" and the `unit=` line: the model sees five real rules in exactly the predicates it must use and copies their shape.

**What it does not do.** It does not pick the rule to change (the model does, from blame), and it never retrieves from another member's unit or from the catalog outside the bundle's pins: the examples are the law the pack will join.

## 3. Layer 2: the refusal that corrects

**Where.** `pack_propose`'s refusal (propose.sh's output: the link's error, the lint rows, the gate's findings), returned to the model as the tool result.

**Change.** Three refusal classes, each answered with the thing that fixes it:

| refusal | today | with layer 2 |
|---|---|---|
| the LINK refuses a token at a position (a parse error, a stray line, an undeclared name) | the error line | the error line, then the spec paragraph that governs the construct (spec 00 §2 grammar or §3 inference, mapped from the error's token class by a fixed table in the loop), then the nearest well-formed rule from the same unit (layer 1's scoring on the refused text's predicates) |
| a LINT row refuses (L1–L12) | the row | the row, then its paragraph from the pattern catalogue (skills/metis-loop/patterns/CHECKS.md, the same text the judge already quotes for the ruling) |
| the GATE refuses (a golden moved, a case failed) | the fired diff | the fired diff, then the golden's case text (the `#init`/`expect` lines) so the model sees what it broke |

The second try is then an EDIT of a rule it can see, which small models do well, instead of a new guess. Spec 20 §10.5 governs one case that is NOT a correction: an unknown atom at the link on a record whose kind is ontological. That refusal says "the vocabulary has no atom for X; propose the predicate and its host contract", and no nearest rule is attached, because the nearest rule would invite a pack around a hole.

## 4. Layer 3: skills as sections

**Where.** pi.sh's `--skill` directories (skills/metis-loop/SKILL.md, 5 headings; patterns/1–8 and CHECKS.md). The listing costs 477 tokens on the first call; no model has read a body (F4).

**Change, after F4.** A `skill_section` tool that returns ONE section by heading or by pattern number, and the SKILL.md listing names the sections. The model asks for "the cycle" or "pattern 2 rules" and gets about 1 KB instead of 7. On a 16 GB card with 32k of context the saving is attention more than tokens, which is why this layer is last: a model that has layers 1 and 2 needs the skills only for the cycle's order.

## 5. Measurement

The step 3 drive of gpt-oss s-0f23f8cd (`files/s5_drive.py`, the two-surprise drive with the DeepSeek v4 pro columns: calls, dead turns, path followed, packs proposed, linked, accepted, goldens, wall time, spend), four runs on pascal's card, medium reasoning only:

| run | model | retrieval |
|---|---|---|
| before | gpt-oss:20b | none (F1–F4 fixed) |
| after | gpt-oss:20b | layers 1 + 2 |
| floor before | qwen3:4b | none |
| floor after | qwen3:4b | layers 1 + 2 |

The reading, five lines: does it write the language first try; how many refusals until a linked pack; does the second try edit or guess; where it stops; against the baseline (A: 0.46–0.49 USD per drive, 66 calls; B glm 0.28; flash failed the ruling path). Layer 3 is measured alone afterwards, by tokens and calls, since its effect is cost, not success.

## 6. Who does what

- the architect: this note; the spec-paragraph table for layer 2 (the token classes of the link's errors mapped to spec 00 sections; about 15 rows); the grammar line of layer 1.
- pascal: F2, F3, F4, F7; then layers 1 and 2 (metis-workspace.ts and the loop's propose path; a test per layer with a recorded refusal); then the four drives of §5; layer 3 last. Subject gpt-oss s-0f23f8cd, step 3.
- opus: F1 (loop-chat s-f6c32d0c), since the case verb is the chat's.
- the architect merges each branch with CI green; the gpt-oss subject's gate stays open until the after numbers are in.

## 7. What stays as it is

No fine-tune. No copied rule files into the loop. No retrieval across members or outside the bundle's pins. The judge decides; the goldens rule; a person's gate on apply. If lexical retrieval falls short on the after numbers, the parked retriever in metis-agent's rack module is the next step, not a new design.
