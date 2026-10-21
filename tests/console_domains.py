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
