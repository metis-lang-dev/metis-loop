"""The phase driver (loop-policy step 2; docs/POLICY.md): the agentic loop's policy over a world host.

    python -m policy.driver --run DIR --world alfworld --family pick_and_place_simple \\
        --phase explore|exploit|refactor --brain openrouter/<model>|claude|script:<file> --budget USD
    python -m policy.driver --run DIR --resume          # re-engage after the person answered the ask
    python -m policy.driver --run DIR --from-run SRC …  # start at the refactor phase from SRC's accepted state

The loop's catalog is RUN/catalog: one domain, `alf`, the lifted BASE every game's instance includes
(the world's generator writes the instances). It starts EMPTY (the generator's declarations, no rule).
Every write is a proposal to metis.gate's EXPERIMENTAL policy, judged by the numbers this driver
measures (gain): on its records and on the GATE split's games (never shown to the brain).

  explore   the brain's rules from TRANSITIONS: each discovery game is walked (the admissible commands,
            the untried first), every step a record (before, command, after, text); a record the rules
            do not predict is the seed of a proposal (gate: fits_records, likelihood not down). Ends
            after K unexplained records without an accept, or when W steps in a row are all predicted.
  exploit   the program acts (the kernel, the host attached); a refused command is a SURPRISE → revise
            (gate: likelihood up, or success up with the likelihood not down); an episode not won with
            no surprise → the policy's rules (the same gate). A surprise refused twice at one rule
            sends the loop to a PROBE there (snapshot, each admissible command once, restore): records.
  refactor  after R rules or K accepts: the brain's refactoring of the base (gate: the discovery games
            replay the same commands, the gate split's success not down, the vector down).

DISENGAGEMENT (POLICY.md): cornered by budget | no_progress | out_of_vocabulary | contradiction |
stuck, the loop stops acting, snapshots (the world's commands, the base, the records, its counters),
and proposes an ASK (one question) through the gate; the run ends with the record as its last line
(exit 3). `--resume` reads the person's answer (metis.gate answer TOKEN) and re-engages from the
snapshot in the phase it names, the instruction in the brain's context.

Records: RUN/records/{transitions,surprises,heldout}.jsonl; RUN/state/{gate.json,journal.jsonl,run.json};
RUN/cost.jsonl (one line per brain call: its reported cost, the key's usage before it); RUN/prompts.jsonl."""
import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

from . import measure, prompts
from . import acting, alfworld, compose, hier, minihack, scienceworld
from .alfworld import AlfWorld, rules_of
from .brain import Brain, Budget, PromptCap, block_of, splice

WORLDS = {"alfworld": (AlfWorld, alfworld.empty_base), "alfworld_view": (alfworld.AlfViewWorld, alfworld.empty_base), "scienceworld": (scienceworld.ScienceWorld, scienceworld.empty_base),
          "minihack": (minihack.MiniHack, minihack.empty_base)}
DOMAIN = "alf"                      # the world's; set per run (Driver.world)
DEFAULTS = {"explore_steps": 40, "explore_k": 6, "explore_w": 30, "exploit_episodes": 6, "act_steps": 60,
            "proposals": 30, "no_progress": 4, "refactor_rules": 14, "refactor_k": 8, "repairs": 2, "probe_after": 3, "fit_repairs": 1,
            "ground_budget": 1000000}


class Disengage(Exception):
    def __init__(self, reason, question, options=(), tried=(), believes=()):
        super().__init__(question)
        self.reason, self.question = reason, question
        self.options, self.tried, self.believes = list(options)[:3], list(tried), list(believes)


def by_verb(rng, acts):
    """A verb first (uniformly), then a command of it: the game lists far more goes than opens,
    takes and puts, and a uniform pick over commands would walk and never act."""
    verbs = sorted({a["verb"] for a in acts})
    v = rng.choice(verbs)
    return rng.choice([a for a in acts if a["verb"] == v])


