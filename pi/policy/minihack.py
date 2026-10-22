"""The policy driver's third world: MiniHack's room family through its host (metis-worlds minihack/world/
mh_host.py) — the same surface as alfworld.AlfWorld (the adapter contract), so the driver reads no
world by name.

A game is a level VARIANT at a layout seed: (size, item, monster, door, trap) and its seed
(levels.sample). Its INSTANCE package (the world's gen_level with a base) declares the level's types
(cell, thing, beast), the grid as static facts (`next(C, D, C2)`: the cell one step in direction D) and
the perceived start, and includes the base the loop is building (`../base/mh.llp`). The world is the
host's: its gym child steps NetHack, its reading is the perception's atoms (the map as cells, the
inventory, the hit points; never the des or the screen).

The host's vocabulary: a rule named `verb` or `verb_why` sends the action (mh_host maps a fired rule by
its first token): move D · open D · kick D · apply D (the key, toward D) · pickup · eat · down · wait ·
search. MiniHack has no admissible list: every action can be sent, and the world REFUSES one by
changing nothing it perceives (a wall, nothing to pick up, no stairs here) — mh_host.act's test.
"""
import os
import random
import shutil
import sys
from pathlib import Path

from .alfworld import args_of, kind_of, rule_verb, rules_of  # noqa: F401 (rules_of: the same reader)

DIRS = ("n", "e", "s", "w", "ne", "se", "sw", "nw")
COMMANDS = {"move": ("move", "D"), "open": ("open", "D"), "kick": ("kick", "D"), "apply": ("apply", "D"),
            "pickup": ("pickup",), "eat": ("eat",), "down": ("down",), "wait": ("wait",), "search": ("search",)}
VERB_TEXT = {"move": "step one cell in direction D (n e s w ne se sw nw; a monster there is attacked)",
             "open": "open the door in direction D", "kick": "kick in direction D (a locked door breaks)",
             "apply": "apply the key you carry to the door in direction D", "pickup": "pick up what is on your cell",
             "eat": "eat something edible you carry", "down": "go down the stairs on your cell", "wait": "wait one turn",
             "search": "search around you one turn"}
# the clock and the slow states are read, never predicted: every taken action moves the turn on
UNPREDICTED = {"turn", "hunger", "hpmax"}
TAKEN_ANYWAY = ("WAIT", "SEARCH")                  # actions that change nothing by design (mh_host.act)
FIGHT = {"said(hit)", "said(killed)", "said(hurt)"}


def world_dir():
    """metis-worlds/minihack/world: $METIS_MH_WORLD, else the sibling checkout."""
    p = os.environ.get("METIS_MH_WORLD")
    if p:
        return Path(p)
    d = Path(__file__).resolve()
    for _ in range(6):
        d = d.parent
        c = d / "metis-worlds" / "minihack" / "world"
        if c.is_dir():
            return c
    raise SystemExit("set METIS_MH_WORLD to metis-worlds/minihack/world")


def _world():
    w = str(world_dir())
    if w not in sys.path:
        sys.path.insert(0, w)
    import gen_level
    import levels
    import mh_host
    return mh_host, gen_level, levels


def empty_base(name="mh"):
    _, gen_level, _ = _world()
    return gen_level.base_source(name)


def iid_of(game):
    variant, seed = game
    return "room_%s_%s_%s_%s_%s_s%d" % (tuple(variant) + (int(seed),))


def host_class():
    """mh_host.MhHost with the perception's numbers as the base's `num` values (hp(16) → hp(n16), as the
    instance's #init has them): the program's counts and the records speak one spelling."""
    mh_host, gen_level, _ = _world()

    class Host(mh_host.MhHost):
        def reading(self):
            return {gen_level.num_atom(a): 1 for a in self.atoms}
    return Host


def _perceived(atoms):
    """What a taken action changes: the perception without the clock and the body (mh_host.act's test)."""
    return {a for a in atoms if kind_of(a) not in ("turn", "hunger", "hp")}


