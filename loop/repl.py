"""The loop REPL — the kernel-as-session, Lean/Coq style: a small
stateful core over the metispy primitives, one dispatcher, two
front-ends (an interactive prompt and a JSON-lines wire). Every UI —
the web console, the Claude Code plugin, an editor — is a wrapper
over this same wire; nothing semantic lives in any wrapper.

State: the WORLD (the accepted catalog so far — tabula rasa starts
empty), the current TEXT (the approved unit), the current CANDIDATE
(.llp) and its gate REPORT, plus the scene (init/steps/seed).

The cycle:  text -> formalize|llp -> gate -> edit -> gate -> trace /
map / marginals (interpret) -> accept -> repeat (next text extends
the accepted world; packs may only ADD)."""
import json
import shlex
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from metis.kernel.filter import ForwardProjection
from metis.kernel.posterior import map_derivation
from metis.kernel.refsample import canonical_events, run_trace
from metis.lang import compile_catalog, parse
from metis.lang.formalize import admit_text_pack

from .core import formalize_loop


def _kv(s: str) -> Dict[str, int]:
    """a=1,b=2 — commas INSIDE parentheses belong to the atom
    (eros(helena,hermia)=1), so split at depth 0 only."""
    out: Dict[str, int] = {}
    part, depth = "", 0
    for ch in s + ",":
        if ch == "," and depth == 0:
            if part.strip():
                k, _, v = part.partition("=")
                out[k.strip()] = int(v or 1)
            part = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        part += ch
    return out


def _ev_name(ev) -> str:
    kind, stage, obj = ev
    return f"{stage}/{getattr(obj, 'name', '?')}"


