"""alfview.py — the loop's ALFWorld with the semantic map (policy-tuning-2 s-e075f47f 2a-ii, the architect's ruling (b)).

The map (metis-worlds semantic_world.room.SemanticMap) follows what the robot sees, step by step. The program's level
ports (`beliefs:` / `levels:` the brain declared, brief v2 §B: DECLARED) are the instrument's (metispy's LevelHook)
over the concrete names: the port where(O, R) is the map's belief that O is in R, and the level atoms are asserted
into the reading each step. Two modes:
  plain   the world "alfworld": every fact read, the map's belief a point mass (the plumbing, exercised whenever a
          level is declared; with none declared the host is alf_host's own, untouched);
  VIEW    the world "alfworld_view", opt-in: the robot sees only what stands before it (the places are known; a
          thing's place is read once seen into: open, or not openable, at the robot's location), and the map
          believes the rest (cancontain's prior over the places that can hold it, less those looked into without it).

The program declares the port it reads, as metisc's instrument needs: `weight where(O, R) reads {inrecep(O, R)}.`,
the level pred with the level first (`pred place_level(level, object, receptacle)`, `type level {low mid high}`), and
`beliefs: {inrecep: {port: where, lone: R}}` (lone: a row floored to nine decimals sums to at most 1)."""
import json
import os
from fractions import Fraction
from pathlib import Path

DECLARED = {}            # {"beliefs": {...}, "levels": {...}}: the level ports the run's accepted proposals declared


def _types(text, name):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("type %s {" % name):
            return s[s.index("{") + 1:s.rindex("}")].split()
    return []


