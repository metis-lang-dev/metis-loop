"""The refactor's product as a TICK TREE (policy-tuning-2 s-e075f47f step 1; brief v2 §A; skill v2 points 11-13): the
loop's split base (hier.Split: one base, each rule's domain its annotation) written as a COMPOSITION the tick runtime
runs and `metisc --interface` checks — the road's shape (metis-catalog domains/road), never a hand-written director:

    ROOT/domains/composition.yaml            capacity, protocol, interfaces, specialists, direct, response, world
    ROOT/domains/tick_types.llp              type domain {the members}. type resource {motion …}.
    ROOT/domains/capacity.llp                the world's types and static facts (the instance's, its start apart)
    ROOT/domains/<m>_domain.llp              member m's base: its own rules, the tick's rules generated beside them
    ROOT/domains/<m>/<m>.llp, domain.yaml    its program (the base, the capacity, the tick types) and manifest
    ROOT/domains/tree_director/              the GENERIC tree director's instance (metispy's iface/director_tree_domain.llp):
                                             its members, priority(specialist, planner), the hysteresis, the resources
    ROOT/domains/iface/<family>.llp          the family's crossing preds (iface_gen's form, from the split's ports)

The catalog's domains/ is the composition's package (as alfworld's domains/hier/ is): the flat base stays in
domains/<world>/, the routing director (the direct move's) in domains/director/.

The members trigger themselves (the road style, the architect's Q1 ruling): a specialist takes a goal kind it reads
($g(…)) in a BEGIN rule (idle → busy, tick__active, tick__want for each resource it needs), its command rules read
$tick__grant(D, R), and the rule that finishes the goal (puts a result out, or consumes the goal for good) gives back
idle with tick__done (tick__stuck on a refusal) and tick__release; the cancels are metis.catalog.protocol_stub's. The
planner holds no resource: it reports tick__active as it takes its start and tick__done / tick__stuck at its ends.
Every rule and line this module writes is marked GENERATED (`% @gen`, the iface move's convention), so the card can
tell the tick's rules from the brain's; a rule the brain already wrote with a tick__ atom is kept as it is.

    comp = compose(sp, world, root, capacity_text, start=…)      → Composition (paths, members, resources)
    rep = interface(comp.path, metisc, home)                      → {"errors", "warnings", "notes", "rc", "listing"}
"""
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .alfworld import kind_of, rules_of
from .hier import ANNOT, rule_atoms

DIRECTOR = "tree_director"
GEN = "% @gen"                       # a generated rule or line (the tick's, this module's)
RESOURCE = "motion"                  # the body: one member moves or handles at a time (Q1: one resource per world)
SECOND = ("hands", "hands2", "hands3")   # added on an I4 two-writer finding (Q1's addition)
HOLD_GRANT, HOLD_STATUS, AGES = 2, 1, 4  # the road's hysteresis: k = 2, m = 1 (brief §9 rule 4)
RESPONSE = 2                         # ρ under the generic tree director (spec/15 amendment 6)
DIRECTOR_SHARED = ("tick__want: in, tick__release: in, tick__status: in, tick__active: in, tick__done: in, tick__stuck: in, "
                   "tick__grant: out, tick__revoke: out, tick__goal: out, tick__cancel: out, tick__stop: in")


@dataclass
class Composition:
    path: Path                                    # composition.yaml
    members: list                                 # the planner first, then the specialists (the tick's stage order)
    planner: str
    resources: dict                               # resource → the members that hold it
    generated: dict = field(default_factory=dict)  # member → the names of the rules this module wrote
    commands: list = field(default_factory=list)   # the command rules (world.in)


def _sends(world, name):
    """Whether rule NAME sends the world a command (its name in the host's table, or `verb[_why]`)."""
    _, commands, verbs = world.vocabulary()
    return name in commands or bool(verbs and name.split("_")[0] in verbs)


def _body(line):
    """A rule line → (pre `NAME [dyn] : `, left, right, trailing comment)."""
    s = ANNOT.sub("", line).rstrip()
    m = re.match(r"^(\s*\w+\s*\[\w+\]\s*:\s*)(.*?)\s+-o\s+(.*?)\.(\s*%.*)?$", s)
    return (m.group(1), m.group(2), m.group(3), m.group(4) or "") if m else None