@dataclass
class Session:
    base_llp: str = ""                  # accepted world source
    world: object = None                # compiled accepted Catalog
    text: str = ""
    cand: str = ""
    report: object = None
    init: Dict[str, int] = field(default_factory=dict)
    steps: int = 6
    seed: int = 1
    accepted: List[str] = field(default_factory=list)   # source log
    _revision: bool = False          # next accept REPLACES the base

    # -- verbs ---------------------------------------------------------

    def cmd_text(self, arg):
        self.text = arg
        return {"ok": True, "chars": len(arg)}

    def cmd_llp(self, arg):
        self.cand = arg
        return {"ok": True, "lines": arg.count("\n") + 1}

    def cmd_load(self, arg):
        """Load a candidate from a .llp FILE, splicing its includes
        against the file's own directory into canonical source (the
        roundtrip contract makes the splice identity-preserving)."""
        from pathlib import Path
        from metis.lang import parse as _parse, resolve_includes
        from metis.lang.ast import pretty
        p = Path(arg.strip()).expanduser()
        cat = resolve_includes(_parse(p.read_text()), p.parent)
        self.cand = pretty(cat)
        return {"ok": True, "file": str(p),
                "lines": self.cand.count("\n") + 1}

    def cmd_formalize(self, arg):
        if not self.text.strip():
            return {"ok": False, "error": "no text — :text first"}
        backend = shlex.split(arg) if arg else None
        if not backend:
            return {"ok": False,
                    "error": "formalize needs a backend command "
                             "(:formalize claude -p --model opus), or "
                             "write the candidate yourself with :llp"}
        res = formalize_loop(self.text, self.base_llp or "(empty world)",
                             backend, base_path=None,
                             scenarios=[self.init] if self.init else (),
                             steps=self.steps)
        self.cand, self.report = res.llp, res.report
        return {"ok": res.ok, "rounds": res.rounds,
                "findings": res.report.findings if res.report else []}

    def cmd_gate(self, arg):
        if not self.cand.strip():
            return {"ok": False, "error": "no candidate — :llp or :formalize"}
        base = None
        if self.base_llp.strip():
            base = compile_catalog(parse(self.base_llp))
        rep = admit_text_pack(self.text, self.cand, base=base,
                              scenarios=(self.init,) if self.init else (),
                              steps=self.steps)
        self.report, self._revision = rep, False
        out = {"ok": rep.ok, "classification": rep.classification,
               "findings": rep.findings, "warnings": rep.warnings,
               "rules": [list(r) for r in rep.rules]}
        if rep.scenarios:
            out["scenarios"] = [
                {"key": s.key, "support": s.support,
                 "diffs": [list(d) for d in s.diffs],
                 "map_events": s.map_events} for s in rep.scenarios]
        return out

    def cmd_accept(self, arg):
        rep = self.report
        if not (rep and rep.ok):
            return {"ok": False, "error": "nothing admitted — :gate first"}
        out = {"ok": True}
        if self._revision:
            # BASE EDIT: the candidate REPLACES the world. Packs
            # admitted against the old base are dropped (they must
            # be re-proposed against the new one), the canonical key
            # changes, and the before/after measure diff on the
            # current scene is the consistency instrument.
            out["diffs"] = self._revision_diff(rep)
            out["dropped_packs"] = len(self.accepted)
            self.world = rep.doc.catalog
            self.base_llp, self.accepted = self.cand, []
            self._revision = False
        else:
            self.world = rep.merged if rep.merged is not None \
                else rep.doc.catalog
            # tabula rasa's first accept IS the base; later accepts
            # append the pack source (packs only ADD).
            if not self.base_llp.strip():
                self.base_llp = self.cand
            else:
                self.accepted.append(self.cand)
        self.cand, self.report = "", None
        out["accepted"] = len(self.accepted) + 1
        return out

    def cmd_revise(self, arg):
        """Gate the candidate as a NEW WORLD (a base edit, the
        doctrine's human-approved catalog diff) instead of a pack.
        `:accept` then REPLACES the base; extension stays `:gate`."""
        if not self.cand.strip():
            return {"ok": False, "error": "no candidate — :llp first"}
        rep = admit_text_pack(self.text, self.cand, base=None,
                              scenarios=(self.init,) if self.init else (),
                              steps=self.steps)
        self.report, self._revision = rep, rep.ok
        out = {"ok": rep.ok, "revision": True,
               "classification": rep.classification,
               "findings": rep.findings, "warnings": rep.warnings,
               "rules": [list(r) for r in rep.rules]}
        if rep.ok and self.world is not None:
            out["diff_preview"] = self._revision_diff(rep)
        return out

    def _revision_diff(self, rep):
        """Old world vs revised world, exact final marginals on the
        current scene — what the base edit CHANGED."""
        if self.world is None or not self.init:
            return []
        def marg(cat):
            pr = ForwardProjection(cat.ground(dict(self.init)),
                                   self.steps)
            m: Dict[str, float] = {}
            for (_, kappa), p in pr.final.items():
                for a, n in kappa:
                    if n > 0:
                        m[a] = m.get(a, 0.0) + p
            return m
        old, new = marg(self.world), marg(rep.doc.catalog)
        return [[a, round(old.get(a, 0.0), 12), round(new.get(a, 0.0), 12)]
                for a in sorted(set(old) | set(new))
                if abs(old.get(a, 0.0) - new.get(a, 0.0)) > 1e-12]

    def _ground(self):
        cat = self.world
        if cat is None and self.report is not None:
            cat = (self.report.merged if self.report.merged is not None
                   else self.report.doc.catalog if self.report.doc else None)
        if cat is None:
            raise ValueError("no world — :gate then :accept first "
                             "(or :gate to inspect the candidate)")
        return cat.ground(dict(self.init))

    def cmd_init(self, arg):
        self.init = _kv(arg)
        return {"ok": True, "init": self.init}

    def cmd_steps(self, arg):
        self.steps = int(arg)
        return {"ok": True, "steps": self.steps}

    def cmd_trace(self, arg):
        prog = self._ground()
        seed = int(arg) if arg.strip() else self.seed
        self.seed = seed + 1
        idx, (stage, kappa) = run_trace(prog, self.steps, seed)
        names = [_ev_name(canonical_events(prog)[i]) for i in idx]
        return {"ok": True, "seed": seed, "events": names,
                "final_stage": stage,
                "final": {a: n for a, n in sorted(kappa)}}

    def cmd_map(self, arg):
        prog = self._ground()
        pr = ForwardProjection(prog, self.steps)
        m = map_derivation(pr)
        def lbl(e):
            if e is None:
                return "(quiesce)"
            k, s, ev = pr.events[e]
            return f"{s}/{getattr(ev, 'name', '?')}"
        return {"ok": True, "prob": m.prob,
                "events": [lbl(e) for e in m.events],
                "final": {a: n for a, n in sorted(m.final[1])},
                "final_stage": m.final[0]}

    def cmd_marginals(self, arg):
        prog = self._ground()
        pr = ForwardProjection(prog, self.steps)
        marg: Dict[str, float] = {}
        for (_, kappa), p in pr.final.items():
            for a, n in kappa:
                if n > 0:
                    marg[a] = marg.get(a, 0.0) + p
        want = arg.split() if arg.strip() else None
        out = {a: round(p, 12) for a, p in sorted(marg.items())
               if want is None or a in want}
        return {"ok": True, "support": len(pr.final), "marginals": out}

    def cmd_show(self, arg):
        which = arg.strip() or "state"
        if which == "text":
            return {"ok": True, "text": self.text}
        if which == "base":
            return {"ok": True, "base": self.base_llp,
                    "packs": self.accepted}
        if which in ("llp", "candidate"):
            return {"ok": True, "llp": self.cand}
        return {"ok": True, "world": bool(self.world),
                "accepted": len(self.accepted) + bool(self.base_llp),
                "candidate": bool(self.cand.strip()),
                "gated": bool(self.report and self.report.ok),
                "init": self.init, "steps": self.steps}

    def cmd_save(self, arg):
        from pathlib import Path
        d = Path(arg or "session")
        d.mkdir(parents=True, exist_ok=True)
        (d / "world.llp").write_text(
            self.base_llp + "".join("\n\n" + p for p in self.accepted))
        (d / "text.md").write_text(self.text)
        if self.cand:
            (d / "candidate.llp").write_text(self.cand)
        return {"ok": True, "dir": str(d)}

    def dispatch(self, op: str, arg: str = ""):
        fn = getattr(self, "cmd_" + op, None)
        if fn is None:
            return {"ok": False, "error": f"unknown op '{op}'",
                    "ops": sorted(n[4:] for n in dir(self)
                                  if n.startswith("cmd_"))}
        try:
            return fn(arg)
        except Exception as e:      # kernel errors are the findings here
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}