def host_class(alf_host):
    """alf_host.AlfHost with the loop's map and level port (see the module's doc)."""

    class MapHost(alf_host.AlfHost):
        def __init__(self, package_dir, view=False, declared=None, **kw):
            self.lmap, self.view, self.loop_levels, self.level_rep = None, view, {}, []
            self.hook, self.hook_preds = None, set()
            super().__init__(package_dir, **kw)
            from semantic_world.room import SemanticMap
            meta = json.load(open(os.path.join(package_dir, "game.json")))
            inst = next(Path(package_dir).glob("*.llp")).read_text()
            facts = [l.strip()[:-1] for l in inst.splitlines() if l.strip().startswith(("target(", "dest(")) and l.strip().endswith(".")]
            targets = [f[7:-1] for f in facts if f.startswith("target(")]
            dests = [f[5:-1] for f in facts if f.startswith("dest(")]
            self.objects, self.receptacles = _types(inst, "object"), _types(inst, "receptacle")
            self.targets = targets
            mp = os.path.join(package_dir, ".loopmap.json")
            for f in (mp, mp + ".journal.jsonl"):         # a host starts on the world as it starts: no earlier host's map
                if os.path.exists(f):
                    os.remove(f)
            self.lmap = SemanticMap.build(mp, self.static, self.consistent(), targets, dests, view=view)
            self.declared = declared
            declared = DECLARED if declared is None else declared
            if declared.get("levels"):
                from metis.kernel.evaluate import LevelHook
                man = {"program": next(Path(package_dir).glob("*.llp")).name, "beliefs": declared.get("beliefs") or {},
                       "levels": declared["levels"]}
                try:
                    self.hook, self.hook_preds = LevelHook(man, package_dir), set(declared["levels"])
                except Exception as e:                  # noqa: BLE001 — a level the program cannot carry: none, said
                    self.level_rep.append({"error": "%s: %s" % (type(e).__name__, e)})
            self._levels()
            self.game_id = meta.get("game")

        def _take(self, out):
            super()._take(out)
            if getattr(self, "lmap", None) is not None:
                self.lmap.observe(self.consistent())    # the map follows what the robot sees
                self._levels()

        def consistent(self):
            """The facts the map folds: an inrecep(O, R) only where R stands at O's objat location (ALFWorld's facts
            can keep a thing in two receptacles at once, a stale one among them: handtowel1 on the countertop and in
            its holder, objat at the holder's)."""
            loc = {rec: l for l, recs in self.recat.items() for rec in recs}
            at = {a[6:-1].split(",")[0]: a[6:-1].split(",")[1] for a in self.dyn if a.startswith("objat(")}
            return {a for a in self.dyn if not a.startswith("inrecep(")
                    or at.get(a[8:-1].split(",")[0]) in (None, loc.get(a[8:-1].split(",")[1]))}

        # ── what the robot sees ──
        def seen_place(self, obj):
            """The receptacle the map has seen OBJ in (None: not seen, or not where it was)."""
            return self.lmap.load()["things"].get(obj, {}).get("in")

        def located(self, r):
            """VIEW: a located fact only for a thing seen there; plain: every fact."""
            if not self.view or self.lmap is None:
                return r
            loc = {rec: l for l, recs in self.recat.items() for rec in recs}
            out = {}
            for a, n in r.items():
                if a.startswith("inrecep("):
                    o, rec = a[8:-1].split(",")
                    if self.seen_place(o) != rec:
                        continue
                elif a.startswith("objat("):
                    o, l = a[6:-1].split(",")
                    p = self.seen_place(o)
                    if p is None or loc.get(p) != l:
                        continue
                out[a] = n
            return out

        def reading(self):
            r = self.located(super().reading())
            r.update(self.loop_levels)
            return r

        def dynamic_preds(self):
            return set(super().dynamic_preds()) | self.hook_preds

        # ── the level port ──
        def where(self):
            """The port where(O, R) over the instance's objects and receptacles: a thing seen, where it was seen; a
            target not seen yet, its wanted kind's belief; else the map's belief of it; else none (a lone row of 0)."""
            from semantic_world.room import want_handle
            d = self.lmap.load()
            tbl = {}
            for o in self.objects:
                seen = d["things"].get(o, {}).get("in")
                bel = {seen: 1.0} if seen else (d["belief"].get(o) or d["belief"].get(want_handle(o)) or {})
                z = sum(bel.values())
                for rec in self.receptacles:
                    p = bel.get(rec, 0.0) / z if z > 0 else 0.0
                    tbl[(o, rec)] = repr(float(Fraction(int(p * 10 ** 9), 10 ** 9)))
            return tbl

        def belief_lines(self, peaked_at=0.5):
            """The host's belief where a fact is UNOBSERVED (policy-tuning-2 2c), through the port the LevelHook reads:
            per task target not seen yet, the places where(O, R) gives mass, the largest mass, spread or peaked. A seen
            target's place is a fact (where = 1.0 there): no line. → ["inrecep(O, R) via where(O, R): candle2 — 18
            places, max 0.06, spread"]."""
            seen = self.lmap.load()["things"]
            tbl, out = self.where(), []
            for o in self.targets:
                if (seen.get(o) or {}).get("in"):
                    continue
                ps = [float(tbl.get((o, r), 0.0)) for r in self.receptacles]
                ps = [x for x in ps if x > 0]
                if not ps:
                    continue
                m = max(ps)
                out.append("inrecep(O, R) via where(O, R): %s — %d place%s, max %.2f, %s"
                           % (o, len(ps), "" if len(ps) == 1 else "s", m, "peaked" if m > peaked_at else "spread"))
            return out

        def _levels(self):
            if self.hook is None:
                return
            beliefs = set(DECLARED.get("beliefs") or {}) if self.declared is None else set(self.declared.get("beliefs") or {})
            counts = {a: 1 for a in self.located(super().reading()) if a.split("(")[0] not in beliefs}   # drawn from the port
            try:
                self.loop_levels, rep = self.hook.levels(counts, {"where": self.where()})
            except Exception as e:                      # noqa: BLE001 — the level is advice: it never stops the run
                self.loop_levels, rep = {}, {"error": "%s: %s" % (type(e).__name__, e)}
            self.level_rep.append(dict(rep, step=len(getattr(self, "commands", []) or [])))

    return MapHost
