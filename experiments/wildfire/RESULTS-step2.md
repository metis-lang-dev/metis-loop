# RDDL Wildfire — step 2 + 2a results: the surprise loop and the notch (2026-10-10)

This is subject rddl-tier1 (s-8f820524), Wildfire, after the user's step-1
checkpoint ("Wildfire go"). **Nothing is committed** (metispy and
metis-loop working trees). This waits for the architect's review.

## Headline

| world (served) | surprises / episode, held-out¹ | in-sample² |
|---|---|---|
| iter0: born catalog (step 1) | 11.5 | 13.3 |
| iter1: revise from mined episode text (per-k literal weights) | 1.3 | 2.0 |
| iter2: one law, weight port `pign(K)`, base prior-flat 0.5 | 12.3 | — |
| **iter2 + notch overlay fitted from episodes** | **1.3** | — |
| *the true generator (RDDL cpfs, same threshold) = the floor* | *1.4* | *2.1* |

¹ 10 fresh episodes (instance 1, random agent, seed 101), never mined or
fitted. ² The 400 steps iteration 1 was mined from.

The surprise threshold is the recorder's default: joint likelihood < 0.05.
In a 9-cell world even the true generator crosses it, so the floor
(`true_likelihood.py`, the cpfs evaluated directly) is the honest target.
**The notched port world sits at the floor.** On the held-out episodes it
flags exactly the transitions iteration 1's fitted literals flag (same
episodes, same counts), with ONE ignition rule instead of nine.

## Step 2a acceptance — the notch table

The port is `weight pign(K) reads {}` on `catch`, with the base binding
prior-flat at 0.5 (`wildfire_plugin.py`). The fit is ML (α=0) over 2400
recorded transitions (iter0 + 50 training episodes, seed 1001), via
`notch_episodes.py`. Each transition is explained by a sampled run of the
served world that reaches the observed next state (2400 of 2400
explained, 0 missed). Its port draws are attributed to (port, args,
scope row), using the session notch's PAIRED estimator.

| k | true 1/(1+e^(4.5−k)) | notched pign(k) | 95% CI | n | fires | true in CI |
|---|---|---|---|---|---|---|
| 0 | 0.0110 | 0.0094 | [0.007, 0.013] | 3194 | 30 | yes |
| 1 | 0.0293 | 0.0258 | [0.021, 0.032] | 3366 | 87 | yes |
| 2 | 0.0759 | 0.0837 | [0.068, 0.102] | 1040 | 87 | yes |
| 3 | 0.1824 | 0.1464 | [0.110, 0.193] | 280 | 41 | yes |
| 4 | 0.3775 | 0.4000 | [0.234, 0.593] | 25 | 10 | yes |
| 5 | 0.6225 | 0.6000 | [0.231, 0.882] | 5 | 3 | yes |

**Every observed k recovers the generator's law within its 95%
interval.** The fit never read the formula; the header's logistic is only
this table's ground-truth column. k ≥ 6 was never exposed in instance 1:
its max degree is 8, but random play burns the grid out first. Target
k=0 is not a port draw, because the world's `screen` stage holds a
target with no burning neighbor. So the k=0 row is non-target exposures,
as in the cpfs.

## The loop, iteration by iteration (transcripts in this directory)

**iter0** (sink only). The born world, 1-step readout: 133 of 400 steps
unmodeled (13.3/ep). Every changing step is unexplainable in the born
vocabulary (`cell`/`tally`/`crew` vs the observed `burning(X,Y)`/
`out_of_fuel(X,Y)`). Under the settle readout plus negatives plus tick
(the elevators-converged interface), the same 133, and 400 of 400
unsettled: the born qui cycle never ends.

**iter1** (`step2-iter1-transcript.md`). Terminal `metis wildfire_born.llp`
in tmux; seat and card as in step 1; `sink`, then record 2 (a k=0
ignition):
- `replay` → likelihood 0.0, explains false.
- `why burning(x3,y2)` → "burning(x3,y2) was never produced and is not in
  the base state".
- `query burning(x3,y2)` → "P = 0 ± 0.0048 … sampled n=400 — exact
  refused: exact filter retained 100001 states".

`mine`: the observed interface; the instance's neighbor relation and
targets, as data from `nonfluents-i1.json`; the regularities with counts.
`formalize` went green in 2 rounds (revise); then `accept` and export
`iter1-world`. The world is in the observed vocabulary, with lockstep
stages `open → count → act → ignite`, a WALKED per-cell neighbor scan
(`nb(X,Y,slot,U,V)` lists, `tally` up a `next` chain), and out-of-fuel,
put-out, cut-out and the target guard.

But ignition came out **unrolled per k** (`catch_plain_k0..k3`,
`catch_target_k1..k4`), with my mined counts as literal weights, and
"1 of 1" turned into certainty (`plainsure`/`targetsure` facts). That
violates the doctrine the card states, and no gate catches it. The cause
is the miner (me): the counts were in the text. Finding 1.

**iter2** (`step2-iter2-transcript.md`). `metis --plugin
wildfire_plugin:make iter1-world/base.llp`, with the card v2 (the step-1
card plus a generic WEIGHT PORTS section, toy example only). On the iter1
replay sink, the instruments:
- `query burning(x3,y2) @frame` → "P = 0.01333 ± 0.0097 … sampled n=600"
  (the unrolled literal 6/494).
- `query burning(x2,y2) @frame` (target, k=0) → "P = 0 ± 0.0048".

