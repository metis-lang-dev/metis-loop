# RDDL Tamarisk — step 2 + 2a results: the surprise loop and the notch (2026-10-11)

This is subject rddl-tier1 (s-8f820524), Tamarisk, after the user's
step-1 checkpoint ("Tamarisk go step 2"). The user then said "Tamarisk
done, you can commit it in catalog". The world is committed as
**metis-catalog 83f5aab** (`domains/rddl/tamarisk.llp`), next to Wildfire
(887aabf). The metis-loop experiment files are not committed.

## Headline: held-out per-step score

| world (served) | log-loss / step¹ | excess over floor | some run matches the whole step |
|---|---|---|---|
| iter0: born catalog (step 1) | 10.874 | 8.226 | 0.19 |
| iter1: the loop's world, ports prior-flat 0.5 | 6.395 | 3.747 | 0.43 |
| **iter1 + notch table fitted from episodes** | **2.717** | **0.069** | **0.89** |
| *the true generator (the RDDL cpfs) = the floor* | *2.648* | *0* | — |

¹ 10 fresh episodes (instance 1, random agent, seed 101, 400 steps),
never mined or fitted. Per step: −Σ log P_model(observed value) over
the 16 observed fluents. Each model marginal comes from 200
reference-sampler runs at the settle readout, with add-½ smoothing.
The floor is the cpfs' exact marginals (`score_episodes.py`).

**Why not Wildfire's surprise count:** at 16 independent fluents per
step, the TRUE generator's joint likelihood is ~1e-3..1e-5. The 0.05
"rare" threshold therefore flags the generator itself 15–18 times per
episode (`true_likelihood.py`: held-out 17.8, iter0 15.0, train 14.6
per episode). A sampled joint below 1/samples also reads as 0. The
per-fluent log-loss is what sampling resolves, and it has an exact
floor. (Wildfire finding 5, sharpened: the count metric breaks down
as the observation widens.)

**The notched world sits 0.069 nats/step above the floor**, one loop
iteration after birth.

## Step 2a acceptance: the notch table

The fit is the per-slot episode notch (`notch_slots.py`; see the tools
section), ML (α=0), over 2400 recorded transitions (iter0 + 50
training episodes, seed 1001). All 19200 of 19200 slot-observations
were explained by a sampled run (0 missed). Stochastic EM, 8 rounds,
each round priced by the previous round's table
(`notch/iter1-em.log`, `notch/iter1-overlay-r*.json`).