def _has_tick(line):
    return "tick__" in line


def member_base(sp, d, world, holds, ends=(), start=()):
    """D's base (sp.base_of) with the tick's rules (the road style): see the module's doc. HOLDS: the resources D needs
    → {resource: [the rule names it gates]} (motion: every command rule)."""
    text = sp.base_of(d)
    planner = d == sp.planner
    goals = sorted(sp.goal.get(d, ()))
    results = set(sp.out.get(d, ())) - set(goals)
    decl = sp.decl
    out, gen = [], []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("namespace ") and not planner:
            out.append(line)
            ns = s.split()[1]
            out += ["pred idle : %s.   %s: no goal taken" % (ns, GEN), "pred busy : %s.   %s: a goal taken (reported active once)" % (ns, GEN)]
            continue
        if s == "stage act {":
            out.append(line)
            if not planner:
                for g in goals:
                    args = ", ".join("X%d" % i for i in range(len(decl.get(g, ([], False))[0])))
                    want = "".join(" * tick__want(%s, %s)" % (d, r) for r in sorted(holds))
                    name = "begin_%s" % g
                    out += ["  %%%% I take my goal, %s." % g,
                            "  %s [dyn] : $%s%s * idle -o busy * tick__active(%s)%s.   %s" % (
                                name, g, "(%s)" % args if args else "", d, want, GEN)]
                    gen.append(name)
            continue
        b = _body(line) if s and not s.startswith("%") and "-o" in s else None
        if b is None or _has_tick(line):
            out.append(line)
            continue
        pre, left, right, tail = b
        name = pre.split()[0]
        needs, reads, prods = rule_atoms(line)
        add_l, add_r = [], []
        if planner:
            if any(k in start for k in needs):
                add_r.append("tick__active(%s)" % d)
            if any(k in sp.finished for k in prods):
                add_r.append("tick__done(%s)" % d)
            elif any(k in ends for k in prods):
                add_r.append("tick__stuck(%s)" % d)
        else:
            for r, gated in sorted(holds.items()):
                if name in gated:
                    add_l.append("$tick__grant(%s, %s)" % (d, r))
            took = [k for k in needs if k in goals and k not in prods]
            made = [k for k in prods if k in results]
            if took or made:
                add_l.append("busy")
                fail = any(k in ends for k in prods)
                add_r += ["idle", "tick__%s(%s)" % ("stuck" if fail else "done", d)]
                add_r += ["tick__release(%s, %s)" % (d, r) for r in sorted(holds)]
        if not add_l and not add_r:
            out.append(line)
            continue
        l2 = " * ".join([left] + add_l)
        r2 = " * ".join(([] if right.strip() == "()" else [right]) + add_r) or "()"
        out.append("%s%s -o %s.%s   %s" % (pre, l2, r2, tail, GEN))
        gen.append(name)
    t = "\n".join(out)
    t = _with_protocol(t)
    t, cancels = _with_cancels(t, d, goals if not planner else [], ends if planner else (), planner)
    return t, gen + cancels


def _with_protocol(text):
    """The protocol module included once, after the base's header (its `stages`, else its `layers` line)."""
    inc = 'include "iface/protocol_domain.llp".'
    if inc in text:
        return text
    lines = text.split("\n")
    at = next((i for i, l in enumerate(lines) if l.strip().startswith("stages ")), None)
    at = at if at is not None else next((i for i, l in enumerate(lines) if l.strip().startswith("layers ")), 0)
    return "\n".join(lines[:at + 1] + ["%s   %s: the tick's reports and grants" % (inc, GEN)] + lines[at + 1:])


def _with_cancels(text, d, goals, ends, planner):
    """The stop's cancels (metis.catalog.protocol_stub.cancel_rules), after the begin rules (the planner: first)."""
    from metis.catalog import protocol_stub
    home = protocol_stub.__file__
    decls = (Path(home).parent / "iface" / "protocol_domain.llp").read_text()
    m = re.search(r"^namespace (\w+)", text, re.M)          # the loop's one base: its namespace, not the member's name
    try:
        rules = protocol_stub.cancel_rules(text, d, goals, ends=list(ends), decls=decls, namespace=m.group(1) if m else None)
    except protocol_stub.StubError:
        return text, []
    if not rules:
        return text, []
    names = [re.match(r"\s*(\w+)", l).group(1) for l in rules if not l.strip().startswith("%")]
    block = [protocol_stub.BEGIN] + rules + [protocol_stub.END]
    lines = text.split("\n")
    i = max((k for k, l in enumerate(lines) if re.match(r"\s*begin_\w+ \[dyn\]", l)), default=None)
    if i is None:
        i = next(k for k, l in enumerate(lines) if l.strip() == "stage act {")
    return "\n".join(lines[:i + 1] + block + lines[i + 1:]), names


