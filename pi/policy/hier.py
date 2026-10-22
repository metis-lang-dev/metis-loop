"""The refactoring moves (loop-policy step 2b; docs/POLICY.md §refactoring): SPLIT a flat base into
specialists and a planner, DIRECT the split with a director instance generated from its ports, PRUNE
the rules that can never fire — and the runner that measures them: the hierarchy acting through one
host, activation by activation, each one's instance NARROWED to the things its goal names.

The split is ONE base: each rule carries its domain as a trailing annotation (`… -o at(L2).  % @nav`),
so the gate writes one file and the flat program is the split read whole. A rule with no annotation
is the planner's.

    sp = split_by_verb(text, world)            # the action rules by the host verb they send (DOMAINS), the rest the planner's
    text2 = annotate(text, sp)                 # the base with its split
    sp = Split.of(text2, world)                # read back; ports from the tokens that cross the domains
    out = run(game, sp, run_dir, base_name, steps, seed)              # the manual switch
    out = run(game, sp, run_dir, base_name, steps, seed, director=make)   # the director's rules make it
    director_text(sp, base_rel)                # the director's instance over the lifted director base

PORTS. A TOKEN is a predicate of the program's own (neither a world fact the host reads nor a static
fact). A domain's goal kinds are the tokens its rules consume (or read) that another domain produces
or the instance's start holds; its result kinds the tokens it produces that another domain consumes.
That is HIERARCHY.md's goal-in / result-out, read off the rules (F1: the policy's tokens are the ports).
"""
import importlib.util
import json
import random
import re
import shutil
from pathlib import Path

from . import acting
from .alfworld import args_of, kind_of, rules_of

ANNOT = re.compile(r"%\s*@(\w+)\s*$")
OUT_KINDS = ("wake", "sleep", "forward", "ask", "ended")
PLANNER = "task"
MODEL = "model"           # never-firing rules kept as the world model: in the base (the likelihood), out of the acting hierarchy


# ── reading a base ──
START = ("unchosen", "start")


def start_tokens(instance_text, dynamic=()):
    """The tokens an instance's start holds (its #init lines of a non-dynamic predicate; nina's N5)."""
    out = set()
    for line in (instance_text or "").splitlines():
        m = re.match(r"^#init\s+(\w+)", line.strip())
        if m and m.group(1) not in dynamic:
            out.add(m.group(1))
    return out


def rule_atoms(line):
    """A rule line → (needs, reads, produces): the predicate names its left side consumes, reads
    ($), and its right side produces (guards like L <> L2 left out)."""
    body = ANNOT.sub("", line).split(":", 1)[1].rstrip().rstrip(".")
    left, _, right = body.partition("-o")
    def atoms(side):
        out = []
        for part in side.split("*"):
            p = part.strip()
            if not p or "<>" in p or "=" in p or p == "()":
                continue
            out.append(p)
        return out
    l, r = atoms(left), atoms(right)
    needs = [kind_of(a) for a in l if not a.startswith("$")]
    reads = [kind_of(a[1:]) for a in l if a.startswith("$")]
    return needs, reads, [kind_of(a) for a in r]


def declarations(text):
    """pred / bwd name → (its argument types, static?)."""
    out = {}
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^(pred|bwd)\s+(\w+)(?:\(([^)]*)\))?", s)
        if m:
            out[m.group(2)] = ([t.strip() for t in (m.group(3) or "").split(",") if t.strip()], m.group(1) == "bwd")
    return out


def verb_of_base(base, commands, verbs):
    spec = commands.get(base) or (verbs.get(base.split("_")[0]) if verbs else None)
    return spec[0] if spec else None


