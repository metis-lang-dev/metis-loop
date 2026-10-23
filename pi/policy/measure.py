"""The numbers the experimental gate judges (metis.gate, POLICY.md §the experimental gate), measured
by the driver on a TREE (a base and the games' instances that include it).

PREDICTION. A transition record (before, the action, after) is PREDICTED by a program when, in the
program's session with the record's before-facts as its state, an enabled event of a rule the host
sends for that action (alfworld.rule_verb: the verb, its bindings the record's) turns the before
into the after on the dynamic facts the host reads; a REFUSED record (the world did not take the
command) is predicted when no event of that action is enabled there. The text game is deterministic, so a record's
probability under the program is ~1 when predicted and ε when not: the LIKELIHOOD of a record set
is the mean of log(1) and log(ε) — a change of +x/n·log(1/ε) per newly predicted record.

    p = Predictor(tree, games)                  # one session per game, opened once per base
    p.predicts(rec)                             # True | False
    fits(p, cand, cur, record, records)         # the candidate's new rules fire on the record, and on
                                                # no record they contradict (gate: fits_records)
    likelihood(p, records)                      # the mean log-probability
    vector(text, p)                             # {rules, ground}: the complexity vector's two numbers
"""
import json
import math

from .alfworld import kind_of, rule_verb, rules_of

EPS = 1e-3


class Predictor:
    def __init__(self, tree, games, dynamic, commands, verbs=None, uncompared=()):
        """tree: the base's tree; games: {iid: AlfWorld}; dynamic: the host's dynamic predicates;
        commands: the host's command table; uncompared: dynamic predicates a rule may NEED but is not
        judged on producing — what the perception reveals rather than what an action changes (the
        adapter's UNCOMPARED: MiniHack's terrain, seen as the agent moves and doors open)."""
        self.tree, self.games, self.dynamic, self.commands, self.verbs = tree, games, set(dynamic), commands, verbs
        self.uncompared = set(uncompared)
        self.sessions, self.errors = {}, {}

    def session(self, iid):
        if iid not in self.sessions:
            from metis.repl import Repl
            try:
                r = Repl.open(self.games[iid].into(self.tree))
                start = dict(r.shell.counts)
                self.sessions[iid] = (r, {a: n for a, n in start.items() if kind_of(a) not in self.dynamic})
            except Exception as e:                    # noqa: BLE001 — the candidate does not compile: its words
                self.sessions[iid] = None
                self.errors[iid] = "%s: %s" % (type(e).__name__, e)
        return self.sessions[iid]

    def compiles(self, iid):
        """None, or the compiler's words for this game's instance over the tree's base."""
        self.session(iid)
        return self.errors.get(iid)

    def _cmp(self, atoms):
        """The facts an after is judged on: the dynamic ones, the uncompared left out."""
        return {a for a in atoms if kind_of(a) in self.dynamic and kind_of(a) not in self.uncompared}

    def table(self, iid):
        """The session's events the host sends a command for, by verb: [(name, base, bindings,
        needs, consume, produce)] on the DYNAMIC facts only — the rule's world behaviour, the
        program's own tokens left out (a policy token says when to act, not what the world does)."""
        s = self.session(iid)
        if s is None:
            return {}
        r, _ = s
        if not hasattr(r, "_by_verb"):
            by = {}
            for _, _, ev in r.shell.events_tbl:
                rv = rule_verb(ev.name, self.commands, self.verbs)
                if rv is None:
                    continue
                dyn = lambda d: {a: n for a, n in dict(d).items() if kind_of(a) in self.dynamic}
                c, pr, ps = dyn(ev.consume), dyn(ev.produce), dyn(getattr(ev, "persist", {}) or {})
                by.setdefault(rv[0], []).append((ev.name, ev.name.split("[")[0], rv[1], dict(c, **ps), c, pr))
            r._by_verb = by
        return r._by_verb

    def events(self, rec, names=None):
        """The events of the record's action that apply in its before-state (their dynamic needs
        there): [(name, after-set)]."""
        before = set(rec["before"])
        verb, args = rec["action"]["verb"], rec["action"]["args"]
        out = []
        for name, base, b, needs, c, pr in self.table(rec["game"]).get(verb, []):
            if names is not None and base not in names:
                continue
            if any(args.get(k) not in (None, v) for k, v in b.items() if k in args):
                continue
            if not all(a in before for a in needs):
                continue
            out.append((name, self._cmp((before - set(c)) | set(pr))))
        return out

    def predicts(self, rec, names=None):
        """A record the world took: an event of the action gives its after. A REFUSED one (the world
        did not take the command, or nothing changed): no event of the action is enabled there —
        the program would not send it."""
        evs = self.events(rec, names)
        if refused(rec):
            return not evs
        want = self._cmp(rec["after"])
        return any(after == want for _, after in evs)

    def contradicted(self, rec, names):
        """The events of the named rules that fire on the record and say another after (on a
        refused record: any of them)."""
        evs = self.events(rec, names)
        if refused(rec):
            return [n for n, _ in evs]
        want = self._cmp(rec["after"])
        return [n for n, after in evs if after != want]