`mine`: the rate is DATA, depends only on k, and is one law, one rule,
`pign(K)` and its complement. `formalize` went green in **1 round**
(revise); then `accept` and export `iter2-world`:

```
weight pign(K) reads {}.
stage screen { … a target with k=0 never starts … }
stage ignite {
  catch [dyn] : fresh(X, Y) * tally(X, Y, K) * not_burning(X, Y)
      -o (burning(X, Y) @w pign(K) | not_burning(X, Y) @w ~pign(K)).
}
```

Served prior-flat, it gives 12.3/ep: the structure is right and the
rates are wrong. Notched (the table above) it gives 1.3/ep, at the floor.

## Findings

1. **Mined counts invite unrolling (doctrine, loop).** Numbers in the
   approved text became per-value rules plus literal weights; the
   doctrine paragraph in the card did not stop it, and no gate measures
   it. With the text saying "rate = data, one law" and the card showing
   port syntax, the seat produced the port world in 1 round.
   Recommendation: the miner keeps counts out of the text (they belong to
   notch), and a gate warning flags ≥3 rules differing only in a ground
   constant of one argument.
2. **The exact filter cannot price lockstep catalogs over a grid**
   (measure). Per-cell scans interleave within a stage, and the
   intermediate states multiply (more than 2M at step 26 for 9 cells).
   `replay`, gate scenarios and `revise`'s diff all hit it. The sampled
   tier carried every measurement here.
3. **Kernel: the factored tier returns likelihood 0 for a reachable
   observation** (NOT patched, per the subject's scope). Repro:
   `iter1-world/base.llp`, transition 0 of
   `transitions/iter0-i1-random-s1-n10.jsonl` (negatives + tick).
   `FactoredProgram(prog, 82).likelihood(obs)` = 0.0, and its constant
   propagation pins `out_of_fuel(x1,y3)=0`. Yet every `run_trace` seed
   reaches the observation (`held` in stage count → `burn_fuel` in stage
   act).
4. **Policy index spaces (fixed in my own port-plugins code).**
   `run_trace` indexes its policy by `canonical_events`; the filter by
   `program.events()`. `PortPricer.policy(prog, canonical=True)` now
   exists for run_trace. `narrate SEED`, `trace SEED` and wire narrate
   priced ports against the wrong events before; there is a regression
   test for both declaration orders. Pre-existing and NOT touched:
   `domains/xtraffic/model.py` hands `run_trace` a policy as well;
   worth a look.
5. **The surprise threshold needs a floor.** A joint likelihood < 0.05
   is crossed by the true generator 1.4–2.1 times per episode here.
   Report surprises against the floor, or use a per-transition
   log-likelihood ratio vs the floor.
6. The step-1 fidelity gaps are resolved by the loop: the flat rate, the
   target guard, cut-out and out-of-fuel all landed in iter1 from the
   episodes. Gap 4 (one action per step) was right all along: the
   instances set max-nondef-actions = 1. Gap 5 (topology) came in as
   observed instance data.
7. **Correction to the architect's note:** the recorder maps state
   fluents and actions, not non-fluents. NEIGHBOR/TARGET entered as
   observed data in the mined text (`nonfluents-i1.json`).

## Tool changes (metispy, uncommitted, tests green)

- `rddl_recorder.surprise_sink` / CLI:
  - `tier` exact | sampled | auto (Monte Carlo with a Wilson ci; every
    record says its tier, n and ci);
  - `frame_cap` (a big lockstep step can exceed 64 events);
  - `plugin` + `overlay` (a notch table JSON) price weight ports in both
    tiers;
  - `port_pricer()` helper.
  - Tests: sampled agrees with exact; auto falls back; exact never
    silently degrades; plugin/overlay pricing.
- `loop/verbs.cmd_accept`: an over-budget revision diff becomes a
  `diff_note` and no longer kills the accept (test).
- `lang/compiler.PortPricer.policy(canonical=)`, with the repl/wire
  seeded traces using it (finding 4, test).
- `fw/plugin.load_plugin`: specs resolve beside the catalog, else in the
  working directory (a derived world in a subfolder still finds its
  experiment's plugin).
- Suites: `tests/fw`, `tests/loop`, `tests/lang/test_repl.py`,
  `tests/test_rddl_recorder.py`, `tests/test_record.py`: 65 passed.

## Artifacts (this directory)

- `transitions/`: iter0 (seed 1, n10), held-out (seed 101, n10),
  training (seed 1001, n50); raw pyRDDLGym steps.
- `sinks/`: every surprise sink above (+ `.summary.json`).
- `iter1-world/`, `iter2-world/`: the accepted worlds (export).
- `step2-iter{1,2}-mined-text.txt`, `step2-language-card-v2.txt`,
  `step2-iter{1,2}-transcript.md`.
- `wildfire_plugin.py` (prior-flat base), `notch_episodes.py` (the
  episode notch), `notch_table.py` (merge + acceptance table),
  `notch/pign-overlay.json` (the fitted overlay), `true_likelihood.py`
  (the floor).

## Not done / next

- The step-2 world is not yet a catalog file with the header's logistic
  riding as the `%%` doc on `weight pign` (architect point 2). That is
  for assembly on approval. iter2-world is the candidate.
- The optional verification arm (logistic as base) was not run: the
  notch already scores within CI at every k.
- Instances 2–10 (bigger grids: 4×4, 5×5) are not run yet. They would
  test the topology-as-data claim and the sampled tier's cost.