class Split:
    """The base's split: domains (name → its rules), the planner, the tokens, the ports."""

    def __init__(self, text, domains, dynamic, planner=PLANNER, start=None):
        self.model = list(domains.get(MODEL, []))
        domains = {d: r for d, r in domains.items() if d != MODEL}
        self.text, self.domains, self.planner = text, domains, planner
        self.decl = declarations(text)
        self.rules = dict(rules_of(text))
        static = {n for n, (_, st) in self.decl.items() if st}
        self.tokens = {n for n in self.decl if n not in static and n not in dynamic}
        uses, makes = {}, {}
        for d, names in domains.items():
            for n in names:
                needs, reads, prods = rule_atoms(self.rules[n])
                uses.setdefault(d, set()).update(k for k in needs + reads if k in self.tokens)
                makes.setdefault(d, set()).update(k for k in prods if k in self.tokens)
        start = set(start or START)
        self.goal = {d: {k for k in uses.get(d, ()) if any(k in makes.get(e, ()) for e in domains if e != d) or k in start}
                     for d in domains}
        self.out = {d: {k for k in makes.get(d, ()) if any(k in uses.get(e, ()) for e in domains if e != d)} for d in domains}
        self.makes, self.uses = makes, uses
        made_all = set().union(*makes.values()) if makes else set()
        terminal = {k for k in made_all if not any(k in uses.get(e, ()) for e in domains)}
        self.ends = {k for k in terminal if k == "stuck" or k.startswith(("wrong", "refused"))}
        self.finished = terminal - self.ends

    @classmethod
    def of(cls, text, world, start=None):
        dyn = world.vocabulary()[0] if hasattr(world, "vocabulary") else world.dynamic
        doms = {}
        for name, line in rules_of(text):
            m = ANNOT.search(line)
            doms.setdefault(m.group(1) if m else PLANNER, []).append(name)
        return cls(text, doms, dyn, start=start)

    @property
    def specialists(self):
        return [d for d in self.domains if d != self.planner]

    def is_split(self):
        return len(self.domains) > 1 or bool(self.model)

    def base_of(self, d):
        """D's base: the flat base's declarations, its own rules only (the annotations kept)."""
        keep = set(self.model if d == MODEL else self.domains.get(d, ()))
        out, in_stage = [], False
        for line in self.text.splitlines():
            s = line.strip()
            if s.startswith("stage ") and s.endswith("{"):
                in_stage = True
            elif in_stage and s == "}":
                in_stage = False
            elif in_stage and s and not s.startswith("%") and ":" in s and s.split()[0] not in keep:
                if out and out[-1].strip().startswith("%%"):
                    out.pop()                           # its %% line goes with it
                continue
            out.append(line)
        return "\n".join(out) + "\n"

    def ports(self):
        return {d: {"goal": sorted(self.goal[d]), "out": sorted(self.out[d])} for d in self.domains}

    def ambiguous(self):
        """The goal kinds more than one specialist takes: a director routing by kind cannot tell which
        (HIERARCHY.md: one goal kind per specialist) → {kind: [domains]}."""
        out = {}
        for d in self.specialists:
            for k in self.goal[d]:
                out.setdefault(k, []).append(d)
        return {k: ds for k, ds in out.items() if len(ds) > 1}


def split_by_verb(text, world, names=None, start=None):
    """The action rules clustered by the host verb they send (the world's DOMAINS: go → nav …), the
    rest (the program's own bookkeeping) the planner's."""
    dynamic, commands, verbs = world.vocabulary()
    names = names or getattr(world, "DOMAINS", {}) or {}
    dead = set(never_firing(text, dynamic, start or START))
    doms = {PLANNER: []}
    for name, _ in rules_of(text):
        v = verb_of_base(name, commands, verbs)
        doms.setdefault(MODEL if name in dead else (names.get(v, v) if v else PLANNER), []).append(name)
    return Split(text, {d: r for d, r in doms.items() if r}, dynamic, start=start)


def annotate(text, sp):
    """The base with each rule's domain as its trailing annotation (the planner's left bare)."""
    dom = {n: d for d, ns in sp.domains.items() for n in ns}
    dom.update({n: MODEL for n in sp.model})
    out = []
    for line in text.splitlines():
        s = line.strip()
        name = s.split()[0] if s and not s.startswith("%") and ":" in s and "-o" in s else None
        if name in dom:
            line = ANNOT.sub("", line).rstrip()
            if dom[name] != sp.planner:
                line += "   %% @%s" % dom[name]
        out.append(line)
    return "\n".join(out) + "\n"