def refused(rec):
    return not rec.get("admissible", True) or rec.get("changed") is False


def new_rules(cand, cur):
    have = {line for _, line in rules_of(cur)}
    return {name for name, line in rules_of(cand) if line not in have}


def fits(p, cand_text, cur_text, record, records):
    """fits_records: the candidate's new rules predict the seed record, and no record (the
    discovery set) has one of them firing with another after."""
    names = new_rules(cand_text, cur_text)
    if not names:
        return False, "no new rule"
    if not p.predicts(record, names):
        return False, "the new rules do not predict the record (%s)" % record["command"]
    for r in records:
        bad = p.contradicted(r, names)
        if bad:
            return False, "%s contradicts record %s t%d (%s)" % (bad[0], r["game"], r["t"], r["command"])
    return True, "fits"


def explain(p, cand_text, cur_text, record, records):
    """Why the candidate does not fit (policy-tuning): what the new rules consume that the world
    keeps, what they miss that the world adds, what they need that the record lacks, or the record
    one of them contradicts — the gate's reason in the brain's terms, for one repair turn."""
    names = new_rules(cand_text, cur_text)
    if not names:
        return "the lines change no rule: the base already has them (write a different rule, or none)"
    words = p.compiles(record["game"]) if hasattr(p, "compiles") else None
    if words:                                 # no event can bind in a program that does not compile: say the compiler's words
        return "the lines do not compile in the world's instance (%s): fix the rule's text first" % words.strip().splitlines()[-1][:300]
    before, after = set(record["before"]), p._cmp(record["after"])            # the facts an after is judged on (Predictor._cmp)
    evs = p.events(record, names)
    verb = record["action"]["verb"]
    if not evs:
        needs = []
        for name, base, b, nd, c, pr in p.table(record["game"]).get(verb, []):
            if base in names and not any(record["action"]["args"].get(k) not in (None, v) for k, v in b.items() if k in record["action"]["args"]):
                needs.append((name, sorted(a for a in nd if a not in before)))
        if needs:
            name, miss = min(needs, key=lambda x: len(x[1]))
            return "no event of %s fires on the record: its left side needs %s, which the facts before lack — read only what the record has" % (name, ", ".join(miss) or "something the instance lacks")
        return "no event of %s binds to the record's action %s %s: the rule's variables do not reach these things (a type or a static fact is wrong)" % (", ".join(sorted(names)), verb, json.dumps(record["action"]["args"]))
    name, got = evs[0]
    removed_wrongly = sorted((before & p._cmp(before)) - got - (p._cmp(before) - after))
    missing = sorted(after - got)
    extra = sorted(got - after)
    parts = []
    if removed_wrongly:
        parts.append("it consumes %s, which the world keeps (read them with $, or produce them again)" % ", ".join(removed_wrongly))
    if missing:
        parts.append("it does not produce %s, which the world adds" % ", ".join(missing))
    if extra:
        parts.append("it leaves or produces %s, which the world does not have after" % ", ".join(extra))
    if parts:
        return "%s fires on the record but predicts the wrong facts after: %s" % (name, "; ".join(parts))
    for r in records:
        bad = p.contradicted(r, names)
        if bad:
            return "%s also fires on record %s t%d (%s) and predicts the wrong facts there: add the precondition that record lacks" % (bad[0], r["game"], r["t"], r["command"])
    return "the new rules do not fit the record"


def likelihood(p, records):
    if not records:
        return 0.0
    hits = sum(1 for r in records if p.predicts(r))
    return (len(records) - hits) * math.log(EPS) / len(records)


def vector(text, p=None, iid=None):
    """{rules, ground}: the base's rule count, and the events one instance grounds (the
    complexity vector's grounding, alf-hierarchy's measure)."""
    v = {"rules": len(rules_of(text))}
    if p is not None and iid is not None:
        s = p.session(iid)
        v["ground"] = len(s[0].shell.events_tbl) if s else None
    return v
