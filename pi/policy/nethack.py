"""The policy driver's world over the REAL game (metis-worlds minihack/world/nh_host.py, a seeded NetHack on a tty, headless), the
same surface as minihack.MiniHack: brief nethack-loop §3.2 and the architect's rulings on step 0.

A game is (seed, scene); discovery is `dlvl1` at seeds 1..n, the gate other seeds. An EPISODE is a task from a checkpoint: reach the
stairs down on this level; won is the dungeon level going up in the perception, death ends it with won False. The game's first
checkpoint is made once, per game, and every host of the game starts from it (a host's gym child has its own player name).

The family `dlvl1_scenes`: a random walk of 150 steps rarely leaves the first room, so an empty base would see no door opened and no stairs
taken. Its discovery games start where those are (nethack_scenes.json: a seed and the commands that lead there, from a directed walk, each
checked on arrival), and a scene's walk begins with what it is there for (`actions`), up to TRIES times, for a door can resist. Plain doors and
single things only: a locked door or a pile would be a refused record against the very rule. Its gate and held-out games are plain starts.

The INSTANCE declares the whole screen, known before any level is seen: 79 x 21 cells with their `next` facts. Its thing, beast and trap
types are the names SEEN so far in this run, kept in checkpoints/names.json, and it is rewritten when a name is new (the architect's
fallback: the whole tile list grounds 5M events, 61 s to open and 5.7 s a tick; seen names 8 s and 0.14 s). A name new to a session
that is already open stays in the records and out of that session (`_sync`).

The hero's own and the world's. A record keeps the whole reading in before and after, for the rules' needs. What a command is judged on
is its own: `judged` is the before with only the hero's own facts moved on (`agent_at`, `holds`, doors beside it, what lies under it);
a monster, the hit points, the terrain seen on the way are read, never predicted. `own_before`/`own_after` are the out-of-vocabulary
test's; `world_moved` says the world did something beside the command, which that test does not hold against it.
"""
import json
import re
import shutil
from pathlib import Path

from . import minihack
from .alfworld import kind_of
from .minihack import COMMANDS, DIRS, FIGHT, TAKEN_ANYWAY, VERB_TEXT, MiniHack, args_of

COLS, ROWS = 79, 21
# may be needed by a rule, not judged on producing: the terrain is seen, a monster and the hit points are the world's
UNCOMPARED = ("floor", "wall", "corridor", "stairs_down", "stairs_up", "unknown", "monster", "trap")
# never predicted and no use to a rule, and a premise on one multiplies the grounding by its values (the paid run's 6 GB: `$turn(T)`):
# out of the base, the prompts and the sessions; the adapter still reads the hit points for world_moved
OUTSIDE = {"turn", "hunger", "hpmax", "hp", "peaceful", "bystander"}
THE_WORLDS = ("monster", "hp")                                       # one of these changed: the world moved
UNDERFOOT = ("obj", "stairs_down", "stairs_up", "door", "trap")      # the hero is drawn over them: what it stands on stays read
UNDER_AT = {"door": 0, "obj": 1, "stairs_down": 0, "stairs_up": 0, "trap": 1}       # which argument of a placed thing is its cell
HURT = "hp_changed"                                                  # the hit points are no atom of a record: the step's events carry it
DICE = FIGHT | {"said(door_stuck)", "said(whamm)", "said(stopped)", "said(asked)", HURT}   # the same command in the same own state can go either way
SCENES = "dlvl1_scenes"
TRIES = 8
UNNAMED = "unnamed"                                                  # a carried thing the tile list has no name for


def world_mod():
    """(nh_host, nh_gym's name_of, nh_tty, gen_level): the world's runtime, by path as minihack's."""
    minihack._world()
    import gen_level
    import nh_gym
    import nh_host
    import nh_tty
    return nh_host, nh_gym, nh_tty, gen_level


def scenes():
    return json.loads((Path(__file__).parent / "nethack_scenes.json").read_text())


def unidentified(tile):
    """A tile's name is its look and its truth ("ELAM EBOW / magic mapping"); the hero knows the look."""
    return tile.split(" / ")[0]