# ── pruning ──
def never_firing(text, dynamic, start=START):
    """The rules that can never fire: one of the tokens they consume or read is produced by no rule
    and held by no start (`explore`: a guard nothing gives)."""
    decl = declarations(text)
    static = {n for n, (_, st) in decl.items() if st}
    tokens = {n for n in decl if n not in static and n not in dynamic}
    rules = [(n, rule_atoms(l)) for n, l in rules_of(text)]
    made, live = set(start), set()
    while True:                             # the fixpoint: a rule lives when every token it needs is made by a living rule or the start
        grew = False
        for name, (needs, reads, prods) in rules:
            if name not in live and all(k not in tokens or k in made for k in needs + reads):
                live.add(name)
                made.update(k for k in prods if k in tokens)
                grew = True
        if not grew:
            break
    return [name for name, _ in rules if name not in live]


# ── narrowing an activation's instance ──
def narrow(instance, keep):
    """The instance with each type in `keep` restricted to those members; every line naming a removed
    member (a static fact, a #init) dropped."""
    removed, out = set(), []
    for line in instance.splitlines():
        m = re.match(r"^type\s+(\w+)\s*\{([^}]*)\}\.\s*$", line.strip())
        if m and m.group(1) in keep:
            members = m.group(2).split()
            kept = [x for x in members if x in keep[m.group(1)]] or members[:1]
            removed.update(x for x in members if x not in kept)
            out.append("type %s {%s}." % (m.group(1), " ".join(kept)))
            continue
        out.append(line)
    if not removed:
        return instance
    res = []
    for line in out:
        s = line.strip()
        if s.startswith("#init "):
            m = re.match(r"^#init\s+(.+?)(?:\s+\d+)?\s*$", s)
            atom = m.group(1) if m else s[6:]
        elif s.endswith(".") and "(" in s and not s.startswith(("%", "type ", "include", "catalog", "provenance")):
            atom = s[:-1]
        else:
            res.append(line)
            continue
        if not (set(args_of(atom)) & removed):
            res.append(line)
    return "\n".join(res) + "\n"


def keep_for(sp, d, pool):
    """The things D's goals name: each goal token's arguments, by the token's declared types."""
    keep = {}
    for a, n in pool.items():
        if n > 0 and kind_of(a) in sp.goal.get(d, ()):
            types = sp.decl.get(kind_of(a), ([], False))[0]
            for t, x in zip(types, args_of(a)):
                keep.setdefault(t, set()).add(x)
    return keep


