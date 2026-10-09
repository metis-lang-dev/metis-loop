# EXPERIMENT — formalization against a synthetic world (RDDL elevators)

**Status: ACCEPTED direction 2026-10-08 (user). An EXPERIMENT, not a
language change: metispy domains + the loop, exercised end to end on
a world nobody hand-modeled. The question: can the loop take a prose
description, produce a certified catalog, and converge it against the
REAL environment through surprise records — with the spec 09-11
instruments used in anger?**

World: IPPC elevators (rddlsim `elevators_mdp.rddl` lineage; served
through pyRDDLGym + rddlrepository, as the existing sysadmin/gol/nav/
xtraffic `rddl_adapter.py` bridges do). Why elevators: boolean
fluents only (clean atom mapping), per-floor Bernoulli arrivals
(weighted rules — the measure is native), real concurrency
(multi-elevator), and a header that is literally a prose spec,
including intended-behavior hints ("hover near likely floors").

## Step 1 — a catalog born from prose (terminal REPL only)

`metis` on a scratch world; both LLM seats on the operator's
subscription: `llm command:claude -p` (the formalize seat; narrate
likewise or ollama). Seed: `text <<EOF` = the elevator header
VERBATIM, nothing else. Then `formalize` → `gate`/`revise` repair
rounds (diagnostics-only, spec 08 D5) → `accept`. Deliverables: the
born catalog + the full transcript (the session IS the evidence);
a human checkpoint reviews the catalog before step 2. Verifies on
the way: the command: seat path works end-to-end in the plain
terminal REPL (the user's "can the agent formalize in repl only").

## Step 2 — the surprise loop against the real world

New, generic: `metis/domains/rddl_recorder.py` — a pyRDDLGym episode
runner that maps grounded boolean fluents ↔ atoms mechanically
(`elevator-at-floor___e0__f2` ↔ `at_floor(e0,f2)`), replays each
transition against the serving catalog (`recover`) and writes
surprise records (JSONL sink) where the likelihood says surprise.
Then the loop as the skill runs it: `sink` → `record`/`replay` →
investigate (`why`, `whatif`, `necessity` — USED IN ANGER, their
outputs quoted in the report) → `mine` → `formalize` → `gate` →
accept → next episodes. Iterate; the metric is SURPRISES PER EPISODE
falling across iterations (numbers, not vibes).

DELIBERATE choice: do NOT pre-teach RDDL's synchronous-step
semantics. metis interleaves; RDDL ticks. The lockstep idiom exists
(the GoL/ceptre-ports precedent) — the experiment records whether
the loop DISCOVERS the tick structure through surprises or needs the
idiom handed over. Either answer is a finding.

## Step 2a — notching: the world matched through probability (user)

metis has no reward — and does not need one to GROUND a domain: the
measure is matched to the world by NOTCHING (fit the weights from
observed data; the skill's "no invented weights" doctrine). Until
now the catalogs followed Ceptre and narrative domains; this is the
turn toward quantitative worlds. After the dynamics gate green and
the surprise loop settles the STRUCTURE, notch the weights from
recorded episodes — and here the experiment has GROUND TRUTH: the
instance's constants (per-floor ARRIVE-PARAM Bernoullis) are the
generator itself. ACCEPTANCE, quantitative: the notched arrival
weights recover the instance's constants within sampling error
(report the table: floor, true param, notched weight, n). Reward
stays out of grounding entirely; it returns only as the arena
objective below.

## Step 3 — extra credit: the arena

The metis agent on the pyRDDLGym loop (IPPC 2023 infrastructure):
policy = one-step/MAP lookahead on the exact measure over the
accepted catalog (the sysadmin `greedy_plan` pattern), objective =
the reward's shape as declared queries (waiting/occupant atoms
minimized — metis has no native reward; the mapping is part of the
report). Score vs NoOpAgent and RandomAgent on the official
instances; "beats Random" is the credit line, "approaches a sane
plan" (pick up, deliver, hover) the narrative check via `narrate`.

## Acceptance

1. Step 1's catalog gates green from the header alone; transcript
   kept; human checkpoint passed.
2. At least one full surprise→accept cycle with instrument outputs
   quoted; surprises/episode falling across ≥3 iterations, numbers
   in the report.
3. The synchrony finding stated either way.
4. Extra credit: the arena table (metis vs NoOp vs Random).
Report = the experiment writeup (this file gains a RESULTS section);
suites green as always.

## Provenance doctrine (user, checkpoint): carry the source header

A catalog born from an external script CARRIES THAT SCRIPT'S HEADER
verbatim as `%` comments at the top (the RDDL domain description, its
author line included), beside the `provenance` declaration. The old
rddl catalogs (sysadmin, xtraffic) lost their tie to the source
exactly by dropping this — we are re-deriving them now partly for
that reason. Applies to elevators_born.llp and every derived catalog
onward.

## Session transcript logging (user, checkpoint): a small REPL feature

`transcript [FILE]` in the terminal REPL: a lab-notebook log —
every command and its output, the system prompts in effect (and
changes to them), candidate snapshots on `llp`/`load`/`formalize`,
gate reports, accepts. Reviewable after the fact; the experiment's
sessions use it (exploratory phase: ctx/run/why…; then the
refactoring phase: mine/formalize/notch). Terminal-REPL only: in
web/shared mode nothing is written to the operator's disk (the D4
doctrine); the console's equivalent stays a download if ever wanted.

## The redo program (user, checkpoint): path diversity as a bug-finder

After elevators proves the recipe, RE-DERIVE the already-adapted
RDDL domains in metis-catalog through the same prompt+discovery
process (sysadmin, gol, nav, xtraffic — author prose as the seed,
the loop + notching as the method) and DIFF the born catalogs
against the hand-written ones. Not a vain exercise: each rerun walks
different tool paths, which surfaces latent bugs and new
possibilities (step 1 alone found the cold-start gap, the
pack-vs-revise gating defect, two directive bugs and a save bug) —
the diversity is the point, the diffs are findings either way.

## The domain shelf (faithful seeds for later REPLs)

rddlrepository carries the AUTHOR's description for all 90 problems
(`ProblemInfo.desc` + the domain file's header comment) — each new
formalization session seeds those VERBATIM, nothing paraphrased.
NOTE: the ippc2023 set is almost entirely continuous-fluent (HVAC,
RaceCar, Reservoir, UAV, PowerGen, MarsRover, RecSim) — not metis
material; the boolean, storied, notchable shelf is 2011/2014/2018:

- Elevators_MDP (this experiment) — Bernoulli arrivals per floor.
- Wildfire_MDP_ippc2014 — spatial spread + ignition probabilities.
- Tamarisk_MDP_ippc2014 — invasive-species spread/eradication.
- SkillTeaching_MDP — probabilistic student learning (storied).
- CrossingTraffic_MDP — robot vs Bernoulli-arriving obstacles.
- TriangleTireworld_MDP — the classic probabilistic-planning fable.
- AcademicAdvising — course-passing probabilities.
(SysAdmin, GoL, Navigation, Traffic already have metispy adapters.)
Each is a candidate rerun of steps 1-2a once elevators proves the
recipe.
