"""The console's two domains explored (console-nav s-b923ebfe, tests): every state the
program reaches from its #init under the person's commands and the host's reports, and in
each the rules a token enables — through metispy's own kernel (the Repl's ground events
and its _candidates over a state), no model.

    ex = Explorer("domains/repl/repl.llp", INJECT_REPL)
    ex.run()                 # BFS to a fixed point
    ex.conflicts             # [(state, token, [rules])]: more than one rule for one token
    ex.stuck                 # [(state, token)]: a token no rule takes
    ex.broken                # [(state, token, atoms)]: a state atom held twice after it (not explored)
    ex.fired                 # {rule: times}: each rule seen to fire
    ex.witness               # {rule: counts}: a state it fires from, for the kernel's own step

An injection is (do-lines, when[, "world"]): `when(state)` says whether the host would send it
in that state (a report answers a task in flight; a command can come at any time); a
"world" one flips a pair the host keeps (no rule takes it). After
a token, the program runs on its own (rules that consume no injected token: the dialog
rising, a pick answered) until nothing is enabled; the outcome tokens (done, refused,
progress, idle_click) are what the host retracts at the next tick."""
import io
from collections import deque

from metis.lang.repl import Repl

OUTCOME = ("done(", "refused(", "progress(")
RETRACTED = ("idle_click",)


def strip(counts):
    return frozenset((a, n) for a, n in counts.items()
                     if n > 0 and not a.startswith(OUTCOME) and a not in RETRACTED)


class Explorer:
    def __init__(self, path, inject, max_states=20000):
        self.r = Repl(path, seed=1, stdout=io.StringIO())
        self.ev = self.r.events_tbl
        self.inject, self.max = inject, max_states
        # the #init without its embedded case's command (the case is the program's own test)
        self.start = strip({a: n for a, n in self.r.counts.items() if not a.startswith("cmd_")})
        self.conflicts, self.stuck, self.fired, self.internal = [], [], {}, []
        self.broken = []        # (state, token, atom): a state atom held more than once (a pair broken)
        self.witness = {}       # rule -> the counts it fired from first (a case for the kernel to replay)
        self.seen = {self.start}

    def enabled(self, counts):
        self.r.counts = dict(counts)
        return [self.ev[i][2] for i, w in self.r._candidates() if w > 0]

    @staticmethod
    def base(name):
        return name.split("[")[0]

    def fire(self, counts, e):
        c = dict(counts)
        for a, n in e.consume.items():
            c[a] = c.get(a, 0) - n
        for a, n in e.produce.items():
            c[a] = c.get(a, 0) + n
        self.fired[self.base(e.name)] = self.fired.get(self.base(e.name), 0) + 1
        return {a: n for a, n in c.items() if n}

    def settle(self, counts, state, label):
        """Rules that fire on their own, one at a time, until none is enabled."""
        for _ in range(50):
            es = self.enabled(counts)
            if not es:
                return counts
            names = sorted({self.base(e.name) for e in es})
            if len(es) > 1:
                self.internal.append((state, label, names))
            self.witness.setdefault(self.base(es[0].name), dict(counts))
            counts = self.fire(counts, es[0])
        raise AssertionError(f"{label}: no quiescence")

    def step(self, state, lines, world=False):
        """One injection: a token a rule must take, or (world) a pair the host flips, which
        no rule takes — the program then runs on its own."""
        counts = dict(state)
        token = None
        for l in lines:
            a = l[1:]
            counts[a] = counts.get(a, 0) + (1 if l[0] == "+" else -1)
            if l[0] == "+" and counts[a] > 0:
                token = a
        counts = {a: n for a, n in counts.items() if n}
        if world:
            return strip(self.settle(counts, state, tuple(lines)))
        es = [e for e in self.enabled(counts) if token in e.consume]
        if not es:
            self.stuck.append((state, tuple(lines)))
            return None
        if len({self.base(e.name) for e in es}) > 1 or len(es) > 1:
            self.conflicts.append((state, tuple(lines), sorted(self.base(e.name) for e in es)))
        self.witness.setdefault(self.base(es[0].name), dict(counts))
        counts = self.fire(counts, es[0])
        return strip(self.settle(counts, state, tuple(lines)))

    def run(self):
        q = deque([self.start])
        while q:
            s = q.popleft()
            d = dict(s)
            for lines, when, *kind in self.inject:
                if not when(d):
                    continue
                t = self.step(s, lines, world=bool(kind and kind[0] == "world"))
                if t is not None and any(n > 1 for _, n in t):
                    self.broken.append((s, lines, sorted(a for a, n in t if n > 1)))
                    continue
                if t is not None and t not in self.seen:
                    if len(self.seen) >= self.max:
                        raise AssertionError("state budget")
                    self.seen.add(t)
                    q.append(t)
        return self


