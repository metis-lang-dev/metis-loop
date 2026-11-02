# The metis pattern catalog

A catalog of metis LANGUAGE AND LOOP USAGE PATTERNS, Gang-of-Four style, beside the language itself (the user's ask, 2026-11-02, language-patterns s-7999ada5). A pattern is a named, reusable answer to a situation that recurs when a domain is written or refined, drawn from work already done, naming its source. It is not a tutorial of the language: that is `SKILL.md` and the specs; this catalog says what to do when you meet the situation, and how the pi loop recognizes it.

## How to use it

The Claude Code seat and the pi seat have file tools: open the category you are in when a situation recurs (`6-loop.md` for the moves, `1-projection.md` for a class that lies); never load the whole catalog into a prompt (72 KB). A driver brain without file tools gets at most the anti-pattern list below, written for it.

## How to read a pattern

```
### <Name>
Intent: one sentence.
Problem: the smell, surprise or failure it answers.
Shape: the skeleton (classes, stage, rule form, ports, manifest; or the loop's verbs in order).
Example: a real one: repo + file + rule or case, quoted.
Consequences: what it costs or changes (grounding, goldens, image hash, consumers, narration).
Related: patterns it combines with; the ANTI-PATTERN it replaces.
Loop: how the pi agent recognizes the situation and applies the pattern.
```

## The categories

| file | category | patterns |
|---|---|---|
| `1-projection.md` | The projection and the class layer | Exclusive family, single reason; Complementary readings; Steady reading; Time to spare; Duty-scoped class with a way on; Intent-blind safety; Measure the class first; Class before reader |
| `2-rules.md` | Rule shape | Bounded yield; The standing resolution; Choice site; Bind before ground |
| `3-protocol.md` | Protocol | Stub-owned echo; Generation guard; Committed action |
| `4-composition.md` | Composition and derivation | Derivation ladder; Leavable unit; Interface package; Stage block merge; Commands as constraints; Split equals unsplit; A room is data |
| `5-cases.md` | Cases and goldens | Goldens move by name; Bounds with owners; Search the seeds for a firing |
| `6-loop.md` | Loop moves | Propose, comment, review; Replay, never rerun; Blame first; Not this package's; Read the diff in order; Two-line certificate; Key receipt; Read the refusal; Mechanical verdict, model's words; What the comment gets wrong; Own facts judged |
| `7-world.md` | Under the readings: the world and the plant | Check the world first; Sim race in the log; Measure the plant; Ramp out of the dead zone; Shield on the motion |
| `8-road.md` | The road (pascal) | pending: filed when pascal's contribution lands |

## Index by intent

- **Exclusive family, single reason** (`1-projection.md`, opus): replace overlapping flags with one family the host keeps exclusive, and one word for why.
- **Complementary readings** (`1-projection.md`, nina): let a rule say "not" with no negation.
- **Steady reading** (`1-projection.md`, nina): keep a class from flickering or lying because a number sits near its edge.
- **Time to spare** (`1-projection.md`, nina): turn a deadline into a class a rule can read, with the unknown case failing safe.
- **Duty-scoped class with a way on** (`1-projection.md`, opus): scope a law to who owes it, and never hold a car with no way to end the hold.
- **Intent-blind safety** (`1-projection.md`, nina): let a belief make the chair go faster, never less safe.
- **Measure the class first** (`1-projection.md`, opus): see what a class would do while no rule reads it, including whether it's alive.
- **Class before reader** (`1-projection.md`, opus): land a new host class in steps a trace can judge.
- **Bounded yield** (`2-rules.md`, nina): a member may wait for someone, but never for ever and never silently.
- **The standing resolution** (`2-rules.md`, architect): a shield must never create a stand it cannot end: a danger that stays true while both sides stand resolves by a bounded motion of the side that has the way.
- **Choice site** (`2-rules.md`, metis): say a probabilistic alternative as one choice, and know what a weight does.
- **Bind before ground** (`2-rules.md`, metis): keep a rule's cost to what the state can hold.
- **Stub-owned echo** (`3-protocol.md`, metis): keep a member's protocol rules generated, and out of its author's hands.
- **Generation guard** (`3-protocol.md`, metis): stop an old report from acting on a newer grant.
- **Committed action** (`3-protocol.md`, nina): a stop must not leave the chair in the road.
- **Derivation ladder** (`4-composition.md`, metis): change a family's behaviour for one consumer by the lowest mechanism that does it.
- **Leavable unit** (`4-composition.md`, metis): let a platform go without a block of behaviour.
- **Interface package** (`4-composition.md`, metis): give every pred that crosses members one owner.
- **Stage block merge** (`4-composition.md`, metis): place an included rule in a stage on purpose.
- **Commands as constraints** (`4-composition.md`, nina): keep WHAT and HOW apart across one narrow boundary.
- **Split equals unsplit** (`4-composition.md`, nina): prove that a process boundary changed nothing.
- **A room is data** (`4-composition.md`, opus): change the world under a running agent without restarting anything that didn't change.
- **Goldens move by name** (`5-cases.md`, opus): rename a class on purpose without either weakening the gate or having it refuse forever.
- **Bounds with owners** (`5-cases.md`, nina): say what must hold, and who answers when it doesn't.
- **Search the seeds for a firing** (`5-cases.md`, opus): show a candidate's effect when the sampler decides whether it fires.
- **Propose, comment, review** (`6-loop.md`, architect): no rule enters a domain unreviewed: every candidate, a person's or the loop's, passes a mechanical verdict and a person's review before it is written.
- **Replay, never rerun** (`6-loop.md`, opus): judge a change to one package on what really happened, with no world and no model.
- **Blame first** (`6-loop.md`, opus): find out whose fault a wrong atom is before writing any rule.
- **Not this package's** (`6-loop.md`, architect): name the verdict that sends a surprise away from a rule: to the host, to a sensor's limit, or to a protocol finding.
- **Read the diff in order** (`6-loop.md`, opus): know how far a fired diff is evidence and where it stops.
- **Two-line certificate** (`6-loop.md`, opus): make a verdict say exactly what it is evidence of.
- **Key receipt** (`6-loop.md`, metis): check, not assert, that an edit stayed in one package.
- **Read the refusal** (`6-loop.md`, metis): treat a refusal as the next step's instructions.
- **Mechanical verdict, model's words** (`6-loop.md`, opus): let a cheap model comment without letting it decide.
- **What the comment gets wrong** (`6-loop.md`, opus): read a cheap model's comment for what it reliably misjudges.
- **Own facts judged** (`6-loop.md`, nina): judge a learned rule on what its own command touched, on a world that moves by itself.
- **Check the world first** (`7-world.md`, george): before reading a run's behaviour, prove the world it ran in was the world you meant.
- **Sim race in the log** (`7-world.md`, george): tell a startup race from a behaviour fault, across runs of the same command.
- **Measure the plant** (`7-world.md`, george): learn what the base does with a command, open loop, before tuning anything or reasoning about rules above it.
- **Ramp out of the dead zone** (`7-world.md`, george): never let a controller approach a command from below when the base does not answer below a threshold.
- **Shield on the motion** (`7-world.md`, george): a floor below the policy must judge what is commanded, or it will make deadlocks it cannot leave. **Open: stated as the problem; the first fix tried, a smaller region, did not work.**

## Anti-patterns, and the pattern that replaces each

- The faked class (a wish sets `lead_slow`, a pace sets `keep_no`) → Exclusive family, single reason.
- Absent means no (a class's absence read as its opposite; `zbusy` as 'nobody'); the negated premise → Complementary readings; Duty-scoped class.
- The self-clearing hold; debounce in the rules; a counter token; the timer in the rule → Steady reading; Bounded yield.
- The optimistic default (an unknown deadline read as plenty); numbers in a premise → Time to spare.
- Trusting the forecast (a rule relaxing on a belief) → Intent-blind safety.
- A class trusted because its docstring is right → Measure the class first.
- A rule and its class in one commit, judged on a trace that cannot hold them → Class before reader.
- A yield that cannot be made; the timer in disguise; a smaller region as the cure; a blind motion → The standing resolution; Bounded yield; Shield on the motion.
- Twin bodies; weight as priority; a rule made to win by raising its weight → Choice site; Search the seeds for a firing.
- The clock in the rule (a time variable grounding once per value) → Bind before ground.
- The hand-written echo (editing inside the generated block); the runtime drop (stamping tokens in the host); the compensating rule → Stub-owned echo; Generation guard; Not this package's.
- A rule for what a sensor cannot see; a planner rule over a false reading → Not this package's; Blame first.
- The goal-held commitment → Committed action.
- The reopened rule (override); hide and replace (rename evasion); the private twin pred; a second stages line → Derivation ladder; Leavable unit; Interface package; Stage block merge.
- Geometry in the rules (a concrete cell or zone id); a controller with opinions; perception over the wire; a rule naming a room; a restart to change data → Commands as constraints; Split equals unsplit; A room is data.
- Goldens edited in a separate commit; a golden as truth; a provisional row unmarked; a golden for the live run first; 'accepted' on a seed where the rule never fired → Goldens move by name; Bounds with owners; Search the seeds for a firing.
- The ad hoc rule; a rule tested by rerunning the agent; the same rule in other words after a refusal → Propose, comment, review; Replay, never rerun; Read the refusal.
- A row after `open_loop_after` read as the world's response; 'accepted on two seeds' with nothing fired → Read the diff in order; Two-line certificate.
- Confined by intent (no receipt); silencing a refusal; the model's 'agree' taken as the review → Key receipt; Read the refusal; Mechanical verdict.
- The whole reading judged; repairing on another after than the gate's → Own facts judged.
- The card on an empty world; tuning a rule against a race; retrying until it passes; tuning against the error message; a timer that kicks the robot → Check the world first; Sim race in the log; Measure the plant; Ramp out of the dead zone.

## Open items from the contributions, ruled (architect, 2026-11-02)

1. The loop never proposes `hiding` is a ruling, not enforced in code (metis): enforce it for the model's drafts only; a person's pack may hide (later, opus).
2. A missing `#init tick__gen` seed is not checked (metis): an L-check on `tick__gen` for a member whose manifest names it (later, metis).
3. 'Not this package's' needed an entry (metis): written in `6-loop.md`, the architect's, with three outcomes.
4. No tool makes the cross-tab of Measure the class first (opus): a `metis.trace` count of an atom by another atom (later, opus).
5. `--move-golden` does not check the move is only a rename (opus): a diff line per moved golden in the ruling (later, opus).
6. 'accepted' with 'no candidate rule was enabled' reads as more than it is (opus): the printed verdict becomes `accepted (inert)` when nothing was enabled; the certificate line stays (later, opus).
7. ALFWorld's room change and the kitchen's seed search as patterns (opus): written, A room is data and Search the seeds for a firing.
8. The road's patterns (pascal): `8-road.md` when filed.
9. `blame` has no verb: `metis.trace`'s CLI has replay and case only (opus's review): a `metis.trace blame` CLI (later, opus); until then the patterns say the Python call.
10. A rule inside the stub's generated block reads to `blame` as a member's rule (metis): count it as a protocol finding (later, opus).
11. The `ground-budget` hint says 'a fact the state holds' where only a `bwd` guard binds at grounding (metis): reword in both toolchains (later, metis).
12. A second rule of one name across stage blocks or through an include was accepted by both toolchains, against spec/18 §4 (metis): FIXED by dup-rule-names s-dfb61f45 (`rule-duplicate` in both resolves; the sweep of every shipped program found 0 duplicates).

## Credits

opus (13), nina (10), metis (10), george (5), the architect (3): 41 patterns; combined and categorized by the architect; reviewed by opus (loop fit, 19 items folded in) and metis (language, 16 items folded in); the user gates.