def jl_append(path, rec):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def jl_read(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


GEN_DECL = "% generated from the levels: block (policy-tuning-2 2g)"


def generated_level_decls(text, levels, ns):
    """The declarations a ```yaml levels: block fully determines and TEXT lacks (2g: nina's 2f row declared a level
    right and its rules read place_level(high, O, R), but the llp lacked `type level` and the pred, and did not
    compile): for a level read from a belief port, `type level {names}`, the port `weight PORT(..) reads {PRED(..)}`
    and `pred NAME(level, <PRED's argument types>)`, each marked generated. LEVELS: one member's {"levels", "beliefs"}."""
    import re
    out = []
    beliefs = (levels or {}).get("beliefs") or {}
    for name, spec in ((levels or {}).get("levels") or {}).items():
        port = ((spec or {}).get("from") or {}).get("belief")
        if not port:
            continue                                   # an evaluate level: its query names no pred to declare
        pred = next((b for b, bs in beliefs.items() if (bs or {}).get("port") == port), None)
        sig = re.search(r"^\s*pred\s+%s\(([^)]*)\)" % re.escape(pred or "\0"), text, re.M) if pred else None
        if sig is None:
            continue                                   # the belief's pred undeclared: nothing determines the arity
        types = [t.strip() for t in sig.group(1).split(",") if t.strip()]
        names = (spec or {}).get("names") or ["low", "mid", "high"]
        if not re.search(r"^\s*type\s+level\s*\{", text, re.M):
            out.append("type level {%s}." % " ".join(names))
        # the port's variables as the brain's level-reading rule names them ($place_level(high, O, R) -> O, R): the
        # belief's `lone:` names one of them, and a port without it cannot resolve the group (the hook's levels fail)
        use = re.search(r"\$%s\(\s*\w+\s*,([^)]*)\)" % re.escape(name), text)
        vs = [v.strip() for v in use.group(1).split(",")] if use else []
        if len(vs) != len(types) or not all(v[:1].isupper() for v in vs):
            vs = []
            for t in types:                            # else the types' initials, made distinct
                v = t[:1].upper() or "X"
                while v in vs:
                    v += "2"
                vs.append(v)
        lone = (beliefs.get(pred) or {}).get("lone") or (beliefs.get(pred) or {}).get("one")
        if lone and lone not in vs and vs:
            vs[-1] = lone
        vars_ = ", ".join(vs)
        if not re.search(r"^\s*weight\s+%s\(" % re.escape(port), text, re.M):
            out.append("weight %s(%s) reads {%s(%s)}." % (port, vars_, pred, vars_))
        if not re.search(r"^\s*pred\s+%s\(" % re.escape(name), text, re.M):
            out.append("pred %s(level, %s) : %s." % (name, ", ".join(types), ns))
    return out


def mark_generated(text, gen):
    """TEXT with each generated declaration marked (splice takes a declaration only when it ends with its period)."""
    out = []
    for line in text.split("\n"):
        out.append(line + "   " + GEN_DECL if line.strip() in gen else line)
    return "\n".join(out)


def yaml_block(answer):
    """The answer's ```yaml block, verbatim (or None)."""
    import re
    m = re.search(r"```ya?ml\n(.*?)```", answer or "", re.S)
    return m.group(1).strip() if m else None


def policy_first(belief):
    """Exploit asks for the policy first when the episode's belief section shows a spread belief (2f)."""
    return any(l.rstrip().endswith("spread") for l in (belief or ()))


class Driver:
    def __init__(self, run, brain, family="pick_and_place_simple", discovery=2, gate_games=2, seed=1, cfg=None, out=print, world="alfworld", skill=None):
        from metis import gate
        global DOMAIN
        self.World, empty_base = WORLDS[world]
        DOMAIN = self.World.DOMAIN
        prompts.set_world(self.World)
        self.skill = Path(skill).resolve() if skill else None            # policy-tuning: the skill file the prompts carry
        prompts.set_skill(self.skill.read_text() if self.skill else "")
        self.run, self.brain, self.family, self.seed = Path(run).resolve(), brain, family, seed
        self.cfg = dict(DEFAULTS, **(cfg or {}))
        self.out = out
        self.root = self.run / "catalog"
        self.rec_dir, self.state_dir = self.run / "records", self.run / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.gate = gate.Gate.at(self.state_dir, policy="experimental", gain=self.gain)
        self.state = json.loads((self.state_dir / "run.json").read_text()) if (self.state_dir / "run.json").exists() else {
            "phase": "explore", "proposals": 0, "accepted": 0, "refused_run": 0, "accepts_since_refactor": 0,
            "family": family, "seed": seed, "discovery": discovery, "gate_games": gate_games, "notes": [],
            "status": "running", "cfg": self.cfg, "world": world, "skill": str(self.skill) if self.skill else None}
        self.cfg = dict(self.state.get("cfg") or self.cfg, **(cfg or {}))
        self.level_preds()                       # a resumed run's declared level ports (recorded and replayed per step)
        # the grounder's budget (metispy METIS_GROUND_BUDGET): a candidate whose variables range over whole types is
        # refused with its words, the brain's to repair, not materialised until the 6G scope kills the run (sw-s2:
        # take over connected(T1, T2), 167^2 terms x things x places, every round of every series)
        os.environ.setdefault("METIS_GROUND_BUDGET", str(self.cfg.get("ground_budget", DEFAULTS["ground_budget"])))
        if not (self.root / "domains" / DOMAIN / ("%s.llp" % DOMAIN)).exists():
            d = self.root / "domains" / DOMAIN
            d.mkdir(parents=True, exist_ok=True)
            (d / ("%s.llp" % DOMAIN)).write_text(empty_base(DOMAIN))      # the generator's start, not a proposal
            (d / "domain.yaml").write_text("program: %s.llp\ndisplay: %s, learned\nline: \"the loop's base over %s\"\n" % (DOMAIN, world, self.World.DESCRIPTION))
        self.disc = [self.World(g, self.run / "trees" / "current")
                     for g in self.World.sample("discovery", family, self.state["discovery"], seed)]
        self.held = [self.World(g, self.run / "trees" / "current")
                     for g in self.World.sample("gate", family, self.state["gate_games"], seed)]
        self.games = {w.iid: w for w in self.disc + self.held}
        self.dynamic, self.commands, self.verbs = self.World.vocabulary()
        self.start = set(hier.START) | hier.start_tokens(self.disc[0].instance_text(), self.dynamic)   # the instance's own start tokens (N5)   # the host's dynamic predicates, its table, its verb_why convention
        self._sync_tree("current", self.base())
        self.pred = None
        self.seed_record = None
        self.where = None                     # the world's snapshot where the loop last acted (N1: the disengagement keeps it)
        self._trans = None
        self.move = None                      # the refactoring move being judged (step 2c: the gate's per-move criteria)
        self.brain.keep(self.state)           # nina's R1: a resumed run keeps the first start's meter and its cap
        if self.state.get("prompt_chars"):
            self.brain.prompt_chars = self.state["prompt_chars"]
        self.save()

    def transitions(self):
        """The transition records so far (read once, then kept: nina's N6)."""
        if self._trans is None:
            self._trans = jl_read(self.rec_dir / "transitions.jsonl")
        return self._trans

    def record(self, rec, surprise=False):
        jl_append(self.rec_dir / ("surprises.jsonl" if surprise else "transitions.jsonl"), rec)
        if not surprise:
            self.transitions().append(rec)

    # ── the base and its trees ──
    def base(self):
        return (self.root / "domains" / DOMAIN / ("%s.llp" % DOMAIN)).read_text()

    def _sync_tree(self, name, text):
        b = self.run / "trees" / name / "base"
        b.mkdir(parents=True, exist_ok=True)
        (b / ("%s.llp" % DOMAIN)).write_text(text)
        return self.run / "trees" / name

    def predictor(self, name="current", text=None):
        tree = self._sync_tree(name, self.base() if text is None else text)
        return measure.Predictor(tree, self.games, self.dynamic, self.commands, self.verbs, getattr(self.World, "UNCOMPARED", ()))

    def current(self):
        if self.pred is None:
            self.pred = self.predictor("current")
        return self.pred

    def save(self):
        (self.state_dir / "run.json").write_text(json.dumps(self.state, indent=1))

    def say(self, what, **kw):
        line = dict({"t": time.strftime("%H:%M:%S"), "phase": self.state["phase"], "event": what}, **kw)
        jl_append(self.run / "run.log.jsonl", line)
        self.out(json.dumps(line))

    # ── the held-out records (the likelihood's set): a seeded walk on the gate split, once ──
    def heldout(self):
        p = self.rec_dir / "heldout.jsonl"
        if not p.exists():
            rng = random.Random(self.seed + 1000)
            for w in self.held:
                w.reset()
                for _ in range(self.cfg["explore_steps"] // 2):
                    acts = w.actions()
                    if not acts or w.done:
                        break
                    for c in w.unadmissible(rng):          # the refusals, from the same state
                        jl_append(p, dict(w.step(c), phase="heldout"))
                    jl_append(p, dict(w.step(by_verb(rng, acts)["command"]), phase="heldout"))
                w.close()
        return jl_read(p)

    # ── the gate's numbers ──
    def gain(self, plan, phase):
        if plan.get("domain") == compose.DIRECTOR:
            return self.gain_compose()
        if plan.get("domain") == "director":
            return self.gain_direct(next(f["text"] for f in plan["files"] if f["path"].endswith("director.llp")))
        text = next(f["text"] for f in plan["files"] if f["path"].endswith("%s.llp" % DOMAIN))
        if phase == "refactor" and hier.Split.of(text, self.World, self.start).is_split():
            return self.gain_split(text)
        cand, cur = self.predictor("candidate", text), self.current()
        held = self.heldout()
        bad = next((cand.compiles(i) for i in self.games if cand.compiles(i)), None)
        if bad:
            return {"fits_records": False, "likelihood": -1.0, "success": -1.0, "replay_identical": False,
                    "vector": {"before": 0, "after": 1}}
        n = {}
        if phase in ("exploit", "refactor"):
            # the success first: its runs' refusals on the gate split join the likelihood's records
            s_c, rc = self.success(self.run / "trees" / "candidate")
            s_0, r0 = self.success(self.run / "trees" / "current")
            n["success"] = round(s_c - s_0, 6)
            held = held + rc + r0
        lk = measure.likelihood(cand, held) - measure.likelihood(cur, held)
        n["likelihood"] = round(lk, 6)
        if phase == "explore":
            ok, why = measure.fits(cand, text, self.base(), self.seed_record,
                                   self.transitions() + jl_read(self.rec_dir / "surprises.jsonl"))
            n["fits_records"] = ok
            self.say("fits", ok=ok, why=why)
        if phase == "refactor":
            if self.move:
                n["move"] = self.move
            n["replay_identical"] = self.replay(self.run / "trees" / "candidate") == self.replay(self.run / "trees" / "current")
            v0, v1 = measure.vector(self.base(), cur, self.disc[0].iid), measure.vector(text, cand, self.disc[0].iid)
            n["vector"] = {"before": (v0.get("ground") or 0) + v0["rules"], "after": (v1.get("ground") or 0) + v1["rules"]}
        return n

    # ── the hierarchy's numbers (loop-policy step 2b) ──
    def hier_runs(self, games, text, label, director=None, guides=None):
        """The split of TEXT acting on GAMES (the manual switch, or with `director` a DirectorLoop
        factory the director's rules), each in RUN/hier/<label>/; with `guides` (each game's recorded
        commands) the records' replay."""
        sp = hier.Split.of(text, self.World, self.start)
        return [hier.run(w, sp, self.run / "hier" / label, "%s.llp" % DOMAIN, self.cfg["act_steps"], self.seed, director=director,
                         guide=(guides[i] if guides else None)) for i, w in enumerate(games)]

    def replays(self, recorded, runs):
        """POLICY.md's regression: every command the current program sent, the candidate sends — the
        candidate's records' replay (guided: where it may choose, it takes the recorded command) sent
        them all, in order, and diverged nowhere."""
        return all(not r.get("diverged") and r["commands"] == rec["commands"] for rec, r in zip(recorded, runs))

    def runs_of(self, games, text, label):
        """A base acting on GAMES: its hierarchy (the manual switch) when it is split, else flat."""
        if hier.Split.of(text, self.World, self.start).is_split():
            return self.hier_runs(games, text, label)
        return [w.act(self._sync_tree(label, text), self.cfg["act_steps"], seed=self.seed) for w in games]

    def vector_of(self, text, label):
        """The complexity vector's one number: rules + the events the instance grounds — summed over
        the domains (each specialist narrowed to its first activation's goal) when the base is split."""
        sp = hier.Split.of(text, self.World, self.start)
        if sp.is_split():
            return hier.split_vector(self.disc[0], sp, self.run / "hier" / ("v-" + label), "%s.llp" % DOMAIN)
        v = measure.vector(text, self.predictor(label, text), self.disc[0].iid)
        return (v.get("ground") or 0) + v["rules"]

    def flat_vector(self, text):
        """The flat program's vector: the base read whole (the program the hierarchy replaces)."""
        v = measure.vector(text, self.predictor("flat-v", text), self.disc[0].iid)
        return (v.get("ground") or 0) + v["rules"]

    def gain_split(self, text):
        """A split (or a split rewritten to the conventions): its manual switch replays what the
        current program sends on the discovery games, the gate split's success not down, the
        likelihood (the rules' world behaviour) not down, the vector — summed over the narrowed
        domains and the world model — below the flat program's (the program the hierarchy replaces)."""
        cand, cur = self.predictor("candidate", text), self.current()
        base = self.base()
        r0 = self.runs_of(self.disc, base, "current")
        rc = self.hier_runs(self.disc, text, "candidate", guides=[acting.Guide.of(r) for r in r0])
        gc, g0 = self.runs_of(self.held, text, "candidate"), self.runs_of(self.held, base, "current")
        held = self.heldout() + [t for e in gc + g0 for t in e["transitions"] if t["kind"] == "surprise"]
        amb = lambda t: len(hier.Split.of(t, self.World, self.start).ambiguous())
        n = {"move": self.move or "split",
             "replay_identical": self.replays(r0, rc),
             "success": round(sum(e["won"] for e in gc) / max(1, len(gc)) - sum(e["won"] for e in g0) / max(1, len(g0)), 6),
             "likelihood": round(measure.likelihood(cand, held) - measure.likelihood(cur, held), 6),
             # step 2c (the architect's ruling): each move against the base it replaces; the flat program's
             # vector beside it (the conventions' cap)
             "vector": {"before": self.vector_of(base, "current"), "after": self.vector_of(text, "candidate")},
             "flat": self.flat_vector(base),
             "ambiguous": {"before": amb(base), "after": amb(text)}}
        self.say("split-numbers", activations=[[a["domain"] for a in r.get("activations", [])] for r in rc][:1],
                 alternatives=sum(r.get("alternatives", 0) for r in rc), **n)
        return n

    def gain_direct(self, dtext):
        """The director: its rules make the switch the manual one made — the same commands on the
        discovery games, the gate split's success not down; the vector the hierarchy's with the
        director's rules, against the flat program's."""
        base = self.base()
        sp = hier.Split.of(base, self.World, self.start)
        make, _ = hier.director_factory(sp, self.run / "hier" / "director", text=dtext)
        rm = self.hier_runs(self.disc, base, "manual")
        rd = self.hier_runs(self.disc, base, "directed", make, guides=[acting.Guide.of(r) for r in rm])
        gd, gm = self.hier_runs(self.held, base, "directed", make), self.hier_runs(self.held, base, "manual")
        amb = len(sp.ambiguous())
        n = {"move": "direct",
             "replay_identical": self.replays(rm, rd),
             "success": round(sum(e["won"] for e in gd) / max(1, len(gd)) - sum(e["won"] for e in gm) / max(1, len(gm)), 6),
             "likelihood": 0.0,
             "vector": {"before": self.vector_of(base, "current"),
                        "after": self.vector_of(base, "current") + len(rules_of(hier.director_base_path().read_text()))},
             "flat": self.flat_vector(base),
             "ambiguous": {"before": amb, "after": amb}}
        self.say("direct-numbers", beats=len(rd[0].get("beats") or []) if rd else 0,
                 alternatives=sum(r.get("alternatives", 0) for r in rd), **n)
        return n

    def composition(self, root, sp):
        """SP as a tick tree under ROOT/domains/ (compose.compose) and its interface check. An I4 finding of two
        writers of a state pred adds a second resource (hands, …) gating both writers' rules that write it, and
        composes again (the architect's Q1 addition). → (Composition, the check's report, the resources added)."""
        metisc = compose.metisc_path()
        from metis.catalog import protocol_stub
        home = Path(protocol_stub.__file__).resolve().parent              # its iface/: the protocol, the tree director
        cap = compose.capacity_of(self.disc[0].instance_text())
        extra, added = {}, []
        while True:
            comp = compose.compose(sp, self.World, root, cap, start=self.start, holds_extra=extra, display=self.World.DESCRIPTION,
                                   levels=self.state.get("levels"))
            rep_ = compose.interface(comp.path, metisc, home)
            two = [(p, ws) for p, ws in compose.two_writers(rep_) if not any(p in r for r in added)]
            if not two or len(extra) >= len(compose.SECOND):
                self._composed = (comp, rep_, added)
                return comp, rep_, added
            for p, writers in two:
                r = compose.SECOND[len(extra)]
                extra[r] = {w: [n for n in sp.domains.get(w, ()) if p in hier.rule_atoms(sp.rules[n])[2]] for w in writers}
                added.append({"resource": r, "pred": p, "writers": writers})

    def gain_compose(self):
        """The composition (written by `composition` under RUN/hier/compose/): metisc --interface's counts, the
        split's replay of the current program's records and its held-out success against the flat program's — the
        tree's own run on metis-agent's Live is the parity harness's (ALFWorld) — the vector the split's with the
        tick's rules and the director's."""
        base = self.base()
        comp, rep_, _ = self._composed
        tree = comp.path.parent
        r0 = [w.act(self._sync_tree("current", base), self.cfg["act_steps"], seed=self.seed) for w in self.disc]
        rm = self.hier_runs(self.disc, base, "compose", guides=[acting.Guide.of(r) for r in r0])
        gm = self.hier_runs(self.held, base, "compose")
        g0 = [w.act(self._sync_tree("current", base), self.cfg["act_steps"], seed=self.seed) for w in self.held]
        v0 = self.vector_of(base, "current")
        n = {"move": "compose",
             "replay_identical": self.replays(r0, rm),
             "success": round(sum(e["won"] for e in gm) / max(1, len(gm)) - sum(e["won"] for e in g0) / max(1, len(g0)), 6),
             "interface": {"errors": rep_["counts"][0], "warnings": rep_["counts"][1]},
             "vector": {"before": v0, "after": v0 + sum(len(g) for g in comp.generated.values())},   # + the tick's rules
             "tree_parity": "pi/policy/parity.py (ALFWorld): the tree on metis-agent's Live against the flat program, not in the gate"}
        self.say("compose-numbers", errors=rep_["errors"][:12], warnings=rep_["warnings"], **n)
        return n

    def success(self, tree):
        """The gate split's win rate under TREE's program, and the refusals its runs met."""
        eps = [w.act(tree, self.cfg["act_steps"], seed=self.seed) for w in self.held]
        return (sum(e["won"] for e in eps) / max(1, len(eps)),
                [t for e in eps for t in e["transitions"] if t["kind"] == "surprise"])

    def replay(self, tree):
        return [w.act(tree, self.cfg["act_steps"], seed=self.seed)["commands"] for w in self.disc]

    # ── a proposal ──
    def propose(self, prompt, purpose, seed_game):
        """The brain's lines → the candidate base (repaired until it compiles in the seed record's
        instance) → the gate. → the verdict ("accept" | "refuse" | "error"). The level ports the answer's ```yaml
        block declares (compose.levels_of) are kept with an accepted proposal, for the members' manifests."""
        self._answer, self._cand_levels = None, {}
        try:
            return self._propose(prompt, purpose, seed_game)
        finally:
            self._cand_levels = {}
            self.level_preds()                              # a refused candidate's ports are gone again

    def splice_levels(self, lines):
        """The candidate: the brain's lines spliced over the base, and the declarations its levels: block determines
        (generated_level_decls) where the lines lack them."""
        text, info = splice(self.base(), lines)
        gen = generated_level_decls(text, (getattr(self, "_cand_levels", None) or {}).get(DOMAIN), DOMAIN)
        if gen:
            text, info = splice(self.base(), gen + list(lines))
            text = mark_generated(text, gen)
            info = dict(info, generated=gen)
            self.say("levels-generated", lines=gen)
        return text, info

    def keep_levels(self):
        """An accepted candidate's level ports join the run's (judge's accept, before anything after it can raise)."""
        for m, keys in (getattr(self, "_cand_levels", None) or {}).items():
            for k, entries in keys.items():
                self.state.setdefault("levels", {}).setdefault(m, {}).setdefault(k, {}).update(entries)

    def candidate_levels(self, answer):
        """The level ports ANSWER's ```yaml block declares (the flat program's own, or a split's members'), in force
        while the candidate is judged — its rules that read a level are exercised by the gate's runs."""
        sp = hier.Split.of(self.base(), self.World, self.start)
        members, planner = (list(sp.domains), sp.planner) if sp.is_split() else ([DOMAIN], DOMAIN)
        decl, findings = compose.levels_of(answer, members, planner)
        if decl or findings:
            self.say("levels-declared", declared=decl, findings=findings)
        self._cand_levels = decl
        self.level_preds(decl)

    def level_preds(self, extra=None):
        """The level ports declared so far (and EXTRA's, a candidate's): recorded per step and replayed from the
        records (acting.LEVEL_PREDS); the world's host carries the instrument for them (alfview.DECLARED, ALFWorld)."""
        from . import alfview
        merged = {}
        for src in (self.state.get("levels") or {}, extra or {}):
            for keys in src.values():
                for k in ("beliefs", "levels"):
                    merged.setdefault(k, {}).update(keys.get(k) or {})
        acting.LEVEL_PREDS = set(merged.get("levels") or {})
        alfview.DECLARED = merged
        return acting.LEVEL_PREDS

    def _propose(self, prompt, purpose, seed_game):
        if self.state["proposals"] >= self.cfg["proposals"]:
            raise Disengage("budget", "The proposals budget (%d) is spent. More proposals, another phase, or stop?" % self.cfg["proposals"],
                            options=["budget: more proposals", "phase: refactor now", "abandon"])
        answer = self._answer = self.ask(prompt, purpose)
        self.candidate_levels(answer)
        yml = yaml_block(answer)
        lines = block_of(answer)
        text, info = self.splice_levels(lines)
        if text == self.base():
            self.say("proposal", verdict="none", why="the brain proposed no change", purpose=purpose, call=self.called())
            return "none"
        for _ in range(self.cfg["repairs"]):
            words = self.predictor("candidate", text).compiles(seed_game)
            if not words:
                break
            # the level is the candidate's: the repair carries its yaml forward and never drops it (2g)
            lines = block_of(self.ask(prompt + "\n\n" + prompts.repair(lines, words, yml if self._cand_levels else None),
                                      purpose + "-repair"))
            text, info = self.splice_levels(lines)
        v = self.judge("program", info=info, cost=self.last_cost(), call=self.called(), text=text)
        # policy-tuning (s-1caedae5): a fits refusal in explore comes back to the brain ONCE, with the gate's
        # reason in its terms — what the rule consumes that the world keeps, what it misses, what it needs
        # that the record lacks, the record it contradicts (measure.explain); the repaired lines are judged
        rec = self.seed_record
        if v == "refuse" and purpose in ("explore", "probe") and rec is not None and self.cfg.get("fit_repairs", 1):
            last = next((e for e in reversed(self.gate.journal()) if e.get("event") == "proposal"), {})
            if (last.get("numbers") or {}).get("fits_records") is False:
                why = measure.explain(self.predictor("candidate", text), text, self.base(), rec, self.transitions())
                self.say("fit-repair", why=why, purpose=purpose)
                lines = block_of(self.ask(prompt + "\n\n" + prompts.fit_repair(lines, why), purpose + "-fit"))
                text2, info2 = splice(self.base(), lines)
                if text2 != self.base() and text2 != text and not self.predictor("candidate", text2).compiles(seed_game):
                    return self.judge("program", info=info2, cost=self.last_cost(), call=self.called(), text=text2)
        return v

    def ask(self, prompt, purpose):
        """One brain call; its caps cornered as a budget disengagement (the spend, nina's R5: the prompt's size)."""
        try:
            return self.brain.ask(prompt, purpose)
        except Budget as e:
            raise Disengage("budget", "The spend budget is exhausted (%s). Raise it, or stop?" % e,
                            options=["budget: more spend", "abandon"]) from None
        except PromptCap as e:
            raise Disengage("budget", "The %s prompt is past the per-request cap (%s): the base has grown. Refactor now, "
                            "or raise the cap?" % (purpose, e), options=["phase: refactor now", "budget: prompt_chars, a larger cap", "abandon"]) from None

    def _judge_uncounted(self, kind, by, info, cost, domain, call, **args):
        try:
            v = self.gate.propose(kind, domain or DOMAIN, self.root, phase=self.state["phase"], cost=cost, **args)["verdict"]
        except Exception as e:                      # noqa: BLE001 — the gate's refusal in words
            self.say("proposal", verdict="error", why=str(e), by=by, call=call, domain=domain or DOMAIN, counted=False, **(info or {}))
            v = {"verdict": "error"}
        else:
            self.say("proposal", verdict=v["verdict"], numbers=v["numbers"], why=v["why"], cost=cost, by=by, call=call,
                     domain=domain or DOMAIN, counted=False, **(info or {}))
        self.state.setdefault("moves", {})[self.move or kind] = v["verdict"]
        self.save()
        return v["verdict"]

    def judge(self, kind, by="brain", info=None, cost=None, domain=None, call=None, counted=True, **args):
        """A proposal through the gate (the brain's or, at re-engagement, the person's rule or edit),
        its bookkeeping one path for both: the counters, the current tree re-synced, the
        contradiction check; a gate's refusal in words is a refused proposal, not an end.
        `call`: the brain's call whose lines are judged (its line in prompts.jsonl; None for a move or
        the person's), journaled with the proposal (nina's policy-tuning R2: the rewrite's digest).
        `counted=False` (the compose move, policy-tuning-2): journaled and judged, but outside the run's counters —
        the card's old columns (proposals, accepted) stay those of the driver before it; its verdict in
        state["moves"]. → "accept" | "refuse" | "error"."""
        if not counted:
            return self._judge_uncounted(kind, by, info, cost, domain, call, **args)
        self.state["proposals"] += 1
        phase = self.state["phase"] if not (by == "person" and self.state["phase"] == "explore") else "exploit"
        try:
            pl = self.gate.propose(kind, domain or DOMAIN, self.root, phase=phase, cost=cost, **args)
            v = pl["verdict"]
        except Exception as e:                      # noqa: BLE001 — the gate's refusal in words (no plan left waiting)
            self.say("proposal", verdict="error", why=str(e), by=by, call=call, domain=domain or DOMAIN, **(info or {}))
            self.state["refused_run"] += 1
            self.save()
            return "error"
        self.say("proposal", verdict=v["verdict"], numbers=v["numbers"], why=v["why"], cost=cost, by=by, call=call,
                 domain=domain or DOMAIN, **(info or {}))
        if v["verdict"] == "accept":
            self.keep_levels()
            self.state["accepted"] += 1
            self.state["accepts_since_refactor"] += 1
            self.state["refused_run"] = 0
            self.pred = None
            self._sync_tree("current", self.base())
            self.check_contradiction()
        else:
            self.state["refused_run"] += 1
        self.save()
        if by == "brain" and self.state["refused_run"] >= self.cfg["no_progress"]:
            raise Disengage("no_progress", "%d proposals in a row were refused (the last: %s). Give me a note on what I miss, "
                            "a rule to try, or another phase?" % (self.state["refused_run"], "; ".join(v["why"][-2:])),
                            options=["note: what the rules miss", "phase: skip this state", "abandon"],
                            tried=self.journal_tail(), believes=[l for _, l in rules_of(self.base())])
        return v["verdict"]

    def called(self):
        """The brain's last call: its line in prompts.jsonl (1-based; the count survives a resume)."""
        p = self.brain.run_dir / "prompts.jsonl"
        return sum(1 for l in p.read_text().splitlines() if l.strip()) if p.exists() else None

    def last_cost(self):
        rows = jl_read(self.run / "cost.jsonl")
        return float(rows[-1].get("cost") or 0) if rows else 0.0

    def journal_tail(self, n=4):
        return [{k: e.get(k) for k in ("phase", "verdict", "why")} for e in self.gate.journal()[-n:] if e.get("event") == "proposal"]

    def note(self):
        return "; ".join(self.state.get("notes") or []) or None

    # ── explore ──
    def explore(self):
        rng = random.Random(self.seed)
        tried, counters = set(), [0, 0]          # unexplained, explained in a row: carried across the games
        for w in self.disc:
            w.reset()
            try:
                if self._explore_game(w, rng, tried, counters):
                    return
            finally:
                w.close()                         # nina's N4: every return closes the game's gym child
        self.say("explore-ends", why="the discovery games' steps are spent")

    def _explore_game(self, w, rng, tried, run):
        """One discovery game walked; → True when exploration is over (run: the counters, carried)."""
        unexplained, explained_run = run
        stale = 0
        for _ in range(self.cfg["explore_steps"]):
            acts = w.actions()
            if not acts or w.done:
                break
            fresh = [a for a in acts if (a["verb"], a["command"]) not in tried]
            stale = 0 if fresh else stale + 1
            if not fresh and self.cfg["probe_after"] and stale >= self.cfg["probe_after"]:
                a = self.brain_pick(w, acts)              # the walk finds nothing new: the brain chooses the probe (2b)
                stale = 0
            else:
                a = by_verb(rng, fresh or acts)
            tried.add((a["verb"], a["command"]))
            rec = w.step(a["command"])
            self.where = w.snapshot()
            self.check_vocabulary(rec)
            self.record(rec)
            if self.current().predicts(rec):
                explained_run += 1
                if explained_run >= self.cfg["explore_w"]:
                    self.say("explore-complete", why="%d steps in a row predicted" % explained_run)
                    return True
                continue
            explained_run = 0
            self.seed_record = rec
            sims = [r for r in self.transitions() if r["action"]["verb"] == rec["action"]["verb"]
                    and (r["game"], r["t"]) != (rec["game"], rec["t"])][-2:]
            verdict = self.propose(prompts.explore(self.base(), (self.commands, self.verbs), rec, sims, w.instance_text(), self.note(),
                                                   belief=self.belief_of(w)),
                                   "explore", rec["game"])
            unexplained = 0 if verdict == "accept" else unexplained + 1
            if unexplained >= self.cfg["explore_k"]:
                self.say("explore-ends", why="%d unexplained records without an accept" % unexplained)
                return True
        run[:] = [unexplained, explained_run]
        return False

    def brain_pick(self, w, acts):
        """The probe the brain chooses (step 2b; POLICY.md: exploration acts without a rule): the state,
        its admissible commands, the verbs the rules explain least; its answer, a number."""
        trans = self.transitions()
        miss = {}
        for r in trans[-200:]:
            if not self.current().predicts(r):
                miss[r["action"]["verb"]] = miss.get(r["action"]["verb"], 0) + 1
        p = prompts.probe(w.reading(), acts, miss, self.note())
        answer = self.ask(p, "probe-pick")
        m = re.search(r"\d+", answer or "")
        k = int(m.group(0)) - 1 if m else 0
        a = acts[k] if 0 <= k < len(acts) else acts[0]
        self.say("probe-pick", command=a["command"], answer=(answer or "").strip()[:80])
        return a

    def check_contradiction(self):
        """contradiction (POLICY.md): two accepted rules answering one action in one state with two
        afters, on the recent records; or a base that comes back to an earlier accepted text (a
        refactoring undone)."""
        sha = hashlib.sha256(self.base().encode()).hexdigest()[:12]
        seen = self.state.setdefault("bases", [])
        if seen and seen[-1] == sha:                 # the base unchanged (a director's or the composition's accept)
            pass
        elif sha in seen[:-1]:
            raise Disengage("contradiction", "The base came back to an earlier accepted version (%s): a change undone. "
                            "Which of the two should stand?" % sha, options=["note: which version", "phase: skip", "abandon"],
                            believes=[l for _, l in rules_of(self.base())])
        else:
            seen.append(sha)
        for rec in self.transitions()[-60:]:
            by = {}
            for name, after in self.current().events(rec):
                by.setdefault(name.split("[")[0], set()).add(frozenset(after))
            afters = set().union(*by.values()) if by else set()
            if len(by) > 1 and len(afters) > 1:
                raise Disengage("contradiction", "Rules %s answer %s in one state with different outcomes. Which one is right there?"
                                % (" and ".join(sorted(by)), rec["command"]), options=["note: which rule", "rule: the right one", "abandon"],
                                tried=[rec["game"], rec["t"]], believes=[l for n, l in rules_of(self.base()) if n in by])

    def check_vocabulary(self, rec):
        """out_of_vocabulary: the same before-facts and command, another after (the host does not read
        a fact the world has, or the world is not deterministic there)."""
        for r in self.transitions():
            if r["game"] == rec["game"] and r["command"] == rec["command"] and r["before"] == rec["before"] and r["after"] != rec["after"]:
                raise Disengage("out_of_vocabulary", "The same command in the same observed state gave two outcomes (%s): the world has a "
                                "fact the host does not read. Which fact, or skip this command?" % rec["command"],
                                options=["note: the missing fact", "phase: skip this state", "abandon"],
                                tried=[r["t"], rec["t"]], believes=[rec["added"], r["added"]])

    # ── exploit ──
    def exploit(self):
        refused_at = {}
        episodes = 0
        while episodes < self.cfg["exploit_episodes"]:
            all_won = True
            for w in self.disc:
                episodes += 1
                ep = w.act(self.run / "trees" / "current", self.cfg["act_steps"], seed=self.seed + episodes)
                for t in ep["transitions"]:
                    self.record(t, surprise=t["kind"] == "surprise")
                self.where = {"game": w.iid, "game_dir": w.game_dir, "commands": list(ep["commands"])}
                self.say("episode", game=w.iid, won=ep["won"], commands=len(ep["commands"]), refused=ep["refused"])
                if ep["stuck"]:
                    raise Disengage("stuck", "The task is stuck (%s) and no rule handles it. What should it do?" % ", ".join(ep["stuck"]),
                                    options=["note: what to do when stuck", "rule: a rule for it", "abandon"],
                                    believes=[l for _, l in rules_of(self.base())])
                if ep["won"]:
                    continue
                all_won = False
                # a surprise at a rule revised in vain fewer than twice → revise; refused twice at one rule →
                # the probe there (data, not another guess: nina's R2); then that rule's failures are the policy's
                sur = next((t for t in ep["transitions"] if t["kind"] == "surprise"
                            and refused_at.get(t["rule"].split("[")[0], 0) < 2), None)
                # policy-tuning-2 2f (ruled): where the host shows a SPREAD belief (a task target unseen), exploit's first
                # ask is the policy's, before the surprise revisions: only a policy rule can read a level
                if policy_first(ep.get("belief")) and not self.state.get("policy_first"):
                    self.state["policy_first"] = "belief"
                    self.say("policy-first", why="belief", game=w.iid, belief=ep.get("belief"))
                    sur = None
                if sur is not None:
                    key = sur["rule"].split("[")[0]
                    line = next((l for n, l in rules_of(self.base()) if n == key), "")
                    self.seed_record = sur
                    v = self.propose(prompts.revise(self.base(), (self.commands, self.verbs), sur, line, w.instance_text(), self.note(),
                                                    belief=ep.get("belief") or ()), "revise", w.iid)
                    if v != "accept":
                        refused_at[key] = refused_at.get(key, 0) + 1
                        if refused_at[key] >= 2:
                            self.probe(w, ep, sur)
                else:
                    self.propose(prompts.policy(self.base(), (self.commands, self.verbs), self.World.task_facts(w.instance_text()), ep,
                                                w.instance_text(), self.note(), belief=ep.get("belief") or ()), "policy", w.iid)
                if self.should_refactor():
                    return "refactor"
            if all_won:
                self.say("exploit-ends", why="every discovery game won")
                return "refactor" if self.should_refactor(force=True) else None
        return None

    def belief_of(self, w):
        """The host's belief where a fact is unobserved, for the prompt (a world without a map: none)."""
        f = getattr(w, "belief_lines", None)
        if f is None or getattr(w, "host", None) is None:
            return []
        try:
            return f()
        except Exception:                               # noqa: BLE001 — the belief is the prompt's aid, never the run's stop
            return []

    def probe(self, w, ep, sur):
        """Snapshot at the surprise's state, each admissible command once from it, restore: the
        records the exploration lacked (POLICY.md: data, not another guess)."""
        k = ep["commands"].index(sur["command"]) if sur["command"] in ep["commands"] else len(ep["commands"])
        snap = {"game": w.iid, "game_dir": w.game_dir, "commands": ep["commands"][:k]}
        w.restore(snap)
        n = 0
        for a in w.actions():
            w.restore(snap)
            rec = dict(w.step(a["command"]), phase="probe")
            self.record(rec)
            n += 1
        w.close()
        self.say("probe", game=w.iid, at=k, records=n)
        # back to exploration around that state: each record the rules do not predict, a proposal
        recs = [r for r in self.transitions()[-n:] if not self.current().predicts(r)] if n else []
        phase, self.state["phase"] = self.state["phase"], "explore"
        try:
            for rec in recs[:3]:
                if self.current().predicts(rec):
                    continue
                self.seed_record = rec
                self.propose(prompts.explore(self.base(), (self.commands, self.verbs), rec, [], w.instance_text(), self.note()), "probe", w.iid)
        finally:
            self.state["phase"] = phase

    def should_refactor(self, force=False):
        n = len(rules_of(self.base()))
        return n and (force or n > self.cfg["refactor_rules"] or self.state["accepts_since_refactor"] >= self.cfg["refactor_k"])

    # ── refactor ──
    def refactor(self):
        """The refactoring moves (see _refactor), the move marker cleared however they end (nina's 2c N1)."""
        try:
            return self._refactor()
        finally:
            self.move = None

    def _refactor(self):
        """POLICY.md's refactoring, as built (step 2b): PRUNE the rules that can never fire; SPLIT the
        base by the host verb its rules send (the planner the rest); when a goal kind has more than one
        specialist, the brain rewrites the split to HIERARCHY.md's conventions; then DIRECT: the
        director's instance from the ports. Each a proposal judged by the replay, the success and the
        vector; a base the moves leave alone gets the brain's flat refactoring."""
        text = self.base()
        sha = hashlib.sha256(text.encode()).hexdigest()[:12]
        if self.state.get("refactored_at") == sha:          # the same base the last refactoring saw: nothing new to ask
            self.say("refactor-skipped", why="the base is unchanged since the last refactoring")
            return
        self.state["accepts_since_refactor"] = 0
        moved = False
        dead = hier.never_firing(text, self.dynamic, self.start)
        if dead:
            pruned, info = splice(text, ["drop %s" % n for n in dead])
            self.move = "prune"
            moved |= self.judge("program", info=dict(info, prune=dead), text=pruned) == "accept"
        sp = hier.Split.of(self.base(), self.World, self.start)
        if not sp.is_split():
            cand = hier.split_by_verb(self.base(), self.World, start=self.start)
            if len(cand.specialists) >= 2:
                self.move = "split"
                moved |= self.judge("program", info={"split": cand.ports()}, text=hier.annotate(self.base(), cand)) == "accept"
                sp = hier.Split.of(self.base(), self.World, self.start)
        if sp.is_split():
            amb = sp.ambiguous()
            if amb:
                self.move = "conventions"
                v = self.propose(prompts.conventions(self.base(), (self.commands, self.verbs), sp.ports(), amb, self.note()),
                                 "conventions", self.disc[0].iid)
                moved |= v == "accept"
                sp = hier.Split.of(self.base(), self.World, self.start)
                amb = sp.ambiguous()
            ddir = self.root / "domains" / "director"
            if not amb and not (ddir / "director.llp").exists():
                ddir.mkdir(parents=True, exist_ok=True)
                shutil.copy(hier.director_base_path(), ddir / "director_domain.llp")      # the lifted director: the world's, as the empty base is
                dtext, _ = hier.director_text(sp, "director_domain.llp")
                self.move = "direct"
                moved |= self.judge("program", domain="director", info={"direct": sp.ports()}, text=dtext) == "accept"
            elif amb:
                self.say("direct-waits", why="goal kinds with more than one specialist: %s" % json.dumps(amb))
            # policy-tuning-2 (brief v2 §A): COMPOSE, the split as a tick tree — members that trigger themselves, the
            # generic tree director's instance (the judged text), metisc --interface as the gate's step
            if not amb and not (self.root / "domains" / compose.DIRECTOR / ("%s.llp" % compose.DIRECTOR)).exists():
                self.move = "compose"
                comp, rep_, added = self.composition(self.run / "hier" / "compose" / "catalog", sp)
                dtext = (comp.path.parent / compose.DIRECTOR / ("%s.llp" % compose.DIRECTOR)).read_text()
                v = self.judge("program", domain=compose.DIRECTOR, counted=False, info={"compose": {
                    "members": comp.members, "resources": comp.resources, "added": added,
                    "interface": rep_["counts"], "errors": rep_["errors"][:12], "warnings": rep_["warnings"]}}, text=dtext)
                if v == "accept":                            # the accepted director's composition, beside the base
                    self.composition(self.root, sp)
                moved |= v == "accept"
        self.move = None
        self.state["refactored_at"] = hashlib.sha256(self.base().encode()).hexdigest()[:12]
        if moved or sp.is_split():
            return
        p = (f"You are refactoring the rules of {self.World.DESCRIPTION} without changing what they do.\n\n{prompts.LANGUAGE}\n\n"
             f"{prompts.vocabulary(self.commands, self.verbs)}\n\nThe base:\n```llp\n{text.strip()}\n```\n\n"
             "Make it smaller and clearer: merge rules that differ only in a fact they read, drop a rule no state can enable, "
             "name the program's tokens so each rule's role reads. Every command the program sends in a state must stay the same."
             f"{prompts.instruction(self.note())}\n\nAnswer with ONE ```llp block of the replaced lines and `drop NAME` lines.")
        self.propose(p, "refactor", self.disc[0].iid)

    # ── the run ──
    def go(self, phase=None):
        if phase:
            self.state["phase"] = phase
        self.save()
        try:
            while True:
                ph = self.state["phase"]
                if ph == "explore":
                    self.explore()
                    self.state["phase"] = "exploit"
                elif ph == "exploit":
                    nxt = self.exploit()
                    if nxt is None:
                        break
                    self.state["phase"] = nxt
                elif ph == "refactor":
                    self.refactor()
                    self.state["phase"] = "exploit"
                    if self.state.get("refactored"):
                        break
                    self.state["refactored"] = True
                self.save()
            self.state["status"] = "done"
            self.save()
            self.say("done", accepted=self.state["accepted"], proposals=self.state["proposals"], spent=round(self.brain.spent(), 4))
            return 0
        except Disengage as d:
            return self.disengage(d)

    def evaluate(self, split, n, mode="flat"):
        """The base as it is, acting on N games of SPLIT (valid_unseen: the held-out): no brain, no
        write; mode flat (the base read whole), hier (its split, the manual switch) or director (the
        catalog's director makes the switch). → RUN/records/evaluate-<split>[-mode].json."""
        games = [self.World(g, self.run / "trees" / "current") for g in self.World.sample(split, self.family, n, self.seed)]
        if mode == "flat":
            eps = [w.act(self.run / "trees" / "current", self.cfg["act_steps"], seed=self.seed) for w in games]
        else:
            make = None
            if mode == "director":
                dfile = self.root / "domains" / "director" / "director.llp"
                if not dfile.exists():
                    raise SystemExit("no director in the catalog yet (the refactor phase's DIRECT)")
                make, _ = hier.director_factory(hier.Split.of(self.base(), self.World, self.start), self.run / "hier" / "evaluate-director",
                                                text=dfile.read_text())
            eps = self.hier_runs(games, self.base(), "evaluate-" + mode, director=make)
        out = {"split": split, "mode": mode, "n": len(eps), "won": sum(e["won"] for e in eps), "rules": len(rules_of(self.base())),
               "commands": [len(e["commands"]) for e in eps], "refused": [e["refused"] for e in eps],
               "games": [{k: e[k] for k in ("game", "won", "commands", "refused", "stuck")} for e in eps]}
        if mode != "flat":
            sp = hier.Split.of(self.base(), self.World, self.start)
            out["activations"] = [len(e.get("activations") or []) for e in eps]
            out["domains"] = sorted(sp.domains)                    # the structural column (policy-tuning step 3)
            out["ports"] = sp.ports()
            out["handles_declared"] = hier.director_text(sp, "director_domain.llp")[0].count("handles(") if sp.is_split() else None
            for g, e in zip(out["games"], eps):
                g["activations"] = [{"domain": x["domain"], "fired": x.get("fired"), "results": x["results"], "reads": x.get("reads") or []}
                                    for x in e.get("activations") or []]
            out["beats"] = [len(e.get("beats") or []) for e in eps] if mode == "director" else None
        (self.rec_dir / ("evaluate-%s%s.json" % (split, "" if mode == "flat" else "-" + mode))).write_text(json.dumps(out, indent=1))
        self.say("evaluate", split=split, mode=mode, won=out["won"], n=out["n"], commands=out["commands"], refused=out["refused"])
        return 0

    def disengage(self, d):
        """The minimal-risk condition: nothing more is sent; the snapshot; the ask."""
        for w in self.games.values():
            w.close()
        snap = {"phase": self.state["phase"], "base_sha": hashlib.sha256(self.base().encode()).hexdigest()[:12],
                "base": self.base(), "world": self.where, "records": str(self.rec_dir), "state": dict(self.state),
                "resume": "the phase re-enters from its start with the base and the records as they are; the world's "
                          "commands (world) say where it stood"}
        sp = self.state_dir / ("snapshot-%d.json" % (len(self.gate.asks()) + len(self.gate.answers()) + 1))
        sp.write_text(json.dumps(snap, indent=1))
        a = self.gate.propose("ask", DOMAIN, self.root, phase=self.state["phase"], reason=d.reason, tried=d.tried,
                              believes=d.believes, options=d.options, question=d.question, snapshot=str(sp))
        self.state.update(status="disengaged", ask=a["token"])
        self.save()
        self.say("disengaged", reason=d.reason, token=a["token"])
        self.out(json.dumps({"disengaged": a["ask"], "token": a["token"],
                             "answer": "python -m metis.gate --state %s answer %s" % (self.state_dir, a["token"])}))
        return 3

    def resume(self):
        """Re-engagement: the person's answer read, the instruction applied, the phase resumed."""
        tok = self.state.get("ask")
        ans = self.gate.answers(tok) if tok else None
        if ans is None:
            self.out(json.dumps({"waiting": tok, "ask": next((a["ask"] for a in self.gate.asks() if a["token"] == tok), None)}))
            return 4
        ins = ans["instruction"]
        self.say("re-engaged", instruction=ins)
        self.state.update(status="running", ask=None, refused_run=0)
        k = ins["kind"]
        if k == "abandon":
            self.state["status"] = "abandoned"
            self.save()
            return 0
        if k in ("note", "rule"):
            self.state.setdefault("notes", []).append(ins.get("text", ""))
        if k == "budget":
            for key, cfgk in (("proposals", "proposals"), ("beats", "explore_steps")):
                if ins.get(key):
                    self.cfg[cfgk] = self.cfg[cfgk] + int(ins[key])
            if ins.get("prompt_chars"):                       # the option the prompt cap's ask offers (nina's N7)
                self.brain.prompt_chars = self.state["prompt_chars"] = int(ins["prompt_chars"])
            if ins.get("spend") and self.brain.spend is not None:
                self.brain.spend += float(ins["spend"])
                self.state["spend_cap"] = self.brain.spend          # the cap the meter keeps across resumes (R1)
            self.state["cfg"] = self.cfg
        phase = None
        if k == "phase":
            phase = ins.get("phase") if ins.get("phase") in ("explore", "exploit", "refactor") else None
            if ins.get("phase") == "skip":
                phase = {"explore": "exploit", "exploit": "refactor", "refactor": "exploit"}[self.state["phase"]]
        # the person's rule or edit: through the gate as the brain's are, one path (nina's R3, R4)
        if k == "rule":
            self.seed_record = None
            text, info = splice(self.base(), block_of(ins["text"]))
            self.judge("program", by="person", info=info, text=text)
        if k == "edit" and (ins.get("path") or "%s.llp" % DOMAIN).split("/")[-1] != "%s.llp" % DOMAIN:
            self.say("proposal", verdict="error", by="person",                # nina's N9: the base is the one file the loop writes
                     why="an edit of %s: the loop's one file is the base, %s.llp" % (ins.get("path"), DOMAIN))
        elif k == "edit":
            # the person's edit applied to the base's text and judged as the base it makes: the SDK's edit check
            # compiles the file alone, and a lifted base has no types of its own (the instance declares them)
            self.seed_record = None
            base, old = self.base(), ins.get("old", "")
            if not old or base.count(old) != 1:
                self.say("proposal", verdict="error", by="person", why="the edit's old text occurs %d times in the base, not once"
                         % (base.count(old) if old else 0))
            else:
                self.judge("program", by="person", info={"edit": True}, text=base.replace(old, ins.get("new", ""), 1))
        return self.go(phase)


HANDED = ("family", "seed", "discovery", "gate_games", "world")


def handover(src, run, skill=None):
    """policy-tuning-2 step 2b's row refactor-from-scripted: RUN starts at the refactor phase from SRC's accepted state (a
    run that passed exploit, the scripted brain's): its base, records and level ports. The counters, the meter, the
    journal and the refactoring's marks are RUN's own (the brain's proposals alone counted); the hand-over in the state."""
    src, run = Path(src).resolve(), Path(run).resolve()
    st = json.loads((src / "state" / "run.json").read_text())
    if (run / "state" / "run.json").exists():
        raise SystemExit("--from-run: %s has a run already" % run)
    if st.get("status") != "done" or not st.get("accepted"):
        raise SystemExit("--from-run: %s did not end done with an accepted policy (%s, %s accepted)" % (src, st.get("status"), st.get("accepted")))
    for sub in ("catalog", "records"):
        shutil.copytree(src / sub, run / sub, dirs_exist_ok=True)
    for ev in (run / "records").glob("evaluate-*.json"):     # the source's numbers: the new run measures its own
        ev.unlink()
    state = {k: st[k] for k in HANDED + ("cfg", "levels", "notes") if k in st}
    state.update(phase="refactor", proposals=0, accepted=0, refused_run=0, accepts_since_refactor=0, status="running",
                 skill=str(Path(skill).resolve()) if skill else None,
                 handover={"from": str(src), "phase": st.get("phase"), "accepted": st.get("accepted"), "proposals": st.get("proposals")})
    (run / "state").mkdir(parents=True, exist_ok=True)
    (run / "state" / "run.json").write_text(json.dumps(state, indent=1))
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy.driver", description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--world", default="alfworld", choices=sorted(WORLDS))
    ap.add_argument("--family", default="pick_and_place_simple")
    ap.add_argument("--phase", choices=["explore", "exploit", "refactor"])
    ap.add_argument("--brain", default="script:/dev/null")
    ap.add_argument("--budget", type=float, default=None, help="the run's spend cap (USD), the key's own usage the meter")
    ap.add_argument("--max-tokens", type=int, default=2048, help="the per-request cap on the answer")
    ap.add_argument("--discovery", type=int, default=2)
    ap.add_argument("--gate-games", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--set", action="append", default=[], help="KEY=N: a budget of DEFAULTS (explore_steps, proposals, …)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--from-run", metavar="SRC", help="start at the refactor phase from SRC's accepted state (a run ended done)")
    ap.add_argument("--evaluate", metavar="SPLIT", help="act the base as it is on --n games of SPLIT (heldout, or the world's own name): no brain")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--skill", metavar="FILE", help="a skill the brain follows: its text in every prompt (policy-tuning)")
    ap.add_argument("--mode", choices=["flat", "hier", "director"], default="flat", help="--evaluate: the base whole, its split, or its director")
    a = ap.parse_args(argv)
    if a.brain.startswith("openrouter/") and a.budget is None:
        ap.error("a paid brain needs --budget (USD): the run's spend is capped where it is spent")
    cfg = {k: int(v) for k, v in (s.split("=", 1) for s in a.set)}
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:
        ap.error("--set: unknown %s (one of %s)" % (", ".join(sorted(unknown)), ", ".join(DEFAULTS)))
    if a.from_run:
        src = handover(a.from_run, a.run, a.skill)
        mine = {"family": a.family, "seed": a.seed, "discovery": a.discovery, "gate_games": a.gate_games, "world": a.world}
        wrong = {k: (src.get(k), mine[k]) for k in HANDED if src.get(k, mine[k]) != mine[k]}
        if wrong:
            shutil.rmtree(Path(a.run) / "state")
            ap.error("--from-run: the source's %s differ from this run's" % wrong)
    brain = Brain(a.brain, a.run, spend=a.budget, max_tokens=a.max_tokens)
    d = Driver(a.run, brain, a.family, a.discovery, a.gate_games, a.seed, cfg, world=a.world, skill=a.skill)
    if a.evaluate:
        return d.evaluate(a.evaluate, a.n, a.mode)
    return d.resume() if a.resume else d.go(a.phase)


if __name__ == "__main__":
    sys.exit(main())