def always(_):
    return True


def has(*atoms):
    return lambda s: all(s.get(a, 0) > 0 for a in atoms)


WIDGETS = ("root band sessbar debugger stream lenses chips prompt chat catalog copy extensions readme "
           "candidates records editor apply").split()

INJECT_UI = (
    [((f"+cmd_go({w})",), always) for w in WIDGETS]
    + [((f"+cmd_{c}",), always) for c in ("exit", "home", "pick", "show", "close", "help", "unknown")]
    + [((f"+click({w})",), has(f"shown({w})")) for w in WIDGETS]          # the page reports clicks on what it shows
    + [(("+picked",), has("picking")), (("+nothing_picked",), has("picking"))]
    + [(("-hidden(apply)", "+shown(apply)"), has("hidden(apply)"), "world"),         # the dialog rises (repl's apply)
       (("-shown(apply)", "+hidden(apply)"), has("shown(apply)", "modal"), "world")]  # … and falls (applied or cancelled)
)

INJECT_REPL = (
    [((f"+cmd_{c}",), always) for c in
     ("load", "run", "step", "undo", "reset", "narrate", "records", "apply", "stop", "tell", "help", "unknown")]
    + [(("+opened",), has("loading")), (("+absent",), has("loading")),
       (("+stopped",), has("running")), (("+run_refused",), has("running")),
       (("+narrated",), has("narrating")), (("+narrate_refused",), has("narrating")),
       (("+plan_shown",), has("applying")), (("+nothing_to_apply",), has("applying")),
       (("+told",), has("telling")), (("+tell_refused",), has("telling"))]
    + [(("-clean", "+dirty"), has("clean", "idle"), "world"), (("-dirty", "+clean"), has("dirty", "idle"), "world"),
       (("-chat_seat", "+no_chat_seat"), has("chat_seat"), "world"),
       (("-no_chat_seat", "+chat_seat"), has("no_chat_seat"), "world")]   # the working copy, the brain's chat seat
)


# -- a stage pipeline (a lockstep program: one pass per beat) --------------------

import re as _re
from pathlib import Path as _Path

TOKENS = ("cmd_", "enter(", "blur", "opened(", "closed(", "picked", "nothing_picked", "ambiguous", "jumped(")


def program_text(path):
    """The program as the compiler reads it: includes spliced beside the includer, once each."""
    seen = set()

    def splice(p):
        p = _Path(p).resolve()
        if p in seen:
            return ""
        seen.add(p)
        return _re.sub(r'^\s*include\s+"([^"]+)"\s*\.\s*$', lambda m: splice(p.parent / m.group(1)),
                       p.read_text(), flags=_re.M)
    return splice(path)


