"""The policy driver's second world: ScienceWorld through its host (metis-worlds scienceworld/world/
sw_host.py) — the same surface as alfworld.AlfWorld (the adapter contract), so the driver reads
neither world by name.

A variation is an INSTANCE package (the world's gen_instance with a base: its types and start) that
includes the base the loop is building (`../base/sw.llp`). The world is the host's: its gym child
steps the Java simulator, its reading is the TEXT's facts (never the simulator's object tree).

The host's vocabulary: a rule named `verb` or `verb_why` sends the command (sw_host maps a fired
rule by its first token): go R · open D · take O · drop O · focus O · connect A B · move O C ·
activate O · deactivate O · wait · look.
"""
import json
import os
import random
import shutil
import sys
from pathlib import Path

from .alfworld import args_of, kind_of, rule_verb, rules_of  # noqa: F401 (rules_of: the same reader)

COMMANDS = {"go": ("go", "R"), "open": ("open", "D"), "close": ("close", "D"), "take": ("take", "O"), "drop": ("drop", "O"),
            "focus": ("focus", "O"), "connect": ("connect", "A", "B"), "move": ("move", "O", "C"),
            "activate": ("activate", "O"), "deactivate": ("deactivate", "O"), "wait": ("wait",), "look": ("look",)}
VERB_TEXT = {"go": "go to the room R (through this room's door to it)", "open": "open D (a door: the room's name; or a container)",
             "close": "close D", "take": "pick up O", "drop": "drop O", "focus": "focus on O (the task scores it)",
             "connect": "connect terminal A to terminal B", "move": "move O into the container C", "activate": "turn O on",
             "deactivate": "turn O off", "wait": "wait one tick", "look": "look around"}


def world_dir():
    """metis-worlds/scienceworld/world: $METIS_SW_WORLD, else the sibling checkout."""
    p = os.environ.get("METIS_SW_WORLD")
    if p:
        return Path(p)
    d = Path(__file__).resolve()
    for _ in range(6):
        d = d.parent
        c = d / "metis-worlds" / "scienceworld" / "world"
        if c.is_dir():
            return c
    raise SystemExit("set METIS_SW_WORLD to metis-worlds/scienceworld/world")


def _world():
    w = str(world_dir())
    if w not in sys.path:
        sys.path.insert(0, w)
    import families
    import gen_instance
    import perceive
    import sw_host
    return sw_host, gen_instance, families, perceive


def empty_base(name="sw"):
    _, gen_instance, _, _ = _world()
    return gen_instance.base_source(name)


def iid_of(game):
    task, v = game
    return "%s_%d" % (task.replace("-", "_"), int(v))


