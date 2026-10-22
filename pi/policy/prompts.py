"""The brain's prompts, one per phase move (POLICY.md). Each carries the world's vocabulary (the host's
command table: the rule names it sends, their variables), the base as it is, the record(s) the
proposal answers, the gate's criterion, and — at re-engagement — the person's instruction."""
import json

from .alfworld import args_of

LANGUAGE_T = """The language (metis LL, linear logic over counted facts):
  NAME [dyn] : A * B * $S(X) * X <> Y -o C * D.
- the left side's plain atoms are CONSUMED when the rule fires; an atom that stays true must be produced again on the right;
- `$S(X)` reads a fact without consuming it (the static facts — {statics} — are always read with $);
- variables are Capitalized, typed by the predicates' declarations; `X <> Y` says two values differ;
- a `%% words with {X}` line above a rule is its spoken line;
- a new predicate needs a declaration line: `pred NAME(type, …) : NS.` (NS is the base's dynamic namespace: the one its other predicates use);
- the rule's NAME decides what the world does when it fires (the table below): a rule named otherwise is the program's own bookkeeping and sends nothing."""

# the world's words in the prompts (an adapter class's attributes; these defaults are ALFWorld's)
ALF = {"description": "a household world (ALFWorld)",
       "verb_text": {"go": "go to the receptacle at location L2 (R, or the one holding O)", "open": "open R", "take": "take O from R", "put": "put O in/on R"},
       "statics": "recat, openable, notopenable, rtype, otype, pickupable, target, dest, …",
       "task_text": "the episode is WON when the target object is in/on a dest receptacle. The instance starts with the token `unchosen` and declares `placed` (the query).",
       "plan_text": "choose a target, go where it is, open what must be opened, take it, go to a dest, open it if needed, put it.",
       "statics_for": None}
WORLD = dict(ALF)
LANGUAGE = LANGUAGE_T.replace("{statics}", ALF["statics"])


def set_world(cls):
    """The world the prompts speak of (the adapter class): its description, its verbs' words, its static
    facts' names (STATICS), the task's won condition (TASK_TEXT), the plan's outline (PLAN_TEXT), and
    which static facts a record's prompt shows (statics_for(rec, instance_text), else those naming the
    action's arguments)."""
    global LANGUAGE
    for key, attr in (("description", "DESCRIPTION"), ("verb_text", "VERB_TEXT"), ("statics", "STATICS"),
                      ("task_text", "TASK_TEXT"), ("plan_text", "PLAN_TEXT"), ("statics_for", "statics_for")):
        WORLD[key] = getattr(cls, attr, ALF[key])
    LANGUAGE = LANGUAGE_T.replace("{statics}", WORLD["statics"])


def vocabulary(commands, verbs=None):
    if isinstance(commands, tuple):
        commands, verbs = commands
    rows = []
    for name, spec in sorted(commands.items()):
        if not spec:
            continue
        verb, vars_ = spec[0], spec[1:]
        what = WORLD["verb_text"].get(verb, verb)
        rows.append("  %-12s binds %-8s → the command: %s" % (name, ", ".join(vars_) or "nothing", what))
    head = "The rule names the world sends a command for (its host's table; a rule's name is one of these, its variables bound by these names):\n"
    if verbs:
        conv = ", ".join("%s_<why> binds %s" % (v, ", ".join(x for x in spec[1:] if not (v == "go" and x == "L2")) + (" (L2 optional)" if v == "go" else ""))
                         for v, spec in sorted(verbs.items()))
        head = ("A rule sends the world a command when its name is a verb, or a verb and why (`take_from_shelf`, `go_to_dest`): "
                + conv + ". So a rule of the program's own bookkeeping (it only moves tokens) must NOT begin with one of these verbs. "
                "The host's own names below keep their bindings:\n")
    return head + "\n".join(rows)


def statics_about(instance_text, handles):
    """The instance's static facts that name one of the handles (what a rule may read with $)."""
    hs = set(handles)
    out = []
    for line in instance_text.splitlines():
        s = line.strip()
        if s.endswith(".") and "(" in s and not s.startswith(("%", "#", "type ", "include", "catalog", "provenance")):
            atom = s[:-1]
            if hs & set(args_of(atom)):
                out.append(atom)
    return out


def _record(rec, instance_text):
    hs = list(rec["action"]["args"].values()) if rec.get("action") else []
    st = WORLD["statics_for"](rec, instance_text) if WORLD["statics_for"] else statics_about(instance_text, [h for h in hs if h])
    lines = ["the command: %s   (the action: %s %s)" % (rec["command"], rec["action"]["verb"], json.dumps(rec["action"]["args"])),
             "the facts before: " + ", ".join(rec["before"]),
             "the world's text: " + rec.get("text", "").replace("\n", " ")[:300]]
    if "added" in rec:
        lines.append("what changed: added %s; removed %s" % (", ".join(rec["added"]) or "nothing", ", ".join(rec["removed"]) or "nothing"))
    if st:
        lines.append("static facts about the things named: " + ", ".join(st))
    return "\n".join("  " + l for l in lines)


SKILL = {"text": ""}


def set_skill(text):
    """The skill the brain follows (policy-tuning s-1caedae5): procedures a careful formalizer keeps —
    read into every prompt after the task, before the person's instruction. Empty: no skill."""
    SKILL["text"] = (text or "").strip()


def instruction(note):
    out = ("\n\nThe skill — the procedures a careful formalizer follows here:\n%s\n" % SKILL["text"]) if SKILL["text"] else ""
    return out + (("\n\nThe person's instruction (at the last disengagement): %s\n" % note) if note else "")