def names():
    """What the perception can say: (things, beasts, traps), from the game's own tile list."""
    _, gym, tty, _ = world_mod()
    n = tty.tile_names()
    things = sorted({gym.name_of(unidentified(x)) for x in n["objects"]} - {"boulder"} | {UNNAMED})
    beasts = sorted({gym.name_of(x) for x in n["monsters"]})
    traps = sorted({gym.name_of(x) for x in n["other"] if re.search(r"trap|pit|hole|web|portal|field|squeaky|mine|teleporter", x)})
    # one name in two types is no use to a rule's type: the beast keeps it (a tile's object form is its own thing word)
    return [t if t not in beasts else t + "_thing" for t in things], beasts, [t + "_trap" if t in things + beasts else t for t in traps]


def empty_base(name="nh"):
    _, _, _, gen_level = world_mod()
    base = gen_level.base_source(name)
    base = base.replace("over MiniHack's room family (world/gen_level.py base_source)", "over the real game (policy/nethack.py)")
    base = base.replace("types (cell thing beast).", "types (cell thing beast trapkind).")
    base = base.replace("pred trap(said_kind, cell) : mh.", "pred trap(trapkind, cell) : mh.")
    return "\n".join(l for l in base.splitlines() if not re.match(r"pred (%s)\(" % "|".join(OUTSIDE), l)) + "\n"


TYPES = {"obj": "thing", "holds": "thing", "monster": "beast", "trap": "trapkind"}
SEEDED = {"thing": [UNNAMED], "beast": ["newt"], "trapkind": ["arrow_trap"]}     # a type is never empty


