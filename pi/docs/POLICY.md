# The loop's policy for building a hierarchy of domains, with disengagement (loop-policy, the architect, 2026-10-22)

The user: "create the policy for the loop to build hierarchical domains, probably split in
phases: exploration, exploitation, refactoring. We know at this point that ALFWorld can be
formalized; now it has to be done by the agentic loop automatically. Add the concept of
disengagement, as in autonomous driving: if the agentic loop is cornered it can disengage
and ask help or instruction from the user."

LEARNING.md gives the closed loop (world → surprises → proposal → experimental gate →
reload → held-out runs). This note gives the loop a POLICY over that cycle: which phase it
is in, what it does there, when it moves, and when it stops and hands over. The policy is
one for both loops (the console's and pi's, loop-parity's rule), in the SDK's `gate`
module, so a person watching the console and pi running unattended follow the same rules.

## The three phases

**Exploration — act without a rule, record, then write the rule.** The domain has no rule
for the state (an empty domain at the start; a surprise nobody resolved later). The loop
acts anyway: the brain (OpenRouter or `claude -p`, the formalization model) picks a command
from the world's admissible set, the host sends it, and the TRANSITION — the facts before,
the command, the facts after, the world's text — is a record. From the records the brain
writes candidate rules (the loop's existing `formalize` with the record as the seed; a rule
= a precondition over the facts before, an effect = the facts' difference) that go through
the experimental gate. A candidate the gate accepts enters the catalog; the explorer
checks the domain after each accept. Exploration ends when the budget for it is spent or
the records stop producing accepted rules (K records without an accept): the domain is as
complete as the records make it.

**Exploitation — the rules act; surprises drive the proposals.** The kernel's program acts
(the ALFWorld pattern); every beat is scored; a refused command or an effect the facts
contradict is a SURPRISE record. One proposal per record (`revise`: the precondition or
the effect the rule missed), through the experimental gate. A surprise that recurs after
its proposal was refused twice sends the loop back to EXPLORATION around that state (a
probe: the admissible commands there, each taken once from a snapshot, the records kept) —
the loop needs data it does not have, not another guess.

**Refactoring — the hierarchy.** Triggered by size, not by failure: a domain past a bound
(rules > R, or predicates per rule above the flat domain's ratio, or the complexity vector's
grounding past G), or after K accepted rules since the last refactoring. Three moves, each a
proposal through the gate:
1. LIFT: facts repeated across instances become a lifted base with the instance's facts
   left to the generator (the catalog's `include`);
2. SPLIT: a cluster of rules whose predicates are disjoint from the rest except for a few
   tokens becomes a specialist domain, the tokens become its goal-in / result-out ports
   (a goal consumed by one rule per state, a result for every outcome, a refusal for every
   dead end — HIERARCHY.md's conventions), and the remaining rules become the task domain
   that emits the goals;
3. DIRECT: the director's instance (`handles/2` from the split's ports) is generated so
   activation is automatic.
A refactoring is accepted iff the recorded traces REPLAY the same (the records as
regression cases: every command the flat program sent, the hierarchy sends), the held-out
success is not down, and the sum of the specialists' complexity vectors is below the flat
one's. The refactoring never changes what the program does in the world; that is why it
can run unattended.

**What SPLIT must separate (loop-policy step 2, F1; as built in step 2b, `pi/policy/hier.py`).**
One flat program is both the world model and the policy. The kernel fires any enabled rule, so a
rule general in the world's facts walks at random, and a rule narrowed to the task cannot explain
the world's other transitions. The loop's rules come out general in the world's facts and GUARDED
by tokens of the program's own (`tofetch(O)`, `todeliver(O)`, `arrived(O, R)`): the token says when
to act, the facts what the world does. The likelihood is measured on the rules' world behaviour,
tokens left out. Those tokens are what SPLIT separates: a domain's goal kinds are the tokens it takes
from another domain, its results the tokens it gives one. As built:
- **PRUNE** proposes dropping the rules nothing can enable (a guard no rule or start produces, by a
  fixpoint). The gate refuses it when they carry the world model (the likelihood falls). Such a rule
  is then kept as `% @model`: in the base for the likelihood, out of the acting hierarchy and its
  vector.
- **SPLIT** clusters the action rules by the host verb they send (the world's DOMAINS: go → nav,
  open → access, take → grasp, put → place); the planner keeps the program's own bookkeeping. Each
  rule carries its domain as a trailing `% @NAME`, so the split is ONE base the gate writes whole. Each
  activation's instance is NARROWED to the things its goal names (the planner to the task's own,
  `planner_keep`). That is where the vector falls.
- **The conventions.** A token several specialists take (`tofetch`: nav, access and grasp) cannot be
  routed by kind. The brain rewrites the split to HIERARCHY.md's conventions: one goal kind per
  specialist, a result for every outcome, a planner that sends no command.
- **DIRECT** writes the director's instance from the ports (`handles/2`, `result/1`, `finished/1`,
  `end/1`) over the lifted director, and runs it with metis-agent's own DirectorLoop.
- **The regression** is the records' replay. The candidate, guided wherever it may choose (an
  enabled event that sends the next recorded command; else a bookkeeping event that names its
  things), must send every recorded command in order. Strict identity of two programs' samples is
  too strict where the flat program chooses at random among equal options.
