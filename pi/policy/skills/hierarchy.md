Procedures distilled from two hand-written hierarchies (ALFWorld's, ScienceWorld's; metis-worlds */docs/HIERARCHY.md, scienceworld/experiments/REPORT.md §2). Follow them unless a record contradicts them.

## always
1. A rule's NAME says what the world does. `verb` or `verb_why` sends that verb's command with the variables the table names; any other rule only moves the program's own tokens and sends nothing. Never start a bookkeeping rule with a verb.
2. A rule is judged by replaying the record: fired on the facts before, it must give exactly the facts after. A dynamic fact the action does not change is READ with `$` (`$at(L)` when you take), never consumed; what the action removes is consumed; what it adds is produced. Nothing else on the right side.
3. Lift, and keep the left side to what the action NEEDS. Variables, not names; static facts read with `$`, the instance's facts separate from the base. A static goes on the left only when the world refuses the action without it; a static that merely holds in the record (`$notopenable(R)`, `$otype(O, _)`) decorates the rule and fails the next record. One rule per action, general over every record of it; when several records are shown, the rule that explains all of them.
4. Prefer the smallest declaration that fits; a new predicate needs a declaration in the base's namespace.

## explore
5. In exploration write WORLD rules only: what each action does, no tokens of the program's own, no guards — a guard that nothing produces makes the rule never fire in the replay, and the gate refuses it.

## exploit
6. The policy is tokens of the program's own. World rules say what an action does; tokens say when to act (`want(O)`, `start`, `ready`). Guard an action rule with a token so the program pursues the task instead of wandering; produce the next token on the right side. Keep every action rule's world behaviour as it is.
7. A result is the WORLD's word, never the rule's. When a rule's answer is a result the planner reads, let the action's own line (`said(KIND)`: moved, picked, opened, connected, waited, looked …) and the next beat's facts produce it, not the acting rule.
8. One consumer per goal per state: give every refusal its own rule with a `%%` line that says why, so a refusal is a result, never a stall.

## refactor
9. Split by what is asked, not by what is seen. A specialist takes a GOAL in (`goto(R)`, `get(O)`, `test(O)`, `put(O, C)`) and puts a RESULT out or a refusal (`elsewhere(R)`); it sees only the world facts it needs. The planner knows WHAT and asks HOW: it holds the task's facts, turns each result into the next goal, and never acts in the world.
10. An experiment is a chain with a verdict: build the test (wire, heat, wait), then LOOK, then read the answer from the facts after the look, carrying the parts you chose in tokens.
