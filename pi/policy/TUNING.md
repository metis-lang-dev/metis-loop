# policy-tuning — the loop's learning policy tuned against a scorecard (s-1caedae5)

The brain's weights never change; what is tuned is the SEARCH POLICY around it (what it is shown,
its instructions, what it hears when refused). The experimental gate is the reward; a variant's
CARD (`policy/scorecard.py`) is its measure: per world and seed, the loop from the EMPTY domain
through its phases, then the base on the held-out split (flat, and through the director when the
refactor built one). Brain: `openrouter/deepseek/deepseek-v4-pro`, `--budget 0.50` per run, the
key's own usage the meter. The user's line: ≈ $3 a week; step 1 under a $1.00 series stop (the
user's, asked directly).

## Step 1 — the card for the fit-repair driver (2026-10-23, metis-loop master 0a6fb32)

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
| fit-skill | scienceworld | 2 | explore | 0 / 3 | 7 | 0.0178 | 0 | — | 0/10 | **oom-killed at 6G** |

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
- **What is still refused:** in exploit, every policy proposal but one per ALFWorld seed failed the
  generalization gain (the likelihood up, or the success up with it not down). No run built a policy
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
cd metis-loop/pi    # the user's $1.00 stop is the series runner's, around policy.scorecard.score_one
python -m policy.scorecard --variant fit --worlds alfworld,scienceworld --seeds 1,2 \
    --brain openrouter/deepseek/deepseek-v4-pro --budget 0.50 --discovery 2 --gate-games 2 --heldout 10
python -m policy.scorecard --variant fit-skill --skill policy/skills/hierarchy.md …   # the same
```
The runs are under `policy-runs/fit*/` (git-ignored); the crashed ones under
`policy-runs/_aborted/step1-crashed-20261023/`.

## Step 2 — the skill rewritten from the journals
(next: `python -m policy.rewrite --start-card policy-runs/fit-skill/scorecard.json …`, under the
series budget.)
