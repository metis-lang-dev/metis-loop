"""The policy driver's world: ALFWorld through its host (metis-worlds alfworld/world/alf_host.py).

A game is an INSTANCE package (the world's gen_instance: its types, static facts, task and start)
that includes the base the loop is building (`../base/alf.llp`, beside the game's directory in a
TREE: the current base's, or a candidate's). The world is the host's: its gym child steps the text
game, its reading is the dynamic facts. Nothing here writes a rule.

    w = AlfWorld(game_dir, tree)                 # the instance generated into TREE/<iid>/
    w.open(); w.actions()                        # [{verb, args, command}]: the admissible commands the host can send
    rec = w.step(command)                        # the TRANSITION: before, action, command, after, added, removed, text
    s = w.snapshot(); …; w.restore(s)            # the commands so far, replayed from the reset
    out = w.act(program_tree, steps)             # the kernel acting (the host attached): commands, refusals, won

The host's vocabulary is its command table (alf_host.COMMANDS): a rule named after an entry (its
base before `[`), with that entry's variables bound, is a command — go* binds L2 (the location) and
R or O, open* R, take* O and R, put* O and R. That table is the world's, and the brain is told it.
"""
import json
import os
import shutil
import sys
from pathlib import Path

VERBS = {"go": ("go", ("R", "L2")), "open": ("open", ("R",)), "take": ("take", ("O", "R")), "put": ("put", ("O", "R"))}


def world_dir():
    """metis-worlds/alfworld/world: $METIS_ALF_WORLD, else the sibling checkout."""
    p = os.environ.get("METIS_ALF_WORLD")
    if p:
        return Path(p)
    d = Path(__file__).resolve()
    for _ in range(6):
        d = d.parent
        c = d / "metis-worlds" / "alfworld" / "world"
        if c.is_dir():
            return c
    raise SystemExit("set METIS_ALF_WORLD to metis-worlds/alfworld/world")


def _world():
    w = str(world_dir())
    if w not in sys.path:
        sys.path.insert(0, w)
    import alf_host
    import families
    import gen_instance
    return alf_host, gen_instance, families


def base_source():
    """The world's flat base (alfred_domain.llp): its declarations are the loop's start, its
    rules the hand reference it is compared with."""
    return (world_dir().parent / "domains" / "alfred_domain.llp").read_text()


# the policy's tokens the instance's start needs declared (#init unchosen, #query placed); the
# hand base's other tokens (want, carrying, arrived, seeking) are its policy, not the world's
KEEP_TOKENS = ("unchosen", "placed")


def empty_base(name="alf"):
    """The EMPTY domain (POLICY.md: the generator emits types, static facts and the task, no
    rules): the hand base's header and declarations — the game's facts, the dynamic facts the
    host reads, the two tokens the instance's start names — and an empty stage."""
    out, in_stage, tokens = [], False, False
    for line in base_source().splitlines():
        s = line.strip()
        if s.startswith("catalog "):
            out.append("catalog %s 1." % name)
            continue
        if s.startswith("provenance "):
            out.append('provenance text "the loop\'s base: the empty domain over ALFWorld\'s facts (loop-policy)" "2026-10-22".')
            continue
        if s.startswith("% ── the policy's own tokens"):
            tokens = True
            out.append("% ── the tokens the instance's start names (the rest is the loop's to declare) ──")
            continue
        if tokens and s.startswith("pred "):
            if s.split()[1].split("(")[0].rstrip(":").strip() in KEEP_TOKENS:
                out.append(line.split("%")[0].rstrip())
            continue
        if s.startswith("stage act {"):
            in_stage = True
            out.append("stage act {")
            continue
        if in_stage:
            if s == "}":
                out.append("}")
                in_stage = False
            continue
        if tokens and not s:
            tokens = False
        if line.startswith("%") and not out:
            continue
        out.append(line)
    head = ["% alf — the loop's base (loop-policy step 2): ALFWorld's facts as the hand base declares them,",
            "% no rule. The loop writes the rules: from the transitions (explore), the surprises (exploit),",
            "% and the hierarchy (refactor), each through the experimental gate."]
    return "\n".join(head + out).rstrip() + "\n"


def rules_of(text):
    """The rule lines of a base's stage blocks: [(name, line)]."""
    out, in_stage = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("stage ") and s.endswith("{"):
            in_stage = True
            continue
        if in_stage and s == "}":
            in_stage = False
            continue
        if in_stage and s and not s.startswith("%") and ":" in s:
            out.append((s.split()[0], s))
    return out


