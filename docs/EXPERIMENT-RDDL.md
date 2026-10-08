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
