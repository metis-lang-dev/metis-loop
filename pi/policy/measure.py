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
    fits(cand, cur, record, records)            # the candidate's new rules fire on the record, and on
                                                # no record they contradict (gate: fits_records)
    likelihood(p, records)                      # the mean log-probability
    vector(text, p)                             # {rules, ground}: the complexity vector's two numbers
"""
import math

from .alfworld import kind_of, rule_verb, rules_of

EPS = 1e-3


class Predictor:
    def __init__(self, tree, games, dynamic, commands):
        """tree: the base's tree; games: {iid: AlfWorld}; dynamic: the host's dynamic predicates;
        commands: the host's command table."""
        self.tree, self.games, self.dynamic, self.commands = tree, games, set(dynamic), commands
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

    def _dyn(self, atoms):
        return {a for a in atoms if kind_of(a) in self.dynamic}

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
                rv = rule_verb(ev.name, self.commands)
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
            out.append((name, self._dyn((before - set(c)) | set(pr))))
        return out

    def predicts(self, rec, names=None):
        """A record the world took: an event of the action gives its after. A REFUSED one (the world
        did not take the command, or nothing changed): no event of the action is enabled there —
        the program would not send it."""
        evs = self.events(rec, names)
        if refused(rec):
            return not evs
        want = self._dyn(rec["after"])
        return any(after == want for _, after in evs)

    def contradicted(self, rec, names):
        """The events of the named rules that fire on the record and say another after (on a
        refused record: any of them)."""
        evs = self.events(rec, names)
        if refused(rec):
            return [n for n, _ in evs]
        want = self._dyn(rec["after"])
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