- **Each move is judged against the base it replaces** (step 2c, the architect's ruling on nina's 2b
  review). All four need the records' replay; the held-out success is required not down for split,
  direct and prune, and checked when given for the conventions (the driver always gives it); the driver passes
  the move, the ambiguity before and after, the current base's vector and the flat program's
  (`move`, `ambiguous`, `vector`, `flat`):

  | move | its own criteria |
  |---|---|
  | prune | the likelihood not down, the vector down |
  | split | the vector down against the current (flat) base |
  | conventions | the ambiguity down (fewer goal kinds with several specialists), the vector not above the flat program's |
  | direct | no ambiguous goal kind left; the vector reported, not judged |

  The conventions and DIRECT each add rules to the base before them; judged against the flat
  program alone, every move would pass on the first split's gain.

## The experimental gate, restated

- EXPLORATION accept: the candidate fires on its record and on no record it contradicts;
  on the held-out split the likelihood is not down.
- EXPLOITATION accept: generalization gain > 0 on the held-out split (likelihood up, or
  task success up with likelihood not down).
- REFACTORING accept: replay-identical on the records, held-out not down, vector down.
- Every proposal, its verdict and its numbers are journaled; the human reads the journal
  after the run (SPEC §10's gate stays human for the catalog; this is the experiment's).

## Disengagement

Autonomous driving's rule: the system knows the edge of its competence, brings the vehicle
to a minimal-risk condition, and REQUESTS A TAKEOVER with a reason and a time budget. The
loop's version:

**Cornered** (any of):
- *budget*: the phase's beats, proposals or spend (the per-request cap and the run's cost
  log, the pi-release lesson) are exhausted;
- *no progress*: N consecutive proposals refused by the gate, or a probe that produced no
  new accepted rule twice at the same state;
- *out of vocabulary*: a surprise whose transition no candidate over the OBSERVED facts can
  explain (the same before-facts, different after-facts across records: the world has a
  fact the host does not read, or the world is stochastic there);
- *contradiction*: the explorer finds two accepted rules consuming one goal in one state, or
  a refactoring that undoes a previous one (split → merge → split);
- *the world says so*: the task's `stuck(X)` — a specialist refused and no rule handles it.

**Minimal-risk condition:** the loop stops acting (no command sent), snapshots the world
(the host's snapshot, replayable), the catalog's state and the records, and writes a
DISENGAGEMENT record: the phase, the reason (one of the five), what it tried (the last
proposals and verdicts), what it believes (the rules in play at that state), the options it
sees (at most three), and ONE question for the person.

**The handover:** the record is a gate proposal of kind `ask` — no file is written; the
console shows the question and waits (the pi loop ends its run with the record as its
last message; the console's run shows it in the gate panel). The person answers with an
instruction: a note (text the brain reads as context at re-engagement), an edit or a rule
(through the ordinary gate), a budget (more beats, more spend), a phase (`explore here`,
`skip this state`, `refactor now`), or `abandon`. The loop RE-ENGAGES from the snapshot in
the phase named, with the answer in its context, and the journal records the handover.

**What disengagement is not:** not a crash (the state is replayable), not a refusal of the
task (the loop asks, then continues), not the gate (the gate judges proposals; disengagement
judges the loop's own competence). Its count per run is a measure beside the three of
LEARNING.md: a loop that disengages often on a family is not autonomous on it; one that
never disengages and never wins is worse.

## The run on ALFWorld (world-alfworld step 2, redefined)

The loop starts from an EMPTY domain over the first family (the generator emits types,
static facts and the task, no rules), runs the policy, and is compared to two references:
the flat domain written by hand and the hierarchy written by hand (alf-hierarchy). The
numbers: held-out success, the complexity vector of what the loop built, proposals
accepted/refused per phase, cost per accepted rule, disengagements and their reasons. The
ablated bases of the earlier step-2 plan (no-open, no-type, …) become the exploitation
phase's starting points when the empty start proves too slow — a fallback, recorded.

## Who builds what

- the architect: this policy; the hierarchy's conventions (HIERARCHY.md); the gate's
  criteria; the judgement of the journal;
- nina (SDK `metis_loop_sdk.gate`): the experimental policy as a `Gate` option (`policy:
  experimental` with a gain hook the run driver fills), the `ask` kind (a disengagement
  record, no write, waits for the person's answer), the journal; the console's gate panel
  showing the question (loop-parity step 2's console verbs);
- opus (metis-agentic-loop, pi): the phase driver (explore / exploit / refactor as the
  loop's state over the world host), the transition and surprise records flowing into
  `formalize`/`revise` with the record as the seed, the probe, the refactoring moves as
  tools (lift / split / direct over the catalog SDK), the disengagement record and the
  re-engagement from a snapshot, the run script with the cost log.