HELP = """\
:text <<EOF ... EOF     set the doc text (the approved unit)
:llp <<EOF ... EOF      set/edit the candidate LLP source
:formalize CMD...       draft the candidate via a backend command
:gate                   run the full gate cascade (findings on fail)
:accept                 admitted candidate joins the world\n:revise                 gate the candidate as a BASE EDIT (accept replaces the world)
:load FILE.llp          load a candidate file (includes spliced)
:init a=1,b=2   :steps N
:trace [seed]           one synthetic trajectory (seeded sampler)
:map                    the modal derivation (Viterbi) + final state
:marginals [atoms]      exact final marginals (the measure)
:show [state|text|base|llp]      :save DIR       :quit"""


def _read_block(first_arg, stdin):
    """`<<EOF` heredoc convention for multi-line text/llp."""
    if not first_arg.startswith("<<"):
        return first_arg
    tag = first_arg[2:].strip() or "EOF"
    lines = []
    for line in stdin:
        if line.rstrip("\n") == tag:
            break
        lines.append(line)
    return "".join(lines)


def run_repl(json_mode: bool = False, stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    s = Session()
    if json_mode:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except ValueError as e:
                print(json.dumps({"ok": False, "error": str(e)}),
                      file=stdout, flush=True)
                continue
            if req.get("op") == "quit":
                break
            print(json.dumps(s.dispatch(req.get("op", ""),
                                        req.get("arg", ""))),
                  file=stdout, flush=True)
        return 0
    print("metis-loop repl — :help for verbs; tabula rasa: the world "
          "is empty until your first :accept.", file=stdout)
    while True:
        try:
            print("μ> ", end="", file=stdout, flush=True)
            line = stdin.readline()
        except KeyboardInterrupt:
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        if line in (":quit", ":q"):
            break
        if line == ":help":
            print(HELP, file=stdout)
            continue
        if not line.startswith(":"):
            print("verbs start with ':' — :help", file=stdout)
            continue
        op, _, arg = line[1:].partition(" ")
        if op in ("text", "llp"):
            arg = _read_block(arg.strip(), stdin) if arg.strip() else ""
        res = s.dispatch(op, arg)
        print(json.dumps(res, indent=1), file=stdout)
    return 0