class ScienceWorld:
    DOMAIN = "sw"
    DESCRIPTION = "a text laboratory (ScienceWorld: rooms behind doors, containers, devices, wires, substances; a task whose answer only an experiment shows)"
    SPLITS = {"discovery": "train", "gate": "dev", "heldout": "test"}
    VERB_TEXT = VERB_TEXT

    def __init__(self, game, tree, max_steps=120):
        sw_host, gen_instance, _, perceive = _world()
        self.sw_host, self.perceive = sw_host, perceive
        self.game = (game[0], int(game[1])) if isinstance(game, (tuple, list)) else (game.rsplit(":", 1)[0], int(game.rsplit(":", 1)[1]))
        self.tree = Path(tree)
        self.iid = iid_of(self.game)
        self.pkg = self.tree / self.iid
        if not (self.pkg / ("%s.llp" % self.iid)).exists():
            self.tree.mkdir(parents=True, exist_ok=True)
            gen_instance.generate(self.game[0], self.game[1], str(self.tree), domain_rel="../base/sw.llp")
        self.path = self.pkg / ("%s.llp" % self.iid)
        self.max_steps, self.host, self.commands = max_steps, None, []

    @classmethod
    def sample(cls, split, family, n, seed=1):
        _, _, families, _ = _world()
        return families.sample(cls.SPLITS.get(split, split), family, n, seed)

    @classmethod
    def vocabulary(cls):
        """(the host's dynamic predicates, its command table, its verb convention)."""
        _, gen_instance, _, _ = _world()
        return set(gen_instance.DYNAMIC_PREDS), COMMANDS, COMMANDS

    @staticmethod
    def task_facts(instance_text):
        return [l.strip()[6:-2].strip() for l in instance_text.splitlines() if l.strip().startswith(("#init task(", "#init where(", "#init threshold("))]

    def into(self, tree):
        dst = Path(tree) / self.iid
        if not dst.exists():
            shutil.copytree(self.pkg, dst)
        return dst / ("%s.llp" % self.iid)

    def instance_text(self):
        return self.path.read_text()

    # ── the variation ──
    def open(self):
        if self.host is None:
            self.host = self.sw_host.SwHost(str(self.pkg), max_steps=self.max_steps)
        return self

    def close(self):
        if self.host is not None:
            self.host.gym.close()
            self.host = None

    def reset(self):
        self.open()
        self.host._reset()
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
        return self.host.message if self.host else ""

    def _name(self, label):
        return self.perceive.name(label)

    def action_of(self, command):
        """An admissible command's text → {verb, args, command} in the host's names; None for one
        the host's table cannot send."""
        c = command.strip()
        n = self._name
        for word, verb, keys, sep in (("go to ", "go", ("R",), None), ("open door to ", "open", ("D",), None), ("open ", "open", ("D",), None),
                                      ("close door to ", "close", ("D",), None), ("close ", "close", ("D",), None),
                                      ("pick up ", "take", ("O",), None), ("drop ", "drop", ("O",), None), ("focus on ", "focus", ("O",), None),
                                      ("connect ", "connect", ("A", "B"), " to "), ("move ", "move", ("O", "C"), " to "),
                                      ("activate ", "activate", ("O",), None), ("deactivate ", "deactivate", ("O",), None)):
            if c.startswith(word):
                rest = c[len(word):]
                if sep:
                    if sep not in rest:
                        return None
                    a, b = rest.split(sep, 1)
                    return {"verb": verb, "args": {keys[0]: n(a), keys[1]: n(b)}, "command": c}
                return {"verb": verb, "args": {keys[0]: n(rest)}, "command": c}
        if c.startswith("wait"):
            return {"verb": "wait", "args": {}, "command": "wait1"}
        if c == "look around":
            return {"verb": "look", "args": {}, "command": c}
        return None

    def _known(self):
        """The names the agent has seen (its reading and the labels): a command naming something else is noise."""
        names = set()
        for a in self.reading():
            names |= set(args_of(a))
        names |= set(self.host.labels)
        return names

    def actions(self):
        """The game's valid commands the host can send, about things the agent has seen (the game lists
        every referent of the house: thousands; the walk should act where it is)."""
        known = self._known()
        out = []
        for c in self.host.valid:
            a = self.action_of(c)
            if a and all(v in known or k in ("D", "R") for k, v in a["args"].items()):
                out.append(a)
        return out

    def unadmissible(self, rng, k=2):
        """k commands the host can send that the game does not list now: a refusal's record."""
        adm = set(self.host.valid)
        r = self.reading()
        here = next((args_of(a)[0] for a in r if a.startswith("here(")), None)
        things = sorted({args_of(a)[0] for a in r if a.startswith("in(")})
        held = sorted(args_of(a)[0] for a in r if a.startswith("holds("))
        w = lambda n: self.sw_host.words(n, self.host.labels)  # noqa: E731
        cands = ["pick up " + w(t) for t in things] + ["drop " + w(t) for t in things if t not in held]
        cands += ["focus on " + w(t) for t in held] + (["go to " + w(here)] if here else [])
        cands = [c for c in cands if c not in adm]
        rng.shuffle(cands)
        return cands[:k]

    def step(self, command, phase="explore"):
        before = self.reading()
        act = self.action_of(command) or {"verb": None, "args": {}, "command": command}
        admissible = command in self.host.valid
        self.host.send(command)
        self.commands.append(command)
        after = self.reading()
        refused = any(e in ("said(unknown)", "said(cant)", "said(ambiguous)") for e in self.host.events)
        b, a = set(before), set(after)
        return {"kind": "transition", "phase": phase, "game": self.iid, "t": len(self.commands),
                "before": before, "action": {"verb": act["verb"], "args": act["args"]}, "command": command,
                "admissible": admissible and not refused, "changed": (b != a) or not refused, "after": after,
                "added": sorted(a - b), "removed": sorted(b - a), "text": (self.host.message or "").strip()[:400], "won": self.won}

    def snapshot(self):
        return {"game": self.iid, "task": self.game[0], "variation": self.game[1], "commands": list(self.commands)}

    def restore(self, snap):
        self.reset()
        for c in snap["commands"]:
            self.host.send(c)
            self.commands.append(c)

    # ── the kernel acting ──
    def act(self, tree, steps=120, seed=1):
        from metis.repl import Repl
        rng = random.Random(seed)
        path = self.into(tree) if Path(tree) != self.tree else self.path
        host = self.sw_host.SwHost(str(path.parent), max_steps=self.max_steps)
        r = Repl.open(path)
        sh = r.shell
        out = {"game": self.iid, "commands": [], "refused": 0, "won": False, "steps": 0, "stuck": [], "transitions": []}
        try:
            for _ in range(steps):
                ws = sh._candidates()
                if not ws or host.done:
                    break
                before = sorted(a for a, n in host.reading().items() if n > 0)
                k = len(host.actions)
                i = rng.choices([i for i, _ in ws], weights=[w for _, w in ws])[0]
                name = sh._fire(i, ws=ws)
                out["steps"] += 1
                rv = rule_verb(name, COMMANDS, COMMANDS)
                if rv is not None:
                    host.on_event(name, ())
                if len(host.actions) > k:
                    cmd = host.actions[-1]
                    refused = any(e in ("said(unknown)", "said(cant)", "said(ambiguous)") for e in host.events)
                    after = sorted(a for a, n in host.reading().items() if n > 0)
                    ev = sh.events_tbl[i][2]
                    verb, bnd = rv
                    t = {"kind": "surprise" if refused else "transition", "phase": "exploit", "game": self.iid,
                         "t": len(host.actions), "rule": name, "command": cmd, "admissible": not refused, "changed": not refused,
                         "action": {"verb": verb, "args": {k2: bnd[k2] for k2 in COMMANDS[verb][1:] if k2 in bnd}},
                         "before": before, "after": after, "said": sorted(ev.produce), "consumed": sorted(ev.consume),
                         "text": (host.message or "").strip()[:400], "won": host.won}
                    out["transitions"].append(t)
                    out["commands"].append(cmd)
                    out["refused"] += 1 if refused else 0
                for line in host.tick(dict(sh.counts)) or []:     # the world's facts and events back into the program
                    sign, rest = line[0], line[1:].split()
                    atom, n = rest[0], int(rest[1]) if len(rest) > 1 else 1
                    sh.counts[atom] = max(0, sh.counts.get(atom, 0) + (n if sign == "+" else -n))
                sh.counts = {a: n for a, n in sh.counts.items() if n > 0}
                out["stuck"] = sorted(a for a in sh.counts if kind_of(a) == "stuck")
                if host.won or out["stuck"]:
                    break
            out["won"] = bool(host.won)
        finally:
            host.gym.close()
        return out