def explore(base, commands, rec, similar, instance_text, note=None):
    sims = "".join("\n- another record of the same action:\n" + _record(r, instance_text) for r in similar[:2])
    return f"""You are building the rules of {WORLD['description']} from what the world does. The program has no rule yet that explains this TRANSITION; write the rule(s) that do.

{LANGUAGE}

{vocabulary(commands)}

The base as it is (its declarations and its rules so far):
```llp
{base.strip()}
```

The transition to explain:
{_record(rec, instance_text)}{sims}

Write the rule for this action, LIFTED (variables, not the things' names): its left side the facts before that the action needs (consume what changes, read with $ what stays), its right side what is true after — so that, fired on the facts before, it gives exactly the facts after. It must not fire where the world would answer differently. Reuse a rule name only to REPLACE that rule (its new text in full).{instruction(note)}

Answer with ONE ```llp block of only the new lines (pred declarations if any, then the rule with its %% line)."""


def revise(base, commands, sur, rule_line, instance_text, note=None):
    return f"""You are maintaining the rules of {WORLD['description']}. A rule fired and the world did not do what it said: a SURPRISE. Revise the rule so it fires only where the world agrees.

{LANGUAGE}

{vocabulary(commands)}

The base as it is:
```llp
{base.strip()}
```

The rule that fired: {sur['rule']}
  its text: {rule_line}
  the command it sent: {sur['command']} — the world {'refused it' if not sur.get('admissible') else 'took it but nothing changed'}
  the facts before: {', '.join(sur['before'])}
  the world's text: {sur.get('text', '')[:300]}

Give the rule's new text in full under its own name (a missing precondition, read with $ or consumed and produced again), or `drop NAME` if no rule of that name can be right here.{instruction(note)}

Answer with ONE ```llp block of only the changed lines."""


def policy(base, commands, task_facts, episode, instance_text, note=None):
    steps = "\n".join("  %s → %s%s" % (t.get("rule"), t.get("command"), "" if t.get("admissible") and t.get("changed", True) else "  (refused)")
                      for t in episode["transitions"][-12:]) or "  (no command was sent)"
    return f"""You are building the rules of {WORLD['description']}. The rules describe the actions; the program acts by firing an enabled rule (chosen at random among them), so the rules must also say WHAT TO DO NEXT toward the task: tokens of the program's own (declare them) that the action rules require and produce, so that from the start the enabled rules lead to the goal.

{LANGUAGE}

{vocabulary(commands)}

The base as it is:
```llp
{base.strip()}
```

The task (this game's facts): {', '.join(task_facts)}; {WORLD['task_text']}
The last episode was NOT won ({episode['steps']} rule firings, {len(episode['commands'])} commands); its last steps:
{steps}

Add or replace rules (keep every action rule's world behaviour: its facts before and after) so the program pursues the task: {WORLD['plan_text']}{instruction(note)}

Answer with ONE ```llp block of only the new or replaced lines."""


def repair(lines, words):
    return ("Your lines did not compile in the world's instance:\n%s\n\nYour lines:\n```llp\n%s\n```\n\n"
            "Answer with ONE ```llp block of the corrected lines." % (words[:2000], "\n".join(lines)))


def task_facts(instance_text):
    return [l.strip()[:-1] for l in instance_text.splitlines() if l.strip().startswith(("target(", "dest(")) and l.strip().endswith(".")]


CONVENTIONS = """The hierarchy's conventions (metis-worlds docs/HIERARCHY.md):
- a SPECIALIST does one kind of thing in the world; its rules are marked with a trailing `% @NAME`;
- it is woken by ONE goal kind of its own: a token the planner produces and no other specialist takes
  (goto(R) for going, open(R) for opening, take(O) for taking, put(O, R) for putting — your names);
- every outcome is a RESULT token the planner takes (reached(R), accessible(R), taken(O), placed …), and a dead
  end is a refusal result (not_here(R), shut(R) …): a specialist never leaves the planner without an answer;
- the PLANNER (rules with no `% @` mark) sends no command: its rules' names never begin with a verb; it reads the
  world's facts with $ and turns the task and the results into the next goal;
- the world's behaviour does not change: in every state, the same commands go out in the same order."""


def conventions(base, commands, ports, ambiguous, note=None):
    amb = "; ".join("%s is taken by %s" % (k, " and ".join(ds)) for k, ds in sorted(ambiguous.items()))
    return f"""You are refactoring the rules of {WORLD['description']} into a HIERARCHY: the base is split into specialists (each rule's `% @NAME`), but its tokens do not follow the conventions, so a director that routes by token kind cannot tell who acts: {amb}.

{LANGUAGE}

{vocabulary(commands)}

{CONVENTIONS}

The split base as it is (its ports, read off the rules: {json.dumps(ports)}):
```llp
{base.strip()}
```

Rewrite the rules so each specialist has its own goal kind and result kinds, the planner turning one into the next. Declare the new tokens; `drop NAME` every rule you replace under another name.{instruction(note)}

Answer with ONE ```llp block: the declarations, the rules (each specialist's with its `% @NAME`), and the drop lines."""


def probe(reading, acts, miss, note=None):
    """The walk found nothing new: which command, from here, teaches the rules the most?"""
    rows = "\n".join("%d. %s   (%s %s)" % (i + 1, a["command"], a["verb"], json.dumps(a["args"])) for i, a in enumerate(acts[:40]))
    weak = ", ".join("%s (%d unexplained)" % (v, n) for v, n in sorted(miss.items(), key=lambda x: -x[1])) or "none"
    return f"""You are exploring {WORLD['description']} to learn its rules. The walk has tried every command here before; choose the one that teaches the rules the most — an action whose outcome the records lack, or one the rules explain least ({weak}).

The facts now: {", ".join(reading)}

The commands the world takes here:
{rows}{instruction(note)}

Answer with the number of ONE command."""