def crossing(sp, start=()):
    """The tokens that cross between members: a goal kind another member puts out, a result another takes (a start
    token only the planner takes stays its own)."""
    made = {k for d in sp.domains for k in sp.makes.get(d, ())}
    return {k for d in sp.domains for k in sp.goal.get(d, ()) if k in made} | \
        {k for d in sp.domains for k in sp.out.get(d, ())}


def shared_of(sp, d, world, holds, base_text, cross):
    """D's manifest `shared`: the world's readings world-private, its goal kinds in, its results out (the crossing
    ones), the protocol's reports and grants it uses, its resources."""
    dyn = world.vocabulary()[0]
    used = set()
    for _, line in rules_of(base_text):
        n, r, p = rule_atoms(line)
        used.update(n + r + p)
    sh = {}
    for p in sorted(used & set(dyn)):
        sh[p] = "world-private"
    for p in sorted(set(sp.goal.get(d, ())) & cross):
        sh[p] = "in"
    for p in sorted(set(sp.out.get(d, ())) - set(sp.goal.get(d, ())) & cross):
        sh[p] = "out"
    reports = [r for r in ("tick__active", "tick__done", "tick__stuck") if "%s(" % r in base_text]
    if holds:
        reports += ["tick__want", "tick__release"]
    for p in reports:
        sh[p] = "out"
    if holds:
        sh["tick__grant"] = "in"
    if "tick__cancel(" in base_text:
        sh["tick__cancel"] = "in"
    for r in sorted(holds):
        sh[r] = "resource"
    return sh


def director_text(members, specialists, planner, resources):
    """The generic tree director's instance (the road's road_director.llp, generated): its members, priority(each
    specialist, the planner), the hysteresis (k = HOLD_GRANT, m = HOLD_STATUS), the resources free."""
    ages = ["a%d" % i for i in range(AGES)]
    lines = ["% tree_director — the generic tree director over the loop's composition (generated by pi/policy/compose.py).   " + GEN,
             "catalog tree_director 1.",
             'provenance text "the generic tree director over the loop\'s members (policy-tuning-2 step 1)" "2026-10-26".',
             'include "iface/director_tree_domain.llp".', 'include "../tick_types.llp".', "",
             "type kind {none}.                         % it routes nothing: the members trigger themselves",
             "bwd specialist(domain)."]
    lines += ["specialist(%s)." % m for m in members]
    lines += ["priority(%s, %s)." % (s, planner) for s in specialists]
    lines += ["young_grant(%s)." % a for a in ages[:HOLD_GRANT]] + ["mature_grant(%s)." % a for a in ages[HOLD_GRANT:]]
    lines += ["mature_status(%s)." % a for a in ages[HOLD_STATUS:]] + [""]
    lines += ["#init free(%s) 1" % r for r in sorted(resources)]
    lines += ["#init offpath(%s) 1" % m for m in members] + ["#init nowant(%s) 1" % m for m in members]
    lines += ["#init nolate(%s) 1" % m for m in members] + ["#init age_of(%s, a0) 1" % m for m in members]
    lines += ["#init issue(%s, t0) 1" % r for r in sorted(resources)] + ["#init serving(%s, t0) 1" % r for r in sorted(resources)]
    lines += ["#steps 6", "#seeds 1"]
    return "\n".join(lines) + "\n"