# ── the runner ──
class Hier:
    """The hierarchy of SP acting on the game through one host: each domain's base in its tree
    (RUN/trees/split/<D>/), each activation's instance narrowed to its goal's things."""

    def __init__(self, world, game, sp, run_dir, base_name):
        self.w, self.g, self.sp = world, game, sp
        self.root = Path(run_dir) / "trees" / "split"
        self.base_name = base_name
        self.inst = game.instance_text()
        for d in list(sp.domains) + ([MODEL] if sp.model else []):
            b = self.root / d / "base"
            b.mkdir(parents=True, exist_ok=True)
            (b / base_name).write_text(sp.base_of(d))
        self.k = 0

    def session(self, d, pool):
        """D's session for this activation: its narrowed instance (the goal's things), opened."""
        from metis.repl import Repl
        if d != self.sp.planner:
            keep = keep_for(self.sp, d, pool)
        else:                                    # the planner sees the task's own things (the world's planner_keep)
            pk = getattr(self.w, "planner_keep", None)
            keep = pk(self.inst) if callable(pk) else {}
        self.k += 1
        pkg = self.root / d / ("%s-%d" % (self.g.iid, self.k))
        if pkg.exists():
            shutil.rmtree(pkg)
        shutil.copytree(self.g.pkg, pkg)
        (pkg / self.g.path.name).write_text(narrow(self.inst, keep))
        return Repl.open(pkg / self.g.path.name)

    def feeds(self, ev, command):
        """Whether the event gives the domain that sends COMMAND (by its verb, the world's DOMAINS) one of
        its goal tokens: the guided replay's choice among the planner's bookkeeping."""
        verb = self.w._verb_of(command) if hasattr(self.w, "_verb_of") else None
        names = getattr(self.w, "DOMAINS", {}) or {}
        d = names.get(verb, verb)
        goals = self.sp.goal.get(d, set())
        return bool(goals) and any(kind_of(a) in goals for a in ev.produce)

    def ground(self, d, pool):
        r = self.session(d, pool)
        return len(r.shell.events_tbl)

    def start_pool(self):
        """The program's own tokens the instance starts with (#init lines of a token)."""
        pool = {}
        for line in self.inst.splitlines():
            s = line.strip().split()
            if len(s) >= 2 and s[0] == "#init" and kind_of(s[1]) in self.sp.tokens:
                pool[s[1]] = int(s[2]) if len(s) > 2 else 1
        return pool

    def activate(self, d, host, pool, rng, out, steps, guide=None):
        """One activation of D: its session's state the world's reading and the pool; its rules fired
        until quiet (or a result another domain takes is out); → (the new pool, the fired rows, why)."""
        r = self.session(d, pool)
        sh = r.shell
        mine = {a: n for a, n in pool.items() if n > 0 and _known(sh, a)}
        held = {a: n for a, n in pool.items() if n > 0 and a not in mine}   # tokens about things this instance does not see
        sh.counts = dict({a: n for a, n in host.reading().items() if n > 0}, **mine)
        k = len(sh.fired_rows)
        out_for_others = self.sp.out.get(d, set())
        why = acting.fire(self.w, host, sh, rng, out, steps,
                          stop=lambda s: any(kind_of(a) in out_for_others for a, n in s.counts.items() if n > 0
                                             and a not in pool), guide=guide, feeds=self.feeds)
        rows = [{"kind": kind, "produce": sorted(ev.produce)} for kind, _, ev in sh.fired_rows[k:]]
        new = {a: n for a, n in sh.counts.items() if n > 0 and kind_of(a) in self.sp.tokens}
        new.update(held)
        return new, rows, why

    def next_domain(self, host, pool, last, skip=(), handed=()):
        """The manual switch: the domain whose rules are enabled now — the ones that take what the last
        activation put out first (its results handed on), then the last one, the specialists, the
        planner (skip: domains whose narrowed activation fired nothing here)."""
        takers = [d for d in self.sp.domains if d != last and set(handed) & self.sp.goal.get(d, set())]
        order = takers + [last] + [d for d in self.sp.specialists if d != last] + [self.sp.planner]
        for d in dict.fromkeys(order):
            if d is None or d in skip:
                continue
            if self.enabled(d, host, pool):
                return d
        return None

    def enabled(self, d, host, pool):
        if not hasattr(self, "_probe"):
            self._probe = {}
        if d not in self._probe:
            self._probe[d] = self.session(d, {})
        sh = self._probe[d].shell
        sh.counts = dict({a: n for a, n in host.reading().items() if n > 0}, **{a: n for a, n in pool.items() if n > 0})
        return bool(sh._candidates())


def _known(sh, atom):
    """Whether the session's program knows the atom (some event consumes, reads or produces it)."""
    cache = getattr(sh, "_known_atoms", None)
    if cache is None:
        cache = set()
        for _, _, ev in sh.events_tbl:
            cache.update(ev.consume)
            cache.update(ev.produce)
            cache.update(getattr(ev, "persist", {}) or {})
        sh._known_atoms = cache
    return atom in cache