class PipelineExplorer(Explorer):
    """The explorer for a stage pipeline: an input arrives at the pass's first stage; each
    stage fires until nothing is enabled, then the next; at the pass's end the outcomes are
    retracted. A token (a command, a port line) two enabled rules consume at once is a
    conflict; one left at the pass's end is stuck. The ground events are indexed by stage and
    by their first required atom (metispy's _candidates scans every event: 31k for ui)."""

    def __init__(self, path, inject, max_states=20000):
        super().__init__(path, inject, max_states)
        self.stages = _re.search(r"^stages\s*\(([^)]*)\)", program_text(path), _re.M).group(1).split()
        self.index = {s: {} for s in self.stages}
        for kind, stage, e in self.ev:
            if kind != "clause" or stage not in self.index:
                continue
            req = dict(e.consume)
            for a, n in e.persist.items():
                req[a] = max(req.get(a, 0), n)
            if not req:
                continue
            key = sorted(req)[0]
            self.index[stage].setdefault(key, []).append((e, req))
        self.races = []          # two enabled rules of one stage that consume the same state atom

    def enabled_in(self, stage, counts):
        out = []
        for a in counts:
            for e, req in self.index[stage].get(a, ()):
                if all(counts.get(x, 0) >= n for x, n in req.items()):
                    out.append(e)
        return out

    def step(self, state, lines, world=False):
        counts = dict(state)
        tokens = set()
        for l in lines:
            a = l[1:]
            counts[a] = counts.get(a, 0) + (1 if l[0] == "+" else -1)
            if l[0] == "+" and a.startswith(TOKENS):
                tokens.add(a)
        counts = {a: n for a, n in counts.items() if n}
        for stage in self.stages:
            for _ in range(100):
                es = self.enabled_in(stage, counts)
                if not es:
                    break
                by = {}
                for e in es:
                    for a in e.consume:
                        by.setdefault(a, set()).add(self.base(e.name))
                for a, names in by.items():
                    if len(names) > 1:
                        (self.conflicts if a.startswith(TOKENS) else self.races).append((state, tuple(lines), a, sorted(names)))
                self.witness.setdefault(self.base(es[0].name), (stage, dict(counts)))
                counts = self.fire(counts, es[0])
            else:
                raise AssertionError(f"{lines}: stage {stage} did not settle")
        left = [a for a in counts if a.startswith(TOKENS)]
        if left:
            self.stuck.append((state, tuple(lines), left))
            return None
        return strip(counts)


def widgets(path):
    return _re.search(r"^type\s+widget\s*\{([^}]*)\}", program_text(path), _re.M).group(1).split()


def inject_ui(path):
    ws = widgets(path)

    def visible(w):
        def ok(s):
            if s.get(f"shown({w})", 0) <= 0:
                return False
            modal = [a[6:-1] for a in s if a.startswith("modal(")]
            return not modal or w == modal[0] or (w in INSIDE.get(modal[0], ()))
        return ok
    INSIDE = {"apply": ()}               # the console's dialog has no children (ui.llp)
    nums = [f"n{i}" for i in range(1, 10)]
    return (
        [((f"+cmd_go({w})",), always) for w in ws] + [((f"+cmd_show({w})",), always) for w in ws]
        + [((f"+cmd_{c}",), always) for c in ("exit", "home", "back", "pick", "numbers", "close", "cancel",
                                                "dictate", "command", "help", "unknown", "jump")]
        + [((f"+cmd_jump_to({l})",), always) for l in ("c", "r")]
        + [((f"+jumped({w})",), has("resolving")) for w in ws]                 # the page resolves a label
        + [(("+nothing_picked",), has("resolving"))]
        + [((f"+cmd_pick_n({n})",), always) for n in ("n1", "n9")]
        + [((f"+enter({w})",), visible(w)) for w in ws]                      # the port: focusin on what is there
        + [(("+blur",), always)]
        + [(("+opened(apply)",), has("free", "hidden(apply)")), (("+closed(apply)",), has("modal(apply)"))]
        + [(("+picked",), has("picking")), (("+nothing_picked",), has("picking")), (("+ambiguous",), has("picking"))]
    ), nums
