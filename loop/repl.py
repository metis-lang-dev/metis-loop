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

from metis.kernel.record import recover

from .core import formalize_loop, load_records


# -- intents: chat-suggested REPL steps, ONE policy for every ferry --
#
# The console's chat window may queue an intent (a single REPL line)
# for execution; whoever ferries it (a loop session draining the
# artifact db) runs it ONLY through run_intent, so the whitelist
# lives here and no wrapper invents its own. Excluded by design:
# :accept (approval is human, and a session accept must be a
# deliberate prompt action), :save/:load/:sink (file paths from page
# viewers), :formalize with an arbitrary external command (shell
# execution — only the built-in ollama backend may be named).
INTENT_VERBS = frozenset(
    ["records", "record", "replay", "mine", "text", "init", "steps",
     "seed", "gate", "revise", "trace", "map", "marginals", "show",
     "formalize", "llm", "narrate", "help"])


def parse_intent(line: str):
    """One chat-suggested REPL line -> (op, arg), or None if the
    policy refuses it."""
    line = (line or "").strip()
    if not line.startswith(":"):
        return None
    op, _, arg = line[1:].partition(" ")
    if op not in INTENT_VERBS:
        return None
    if op == "formalize":
        a = arg.strip()
        if a and a != "ollama" and not a.startswith("ollama:"):
            return None
    if op == "llm" and arg.strip().startswith("command"):
        return None          # shell execution never from page intents
    return op, arg


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
    records: List[dict] = field(default_factory=list)   # surprise sink
    rec_idx: Optional[int] = None
    llm: str = ""                    # LLM endpoint spec ('' = default)
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
        roundtrip contract makes the splice identity-preserving).
        A file carrying embedded '#'-directives (metis-lang spec §8)
        donates them to the SCENE where it is still unset: #init when
        no :init was given, #steps when :steps is at its default —
        explicit verbs always win. Likewise the file's leading
        comment block (its own doc, the approved unit of a committed
        catalog) becomes the TEXT when none was set."""
        from pathlib import Path
        from metis.lang import parse as _parse, resolve_includes
        from metis.lang.ast import pretty
        from metis.lang.directives import embedded_case
        p = Path(arg.strip()).expanduser()
        text = p.read_text()
        cat = resolve_includes(_parse(text), p.parent)
        self.cand = pretty(cat)
        out = {"ok": True, "file": str(p),
               "lines": self.cand.count("\n") + 1}
        case = embedded_case(text)
        adopted = {}
        if case["init"] and not self.init:
            self.init = {a: n for a, n in case["init"].items() if n > 0}
            adopted["init"] = self.init
        if case["steps"] and self.steps == 6:
            self.steps = case["steps"]
            adopted["steps"] = self.steps
        if adopted:
            out["adopted_directives"] = adopted
        if not self.text.strip():
            head = []
            for line in text.splitlines():
                if line.startswith("%"):
                    head.append(line)
                elif line.strip():
                    break
            if head:
                self.text = "\n".join(head)
                out["adopted_text_chars"] = len(self.text)
        return out

    def cmd_formalize(self, arg):
        """Draft the candidate from the text. Default backend: the
        local model via the Ollama adapter (no plugins) — bare
        `:formalize`, or `:formalize ollama:MODEL`; any other arg is
        an external command (prompt on stdin, LLP on stdout)."""
        if not self.text.strip():
            return {"ok": False, "error": "no text — :text first"}
        arg = arg.strip()
        if not arg or arg == "ollama" or arg.startswith("ollama:"):
            from .ollama import backend as ollama, default_model
            model = arg.partition(":")[2] or None
            backend = ollama(model)
            label = f"ollama:{model or default_model()}"
        else:
            backend = shlex.split(arg)
            label = arg
        base_path = None
        if self.base_llp.strip():
            # gate each round against the ACCEPTED world, exactly as
            # :gate does — a drafted pack must admit as a pack
            import tempfile
            f = tempfile.NamedTemporaryFile(
                "w", suffix=".llp", delete=False)
            f.write(self.base_llp)
            f.close()
            base_path = f.name
        try:
            res = formalize_loop(
                self.text, self.base_llp or "(empty world)",
                backend, base_path=base_path,
                scenarios=[self.init] if self.init else (),
                steps=self.steps)
        finally:
            if base_path:
                import os
                os.unlink(base_path)
        self.cand, self.report = res.llp, res.report
        return {"ok": res.ok, "backend": label, "rounds": res.rounds,
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

    # -- the surprise / refinement loop --------------------------------

    def _rec_line(self, i, r):
        return {"idx": i, "kind": r.get("kind"),
                "likelihood": r.get("likelihood"),
                "steps": r.get("steps"),
                "observed": r.get("observed", {}),
                "source": (r.get("meta") or {}).get("source", ""),
                "mined": bool(r.get("mined_text"))}

    def cmd_sink(self, arg):
        """Load surprise records from a JSONL sink (kernel/record.py
        wire; pointers, not traces — :replay re-derives everything)."""
        if not arg.strip():
            return {"ok": False, "error": "usage: :sink FILE.jsonl"}
        self.records = load_records(arg.strip())
        self.rec_idx = None
        return {"ok": True, "file": arg.strip(),
                "records": [self._rec_line(i, r)
                            for i, r in enumerate(self.records)]}

    def cmd_records(self, arg):
        return {"ok": True,
                "records": [self._rec_line(i, r)
                            for i, r in enumerate(self.records)]}

    def cmd_record(self, arg):
        """Select a record (default: the newest); its init/steps
        become the scene, so :replay, :marginals and the gate's
        scenario all speak about the record's tick."""
        if not self.records:
            return {"ok": False, "error": "no records — :sink first"}
        i = int(arg) if arg.strip() else len(self.records) - 1
        if not 0 <= i < len(self.records):
            return {"ok": False,
                    "error": f"record {i} out of 0..{len(self.records)-1}"}
        self.rec_idx = i
        r = self.records[i]
        self.init = {a: n for a, n in r.get("init", {}).items() if n > 0}
        if r.get("steps"):
            self.steps = r["steps"]
        if r.get("mined_text"):
            self.text = r["mined_text"]
        return {"ok": True, **self._rec_line(i, r),
                "init": self.init,
                "program_key": r.get("program_key", "")}

    def cmd_replay(self, arg):
        """recover() the selected record against the current world
        (or the gated candidate) — the explanation before a fix, the
        verification after one: an accepted fix must move the
        record's likelihood positive."""
        if self.rec_idx is None:
            return {"ok": False, "error": "no record — :record first"}
        r = self.records[self.rec_idx]
        prog = self._ground()
        out = recover(r, prog, steps=r.get("steps"))
        logged = r.get("likelihood", 0.0)
        now = out["likelihood"]
        return {"ok": True, "logged_likelihood": logged,
                "likelihood": now, "explains": out["explains"],
                "explanation_events": out.get("explanation_events"),
                "fixed": bool(now > 0 >= logged)}

    def cmd_mine(self, arg):
        """With TEXT: set it as the approved unit AND stamp it on the
        selected record (mined_text). Bare: show what there is to
        mine — the observed-vs-modeled gap."""
        if self.rec_idx is None:
            return {"ok": False, "error": "no record — :record first"}
        r = self.records[self.rec_idx]
        if arg.strip():
            self.text = arg
            r["mined_text"] = arg
            return {"ok": True, "chars": len(arg)}
        return {"ok": True, "kind": r.get("kind"),
                "likelihood": r.get("likelihood"),
                "init": r.get("init", {}),
                "observed": r.get("observed", {}),
                "hint": "state what happened that the world cannot "
                        "derive; quote atoms; that text is the "
                        "approved unit (:mine <text>)"}

    # -- the scene -----------------------------------------------------

    def cmd_init(self, arg):
        self.init = _kv(arg)
        return {"ok": True, "init": self.init}

    def cmd_steps(self, arg):
        self.steps = int(arg)
        return {"ok": True, "steps": self.steps}

    def cmd_seed(self, arg):
        """Set the sampler seed :trace starts from (the scene's third
        coordinate; a bare :trace then walks seed, seed+1, ...)."""
        self.seed = int(arg)
        return {"ok": True, "seed": self.seed}

    def cmd_help(self, arg):
        return {"ok": True, "help": HELP}

    def cmd_trace(self, arg):
        prog = self._ground()
        seed = int(arg) if arg.strip() else self.seed
        self.seed = seed + 1
        idx, (stage, kappa) = run_trace(prog, self.steps, seed)
        names = [_ev_name(canonical_events(prog)[i]) for i in idx]
        return {"ok": True, "seed": seed, "events": names,
                "final_stage": stage,
                "final": {a: n for a, n in sorted(kappa)}}

    def cmd_llm(self, arg):
        """Show or set the LLM endpoint for both text boundaries
        (:formalize default backend stays ollama; :narrate uses
        this). Specs: ollama[:MODEL] | anthropic[:MODEL] |
        command:ARGV."""
        from .llm import DEFAULT_SPEC, resolve
        a = arg.strip()
        if not a:
            return {"ok": True,
                    "llm": self.llm or f"(default: {DEFAULT_SPEC})"}
        resolve(a)                       # validate now, fail loudly
        self.llm = a
        return {"ok": True, "llm": a}

    def cmd_narrate(self, arg):
        """The narrate-out boundary: one seeded trace of the world,
        told as prose from certified material only (the trace's
        Foata beats + final state + the rules' %% docs), through the
        configured :llm endpoint."""
        from .narrate import narrate
        prog = self._ground()
        seed = int(arg) if arg.strip() else self.seed
        idx, (stage, kappa) = run_trace(prog, self.steps, seed)
        events = canonical_events(prog)
        rows = [events[i] for i in idx]
        rules_src = self.base_llp or self.cand
        if not rules_src.strip():
            return {"ok": False,
                    "error": "no rule source — :accept a world or "
                             ":load a candidate first"}
        text = narrate(self.llm or "ollama", rows, stage, kappa,
                       rules_src, seed=seed)
        return {"ok": True, "seed": seed, "events": len(rows),
                "llm": self.llm or "ollama", "narration": text}

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

    def run_intent(self, line: str):
        """Execute one chat-queued intent under the module policy."""
        p = parse_intent(line)
        if p is None:
            return {"ok": False, "cmd": line,
                    "error": "intent refused — allowed verbs: " +
                             " ".join(sorted(INTENT_VERBS)) +
                             " (:formalize only bare or ollama[:model])"}
        return self.dispatch(*p)

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
the surprise / refinement loop:
:sink FILE.jsonl        load surprise records (the runtime's sink)
:records                list them (kind, likelihood, observed)
:record [N]             select one (default newest); its init/steps
                        become the scene
:mine [TEXT]            bare: the observed-vs-modeled gap to mine;
                        with TEXT: set the approved unit + stamp it
:replay                 recover() the record against the world —
                        explanation before a fix, verification after
                        (fixed: likelihood moved positive)

the candidate:
:text <<EOF ... EOF     set the doc text (the approved unit)
:llp <<EOF ... EOF      set/edit the candidate LLP source
:formalize [BACKEND]    draft via the local model (default: the
                        Ollama adapter; ollama:MODEL picks a model;
                        anything else is an external command)
:gate                   run the full gate cascade (findings on fail)
:accept                 admitted candidate joins the world
:revise                 gate the candidate as a BASE EDIT (accept
                        then REPLACES the world; measure diff shown)
:load FILE.llp          load a candidate file (includes spliced; its
                        '#'-directives seed the scene where unset)
:init a=1,b=2   :steps N   :seed N        the scene
:trace [seed]           one synthetic trajectory (seeded sampler)
:llm [SPEC]             show/set the LLM endpoint —
                        ollama[:MODEL] | anthropic[:MODEL] |
                        command:ARGV (narrate + future text verbs)
:narrate [seed]         tell one trace as prose (Foata beats +
                        final state + %% docs through the endpoint —
                        the narrate-out boundary, SPEC §1)
:map                    the modal derivation (Viterbi) + final state
:marginals [atoms]      exact final marginals (the measure)
:show [state|text|base|llp]      :save DIR      :help      :quit"""


def _read_block(first_arg, next_line):
    """`<<EOF` heredoc convention for multi-line text/llp."""
    if not first_arg.startswith("<<"):
        return first_arg
    tag = first_arg[2:].strip() or "EOF"
    lines = []
    while True:
        line = next_line()
        if line is None or line.rstrip("\n") == tag:
            break
        lines.append(line if line.endswith("\n") else line + "\n")
    return "".join(lines)


def _wire_readline(session):
    """Line editing, persistent history and verb completion for the
    interactive prompt — degrades silently where readline is absent.
    Only wired when stdin is the real tty (piped transcripts and the
    JSON wire stay byte-clean)."""
    try:
        import atexit
        import os
        import readline
    except ImportError:
        return
    from pathlib import Path
    verbs = sorted(":" + n[4:] for n in dir(session)
                   if n.startswith("cmd_")) + [":quit"]

    def complete(text, state):
        hits = [v + " " for v in verbs if v.startswith(text or ":")]
        return hits[state] if state < len(hits) else None

    readline.set_completer_delims(" \t\n")
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    base = Path(os.environ.get("XDG_STATE_HOME",
                               Path.home() / ".local/state"))
    try:
        d = base / "metis-loop"
        d.mkdir(parents=True, exist_ok=True)
        hist = d / "history"
        try:
            readline.read_history_file(hist)
        except OSError:
            pass
        readline.set_history_length(1000)
        atexit.register(lambda: readline.write_history_file(hist))
    except OSError:
        pass


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
    tty = (stdin is sys.stdin and stdout is sys.stdout
           and hasattr(stdin, "isatty") and stdin.isatty())
    if tty:
        _wire_readline(s)

    def next_line(prompt="μ> "):
        if tty:
            try:
                return input(prompt) + "\n"
            except (EOFError, KeyboardInterrupt):
                return None
        print(prompt, end="", file=stdout, flush=True)
        return stdin.readline() or None

    print("metis-loop repl — :help for verbs (tab completes; history "
          "kept); tabula rasa: the world is empty until your first "
          ":accept.", file=stdout)
    while True:
        line = next_line()
        if line is None:
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
            arg = _read_block(arg.strip(),
                              lambda: next_line("")) \
                if arg.strip() else ""
        res = s.dispatch(op, arg)
        if res.get("ok") and "narration" in res:
            head = {k: v for k, v in res.items() if k != "narration"}
            print(json.dumps(head, indent=1), file=stdout)
            print(res["narration"], file=stdout)
        else:
            print(json.dumps(res, indent=1), file=stdout)
    return 0