def iface_text(sp, family, preds):
    """The family's interface package (metis-worlds tools/iface_gen.py's form): PREDS declared once, in its namespace."""
    sigs = {p: sp.decl[p][0] for p in sorted(preds)}
    types = sorted({t for s in sigs.values() for t in s})
    lines = ["%% %s — the %s family's interface package: the preds that cross between its members (generated by pi/policy/"
             "compose.py from the split's ports). Declaration only.   %s" % (family, family, GEN),
             "catalog %s_iface 1." % family,
             'provenance text "the %s family\'s crossing preds, from the split\'s ports" "2026-10-26".' % family]
    lines += ["types (%s)." % " ".join(types)] if types else []
    lines += ["", "namespace %s_iface produce (dyn).", ""]
    lines[-2] = lines[-2] % family
    lines += ["pred %s%s : %s_iface." % (p, "(%s)" % ", ".join(s) if s else "", family) for p, s in sigs.items()]
    return "\n".join(lines) + "\n"


def strip(text, preds, family):
    """TEXT without its declarations of PREDS, the family package included after the protocol's (iface_gen.strip)."""
    inc = 'include "iface/%s.llp".   %s: the family\'s crossing preds, declared once' % (family, GEN)
    out = []
    for line in text.split("\n"):
        m = re.match(r"^\s*pred (\w+)", line)
        if m and m.group(1) in preds:
            continue
        out.append(line)
        if line.startswith('include "iface/protocol_domain.llp".'):
            out.append(inc)
    return "\n".join(out)


def flow(d):
    return "{%s}" % ", ".join("%s: %s" % kv for kv in d.items())


def compose(sp, world, root, capacity_text, start=(), holds_extra=None, display=""):
    """SP written as the composition under ROOT/domains/tree/ (see the module's doc). CAPACITY_TEXT: the world's types
    and statics (capacity_of). HOLDS_EXTRA: {resource: {member: [rule names]}} added on an I4 finding. → Composition."""
    tree = Path(root) / "domains"
    tree.mkdir(parents=True, exist_ok=True)
    specialists = [d for d in sp.domains if d != sp.planner]
    members = [sp.planner] + specialists
    holds, resources = {}, {}
    for d in specialists:
        cmds = [n for n in sp.domains[d] if _sends(world, n)]
        if cmds:
            holds.setdefault(d, {})[RESOURCE] = cmds
            resources.setdefault(RESOURCE, []).append(d)
    for r, by in (holds_extra or {}).items():
        for d, names in by.items():
            holds.setdefault(d, {})[r] = names
            resources.setdefault(r, []).append(d)
    if not resources:
        resources[RESOURCE] = []
    (tree / "capacity.llp").write_text(capacity_text)
    (tree / "tick_types.llp").write_text(
        "%% tick_types — the composition's members and resources (generated by pi/policy/compose.py).   %s\n"
        "catalog tick_types 1.\ntype domain {%s}.\ntype resource {%s}.\n" % (GEN, " ".join(members), " ".join(sorted(resources))))
    comp = Composition(tree / "composition.yaml", members, sp.planner, resources)
    world_out, commands = set(), []
    cross = crossing(sp, start)
    family = getattr(world, "DOMAIN", "loop")
    if cross:
        (tree / "iface").mkdir(exist_ok=True)
        (tree / "iface" / ("%s.llp" % family)).write_text(iface_text(sp, family, cross))
        (tree / "iface" / ("%s.yaml" % family)).write_text(
            "# %s — the natures of the family's crossing preds (spec/15 I11; generated by pi/policy/compose.py)\n"
            "nature: {%s}\n" % (family, ", ".join("%s: signal" % p for p in sorted(cross))))
    for d in members:
        base, gen = member_base(sp, d, world, holds.get(d, {}), ends=sorted(sp.ends), start=start)
        if cross:
            base = strip(base, cross, family)
        comp.generated[d] = gen
        (tree / ("%s_domain.llp" % d)).write_text(base)
        pkg = tree / d
        pkg.mkdir(exist_ok=True)
        (pkg / ("%s.llp" % d)).write_text(
            "%% %s — the loop's %s member (generated by pi/policy/compose.py).   %s\ncatalog %s 1.\n"
            'include "../%s_domain.llp".\ninclude "../capacity.llp".\ninclude "../tick_types.llp".\n%s#steps 6\n#seeds 1\n'
            % (d, d, GEN, d, d, "" if d == sp.planner else "#init idle 1\n"))
        sh = shared_of(sp, d, world, holds.get(d, {}), base, cross)
        world_out.update(p for p, v in sh.items() if v == "world-private")
        commands += [n for n in sp.domains[d] if _sends(world, n)]
        st = {"success": ["tick__done"] if "tick__done" in sh else [], "failure": ["tick__stuck"] if "tick__stuck" in sh else []}
        (pkg / "domain.yaml").write_text(
            "# %s — the loop's %s member (generated by pi/policy/compose.py)\nprogram: %s.llp\nhost: %s\nclock: {beats: 1}\n"
            "display: %s\nline: \"%s\"\nshared: %s\nstatus: {success: [%s], failure: [%s]}\n%s"
            % (d, d, d, getattr(world, "HOST", "host.py:make"), display or d, d, flow(sh), ", ".join(st["success"]),
               ", ".join(st["failure"]), "" if d == sp.planner else "gating: program\n"))
    ddir = tree / DIRECTOR
    ddir.mkdir(exist_ok=True)
    (ddir / ("%s.llp" % DIRECTOR)).write_text(director_text(members, specialists, sp.planner, resources))
    res = ", ".join("%s: {count: 1, free: free, held_by: [holder]}" % r for r in sorted(resources))
    (ddir / "domain.yaml").write_text(
        "# tree_director — the generic tree director (generated by pi/policy/compose.py)\nprogram: tree_director.llp\nhost: pass_host.py:make\n"
        "clock: {beats: 1}\ndisplay: the director\nline: \"who holds the body, the specialists before the plan\"\n"
        "shared: {%s}\nresources: {%s}\n" % (DIRECTOR_SHARED, res))
    comp.commands = commands
    comp.world_out = sorted(world_out)
    comp.interfaces = ["iface/%s.llp" % family] if cross else []
    _write_composition(comp, comp.interfaces)
    return comp