def run(game, sp, run_dir, base_name, steps=60, seed=1, director=None, max_activations=40, guide=None):
    """The hierarchy acting on the game: {commands, refused, won, steps, stuck, transitions,
    activations: [{domain, goal, results}], beats?, diverged?} — the manual switch, or with `director`
    (a DirectorLoop factory) the director's rules make it; with `guide` (the recorded commands) the
    records' replay (acting.fire's guide: the run must send them, in order)."""
    guide = list(guide) if guide is not None else None
    h = Hier(game, game, sp, run_dir, base_name)
    host = game._host_for(game.pkg)
    rng = random.Random(seed)
    out = acting.new_out(game.iid)
    out["activations"] = []
    pool = h.start_pool()
    try:
        if director is None:
            last, skip, handed = None, set(), ()
            for _ in range(max_activations):
                d = h.next_domain(host, pool, last, skip, handed)
                if d is None or host.won or out["stuck"]:
                    break
                goal = sorted(a for a, n in pool.items() if n > 0 and kind_of(a) in sp.goal.get(d, ()))
                pool, rows, why = h.activate(d, host, pool, rng, out, steps - out["steps"], guide)
                if why == "diverged":
                    out["diverged"] = True
                skip = skip | {d} if not rows else set()          # enabled whole, nothing once narrowed: the next one
                out["activations"].append({"domain": d, "goal": goal, "fired": len(rows),
                                           "results": sorted({a for r in rows for a in r["produce"] if kind_of(a) in sp.out.get(d, ())})})
                handed = {kind_of(a) for a in out["activations"][-1]["results"]}
                last = d
                if out["steps"] >= steps:
                    break
        else:
            out["beats"] = run_directed(h, host, pool, rng, out, steps, director, max_activations, guide)
        out["won"] = bool(host.won)
    finally:
        host.gym.close()
    return out


def run_directed(h, host, pool, rng, out, steps, make_loop, max_activations, guide=None):
    """The director's run: the planner first; every produced token of a port kind arrives; the
    director's beats wake, forward and sleep; a forward runs that domain next."""
    queue, beats = [h.sp.planner], []
    box = {"pool": pool}

    class Ops:
        def beat(self, name, lines):
            return h.director_beat(lines)

        def instance(self, d, goal):
            queue.append(d)

        def activate(self, d):
            pass

        def deactivate(self, d):
            pass

        def say(self, text, kind="line"):
            pass
    loop = make_loop(Ops())
    n = 0
    while queue and n < max_activations and not host.won and not out["stuck"] and loop.outcome is None:
        d = queue.pop(0)
        goal = sorted(a for a, k in box["pool"].items() if k > 0 and kind_of(a) in h.sp.goal.get(d, ()))
        box["pool"], rows, why = h.activate(d, host, box["pool"], rng, out, steps - out["steps"], guide)
        if why == "diverged":
            out["diverged"] = True
        out["activations"].append({"domain": d, "goal": goal, "fired": len(rows),
                                   "results": sorted({a for r in rows for a in r["produce"] if kind_of(a) in h.sp.out.get(d, ())})})
        loop.produced(d, {"fired": rows})
        loop.step()
        n += 1
    beats = [{k: b.get(k) for k in ("arrival", "effects", "goals")} for b in loop.log]
    return beats


# ── the director ──
def director_text(sp, base_rel, name="director"):
    """The director's instance from the split's ports (what gen_hier.director_facts writes by hand for
    ALFWorld): the roles, handles/2 (a specialist its goal kinds, the planner its result kinds),
    result/1, finished/1 and end/1, nohandler/1 for the rest; its start (the planner active)."""
    kinds = sorted(set().union(*sp.goal.values(), *sp.out.values()) | sp.finished | sp.ends)
    specs = sp.specialists
    facts = ["specialist(%s)" % d for d in specs] + ["planner(%s)" % sp.planner]
    handled = set()
    for d in specs:
        for k in sorted(sp.goal[d]):
            facts.append("handles(%s, %s)" % (d, k))
            handled.add(k)
    results = sorted(set().union(*(sp.out[d] for d in specs)) if specs else set())
    for k in results:
        facts.append("handles(%s, %s)" % (sp.planner, k))
        handled.add(k)
    facts += ["result(%s)" % k for k in results]
    facts += ["finished(%s)" % k for k in sorted(sp.finished)] + ["end(%s)" % k for k in sorted(sp.ends)]
    facts += ["nohandler(%s)" % k for k in kinds if k not in handled and k not in sp.finished and k not in sp.ends]
    lines = ["% " + name + " — the director over the loop's split (generated by pi/policy/hier.py from its ports).",
             "catalog %s 1." % name,
             'provenance text "generated from the split base\'s ports (loop-policy step 2b)" "2026-10-22".',
             'include "%s".' % base_rel,
             "type domain {%s}." % " ".join(sorted(sp.domains)), "type kind {%s}." % " ".join(kinds), ""]
    lines += [f + "." for f in facts] + [""]
    lines += ["#init active(%s) 1" % sp.planner, "#init attention(%s) 1" % sp.planner, "#init fresh 1"]
    lines += ["#init inactive(%s) 1" % d for d in specs]
    return "\n".join(lines) + "\n", kinds