class MiniHack:
    DOMAIN = "mh"
    DESCRIPTION = ("a NetHack room (MiniHack: a lit grid of cells; the agent, the stairs down — standing on them wins —, "
                   "and maybe an item, a monster, a closed door with the stairs behind it, a trap)")
    SPLITS = {"discovery": "discovery", "gate": "gate", "heldout": "held_out", "valid_unseen": "held_out"}
    VERB_TEXT = VERB_TEXT
    STATICS = "next(C, D, C2): the cell C2 one step from C in direction D"
    # the terrain is SEEN, not made: the arrival stairs show only when the agent leaves them, a door's room
    # when it opens. A rule may need a terrain fact (floor(C2)) but is not judged on producing one
    UNCOMPARED = ("floor", "wall", "corridor", "stairs_down", "stairs_up", "unknown")
    TASK_TEXT = "the episode is WON when the agent stands on the stairs down (the cell of stairs_down)."
    PLAN_TEXT = ("step toward the stairs down (next facts lead there), open or kick a closed door in the way "
                 "(apply a carried key to a locked one), and do not stand still.")

    def __init__(self, game, tree, max_steps=200):
        self.mh_host, self.gen_level, _ = _world()
        self.game = (tuple(game[0]), int(game[1]))
        self.tree = Path(tree)
        self.iid = iid_of(self.game)
        self.game_dir = "%s@%d" % ("_".join(self.game[0]), self.game[1])     # the game's name in a snapshot
        self.pkg = self.tree / self.iid
        if not (self.pkg / ("%s.llp" % self.iid)).exists():
            self.tree.mkdir(parents=True, exist_ok=True)
            self.gen_level.generate(self.game[0], self.game[1], str(self.tree), domain_rel="../base/mh.llp", name=self.iid)
        self.path = self.pkg / ("%s.llp" % self.iid)
        self.max_steps, self.host, self.commands = max_steps, None, []

    @classmethod
    def sample(cls, split, family, n, seed=1):
        _, _, levels = _world()
        family = "room" if family in (None, "pick_and_place_simple") else family     # the driver's default is ALFWorld's
        return levels.sample(cls.SPLITS.get(split, split), family, n, seed)

    @classmethod
    def vocabulary(cls):
        """(the host's dynamic predicates, its command table, its verb convention)."""
        mh_host, _, _ = _world()
        return set(mh_host.PERCEIVED) - UNPREDICTED, COMMANDS, COMMANDS

    @staticmethod
    def task_facts(instance_text):
        return [l.strip()[6:-2].strip() for l in instance_text.splitlines() if l.strip().startswith("#init stairs_down(")]

    @staticmethod
    def statics_for(rec, instance_text):
        """The grid around the agent before the action: the next facts from its cell (not every fact
        naming the direction: a level has hundreds)."""
        at = next((args_of(a)[0] for a in rec.get("before", []) if a.startswith("agent_at(")), None)
        return [l.strip()[:-1] for l in instance_text.splitlines() if at and l.strip().startswith("next(%s," % at)]

    def into(self, tree):
        dst = Path(tree) / self.iid
        if not dst.exists():
            shutil.copytree(self.pkg, dst)
        return dst / ("%s.llp" % self.iid)

    def instance_text(self):
        return self.path.read_text()

    # ── the level ──
    def open(self):
        if self.host is None:
            self.host = host_class()(str(self.pkg), max_steps=self.max_steps)
        return self

    def close(self):
        if self.host is not None:
            self.host.gym.close()
            self.host = None

    def reset(self):
        self.open()
        self.host._reset(self.host.seed)
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

    @staticmethod
    def action_of(command):
        """A command atom (`cmd_move(n)`, `cmd_pickup`) → {verb, args, command}; None for another."""
        c = command.strip()
        if not c.startswith("cmd_"):
            return None
        verb, _, rest = c[4:].partition("(")
        spec = COMMANDS.get(verb)
        if spec is None:
            return None
        args = [x.strip() for x in rest.rstrip(")").split(",") if x.strip()] if rest else []
        if len(args) != len(spec) - 1 or (args and args[0] not in DIRS):
            return None
        return {"verb": verb, "args": dict(zip(spec[1:], args)), "command": c}

    def actions(self):
        """Every action the host can send (MiniHack lists none: the world refuses by changing nothing)."""
        out = []
        for verb, spec in COMMANDS.items():
            for d in (DIRS if len(spec) > 1 else (None,)):
                out.append(self.action_of("cmd_%s(%s)" % (verb, d) if d else "cmd_" + verb))
        return out

    def unadmissible(self, rng, k=2):
        """k actions the perception says the world refuses now (a refusal's record, so no restore): a move off
        the level's cells or into a wall, a pickup with nothing here, a down off the stairs, an open with no
        door there."""
        r = set(self.reading())
        at = next((args_of(a)[0] for a in r if a.startswith("agent_at(")), None)
        if at is None:
            return []
        x, y = (int(v) for v in at[1:].split("_"))
        cells = set(self.host.cells)
        steps = self.gen_level.STEPS
        cell = lambda d: "c%d_%d" % (x + steps[d][0], y + steps[d][1])  # noqa: E731
        cands = ["cmd_move(%s)" % d for d in DIRS if cell(d) not in cells or "wall(%s)" % cell(d) in r]
        cands += ["cmd_open(%s)" % d for d in DIRS if not any(a.startswith("door(%s," % cell(d)) for a in r)]
        if not any(a.startswith("obj(") and a.endswith(",%s)" % at) for a in r):
            cands.append("cmd_pickup")
        if "stairs_down(%s)" % at not in r:
            cands.append("cmd_down")
        rng.shuffle(cands)
        return cands[:k]

    def _send(self, command):
        """The action through the host's act face: → acted (the world took it)."""
        out = self.host.act(command)
        return bool(out.get("acted"))

    def step(self, command, phase="explore"):
        before = self.reading()
        act = self.action_of(command) or {"verb": None, "args": {}, "command": command}
        acted = self._send(command)
        self.commands.append(command)
        after = self.reading()
        b, a = set(before), set(after)
        return {"kind": "transition", "phase": phase, "game": self.iid, "t": len(self.commands),
                "before": before, "action": {"verb": act["verb"], "args": act["args"]}, "command": command,
                "admissible": acted, "changed": acted, "after": after, "added": sorted(a - b), "removed": sorted(b - a),
                "text": (self.host.message or "").strip()[:400], "won": self.won}

    def snapshot(self):
        return {"game": self.iid, "game_dir": self.game_dir, "variant": list(self.game[0]), "seed": self.game[1],
                "commands": list(self.commands)}

    def restore(self, snap):
        self.reset()
        for c in snap["commands"]:
            self._send(c)
            self.commands.append(c)

    # ── the kernel acting ──
    def act(self, tree, steps=120, seed=1):
        """The program of TREE (its base, this level's instance) acting through the host, one rule at a
        time: {commands, refused, won, steps, stuck, transitions}; a refused action (the perception did
        not change) is a SURPRISE."""
        from metis.repl import Repl
        from . import acting
        path = self.into(tree) if Path(tree) != self.tree else self.path
        host = self._host_for(path.parent)
        r = Repl.open(path)
        out = acting.new_out(self.iid)
        try:
            acting.fire(self, host, r.shell, random.Random(seed), out, steps)
            out["won"] = bool(host.won)
        finally:
            host.gym.close()
        return out

    # ── the acting loop's world parts (acting.py) ──
    def _host_for(self, pkg):
        return host_class()(str(pkg), max_steps=self.max_steps)

    def _rule_verb(self, name):
        return rule_verb(name, COMMANDS, COMMANDS)

    def _command_of(self, host, name):
        """The command the host would send for the rule (the guided replay compares it)."""
        rv = self._rule_verb(name)
        if rv is None:
            return None
        verb, bnd = rv
        args = {k2: bnd[k2] for k2 in COMMANDS[verb][1:] if k2 in bnd}
        return "cmd_%s(%s)" % (verb, args["D"]) if "D" in args else "cmd_" + verb

    def _sync(self, host, counts):
        return host.tick(counts)

    def _before(self, host):
        return {"before": sorted(a for a, n in host.reading().items() if n > 0), "k": len(host.actions),
                "seen": _perceived(host.atoms), "n": None}

    def _after(self, host, pre, name, rv, ev):
        if len(host.actions) <= pre["k"]:
            return None
        sent = host.actions[pre["k"]:]
        taken = (_perceived(host.atoms) != pre["seen"] or host.done or host.reward > 0 or sent[0] in TAKEN_ANYWAY
                 or bool(set(host.events) & FIGHT))
        verb, bnd = rv
        args = {k2: bnd[k2] for k2 in COMMANDS[verb][1:] if k2 in bnd}
        cmd = "cmd_%s(%s)" % (verb, args["D"]) if "D" in args else "cmd_" + verb
        return {"kind": "transition" if taken else "surprise", "phase": "exploit", "game": self.iid,
                "t": len(host.actions), "rule": name, "command": cmd, "admissible": taken, "changed": taken,
                "action": {"verb": verb, "args": args}, "before": pre["before"],
                "after": sorted(a for a, n in host.reading().items() if n > 0),
                "said": sorted(ev.produce), "consumed": sorted(ev.consume),
                "text": (host.message or "").strip()[:400], "won": host.won}
