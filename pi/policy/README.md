# pi/policy — the loop's policy over a world (loop-policy step 2)

The phase driver of [`docs/POLICY.md`](../docs/POLICY.md): the loop builds a world's domain from an
EMPTY base in three phases, every write a proposal to `metis.gate`'s experimental policy, and
disengages with ONE question when it is cornered. The first world is ALFWorld (metis-worlds
`alfworld/`, its host `world/alf_host.py`); the first family `pick_and_place_simple`.

```sh
run.sh --world alfworld --family pick_and_place_simple --brain claude/claude-opus-5-5 --discovery 2 --gate-games 2
run.sh … --brain openrouter/<model> --budget 0.50          # a paid brain: --budget is required
run.sh --run DIR --answer TOKEN 'a note'                   # the person answers the ask
run.sh --run DIR --resume --brain …                        # re-engage from the snapshot
```

`run.sh` runs `python -m policy.driver` under the world's venv (`.worlds/alf` for ALFWorld,
`.worlds/sw` for ScienceWorld, `.worlds/mh` for MiniHack; metispy in each), in a memory-capped
scope. `--world` picks the adapter (`policy/alfworld.py`, `policy/scienceworld.py`,
`policy/minihack.py`: the contract is the class's surface — sample, open/step/snapshot/restore/act,
actions/unadmissible, vocabulary, task_facts, `iid` and `game_dir` (a snapshot's name of the game),
and the class's DOMAIN, DESCRIPTION, SPLITS and VERB_TEXT the driver and the prompts read; optional:
STATICS, TASK_TEXT, PLAN_TEXT and `statics_for(rec, instance_text)`, the prompts' world-specific
words, ALFWorld's when absent, and UNCOMPARED, the dynamic predicates a rule may need but is not
judged on producing). `--set KEY=N` changes a budget (`DEFAULTS` in driver.py:
explore_steps, explore_k, explore_w, exploit_episodes, act_steps, proposals, no_progress,
refactor_rules, refactor_k, repairs).

## The run's directory

| path | what |
|---|---|
| `catalog/domains/alf/alf.llp` | the BASE the loop builds: it starts as the hand base's declarations with no rule (`alfworld.empty_base`); the gate writes it |
| `trees/current/`, `trees/candidate/` | each game's instance (the world's `gen_instance`, `include "../base/alf.llp"`) beside a copy of the base: the current one and the one being judged |
| `records/transitions.jsonl` | explore's transitions (before, action, command, after, added, removed, text), and the probes' |
| `records/surprises.jsonl` | exploit's refusals: the rule, its command, the facts before, the world's text |
| `records/heldout.jsonl` | the gate split's walk, the likelihood's records; never shown to the brain |
| `state/gate.json`, `state/journal.jsonl` | the gate's plans, asks and answers; every judged proposal with its numbers and verdict |
| `state/run.json`, `state/snapshot-N.json` | the driver's counters and phase; the snapshot a disengagement leaves |
| `cost.jsonl`, `prompts.jsonl` | one line per brain call (its cost, the key's usage before it); what the brain was given and said |
| `run.log.jsonl` | the run's events (proposals, episodes, probes, phase ends, the disengagement) |

## The phases (POLICY.md, as built)

- **explore.** The discovery games (train) are walked: a verb first, then an untried command
  of it, from the admissible list the host can send (go, open, take, put). Every step is a
  TRANSITION record. A record the base does not predict is the seed of a proposal: the brain
  writes the rule from it and up to two records of the same action. The gate checks
  `fits_records` (the new rules predict the seed and contradict no record) and that the
  held-out likelihood is not down. Explore ends after `explore_w` steps in a row are all
  predicted, `explore_k` unexplained records without an accept, or the steps.
- **exploit.** The program acts (the kernel, the host attached, one rule at a time). A command
  the world refused is a SURPRISE, and the brain revises that rule. An episode not won, with
  no surprise left at a rule that has not been revised in vain, goes to the brain for the
  POLICY: tokens of the program's own that make the action rules pursue the task. The gate
  wants the likelihood up, or the success up with the likelihood not down. A rule revised in
  vain twice sends the loop to a PROBE at that state (snapshot, each admissible command once,
  restore). The probe's unexplained records are proposed as in explore.
- **refactor.** After `refactor_rules` rules, `refactor_k` accepts, or when every discovery
  game is won, the brain refactors the base. The gate wants the discovery games to replay the
  same commands, the success not down, and the vector (rules + ground events) down.

## What the numbers measure (`measure.py`)

- **A rule's world behaviour.** In a record's before-state, an event of a rule the host sends
  for that action (the rule's name is in the host's command table, its bindings the record's)
  APPLIES when the dynamic facts it consumes and reads are there. Its effect is the facts it
  consumes and produces. The program's own tokens are left out: a token says when to act,
  not what the world does. That is what lets the policy's guarded rules keep the action
  model's likelihood.
- **Prediction.** A taken record is predicted when an applying event gives its after. A
  REFUSED record (not admissible, or nothing changed) is predicted when no event of the
  action applies, so a precondition fix is measurable.
- **Likelihood.** The world is deterministic, so a record's probability is ~1 or ε (1e-3).
  The likelihood is the mean log over `heldout.jsonl`, plus the refusals the success runs met.
  The held-out walk tries two host-sendable commands the game does not list, at the
  receptacles where the agent is (a refusal there says something about a precondition; one
  elsewhere does not).
- **Success** is the gate split's (valid_seen) win rate, with the program acting `act_steps`
  rule firings.
- **The vector** is the base's rules plus the events one instance grounds.

## Disengagement

The five reasons of POLICY.md, as the driver detects them:
- **budget:** the proposals, the steps or the spend; a paid brain's spend is the KEY's own
  usage (OpenRouter `/key`), read before each call;
- **no_progress:** `no_progress` proposals refused in a row;
- **out_of_vocabulary:** the same command in the same observed state with two afters;
- **stuck:** a `stuck(X)` atom in the acting program's state;
- **contradiction:** after an accept, two rules answering one recorded action with two
  afters, or a base back at an earlier accepted text (a change undone).

On any of them, nothing more is sent. The driver closes the games, writes the snapshot (phase,
base hash, counters, records), and proposes the ASK through the gate: phase, reason, tried,
believes, at most three options, one question. The run's last line is the record and the answer
command, and it exits with 3. `--resume` reads the answer:
- a note goes into every later prompt;
- a rule is proposed through the gate;
- a budget raises a cap;
- a phase moves the loop;
- abandon ends the run.

## The brain (`brain.py`)

- `openrouter/<model>`: through `metis_loop_sdk.models.openai`. The key comes from the
  environment only, and the request asks for providers that keep no prompts.
- `claude[/<model>]`: the operator's login, through the SDK's `claude-command` under the
  workspace's `.venv`.
- `script:<file>`: answers chosen by a regex on the prompt, for the tests (`tests/hand-script.jsonl`).

Every request is capped (`--max-tokens`, 40 000 prompt characters). The brain answers with an
` ```llp ` block of lines (`pred …`, rules with their `%%` line, `drop NAME`), spliced into the base.
A candidate that does not compile in the seed record's instance goes back with the compiler's
words, up to `repairs` rounds.

## MiniHack (`policy/minihack.py`)

The room family (metis-worlds `minihack/`): a game is a level variant at a layout seed
(`levels.sample`). discovery is the discovery split's variants; the **gate** is the same variants at
other layouts (seed 1000 + the run's: seen kinds, unseen layouts); **heldout** is the compositions
discovery never shows (a monster and a trap, a door and a key). The family `room_quiet` drops the
monster levels: a monster moves on its own, so its records are not the command's alone.

```sh
run.sh --world minihack --family room_quiet --brain claude/claude-opus-5-5 --set explore_steps=120   # 9 verbs: 120, not ALFWorld's 40
```

- **The instance** (world/gen_level.py with a base) declares the level's types (cell, thing, beast),
  the grid as static facts `next(C, D, C2)` (the cell one step from C in direction D: the cells are
  named by their coordinates, so this is the frame the perception already has) and the perceived
  start. The base (`gen_level.base_source`) has the predicates and no rule. The grid is instance
  knowledge of the same kind as ScienceWorld's house graph and ALFWorld's `recat`: the world's layout,
  not a property an experiment would reveal (the architect's ruling).
- **The actions:** MiniHack lists none, so `actions()` is every command the host can send (37: move,
  open, kick and apply × 8 directions, and pickup, eat, down, wait, search). The world REFUSES one
  by changing nothing it perceives (mh_host.act's test), and that is the record's `admissible`.
  With 9 verbs, a walk picks a move one step in 9: set `explore_steps` well above ALFWorld's 40.
- **The numbers:** hp(16) is read as hp(n16) (the base's `num`). The turn, the hunger and hpmax are
  read but never predicted. The terrain (floor, wall, corridor, the stairs, unknown) is UNCOMPARED:
  NetHack shows the arrival stairs only when the agent leaves them, and the room behind a door
  only once it opens. Judged on those, no move rule fits a level's first step.
- **The prompts** show the `next` facts from the agent's cell (`statics_for`), not every fact
  naming the direction.