def kind_of(atom):
    return atom.split("(", 1)[0].strip()


def args_of(atom):
    i = atom.find("(")
    return [x.strip() for x in atom[i + 1:atom.rindex(")")].split(",")] if i >= 0 else []


def rule_verb(name, commands, verbs=None):
    """A fired rule's name (`go[R=…,L2=…]`) → (verb, bindings) when the host sends a command for
    it, else None (a rule of the policy's own tokens). The host's table first; else, when the host
    has the convention (alf_host.VERBS: `verb` or `verb_why`), the name's first token — a go there
    may leave L2 to the host (it reads the receptacle's location)."""
    base, _, rest = name.partition("[")
    base = base.split("-")[0]
    spec, optional = commands.get(base), ()
    if not spec and verbs:
        spec = verbs.get(base.split("_")[0])
        optional = ("L2",) if spec and spec[0] == "go" else ()
    if not spec:
        return None
    b = {}
    for kv in rest.rstrip("]").split(",") if rest else []:
        k, _, v = kv.partition("=")
        b[k.strip()] = v.strip()
    if not all(v in b for v in spec[1:] if v not in optional):     # the command needs the entry's variables bound (nina's N3)
        return None
    return spec[0], b


class AlfWorld:
    # the specialists SPLIT names by the host verb their rules send (hier.split_by_verb; HIERARCHY.md's names)
    DOMAINS = {"go": "nav", "open": "access", "take": "grasp", "put": "place"}

    @staticmethod
    def planner_keep(instance_text):
        """The planner's narrowing (hier.Hier.session): the objects the task names (its target(O) facts),
        as alf-hierarchy's task instance sees its targets; the receptacles stay whole."""
        objs = {l.strip()[len("target("):-2] for l in instance_text.splitlines() if l.strip().startswith("target(")}
        return {"object": objs} if objs else {}

    DOMAIN = "alf"
    VIEW = False                         # the world "alfworld_view" (AlfViewWorld): the robot sees only what stands before it
    HOST = "alf_host.py:make"            # a composition member's host (metis-worlds alfworld/world, its package shim)
    DESCRIPTION = "a household world (ALFWorld)"
    SPLITS = {"discovery": "train", "gate": "valid_seen", "heldout": "valid_unseen"}
    VERB_TEXT = {"go": "go to the receptacle at location L2 (R, or the one holding O)", "open": "open R", "take": "take O from R", "put": "put O in/on R"}

    @classmethod
    def vocabulary(cls):
        """(the host's dynamic predicates, its command table, its verb convention)."""
        alf_host, _, _ = _world()
        return set(alf_host.DYNAMIC_PREDS), alf_host.COMMANDS, getattr(alf_host.AlfHost, "VERBS", None)

    @staticmethod
    def task_facts(instance_text):
        return [l.strip()[:-1] for l in instance_text.splitlines() if l.strip().startswith(("target(", "dest(")) and l.strip().endswith(".")]

    def __init__(self, game_dir, tree, max_steps=60):
        alf_host, gen_instance, _ = _world()
        self.alf_host, self.game_dir = alf_host, str(game_dir)
        self.tree = Path(tree)
        self.iid = gen_instance.instance_id(self.game_dir)
        self.pkg = self.tree / self.iid
        if not (self.pkg / ("%s.llp" % self.iid)).exists():
            self.tree.mkdir(parents=True, exist_ok=True)
            gen_instance.generate(self.game_dir, str(self.tree), domain_rel="../base/alf.llp")
            gj = self.pkg / "game.json"                          # the loop's instance: a rule named verb_why is a command (alf_host's opt-in)
            meta = json.loads(gj.read_text()); meta["verbs"] = True; gj.write_text(json.dumps(meta, indent=1))
        self.path = self.pkg / ("%s.llp" % self.iid)
        self.max_steps, self.host, self.commands = max_steps, None, []

    @classmethod
    def sample(cls, split, family, n, seed=1):
        _, _, families = _world()
        return families.sample(cls.SPLITS.get(split, split), family, n, seed)

    def into(self, tree):
        """This game's instance in another tree (a candidate's): copied, the include the same."""
        dst = Path(tree) / self.iid
        if not dst.exists():
            shutil.copytree(self.pkg, dst)
        return dst / ("%s.llp" % self.iid)

    def instance_text(self):
        return self.path.read_text()

    # ── the game ──
    def open(self):
        if self.host is None:
            self.host = self._host_for(self.pkg)
            self.from_name = {v: k for k, v in self.host.to_name.items()}
            self.loc_of = {r: l for l, rs in self.host.recat.items() for r in rs}
        return self

    def close(self):
        if self.host is not None:
            self.host.gym.close()
            self.host = None

    def reset(self):
        self.open()
        self.host._take(self.host.gym.call("reset"))
        self.host.done = self.host.won = False
        self.commands = []

    def reading(self):
        return sorted(a for a, n in self.host.reading().items() if n > 0)

    @property
    def won(self):
        return bool(self.host and self.host.won)

    @property
    def done(self):
        return bool(self.host and self.host.done)

    @property
    def text(self):
        return self.host.obs if self.host else ""

    def action_of(self, command):
        """An admissible command's text → {verb, args, command} in the host's handles; None for a
        command the host's table cannot send (look, examine, close, use, …)."""
        h = self.from_name.get
        c = command.strip()
        if c.startswith("go to "):
            r = h(c[6:])
            return r and {"verb": "go", "args": {"R": r, "L2": self.loc_of.get(r)}, "command": c}
        if c.startswith("open "):
            r = h(c[5:])
            return r and {"verb": "open", "args": {"R": r}, "command": c}
        for word, verb, sep in (("take ", "take", " from "), ("move ", "put", " to ")):
            if c.startswith(word) and sep in c:
                o, r = c[len(word):].split(sep, 1)
                o, r = h(o), h(r)
                return o and r and {"verb": verb, "args": {"O": o, "R": r}, "command": c}
        return None

    def actions(self):
        return [a for a in (self.action_of(c) for c in self.host.admissible) if a]

    def unadmissible(self, rng, k=2):
        """k commands the host can send that the game does not list now, at the receptacles where the
        agent is (take what is in one, put what is held, open one): the refusals a gate split's walk
        records (a refused command changes nothing, so no restore is needed)."""
        name = self.host.to_name
        dyn = set(self.reading())
        here = next((args_of(a)[0] for a in dyn if a.startswith("at(")), None)
        recs = sorted(r for r, l in self.loc_of.items() if l == here)      # where the agent is: a refusal elsewhere says nothing
        held = [args_of(a)[0] for a in dyn if a.startswith("holds(")]
        inr = [args_of(a) for a in dyn if a.startswith("inrecep(")]
        cands = ["open " + name[r] for r in recs]
        cands += ["take %s from %s" % (name[o], name[r]) for o, r in inr if o in name and r in recs]
        cands += ["move %s to %s" % (name[o], name[r]) for o in held for r in recs]
        adm = set(self.host.admissible)
        cands = [c for c in cands if c not in adm]
        rng.shuffle(cands)
        return cands[:k]

    def step(self, command, phase="explore"):
        """One command sent: the transition record (the world's answer is the facts after)."""
        before = self.reading()
        act = self.action_of(command) or {"verb": None, "args": {}, "command": command}
        admissible = command in self.host.admissible
        self.host._take(self.host.gym.call("step", command=command))
        self.commands.append(command)
        after = self.reading()
        b, a = set(before), set(after)
        return {"kind": "transition", "phase": phase, "game": self.iid, "t": len(self.commands),
                "before": before, "action": {"verb": act["verb"], "args": act["args"]}, "command": command,
                "admissible": admissible, "after": after, "added": sorted(a - b), "removed": sorted(b - a),
                "text": (self.host.obs or "").strip()[:400], "won": self.won}

    def snapshot(self):
        return {"game": self.iid, "game_dir": self.game_dir, "commands": list(self.commands)}

    def restore(self, snap):
        self.reset()
        for c in snap["commands"]:
            self.host._take(self.host.gym.call("step", command=c))
            self.commands.append(c)

    # ── the kernel acting ──
    def act(self, tree, steps=60, seed=1):
        """The program of TREE (its base, this game's instance) acting through the host, one rule
        at a time (acting.fire): {commands, refused, won, steps, stuck, transitions} — each command's
        transition (before, the rule, the command, admissible, after), the refused ones the
        exploitation's SURPRISES. A host of its own (the world as the game starts)."""
        import random
        from metis.repl import Repl
        from . import acting
        path = self.into(tree) if Path(tree) != self.tree else self.path
        host = self._host_for(path.parent)
        r = Repl.open(path)
        out = acting.new_out(self.iid)
        if getattr(host, "lmap", None) is not None:      # the map's host: the program starts on what it sees, its levels
            r.shell.counts = acting.apply_lines(dict(r.shell.counts), host.sync(dict(r.shell.counts)))
        try:
            acting.fire(self, host, r.shell, random.Random(seed), out, steps)
            out["won"] = bool(host.won)
        finally:
            host.gym.close()
        return out

    # ── the acting loop's world parts (acting.py) ──
    def _host_for(self, pkg):
        """The game's host: alf_host's own, or (VIEW, or a level port declared: alfview.DECLARED) the loop's map host."""
        from . import alfview
        if self.VIEW or alfview.DECLARED.get("levels"):
            return alfview.host_class(self.alf_host)(str(pkg), view=self.VIEW, max_steps=self.max_steps)
        return self.alf_host.AlfHost(str(pkg), max_steps=self.max_steps)

    def _rule_verb(self, name):
        return rule_verb(name, self.alf_host.COMMANDS, getattr(self.alf_host.AlfHost, "VERBS", None))

    def _handles_of(self, host, command):
        """The handles a command names (the game's names back to the program's)."""
        h = {v: k for k, v in host.to_name.items()}
        return [h[x] for x in h if x in command]

    def _verb_of(self, command):
        """A command's verb (the hierarchy's guided replay: which domain sends it)."""
        c = command.strip()
        for word, verb in (("go to ", "go"), ("open ", "open"), ("take ", "take"), ("move ", "put"), ("put ", "put")):
            if c.startswith(word):
                return verb
        return None

    def _command_of(self, host, name):
        """The command the host would send for the rule (the guided replay compares it)."""
        try:
            return host.command_of(name, ())
        except Exception:  # noqa: BLE001 — a rule the host cannot word sends nothing
            return None

    def _sync(self, host, counts):
        return host.sync(counts)

    def _before(self, host):
        return {"before": sorted(a for a, n in host.reading().items() if n > 0), "k": len(host.commands)}

    def _after(self, host, pre, name, rv, ev):
        if len(host.commands) <= pre["k"]:
            return None
        _, _, cmd, adm, changed = host.commands[-1]
        verb, bnd = rv
        return {"kind": "surprise" if not (adm and changed) else "transition", "phase": "exploit", "game": self.iid,
                "t": len(host.commands), "rule": name, "command": cmd, "admissible": adm, "changed": changed,
                "action": {"verb": verb, "args": {k: bnd[k] for k in VERBS[verb][1] if k in bnd}},
                "before": pre["before"], "after": sorted(a for a, n in host.reading().items() if n > 0),
                "said": sorted(ev.produce), "consumed": sorted(ev.consume),
                "text": (host.obs or "").strip()[:400], "won": host.won}


