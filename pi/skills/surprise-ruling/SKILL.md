---
name: surprise-ruling
description: Ruling a surprise dropped on a trace - blame first, the case, the smallest pack, pack_propose and its verdict card - shown on real rulings (a missing rule accepted, a missing premise refused by a golden, an explain with no pack), and the loop's anti-patterns with what the gate said. Load when a surprise is taken, explained or proposed, or a refusal is read.
---

# Ruling a surprise

The path: `surprise_next` → `trace_blame` on each differing atom at k, `trace_fired` on the window → name the cause → `trace_case` → the smallest pack (skill `metis-language`) → `pack_propose` → say the verdict in the card's fields. The rows below are quoted from the real rulings in `rulings/` beside this file (their `ruling.md` and `pack.llp`; `rulings/README.md` says how each was judged). The domains are only the setting: the lesson is the ruling's shape.

## 1. A missing rule: accepted (`rulings/road-brake-late/`)

The planner kept the limit where the zone ahead came too late to stop for. The pack adds the command rule the program lacked, in the stage that pre-empts progress:

    stage safety {
      %% The zone ahead comes too late to stop for at my pace: I ease off, {R}.
      brake_late [dyn] : $busy * $tick__grant(planner, controls) * $late(nextzone) * $soft(R) * now -o ().
    }

The card, from the ruling:
- Programs moved: planner, ei_key holds.
- First enabled: tick 141, brake_late[R=brake_min_correct], beside nothing.
- First fired difference: tick 141, planner: the record ['decide', 'keep_limit', 'back'], the candidate ['brake_late[R=brake_min_correct]'].
- 49 cases (…), none broken, on seeds 1 to 3.
- Open-loop: every tick of the trace to its first differing output (tick 141), and past it only as a world that obeyed the old command.

Say: accepted; first enabled 141; it replaces keep_limit there; no golden moved; open-loop past 141.

## 2. A missing premise, guessed: refused (`rulings/kitchen-missing-premise/`)

A cook fetches an onion with nothing said about its own state. The pack replaces the rule with one more premise:

    drop fetch_onion.
    stage act {
      %% I take an onion for my order, while I wait for nothing.
      fetch_onion [dyn] : $order * hand_free * $pot_space * $self(S) * $calm(S) -o held_onion.
    }

The gate:
- the edit is not confined to cook_a: the programs of cook_a, cook_b moved
- golden whole_order.yaml of cook_a (…; seed 1): out [], expected ['tick__active(cook_a)', 'tick__done(cook_a)', 'tick__released(cook_a,pot,g0)', 'tick__want(cook_a,pot)']; status running, expected success
- First difference per member: cook_a at 0, cook_b at 0, pot_director at 3.

Read it: the unit is the cooks' shared one, so cook_b moves with it (amend the member's own unit, or say the surprise is the family's). The golden says the order never completes: `ask_pot` consumes `calm(S)` after the first onion (`rule_text ask_pot`), so the premise blocks the second. The premise was guessed, not read from the trace. One repair, from the blame rows and the rules that move the atom; then the ruling stands.

## 3. Explain at k, no pack (`rulings/kitchen-explain/blame-k4.txt`)

The person asks why cook_a's hands are not free at 4:

    verdict: this package's
    whose                            atom       want  have  last_k  last_by  last_what
    the member's rule                hand_free  1     0     4       rule     fetch_onion
    nobody's: it holds as it should  held_soup  0     0     4       rule     serve[S=cook_a]
    the member's rule                pot_onion  1     0     4       rule     start[S=cook_a]

Three lines from these rows, no pack: at 4 the program served (`serve[S=cook_a]` freed the hands) and `fetch_onion` took them again in the same tick; the world moved none of these atoms; the premise `fetch_onion` lacks is whatever should keep a cook that just served from fetching for the next order. "this package's": the member's own rules moved them.

## What the loop must not do (and what the gate said)

- **The ad hoc rule** (`rulings/road-golden/`): `go_on [dyn] : go -o went_on.` The gate: "6 of 12 cases refused", e.g. "golden drive.yaml of planner (…): fired ['decide', 'go_on', 'back'], expected ['decide', 'accel', 'back']". A rule that reads only the atom that changed fires everywhere.
- **The same rule in other words after a refusal** (`rulings/road-duplicate/`): "the pack's yield_again repeats yield_zone in planner_domain.llp: the same premises and effects". A second draft changes a premise the refusal named, never the name.
- **Accepted with nothing fired** (`rulings/road-accepted-inert/`): "Ruling: accepted … Open-loop: no candidate rule was enabled on this trace: it says nothing of the rule's effect." Say so: the goldens held, and this trace shows nothing of the rule; the card's first enabled is empty. The card now also says whether the pack changes what fires at the surprise's tick (TARGET, under "What this record identifies"): `not identified` means it does not answer this surprise, and the judge refuses it as a try ("it does not change the surprise's tick: the rule that fired there still fires": amend THAT rule); a restriction that stops the wrong firing there is `identified` even when its rule is never enabled.
- **A token the record never held.** "A rule needing a new `#init` token is never enabled, because the replay starts from the record's session" (alf-bundle step 3, on a recorded alfworld bundle run). A premise no take, beat or rule of the record ever made gives an inert ruling whatever the rule says: read the premise from the trace (`trace_blame`), and look for a firing with `trace_fired`; never add the token with the pack's `#init`.
- **Enabled only beside another rule.** "The first trivial pack, which read `$take(O)`, was only enabled beside `take_plain`: 0 rows" (the same run). Enabled is not fired: read the card's first enabled and what it stands *beside* before you call the rule judged; a rule that is only ever a second choice says nothing of its effect.
- **A rule tested by running the world again.** The trace is the evidence; `trace_replay` and `pack_propose` replay it. A rerun is another record, and its difference is the world's, not the rule's.
- **The model's agree taken as the review.** The verdict is the gate's; the ruling's "The model's words" are a comment for the person, who reviews. Never say a pack is right because the comment agrees.
- **The whole reading judged.** Name the atoms that differ at k and blame those; a pack that rewrites what the member reads to explain one tick moves every golden.
- **A rule of another member.** When the blame row's verdict names another member, a take or the world ("Not this package's"), the pack is not this member's: say whose surprise it is and stop. A shared unit moves every member that includes it (§2's "not confined to cook_a").