| port (the seat's name) | RDDL non-fluent (truth) | truth | notched | 95% CI | n | truth in CI |
|---|---|---|---|---|---|---|
| perad | ERADICATION-RATE | 0.9 | 0.894 | [0.867, 0.916] | 614 | yes |
| prest | RESTORATION-RATE | 0.9 | 0.918 | [0.869, 0.950] | 183 | yes |
| pdown | DOWNSTREAM-SPREAD-RATE | 0.6 | 0.602 | [0.572, 0.631] | 1068 | yes |
| psib | DOWNSTREAM-SPREAD-RATE (within reach)² | 0.6 | 0.576 | [0.531, 0.620] | 465 | yes |
| pup | UPSTREAM-SPREAD-RATE | 0.15 | 0.098 | [0.080, 0.119] | 889 | **no** |
| ptdie | DEATH-RATE-TAMARISK | 0.05 | 0.046 | [0.042, 0.050] | 10148 | edge (0.0500) |
| pndie | DEATH-RATE-NATIVE | 0.05 | 0.049 | [0.044, 0.056] | 4955 | yes |
| ptborn | EXOGENOUS-PROD-RATE-TAMARISK | 0.1 | 0.134 | [0.122, 0.148] | 2662 | **no** (still falling) |
| pnborn | EXOGENOUS-PROD-RATE-NATIVE | 0.1 | 0.094 | [0.084, 0.106] | 2669 | yes |
| ptcomp | COMPETITION-WIN-RATE-TAMARISK | 0.8 | 0.787 | [0.738, 0.829] | 305 | yes |
| pncomp | COMPETITION-WIN-RATE-NATIVE | 0.2 | 0.200 | [0.159, 0.248] | 305 | yes |

² The cpfs comment says "UPSTREAM rate for spread within a reach", but
the code uses DOWNSTREAM-SPREAD-RATE. The mined text gave within-reach
its own rate, and the notch recovered it ≈ pdown: a structure the loop
discovered rather than one it was told.

- **8 of 11 contain the truth** (ptdie at the edge).
- **The 7 identifiable rates are converged from round 0–1.** These are
  eradication, restoration, both deaths, native arrival and both
  competition rates: their draws are pinned by the observation.
- **The 4 tamarisk-arrival rates share credit.** For an empty slot that
  gains tamarisk with several live sources, the observation does not
  say which draw seeded it. That is the noisy-or ambiguity the step-1
  audit predicted ("a per-source port fits exactly only if each source
  is its own draw"). EM moves the credit round by round: ptborn went
  0.307 → 0.262 → 0.231 → … → 0.134 and is still falling; pdown went
  0.409 → 0.602 and psib 0.346 → 0.576. pup stays low (0.137 → 0.098),
  the one rate the trajectory moves away from. Single-sample stochastic
  EM is slow on exactly this coupling. More rounds, or several imputed
  samples per transition, are the next lever; not run.
- The residual misfit costs little: 0.069 nats/step over the floor on
  held-out data.

### Structure check: per-reach rows equal

The seat chose global ports (no reach argument), unlike the born
catalog's `pdown(R)`. To check the structure anyway, one notch round
priced by the final table was re-run with every row split by the rule's
reach binding (`--split R`, `notch/split-by-reach.json`). Of **36
per-reach rows, 2 fall outside their own 95% CI of the global value**
(perad r4 0.818; psib r2 0.452), about the 1.8 expected by chance. The
rates show no reach dependence, as in the cpfs.

## The loop (`step2-iter1-transcript.md`)

Terminal `metis --plugin tamarisk_plugin:make tamarisk_born.llp` in tmux
`tamarisk`, with the claude -p seat (`seat-claude.sh`, claude-opus-5-5)
and the step-1 card (= card v2) as the formalize system prompt.

**iter0** (`sink sinks/iter0--born--frame-neg-tick.jsonl`, sampled
tier): 289 of 400 steps unmodeled. The born vocabulary
(`empty`/`cost`/`penalty`, 3 illustrative reaches) never produces the
observed `tamarisk_at(S)`/`native_at(S)` over sRsK slots.
- `record 1`, then `replay`.
- `why tamarisk_at(s3s2)` → "was never produced and is not in the base
  state".
- `query tamarisk_at(s3s2) @frame` → "P = 0, tier exact (priced world)".

**mine** (`step2-iter1-mined-text.txt`): the interface; the instance as
data (slot→reach, r1→r2→r3→r4); five qualitative laws (competition,
tamarisk alone, native alone, empty→tamarisk with each source a
separate chance, empty→native). **No counts**: every rate is "a rate,
DATA, one law priced by a weight port" (memory: mined-text-no-counts).
The laws were read off an iter0 contingency table (state × action ×
source counts); the table stayed out of the text.

**formalize: green in 1 round** (revise, base edit, no findings; a
warning listed the 9 new unbound ports). The world:
- lockstep `snap → rouse → act → fate → write`;
- a start-of-step snapshot (`old_t`/`old_n`…) so nothing seeds within
  the step;
- per-reach `erad`/`noerad`, `rest`/`norest` flags from the action;
- one fate rule per law, each a complement pair on a global port;
- tamarisk arrival as `t_born` then a WALKED scan over a `pos` chain of
  slots (`seed_sib`/`seed_down`/`seed_up` per live source, `pass_bare`/
  `pass_far` otherwise, `seed_none` at the end). That is a declarative
  noisy-or: each source is its own draw and the first success seeds.

There was no per-value unrolling and no literal weight. `plugin
tamarisk_plugin:make` (re-read, ports added), then `accept`, then
`export iter1-world`. One iteration sufficed. With the notch the world
is at the floor (above), so no iter2 was mined.

## Findings

1. **The rate-as-data doctrine held at birth+1.** With counts kept out
   of the mined text and the card's port section, the seat produced 11
   one-law ports and a walked noisy-or in 1 round. Compare Wildfire
   iter1, which unrolled per count from counted text.
2. **Joint-match rejection does not scale to wide observations**
   (notch, measure). notch_episodes' whole-step rejection is hopeless at
   ~1e-4 joint likelihood. The fix used here is a per-unit factorisation:
   conditioning on each slot's own atoms and attributing the events
   bound to that slot. It is exact when units are conditionally
   independent given the start state, as here. This is worth lifting
   into metispy's notch with a declared unit variable.
3. **Single-imputation stochastic EM is slow on shared-credit ports**
   (the noisy-or coupling: ptborn/pup). Recommendation: several imputed
   samples per transition, or an exact per-slot E-step (the slot's
   branch tree is small), before calling a rate fitted.
4. **The domain's eradication guard is dead code.** `~(forall_{?s2}
   [SLOT-AT-REACH(?s2,?r) ^ tamarisk-at(?s2)])` quantifies over every
   slot of the instance, so it is never false, and eradication is never
   blocked on a fully invaded reach. The episodes agree (eradicate on a
   full reach cleared 64 of 78 slots). `true_likelihood.py` follows the
   cpfs as written; my first floor modelled the intended guard and was
   wrong.
5. **A `%%` before a `weight` declaration attaches to the next rule**
   (Wildfire assembly). Docs attach to rules only, so the header's
   logistic rides on `catch`, the rule its port prices.
6. The exact filter again exceeded its budget on the catalog scene
   (500k states at step 30/200). This is the same lockstep-scan blowup
   as Wildfire finding 2: a warning, not a finding.
7. **Step-1 fidelity gaps.** 1–6 were all resolved by the loop:
   interventions became actions with stochastic success, deaths and
   exogenous production were added, competition became coexistence,
   and spread became a noisy-or with a within-reach rate. Gap 7
   (reward-as-state) is gone: the observed world has no reward atoms.
   Gap 8 (topology) came in as instance data.

## Tools (metis-loop experiments/tamarisk, not committed; metispy untouched)

- `true_likelihood.py`: the floor (cpfs evaluated directly, guard
  as written).
- `score_episodes.py`: per-fluent log-loss vs the floor, joint-hit
  fraction.
- `notch_slots.py`: per-unit episode notch, stochastic EM rounds,
  `--overlay` start, `--split VAR` structure check, `--jobs` (default 4;
  run under `nice`).
- `notch_episodes.py`: Wildfire's, copied (default plugin switched).
  Unused here: finding 2.

## Artifacts

- `transitions/`: iter0 (seed 1, n10), held-out (seed 101, n10),
  training (seed 1001, n50).
- `sinks/iter0--born--frame-neg-tick.jsonl`.
- `step2-iter1-mined-text.txt`, `step2-iter1-transcript.md`,
  `step2-iter1-candidate.llp`, `iter1-world/`.
- `notch/`: `iter1-em.log`, `iter1-overlay-r0..7.json`,
  `iter1-overlay.json` (= r7), `split-by-reach*.json|.log`.
- `scores/`: `heldout--born|iter1-flat|iter1-notched.json`.
- `tamarisk_plugin.py`: the PORTS list extended with the iter1 ports.

## Close (2026-10-11, user)

The user: Wildfire and Tamarisk are synthetic gym domains. Matching the
gym was never the point. The point was the split: natural numbers and
the step timeline structured in LL (walked chains, lockstep stages, one
rule per law), and rates at runtime (ports plus notch). Both domains
show it. The fitted tables are imported as the last result against the
gym in metis-catalog `domains/rddl/` (README.md, `<domain>.notch.json`).
The subject is closed after step 4. The remaining shelf domains are not
run.