class AlfViewWorld(AlfWorld):
    """ALFWorld seen from where the robot stands (the world "alfworld_view", opt-in; policy-tuning-2 2a-ii): a thing's
    place is read once seen, the semantic map believes the rest, the program's level port reads that belief."""
    VIEW = True
    DESCRIPTION = "a household world (ALFWorld) seen from where the robot stands"
    LOCATED = ("inrecep(", "objat(")

    @classmethod
    def revealed(cls, before, after):
        """The located facts a command REVEALED: in the reading after it, not before, of a thing the robot did not hold
        (a put places what it held: that is an effect). They were there; the robot saw them: perception, not a change."""
        held = {a[6:-1] for a in before if a.startswith("holds(")}
        return sorted(a for a in after if a.startswith(cls.LOCATED) and a not in before and a[a.index("(") + 1:].split(",")[0] not in held)

    def _seen_before(self, rec):
        """A transition record with what the command revealed moved into its `before` (the records the gate fits)."""
        if rec is None:
            return rec
        shown = self.revealed(rec["before"], rec["after"])
        if shown:
            rec["before"] = sorted(set(rec["before"]) | set(shown))
            rec["revealed"] = shown
            if "added" in rec:
                rec["added"] = sorted(set(rec["added"]) - set(shown))
        return rec

    def step(self, command, phase="explore"):
        return self._seen_before(super().step(command, phase))

    def _after(self, host, pre, name, rv, ev):
        return self._seen_before(super()._after(host, pre, name, rv, ev))