def director_loop_class():
    """metis-agent's DirectorLoop (py/metis_agent/director.py), by its file: the agent's own frames."""
    d = Path(__file__).resolve()
    for _ in range(8):
        d = d.parent
        c = d / "metis-agent" / "py" / "metis_agent" / "director.py"
        if c.exists():
            spec = importlib.util.spec_from_file_location("metis_agent_director", c)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("no metis-agent checkout beside this one (py/metis_agent/director.py)")


class DirectorSession:
    """The director's program as a session: world lines in, its rules fired, its out atoms reported
    and retracted (DirectorHost.tick's way)."""

    def __init__(self, path):
        from metis.repl import Repl
        self.r = Repl.open(path)

    def beat(self, lines):
        sh = self.r.shell
        for l in lines:
            a = l.strip().lstrip("+").split()[0]
            sh.counts[a] = sh.counts.get(a, 0) + 1
        k = len(sh.fired_rows)
        while sh._candidates():
            sh._fire(sh._candidates()[0][0])
            if len(sh.fired_rows) - k > 50:
                break
        rows = [{"kind": kind, "produce": sorted(ev.produce)} for kind, _, ev in sh.fired_rows[k:]]
        sh.counts = {a: n for a, n in sh.counts.items() if n > 0 and kind_of(a) not in OUT_KINDS}
        return [{"fired": rows}]


def director_factory(sp, run_dir, director_base=None, text=None):
    """A DirectorLoop factory over the director (TEXT, else generated from the split's ports; its
    session in RUN/trees/split/director/) → (make, text)."""
    mod = director_loop_class()
    d = Path(run_dir) / "trees" / "split" / "director"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(director_base or director_base_path(), d / "director_domain.llp")
    gen, kinds = director_text(sp, "director_domain.llp")
    text = text or gen
    m = re.search(r"^type\s+kind\s*\{([^}]*)\}", text, re.M)
    kinds = m.group(1).split() if m else kinds
    (d / "director.llp").write_text(text)
    facts = mod.director_facts(text)

    def make(ops):
        sess = DirectorSession(d / "director.llp")

        class Bound(type(ops)):
            def beat(self, name, lines):
                return sess.beat(lines)
        bound = Bound()
        return mod.DirectorLoop("director", facts, [k for k in kinds], bound)
    return make, text


def split_vector(game, sp, run_dir, base_name, steps=60):
    """Σ over the domains of rules + the events its instance grounds, each specialist at the narrowing
    of its first activation in the game's manual run (the planner whole): the split's complexity."""
    out = run(game, sp, run_dir, base_name, steps=steps, seed=1)
    h = Hier(game, game, sp, run_dir, base_name)
    total, seen = 0, set()
    for act in out["activations"]:
        d = act["domain"]
        if d not in seen:
            seen.add(d)
            total += len(sp.domains[d]) + h.ground(d, {a: 1 for a in act["goal"]})
    for d in sp.domains:
        if d not in seen:
            total += len(sp.domains[d]) + h.ground(d, {})
    if sp.model:                                 # nina's N2: the world model's rules count, though they never act
        total += len(sp.model) + h.ground(MODEL, {})
    return total


def director_base_path():
    """The lifted director (DIRECTOR.md; world-neutral): its canonical home, metis-catalog
    domains/director/ (the architect's G5 ruling: the catalog is the domains' repo), else the worlds'
    copy (metis-worlds alfworld/domains/director_domain.llp)."""
    d = Path(__file__).resolve()
    for _ in range(8):
        d = d.parent
        for c in (d / "metis-catalog" / "domains" / "director" / "director_domain.llp",
                  d / "metis-worlds" / "alfworld" / "domains" / "director_domain.llp"):
            if c.exists():
                return c
    raise SystemExit("no lifted director beside this checkout (metis-catalog domains/director/, or metis-worlds alfworld/domains/)")
