# policy-tuning — the loop's learning policy tuned against a scorecard (s-1caedae5)

The brain's weights never change; what is tuned is the SEARCH POLICY around it (what it is shown,
its instructions, what it hears when refused). The experimental gate is the reward; a variant's
CARD (`policy/scorecard.py`) is its measure: per world and seed, the loop from the EMPTY domain
through its phases, then the base on the held-out split (flat, and through the director when the
refactor built one). The brain is named on each card (a card is read only against cards of the same
brain); `--budget 0.50` per run, the key's own usage the meter. The user's line: ≈ $3 a week; step 1 under a $1.00 series stop (the
user's, asked directly).

## Step 1 — the card for the fit-repair driver (2026-10-23, metis-loop master 0a6fb32)

**Brain:** `openrouter/deepseek/deepseek-v4-pro`, 0.955 / 1.911 USD per M (prompt / completion).

Variants: `fit` (the fit-repair turn: a fits refusal comes back to the brain once with the gate's
reason in its terms, `measure.explain`) and `fit-skill` (the same + `skills/hierarchy.md` by phase);
ALFWorld (`pick_and_place_simple`) and ScienceWorld (`conductivity`), seeds 1 and 2; discovery 2,
gate games 2, held-out 10.

| variant | world | seed | phase reached | accepted / proposals | calls | usd | rules | usd/rule | held-out flat | end |
|---|---|---|---|---|---|---|---|---|---|---|
| fit | alfworld | 1 | exploit | 6 / 11 | 21 | 0.0385 | 6 | 0.0064 | 0/10 | no_progress |
| fit | alfworld | 2 | exploit | 7 / 11 | 17 | 0.0369 | 15 | 0.0025 | 0/10 | contradiction |
| fit | scienceworld | 1 | exploit | 4 / 12 | 36 | 0.0571 | 4 | 0.0143 | 0/10 | no_progress |
| fit | scienceworld | 2 | explore | 0 / 4 | 14 | 0.0235 | 0 | — | 0/10 | no_progress |
| fit-skill | alfworld | 1 | exploit | 4 / 10 | 15 | 0.0332 | 4 | 0.0083 | 0/10 | no_progress |
| fit-skill | alfworld | 2 | exploit | 5 / 9 | 17 | 0.0383 | 12 | 0.0032 | 0/10 | contradiction |
| fit-skill | scienceworld | 1 | exploit | 5 / 13 | 36 | 0.0726 | 5 | 0.0145 | 0/10 | no_progress |
| fit-skill | scienceworld | 2 | explore | 0 / 3 | 7 | 0.0178 | 0 | — | 0/10 | **killed** (oom at the 6G cap) |

**Spend:** $0.3208 by the key's meter ($0.3179 reported) for the eight runs. Before them, the
regression below cost $0.0287 (seven crashed runs). Step 1 in all: **$0.35**.

**Against the cards before it** (the old driver, no fit-repair; and the scripted-brain reference):

| | explore accepted | reached exploit | held-out |
|---|---|---|---|
| baseline (old driver), ALFWorld | 1/5 | no | 0/10 |
| skill v1 (old driver), ALFWorld | 1/6 | no | 0/10 |
| **fit**, ALFWorld (s1, s2) | 6/7, 6/9 | yes, yes | 0/10, 0/10 |
| **fit-skill**, ALFWorld (s1, s2) | 4/6, 4/6 | yes, yes | 0/10, 0/10 |
| scripted reference (step 2's dry run), ALFWorld | 6/6 | yes: the policy accepted | 10/10 |

### What moved
- **The fit-repair turn works:** 13 of 21 repair turns ended in an accepted rule (`fit` 7/12,
  `fit-skill` 6/9). Explore now builds ALFWorld's action rules from the empty domain (all six
  of them for `fit` s1: go, take_plain/open, put_plain/open, open_closed), where the old driver
  stalled at one. Six of eight runs reached exploit.
- **What is still refused:** in exploit, the policy proposals failed the generalization gain, but for
  one per variant on ALFWorld seed 2 (none on seed 1, none on ScienceWorld) (the likelihood up, or the success up with it not down). No run built a policy
  that wins a held-out game: **0/10 everywhere**, against the scripted reference's 10/10. The runs
  ended by the driver's own rules: no_progress (5), contradiction (2: both ALFWorld seed 2, where
  the policy's rules answered one action two ways).
- **The skill:** no measurable gain at two seeds. On ALFWorld `fit-skill` accepted fewer world rules
  (4 vs 6) and paid more per rule on seed 1 (0.0083 vs 0.0064); on ScienceWorld the two are level.
  Too few seeds to call; the rewrite rounds (step 2) start from this card.

### What each run's brain built (the base's rules at the end)
| run | rules |
|---|---|
| fit alfworld 1 | go, take_plain, put_plain, open_closed, take_open, put_open (the six action rules) |
| fit alfworld 2 | the six, then a policy: choose_target, go_target, open_target, take_from_open, take_from_plain, go_to_dest, open_dest, put_at_dest, put_at_dest_plain (15; ended in a contradiction: two of them answer one action two ways) |
| fit scienceworld 1 | close, wait, look, activate |
| fit scienceworld 2 | — |
| fit-skill alfworld 1 | go, take_plain, put_plain, open_closed |
| fit-skill alfworld 2 | go, take_plain, open_closed, then a policy: choose, go_obj, open_obj, take_open, take_from_shelf, go_to_dest, open_target, put_open, put_plain (12; a contradiction) |
| fit-skill scienceworld 1 | close, wait, look, activate, focus |
| fit-skill scienceworld 2 | — (oom-killed) |

### Refusals, by what the gate and the fit-repair said
- **ALFWorld, explore:** "fires on the record but predicts the wrong facts after" for `take_plain`
  / `take_open` (the brain consumes what the world keeps: the fit-repair names it, and the repair is
  accepted in most runs).
- **ScienceWorld, explore:** compile failures dominate, "var Desk typed both place and thing" (`connect`,
  `move`, `focus`, `deactivate`). The typed vocabulary (metis-worlds 5f8e215: room / place / term /
  thing) makes a variable the brain reuses across two argument kinds a type error. Next is "no event of
  close binds to the record's action close {D: door}": the brain's rule does not reach the door's name.
- **Both, exploit:** "a generalization gain: the likelihood up, or the success up with the likelihood
  not down" (the policy proposals).

### Findings for the user and the architect
1. **The regression (cost $0.0287).** The first seven runs of this card crashed after their first
   refused proposal. The fit-repair's `measure.explain` called `Predictor._dyn`, which nina's
   MiniHack adapter (4c473c6) had renamed to `_cmp`, and the explain test used a fake predictor
   that still had `_dyn`. Fixed in 46f0fa9: explain reads `_cmp`, a candidate that does not compile
   is told the compiler's words, and the test runs on the real `Predictor`. The one result those
   runs still gave: `fit-skill`'s `go` was accepted on both ALFWorld seeds, while `fit`'s `go :`
   (no layer) never compiled. 0a6fb32 now names the layer when the compiler says
   "expected [, got ':'" (both repair turns had read it as "put the variables in brackets").
2. **The 6G cap was hit once** (`fit-skill` ScienceWorld seed 2, at 80 s, the systemd scope's
   OOM kill): the brain's `connect [dyn] : $in(Drawer, Desk) * $here(Room) -o
   connected(Drawer_terminal_1, Desk_terminal_1).` has variables only on its RIGHT side. The
   grounder enumerates every value of their type (167 terms each), for every `in` fact and room.
   The cap held, as the standing rule means. **The guard is the compiler's** (the architect's
   ruling: metisc accepts and draws such a rule today): a diagnostic for a right-side variable its
   left side does not bind (range restriction), in metis-lang and metispy (opus), which the driver
   then hears through `compiles()` as any compile failure, before grounding.
3. **ScienceWorld seed 2 built nothing** in either variant (0 of 7 proposals): the type collisions
   above, then the cap. Seed 1 built four or five world rules (close, wait, look, activate, focus).

### Reproduce
```sh
cd metis-loop/pi    # policy/card.py: the variants interleaved under one series cap (the user's $1.00 stop)
python -m policy.card --variant fit --variant fit-skill=policy/skills/hierarchy.md --worlds alfworld,scienceworld \
    --seeds 1,2 --brain openrouter/deepseek/deepseek-v4-pro --budget 0.50 --series-budget 1.00 \
    --discovery 2 --gate-games 2 --heldout 10
```
The card's `status` for a driver the 6G scope killed is `killed` (scorecard 262bc46); the step-1 run
was scored before that and its card file says `running`.
The runs are under `policy-runs/fit*/` (git-ignored); the crashed ones under
`policy-runs/_aborted/step1-crashed-20261023/`.

## Step 2 — the skill rewritten from the journals
(next: `python -m policy.rewrite --start-card policy-runs/fit-skill/scorecard.json …`, under the
series budget.)

## policy-tuning-2 (s-e075f47f) round 0 — skill v2 re-baselined on the flash brain (2026-10-28, master 96fa090)

**Brain:** `openrouter/deepseek/deepseek-v4.1-flash-1017` (reasoning off, 2048 out, data_collection deny),
0.30 / 1.20 USD per M list (Amendment 3). This card, not step 1's, is the reference for rounds 1–3.

Variant `r0-flash` = `fit-skill` with skill v2 (`skills/hierarchy.md`, 56a8db5); the step-1 worlds, seeds,
discovery 2, gate games 2, held-out 10. Master 96fa090 holds 2a + 2a-ii; the old columns are unchanged.

| variant | world | seed | phase reached | accepted / proposals | calls | usd | rules | usd/rule | held-out flat | end |
|---|---|---|---|---|---|---|---|---|---|---|
| r0-flash | alfworld | 1 | exploit | 4 / 11 | 22 | 0.0042 | 4 | 0.0010 | 0/10 | disengaged (no_progress) |
| r0-flash | alfworld | 2 | explore | 3 / 10 | 16 | 0.0019 | 3 | 0.0006 | 0/10 | disengaged (no_progress) |
| r0-flash | scienceworld | 1 | exploit | 3 / 13 | 38 | 0.0046 | 3 | 0.0015 | 0/10 | disengaged (no_progress) |
| r0-flash | scienceworld | 2 | explore | 2 / 9 | 28 | 0.0029 | 2 | 0.0014 | 0/10 | disengaged (no_progress) |

**Spend:** $0.0136 billed for the four runs (cost.jsonl; the series guard's meter agrees). At list prices
the same tokens (246k prompt, 13k completion) would be $0.090: the providers OpenRouter routed to (mostly
Wafer) billed about a sixth of list. Step 1's `fit-skill` on v4-pro: $0.1619.

- **Built:** ALFWorld go, take_plain, put_plain (s1 only), open_closed; ScienceWorld close_door (s1), wait,
  look. v4-pro's `fit-skill` built 4 / 12 / 5 / 0 rules; flash builds 4 / 3 / 3 / 2. Flash is level on
  seed 1, behind on ALFWorld seed 2 (stalled in explore), and builds something on ScienceWorld seed 2,
  where v4-pro built nothing.
- **Refused:** explore mostly on "the candidate fires on its record and on no record it contradicts" (21 of
  25 explore refusals); ALFWorld s2 four times on "the held-out likelihood not down". Exploit: all six
  policy proposals refused on the generalization gain.
- **The refactor move:** not reached. No run passed exploit (as on v4-pro), so the flash model neither held,
  refused nor wrote a composition. Held-out 0/10 everywhere, as before. Structural columns: "not split";
  level ports 0 / 0.
- `end` is the card's status with the driver's reason; step 1's `end` column shows the reason alone
  (those runs disengaged too).

```sh
cd metis-loop/pi    # the key: run.sh's environment / ~/.config/metis/openrouter.env
python -m policy.card --variant r0-flash=policy/skills/hierarchy.md --worlds alfworld,scienceworld --seeds 1,2 \
    --brain openrouter/deepseek/deepseek-v4.1-flash-1017 --budget 0.50 --series-budget 1.00 \
    --discovery 2 --gate-games 2 --heldout 10
```

### Rounds 1–3 (2026-10-28, master 356f48b), the same brain

`python -m policy.rewrite --skill policy/skills/hierarchy.md --rounds 3 --start-card policy-runs/r0-flash/scorecard.json`
with the same worlds, seeds and caps.

| round | rules (alf s1, s2, sw s1, s2) | held-out | usd (runs) | usd/rule | kept |
|---|---|---|---|---|---|
| 0 | 4, 3, 3, 2 | 0/10 ×4 | 0.0136 | 0.0011 | — |
| 1 | 4, 3, 0, 2 | 0/10 ×4 | 0.0079 | 0.0009 | kept (usd/rule) |
| 2 | 4, 3, 5, 2 | 0/10 ×4 | 0.0123 | 0.0009 | not kept (tie) |
| 3 | 4, 3, 3, 2 | 0/10 ×4 | 0.0124 | 0.0010 | not kept |

**Spend:** $0.0367 for the series (three rewrite calls: $0.0040).
- The rewrites added the round-0 lessons: over-fit statics, unbound variables, the world's types, the
  fit-repair as the spec, and token rules that fire. The cards did not move: exploit refusals on the gain
  went 6 → 6 / 8 / 7, compile type confusions 7 → 5 / 9 / 8, and no policy compiled.
- Round 1 was kept on usd/rule while it built fewer rules. With held-out 0 everywhere, the tiebreak
  rewards a cheap empty run.
- Round 3's rewrite was cut at 2048 tokens: a stray fence, and the last point truncated.
- The refactor-from-scripted row (handover at refactor from the hand-script's alfworld s1, $0.00099): flash's
  conventions answer was refused (the replay diverged; it rewrote the action layer), so compose was not
  reached (s-e075f47f steps/step2b-refactor-row.md).

## policy-tuning-2: back to v4-pro (the user, 2026-10-28; Amendment 4)

The flash cards above stay as flash's. The user's decision on them: flash cannot replace v4-pro (about on
par with the local Gemma 4). **`openrouter/deepseek/deepseek-v4-pro` is the only paid brain**, and the policy
is retuned on it.

**The v4-pro baseline is skill v2's round 0 on v4-pro** (`pi/policy-runs/pro/`, `rw0`), not step 1's
`fit-skill` card. That card (rules 4 / 12 / 5 / 0, $0.1619) was scored on 2026-10-23 with **skill v1**
(b7843d6's text); skill v2 (56a8db5) came on 10-26. Rounds from it would judge v2 against v1's card, and
rewrite.py's check would not catch it: it compares the card's skill *path*, and that file now holds v2. So
rewrite.py runs without `--start-card` and scores v2 itself (`--series-budget 1.50`, `--max-tokens 4096`).

### v4-pro: skill v2 round 0 + rounds 1–3 (2026-10-28, master de60c4d)

`python -m policy.rewrite --skill policy/skills/hierarchy.md --rounds 3 --brain openrouter/deepseek/deepseek-v4-pro
--budget 0.50 --series-budget 1.50 --max-tokens 4096 --runs policy-runs/pro` (no --start-card: rw0 is v2's card).

| round | rules (alf s1, s2, sw s1; sw s2) | held-out alf s1 / s2 | usd | kept |
|---|---|---|---|---|
| 0 (v2) | 4, 5, 6; unmeasured (6G) | 0/10, 0/10 | 0.2191 | baseline |
| 1 | 5, 3, 4; unmeasured (6G) | 0/10, 0/10 | 0.2115 | no: fewer rules |
| 2 | 6, 4, 4; unmeasured (6G) | **1/10, 1/10** | 0.2603 | **kept** (variance caveat) |
| 3 | 5, 19, 1; unmeasured (6G) | 0/10, 0/10 | 0.2129 | no |

**Spend:** $0.9424 (rewrite calls $0.0335).
- These are the first held-out wins (rw2). r1 and r2 carry the same three new points, so the difference
  may be variance at two seeds.
- ScienceWorld held-out was 0/10 throughout. **sw s2 is unmeasured (6G)**: it was OOM-killed at the cap in
  every round, after 1 rule in explore. The cap stays at 6G (the standing rule), and the cause is being found.
- No run reached refactor.

### The refactor rows on v4-pro (handover at refactor from the hand-script's alfworld s1)

| row | ask | conventions | replay | success / likelihood | direct, compose | held-out (flat / director) | usd |
|---|---|---|---|---|---|---|---|
| refactor-from-scripted-pro | fixed (gate named) | refused | diverged | −1 / +0 | not reached | 10/10 / — | 0.0111 |
| refactor-from-scripted-pro-example | + worked example | refused | diverged | −0.5 / +0 | not reached | 10/10 / — | 0.0162 |
| **refactor-from-scripted-pro-example2** | example + agreeing ask (15d4d25) | **accepted** | identical | +0 / +0 | **accepted; `metisc --interface` 0 errors, composition full marks** | **8/10 / 10/10** | 0.0101 |

- v4-pro holds the refactor move once the ask shows the shape. Flash did not, on two asks.
- The conventions rewrite costs the flat program 2 held-out wins, which the director recovers; the gate's 2
  games do not see the flat drop.

### The level row (alfworld_view, v4-pro, kept skill r2, seeds 1–2)

No level was declared (0 / 0). Held-out 1/10 (s1), 0/10 (s2); $0.1252. On this driver a level can be
declared only in refactor: the level point sits under the skill's `## refactor`, shown by phase, and no
run reached it. The exploit prompt shows no belief. A design call before this row means anything.

## policy-tuning-2 step 2b — closing (2026-10-28)

**Brain:** `deepseek/deepseek-v4-pro` (the user: flash is not a substitute). **Spend for 2b: $1.1573**: flash
$0.0523 (round 0, rounds 1–3, two refactor rows); v4-pro $1.1050 (v2 round 0 + rounds 1–3 $0.9424; three
refactor rows $0.0374; the level row $0.1252). No run or call was cut by a cap. The user's standing cap is $7.

**What 2b established:**
1. **The refactor move holds on v4-pro** (example2): conventions accepted, then direct and compose by the
   driver, with the interface clean and the director 10/10 held-out. This is the first composition a paid
   brain produced in policy-tuning. The ask, not the brain size alone, was the blocker: both brains rewrote
   the action layer until the ask showed the move's shape.
2. **The rewrite rounds give the first held-out wins** (v4-pro round 2: ALFWorld 1/10 on each seed). The
   kept skill is `policy-runs/pro/rewrite/skills/r2.md`. With r1 and r2 near-identical and at 2 seeds,
   variance is not excluded.
3. **From the empty domain, no paid run reaches refactor.** Exploit refuses the brains' policies (wrong
   guards, unbound variables, type confusion). The skill's lessons did not move these at 2 seeds. So the
   structural columns and the level ports stay unmeasured from scratch; the handover rows measure them.
4. **Flash** (`deepseek-v4.1-flash-1017`) is about 12× cheaper per card and about on par with the local
   Gemma 4 (the user). It built rules at seed 1, never held the refactor move, and its rewrites moved nothing.

**Open items for step 3 (opus's structural judgement) and the architect:**
- scienceworld s2 is unmeasured (6G) on every v4-pro card: the cap stays, and metis finds the growing process.
- The level point is reachable only in refactor; the exploit prompt shows no belief (the level row).
- The flat held-out drop after conventions (10 → 8) is invisible to the 2-game gate.
- Harness fixes already in or pending: the tiebreak guard and the rewrite `--max-tokens` (in, de60c4d); the
  scorecard's bare `metisc` in composition_card (pending, metis); a no-source handover as a row state (in).
- More seeds before round 2's wins are read as the skill's.