def names_of(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {k: list(v) for k, v in SEEDED.items()}


def names_seen(path, atoms):
    """The names in ATOMS added to the run's list."""
    if not path:
        return
    have, new = names_of(path), False
    for a in atoms:
        ty = TYPES.get(kind_of(a))
        if ty and args_of(a)[0] not in have[ty]:
            have[ty].append(args_of(a)[0])
            new = True
    if new:
        Path(path).write_text(json.dumps(have))


def type_lines(path):
    have = names_of(path)
    return ["type %s {%s}." % (ty, " ".join(sorted(have[ty]))) for ty in ("thing", "beast", "trapkind")]


def session_names(text):
    """The names an instance's types declare."""
    return {ty: set(m.split()) for ty, m in re.findall(r"^type (thing|beast|trapkind) \{(.*)\}\.$", text, re.M)}


def screen_cells():
    return ["c%d_%d" % (x, y) for y in range(ROWS) for x in range(COLS)]


def iid_of(game):
    return "nh_s%d_%s" % (int(game[0]), game[1])


def cell_of(c):
    return tuple(int(v) for v in c[1:].split("_"))


def hero_of(atoms):
    return next((args_of(a)[0] for a in atoms if a.startswith("agent_at(")), None)


def near(c, at):
    x, y, u, v = cell_of(c) + cell_of(at)
    return abs(x - u) <= 1 and abs(y - v) <= 1


def placed(a):
    """The cell a door, an object, stairs or a trap is at; None for anything else."""
    k = kind_of(a)
    return args_of(a)[UNDER_AT[k]] if k in UNDER_AT else None


def own_facts(atoms, cells, known=None):
    """The hero's own facts round the cells it stood on: where it is, what it holds, a door beside it, what lies under it. With `known`
    (the cells the before had such a thing at), one first seen now is left out: a sighting is the world's, the command made nothing."""
    out = set()
    for a in atoms:
        k, at = kind_of(a), placed(a)
        if k in ("agent_at", "holds"):
            out.add(a)
        elif at is None or (known is not None and (k, at) not in known):
            continue
        elif (k == "door" and any(near(at, c) for c in cells)) or at in cells:
            out.add(a)
    return out


def own_record(before, after, events=()):
    """What a command is judged on. own_before says the before alone, from the cell the hero stood on, so one before has one; own_after
    what came of it; added and removed the hero's own too (the brain's "what changed"); judged the before with only those moved on;
    world_moved: the monsters or the hit points changed, or the step's outcome was the world's dice (a door resisting, a blow, a pet)."""
    b, a = set(before), set(after)
    cells = [c for c in (hero_of(b), hero_of(a)) if c]
    known = {(kind_of(x), placed(x)) for x in b if placed(x)}
    was, now = own_facts(b, cells), own_facts(a, cells, known)
    moved = {x for x in b ^ a if kind_of(x) in THE_WORLDS} or set(events) & DICE
    return {"own_before": sorted(own_facts(b, cells[:1])), "own_after": sorted(now), "added": sorted(now - was), "removed": sorted(was - now),
            "judged": sorted((b - was) | now), "world_moved": bool(moved)}


def said(host, hp):
    """The step's events, and the hit points' change as one of them."""
    return list(host.events) + ([HURT] if host.hp_now() != hp else [])


def own_of(before, after, events, dlvl, now):
    """own_record, but a new level is a new map: where the hero lands is the world's, so the step is judged as changing nothing here."""
    own = own_record(before, before if dlvl != now else after, events)
    return dict(own, world_moved=True) if dlvl != now else own


def host_class():
    nh_host, _, _, gen_level = world_mod()
    thing_names, beasts, traps = names()
    known = set(thing_names)
    worn = {}
    _, gym, tty, _ = world_mod()
    looks = {gym.name_of(x): gym.name_of(unidentified(x)) for x in tty.tile_names()["objects"]}

    def carried(x):
        """holds(blessed_1_long_swords) → the longest tile name in it, singular; UNNAMED when the list has none."""
        if x not in worn:
            forms = (x, re.sub(r"s(?=_|$)", "", x))
            hit = [n for n in known if n != UNNAMED and any(re.search(r"(^|_)%s($|_)" % re.escape(n), f) for f in forms)]
            worn[x] = max(hit, key=len, default=UNNAMED)
        return worn[x]

    def spoken(a):
        k = kind_of(a)
        if k == "holds":
            return "holds(%s)" % carried(args_of(a)[0])
        if k == "obj":
            n, c = args_of(a)
            n = looks.get(n, n)
            return "obj(%s,%s)" % (n if n in known else n + "_thing" if n + "_thing" in known else UNNAMED, c)
        if k == "trap":
            n, c = args_of(a)
            return "trap(%s,%s)" % (n if n in traps else n + "_trap", c)
        return gen_level.num_atom(a)

    class Host(nh_host.NhHost):
        """One game, no page: no map (the program speaks the screen's cells), the game's end and the level's end are the episode's."""

        def _take(self, out, fresh=True):
            # a game that has just started, or a scene: what the hero stands on there is not drawn
            was, at = set(getattr(self, "atoms", ())) or set(self.level.get("under", ())), getattr(self, "dlvl", None)
            super()._take(out, fresh)
            died, self.done = getattr(self, "over", False), False
            if out.get("dlvl") is not None:
                self.dlvl = out["dlvl"]
                if getattr(self, "first_dlvl", None) is None:
                    self.first_dlvl = self.dlvl
            if at is not None and self.dlvl != at:
                was = set()                          # a level's map is its own
            self.carry(was, out)
            self.won = self.dlvl > self.first_dlvl
            self.done = died or self.won

        def carry(self, was, out):
            """The hero is drawn over what it stands on: read on, until it is taken or the hero has left it."""
            here = hero_of(self.atoms)
            if not here:
                return
            events = out.get("events", ())
            for a in was:
                if kind_of(a) in UNDERFOOT and placed(a) == here:
                    if kind_of(a) == "obj" and "said(picked)" in events:
                        continue
                    self.atoms.add(a)

        def restore(self, snap):
            """What lay under the hero at the snapshot is read on from there, not from where the game has been since."""
            if snap.get("checkpoint"):
                self.atoms, self.dlvl = set(snap["sign"]), None
            super().restore(snap)

        def hp_now(self):
            return next((a for a in self.atoms if kind_of(a) == "hp"), None)

        def note(self, *a, **k):
            pass                                     # the page's journal (nh_host.surprise); the driver keeps the loop's records

        def reading(self):
            out = {spoken(a): 1 for a in self.atoms if kind_of(a) not in OUTSIDE}
            names_seen(self.level.get("names"), out)
            return out

        def act(self, atom):
            before = set(self.reading())
            out = super().act(atom)
            after = set(self.reading())
            own = own_record(before, after)
            sent = out.get("action") or [None]
            out["acted"] = (set(own["own_before"]) != set(own["own_after"]) or self.done or sent[0] in TAKEN_ANYWAY
                            or bool(set(self.events) & FIGHT)) if out.get("action") else False
            return out
    return Host


class NetHack(MiniHack):
    DOMAIN = "nh"
    HOST = "nh_host.py:make"
    DESCRIPTION = ("the real NetHack 3.6.6, a Valkyrie on a dungeon level seen only as she explores it: rooms, doors, corridors, "
                   "monsters that move on their own, a pet that follows. c<x>_<y> names a cell of the 79 x 21 screen")
    SPLITS = {"discovery": "discovery", "gate": "gate", "heldout": "heldout", "valid_unseen": "heldout"}
    VERB_TEXT = VERB_TEXT
    STATICS = "next(C, D, C2): the cell C2 one step from C in direction D on the screen (it says nothing of what is there)"
    UNCOMPARED = UNCOMPARED
    TASK_TEXT = "the episode is WON when the hero goes down the stairs: the dungeon level goes up. Dying ends it, not won."
    PLAN_TEXT = ("explore toward what has not been seen, open or kick a closed door in the way, fight what blocks the way, "
                 "and on the stairs down (stairs_down) go down; do not stand still.")

    def __init__(self, game, tree, max_steps=400):
        self.game = (int(game[0]), str(game[1]))
        self.tree = Path(tree)
        self.iid = iid_of(self.game)
        self.game_dir = "%s@%d" % (self.game[1], self.game[0])
        self.pkg = self.tree / self.iid
        self.path = self.pkg / ("%s.llp" % self.iid)
        self.max_steps, self.host, self.commands, self.scene_left = max_steps, None, [], TRIES
        self.names = str(self.tree.resolve().parent.parent / "checkpoints" / "names.json")
        if not self.path.exists():
            self.generate()

    @classmethod
    def sample(cls, split, family, n, seed=1):
        """(seed, scene): dlvl1 first; the other scenes when a run's numbers ask for them (brief §3.2)."""
        family = "dlvl1" if family in (None, "pick_and_place_simple") else family
        split = cls.SPLITS.get(split, split)
        if family == SCENES:
            if split == "discovery":
                return [(s["seed"], name) for name, s in list(scenes().items())[:n]] + [(seed + i, "dlvl1") for i in range(max(0, n - len(scenes())))]
            family = "dlvl1"
        at = {"discovery": seed, "gate": 1000 + seed, "heldout": 2000 + seed}[split]
        return [(at + i, family) for i in range(n)]

    @classmethod
    def vocabulary(cls):
        nh_host, _, _, _ = world_mod()
        import mh_host
        return set(mh_host.PERCEIVED) - OUTSIDE, COMMANDS, COMMANDS

    @staticmethod
    def task_facts(instance_text):
        return ["reach(stairs_down)"]

    # ── the instance ──
    def generate(self):
        """The game's package: its first checkpoint, kept beside the run's trees, and the whole screen as types and statics."""
        _, _, _, gen_level = world_mod()
        checkpoints = self.tree.resolve().parent.parent / "checkpoints" / self.iid
        checkpoints.parent.mkdir(parents=True, exist_ok=True)
        self.pkg.mkdir(parents=True, exist_ok=True)
        (self.pkg / "level.json").write_text(json.dumps({
            "seed": self.game[0], "max_steps": 10 ** 9, "names": self.names, "replay": {"seed": self.game[0], "checkpoints": str(checkpoints)}}))
        host = host_class()(str(self.pkg))
        try:
            scene = scenes().get(self.game[1])
            if scene:
                self.into_scene(host, scene, checkpoints)
            start = sorted(host.reading())
        finally:
            host.gym.close()
        cells = screen_cells()
        lines = ["%% %s: the real game at seed %d, generated by policy/nethack.py: the screen, what the perception can say, the perceived start." % (self.iid, self.game[0]),
                 "catalog %s 1." % self.iid,
                 'provenance text "the real game, seed %d" "2026-10-31".' % self.game[0],
                 'include "../base/nh.llp".',
                 "type cell {%s}." % " ".join(cells)] + type_lines(self.names) + ["", "% the screen"] + gen_level.geometry(cells) + ["", "% the start"]
        lines += ["#init %s 1" % a for a in start] + ["#steps 20", "#seeds 1"]
        self.path.write_text("\n".join(lines) + "\n")
        (self.pkg / "intent.yaml").write_text(gen_level.CARD)

    def into_scene(self, host, scene, checkpoints):
        """The game walked to its scene, checked, and saved as its start; what lies under the hero kept in level.json."""
        if self.game[0] != scene["seed"]:
            raise ValueError("%s: scene %s is seed %d's" % (self.iid, self.game[1], scene["seed"]))
        for c in scene["commands"]:
            host.act(c)
        here = set(host.atoms)
        missing = [a for a in scene["expect"] if a not in set(host.reading())]
        if missing:
            raise RuntimeError("%s: the walk did not reach its scene: no %s (the commands were recorded on another day? the clock is not in the seed yet)" % (self.iid, missing))
        host.gym.call("save", name="start")
        at = hero_of(here)
        level = json.loads((self.pkg / "level.json").read_text())
        level["under"] = sorted(a for a in here if placed(a) == at)
        (self.pkg / "level.json").write_text(json.dumps(level))

    def refresh(self, path):
        """The instance at PATH with the run's names as they are now."""
        text, lines = Path(path).read_text(), type_lines(self.names)
        new = text
        for line in lines:
            new = re.sub(r"^type %s \{.*\}\.$" % line.split()[1], lambda _: line, new, flags=re.M)
        if new != text:
            Path(path).write_text(new)

    def into(self, tree):
        dst = Path(tree) / self.iid
        if not dst.exists():
            shutil.copytree(self.pkg, dst)
        self.refresh(dst / ("%s.llp" % self.iid))
        return dst / ("%s.llp" % self.iid)

    @staticmethod
    def statics_for(rec, instance_text):
        at = hero_of(rec.get("before", []))
        return [l.strip()[:-1] for l in instance_text.splitlines() if at and l.startswith("next(%s," % at)]

    # ── the game ──
    def open(self):
        if self.host is None:
            self.host = host_class()(str(self.pkg))
        return self

    def reset(self):
        self.open()
        self.host.first_dlvl, self.host.atoms = None, set()
        self.host.dlvl = None
        self.host._take(self.host.gym.call("load", name="start"))
        self.commands, self.host.actions, self.host.t, self.scene_left = [], [], 0, TRIES

    def close(self):
        if self.host is not None:
            self.host.gym.close()
            self.host = None

    def actions(self):
        """A scene's walk first takes what the scene is for; then every action, as MiniHack's."""
        scene = scenes().get(self.game[1])
        if scene and self.scene_left:
            return [self.action_of(scene["next"])]
        return super().actions()

    def unadmissible(self, rng, k=2):
        """k actions the perception says the world refuses now, over the cells seen: a move into a wall, an open with no door
        beside it, a pickup with nothing here, a down off the stairs."""
        _, _, _, gen_level = world_mod()
        r = set(self.reading())
        at = hero_of(r)
        if at is None:
            return []
        x, y = cell_of(at)
        cell = lambda d: "c%d_%d" % (x + gen_level.STEPS[d][0], y + gen_level.STEPS[d][1])  # noqa: E731
        cands = ["cmd_move(%s)" % d for d in DIRS if "wall(%s)" % cell(d) in r]
        cands += ["cmd_open(%s)" % d for d in DIRS if not any(a.startswith("door(%s," % cell(d)) for a in r)]
        if not any(a.startswith("obj(") and a.endswith(",%s)" % at) for a in r):
            cands.append("cmd_pickup")
        if "stairs_down(%s)" % at not in r:
            cands.append("cmd_down")
        rng.shuffle(cands)
        return cands[:k]

    def step(self, command, phase="explore"):
        before, dlvl, hp = self.reading(), self.host.dlvl, self.host.hp_now()
        act = self.action_of(command) or {"verb": None, "args": {}, "command": command}
        acted = self._send(command)
        self.commands.append(command)
        self.scene_left = 0 if acted else max(0, self.scene_left - 1)
        after = self.reading()
        b, a = set(before), set(after)
        return dict({"kind": "transition", "phase": phase, "game": self.iid, "t": len(self.commands),
                     "before": before, "action": {"verb": act["verb"], "args": act["args"]}, "command": command,
                     "admissible": acted, "changed": acted, "after": after, "added": sorted(a - b), "removed": sorted(b - a),
                     "text": (self.host.message or "").strip()[:400], "won": self.won, "dlvl": self.host.dlvl}, **own_of(before, after, said(self.host, hp), dlvl, self.host.dlvl))

    def snapshot(self):
        snap = {"game": self.iid, "game_dir": self.game_dir, "seed": self.game[0], "scene": self.game[1], "commands": list(self.commands)}
        if self.host is not None:
            snap["host"] = self.host.snapshot()
        return snap

    def restore(self, snap):
        """The checkpoint and the keys since (brief §3.1); a snapshot with no host's part is its commands from the start."""
        if snap.get("host"):
            self.open()
            self.host.restore(snap["host"])
            self.commands = list(snap["commands"])
        else:
            self.reset()
            for c in snap["commands"]:
                self._send(c)
                self.commands.append(c)
        self.scene_left = 0 if snap["commands"] else TRIES      # a scene's first command is for its start only

    @property
    def divergences(self):
        return getattr(self.host, "divergences", 0) if self.host else 0

    # ── the acting loop's world parts (acting.py) ──
    def _host_for(self, pkg):
        self.session = session_names(next(Path(pkg).glob("*.llp")).read_text())
        return host_class()(str(pkg))

    def _sync(self, host, counts):
        """The world's do-lines for the open session: a name new since it opened is outside its types (the records keep it)."""
        lines = host.tick(counts)
        if lines is None or not getattr(self, "session", None):
            return lines
        told = lambda line: TYPES.get(kind_of(line[1:].split()[0])) is None or args_of(line[1:].split()[0])[0] in self.session[TYPES[kind_of(line[1:].split()[0])]]
        return [line for line in lines if told(line)]

    def _before(self, host):
        return {"before": sorted(a for a, n in host.reading().items() if n > 0), "k": len(host.actions), "dlvl": host.dlvl, "hp": host.hp_now()}

    def _after(self, host, pre, name, rv, ev):
        if len(host.actions) <= pre["k"]:
            return None
        sent = host.actions[pre["k"]:]
        after = sorted(a for a, n in host.reading().items() if n > 0)
        own = own_of(pre["before"], after, said(host, pre["hp"]), pre["dlvl"], host.dlvl)
        taken = set(own["own_before"]) != set(own["own_after"]) or host.done or sent[0] in TAKEN_ANYWAY or bool(set(host.events) & FIGHT)
        verb, bnd = rv
        args = {k2: bnd[k2] for k2 in COMMANDS[verb][1:] if k2 in bnd}
        cmd = "cmd_%s(%s)" % (verb, args["D"]) if "D" in args else "cmd_" + verb
        return dict({"kind": "transition" if taken else "surprise", "phase": "exploit", "game": self.iid,
                     "t": len(host.actions), "rule": name, "command": cmd, "admissible": taken, "changed": taken,
                     "action": {"verb": verb, "args": args}, "before": pre["before"], "after": after,
                     "said": sorted(ev.produce), "consumed": sorted(ev.consume),
                     "text": (host.message or "").strip()[:400], "won": host.won, "dlvl": host.dlvl}, **own)