def _write_composition(comp, interfaces):
    comp.path.write_text(
        "# composition — the loop's split as a tick tree (generated by pi/policy/compose.py)\n"
        "capacity: capacity.llp\nprotocol: iface/protocol_domain.llp\n%sspecialists: [%s]\ndirect: %s\nresponse: %d\n"
        "world: {out: [%s], in: [%s]}\n" % (
            "interfaces: [%s]\n" % ", ".join(interfaces) if interfaces else "", ", ".join(comp.members), DIRECTOR, RESPONSE,
            ", ".join(comp.world_out + ["tick__stop"]), ", ".join(comp.commands)))


def capacity_of(instance_text):
    """The world's types and static facts from a game's instance: its `type` lines and its facts, without its header,
    its includes, its start (#init) and its directives."""
    keep = ["% capacity — the world's types and static facts, from a discovery game's instance (pi/policy/compose.py).   " + GEN,
            "catalog capacity 1."]
    for line in instance_text.splitlines():
        s = line.strip()
        if not s or s.startswith(("%", "#", "include", "catalog", "provenance")):
            continue
        keep.append(line)
    return "\n".join(keep) + "\n"


# ── the interface check as a gate step ──
RESULT = re.compile(r"^result (\d+) error\(s\), (\d+) warning\(s\), (\d+) note\(s\)")


def interface(path, metisc, home, timeout=120):
    """`metisc --interface PATH` (METIS_HOME: HOME, the protocol and the generic director's package root) → {"rc",
    "errors", "warnings", "notes", "counts", "listing"}: every finding line as metisc prints it."""
    import os
    env = dict(os.environ, METIS_HOME=str(home))
    p = subprocess.run([str(metisc), "--interface", str(Path(path).name)], capture_output=True, text=True,
                       cwd=str(Path(path).parent), env=env, timeout=timeout)
    lines = (p.stdout + p.stderr).splitlines()
    out = {"rc": p.returncode, "errors": [l for l in lines if l.startswith("error ")],
           "warnings": [l for l in lines if l.startswith("warning ")], "notes": [l for l in lines if l.startswith("note ")],
           "listing": lines}
    m = next((RESULT.match(l) for l in lines if RESULT.match(l)), None)
    out["counts"] = [int(x) for x in m.groups()] if m else [len(out["errors"]) or 1, len(out["warnings"]), len(out["notes"])]
    return out


def two_writers(rep):
    """The I4 findings of two writers of a state pred → [(pred, [members])]."""
    out = []
    for l in rep["errors"]:
        m = re.match(r"^error I4 (\w+): ([\w, ]+) are all writers", l)
        if m:
            out.append((m.group(1), [x.strip() for x in m.group(2).split(",")]))
    return out
