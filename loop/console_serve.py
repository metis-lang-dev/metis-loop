"""The console's serving half (CONSOLE §5a): one kernel REPL per open
console window, over the catalog root — the directory the console was
started in (cd DIR && metis-loop), or $METIS_CATALOG.

The gateway (loop/gateway.py, `metis-loop console-serve`) is its only caller since loop-ui 2.4: the
artifact-era db transport (a claude.ai artifact's db drained by a Claude session) is gone. The calls:

  - `catalogs()`           names for meta/catalogs (load chips);
  - `open_session(sid, doc)` binds an interpreter to a session and returns its fields;
  - `serve_one(sid, cmd)`  runs ONE queued intent line through the
                            run_intent whitelist (`intent_posting`) and
                            returns {posting, session};
  - `close_session(sid)`.

v1 keeps the interpreters in-process (`Repl` instances); the fifo bus
of N `metis --json` processes (SPEC §6) is a v2 swap behind the same
four calls. The epoch (start 1) bumps when the world under a window
changes — a reset, or a new program key — and the page clears its
stream on a bump."""
import io
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

from metis import catalog
from metis.gate import Gate, Refused, public          # metispy's (metis-packages); the SDK modules are their shims


def catalog_root() -> Path:
    """The catalog root, by metispy's one rule (metis.catalog.root:
    $METIS_CATALOG, else the cwd). The installed metis-catalog's data is
    only what a loop copies a known domain from, never the served catalog."""
    return catalog.root()


def _shared(root):
    """METIS_HOME's domains the root lacks (metis.catalog.shared, metispy >= 0.1.4): listed after
    the root's, marked shared, and opened from METIS_HOME — a package resolves as an include does,
    the root first, then METIS_HOME."""
    f = getattr(catalog, "shared", None)
    return f(root) if f else []


# `new <name>`: the skeleton program (the header, #init, one commented rule
# with its %% line — the mapper reads the %% line)
SKELETON = """% {name} — {line}
% Made in the loop console (new). Say in prose what there is, what can
% happen and what the person can ask; the pi loop writes the rules.
catalog {name} 1.
provenance text "{line}" "{date}".
layers (dyn).
stages (main).

namespace {name} produce (dyn).

pred idle : {name}.
pred awake : {name}.

stage main {{
  %% I wake up.
  wake [dyn] : idle -o awake.
}}

#init idle 1
"""

README_MAX = 64 * 1024      # the root README the page lands on


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ConsoleServer:
    """{sid: Repl} plus the per-session epoch."""

    def __init__(self, root: Optional[Path] = None, seed: int = 1, take_into: Optional[Path] = None,
                 loop_state: Optional[Path] = None):
        self.root = Path(root) if root else catalog_root()
        self.seed = seed
        # every catalog write is a plan the person confirms (loop-parity step 2, docs/LOOP.md): the
        # loop's one policy, its memory of refused proposals in this process
        self.gate = Gate()
        self.take_into = Path(take_into) if take_into else None
        # a loop running elsewhere (pi, unattended) keeps its gate in its state directory: its asks
        # (the disengagement records, loop-policy) are shown and answered here ([console] loop_state)
        self.loop_state = Path(loop_state).expanduser() if loop_state else None
        self.shells: Dict[str, object] = {}
        self.epochs: Dict[str, int] = {}
        self._roots = sorted({str(self.root), str(self.root.resolve())},
                             key=len, reverse=True)
        home = str(Path.home())
        self._home = home if len(home) > 1 else ""

    # -- catalogs --------------------------------------------------------

    def catalogs(self):
        """Every .llp under the root, as names relative to it without the
        suffix (`domains/ceptre/three_pigs/three_pigs`), sorted — the loader's
        walk, as its index: none under a dot directory (.metis/, .git/ …),
        build/, records/, __pycache__/, node_modules/."""
        return sorted(str(p.relative_to(self.root).with_suffix("")) for p in catalog.walk("*.llp", self.root))

    def readme(self):
        """DIR/README.md, the catalog's context (cwd-root rule 10): {path,
        text, links} — `links` maps each of its relative links that names a
        package (its directory, or its program) to that package's path as
        the list has it, so the page opens the package from the README; None
        without a README. Read, never written."""
        import re
        f = self.root / "README.md"
        if not f.is_file():
            return None
        text = f.read_text(errors="replace")[:README_MAX]
        progs = {e["path"] for e in catalog.index(self.root) if e["kind"] == "domain" and e.get("path")}
        dirs = {os.path.dirname(p): p for p in progs if os.path.basename(p) == os.path.basename(os.path.dirname(p))}
        links = {}
        for href in re.findall(r"\]\(([^)\s]+)\)", text):
            h = href.split("#")[0]
            if not h or ":" in h or h.startswith("/"):
                continue
            rel = os.path.normpath(h)
            if rel in dirs:
                links[href] = dirs[rel]
            elif rel.removesuffix(".llp") in progs:
                links[href] = rel.removesuffix(".llp")
        return self.scrub({"path": "README.md", "text": text, "links": links})

    def domains(self):
        """The CATALOG panel's list (the SDK's catalog.index): every catalog
        with its display line and what it has, the domains first; a domain
        carries its README's opening (readme_text) for the panel."""
        rows = [{**e, "readme_text": catalog.readme_head(e["readme"], r=self.root)} if e["readme"] else e
                for e in catalog.index(self.root)]
        if _shared(self.root):                  # METIS_HOME's, after the root's domains, marked shared
            n = sum(1 for e in rows if e["kind"] == "domain")
            rows[n:n] = catalog.shared_index(self.root)
        return rows

    def resolve(self, llp: str) -> Path:
        """A catalog name -> its file in the checkout: the full
        relative name (with or without .llp), or a unique basename
        (`three_pigs`). Never outside the checkout."""
        name = (llp or "").strip()
        if not name:
            raise ValueError("no catalog named")
        name = name[:-4] if name.endswith(".llp") else name
        names = self.catalogs()
        hits = [n for n in names if n == name] or \
               [n for n in names if n.split("/")[-1] == name] or \
               [n for n in names if n.endswith("/" + name)]
        if not hits:
            for d in _shared(self.root):        # a METIS_HOME package: by its name or its (absolute) path
                if d.program and name in (d.name, str(Path(d.program).with_suffix(""))):
                    return Path(d.program).resolve()
            raise ValueError(f"no catalog '{llp}' in {self.root} nor METIS_HOME ({catalog.home()})")
        if len(hits) > 1:                       # a package's program wins over any other .llp (a goldens case
            progs = {d["path"] for d in self.domains() if d.get("kind") == "domain"}     # is not a package)
            hits = [n for n in hits if n in progs] or hits
        if len(hits) > 1:
            raise ValueError(f"'{llp}' is ambiguous: {', '.join(hits)}")
        path = (self.root / (hits[0] + ".llp")).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"'{llp}' resolves outside the checkout")
        return path

    # -- what leaves for the web -----------------------------------------

    def scrub(self, obj):
        """Web output never names the operator's filesystem: the
        checkout root becomes relative ("domains/ceptre/three_pigs/three_pigs.llp") and
        any other home path "~/…". Applied to every posting, session
        doc and ctx this server hands out; the terminal REPL never comes
        through here and keeps its absolute paths (the user's own
        machine)."""
        if isinstance(obj, str):
            for root in self._roots:
                obj = obj.replace(root + "/", "").replace(root, ".")
            return obj.replace(self._home + "/", "~/") if self._home else obj
        if isinstance(obj, dict):
            return {k: self.scrub(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self.scrub(v) for v in obj]
        return obj

    # -- sessions --------------------------------------------------------

    def _fields(self, sid: str) -> dict:
        """The session doc's backend-owned fields, ctx included (the
        band renders from it)."""
        r = self.shells[sid]
        c = r.ctx()
        return self.scrub({"name": c["catalog"], "key": c["key"],
                           "stage": c["stage"], "status": c["status"],
                           "epoch": self.epochs[sid], "ctx": c,
                           "last_ts": _now()})

    @staticmethod
    def _extension_text(src: str) -> str:
        """A extension's approved text = its leading `%` comment block (the
        `load` convention) — what its %% docs quote at the gate."""
        head = []
        for line in src.splitlines():
            if line.startswith("%"):
                head.append(line.lstrip("%").strip())
            elif line.strip():
                break
        return "\n".join(head) or "extension"

    def build(self, doc: dict):
        """A Repl for `{llp}` (a checkout catalog: the workspace owns the file, workspace-files s-9ea4cfa4),
        its domain's extensions merged into THIS session (llp → gate → accept, `accept` off the wire).
        Returns (repl, llp label, extension reports); raises ValueError with the findings on any failure."""
        from metis.lang.repl import Repl
        if doc.get("source") is not None:
            raise ValueError("a session opens a checkout program ({llp}): the workspace owns the file, "
                             "edit it in the EDITOR (no in-memory catalogs)")
        path = self.resolve(doc.get("llp", ""))
        # a member's unit (grasp_domain.llp, which alone lacks the tick protocol its member includes) serves the
        # program that includes it, as the terminal's `metis UNIT` does (two-terminals; loop-ui I5); the unit is
        # the session's, so a drop records the file the person opened (I1)
        unit, note = None, None
        target, note = catalog.serve_target(str(path), root=self.root)
        if target is not None and Path(target).resolve() != path.resolve():
            unit, path = path, Path(target).resolve()
        rel = str(path.relative_to(self.root.resolve()).with_suffix(""))
        # {llp, host: true} — the one-click open of the CATALOG panel: the host the INDEX names for this
        # checkout file (never a spec from the wire: D4), attached as an operator's --host
        spec = catalog.host_of(rel, self.root) if doc.get("host") else None
        try:
            r = Repl(path, seed=self.seed, stdout=io.StringIO(), plugin=spec, host=bool(spec),
                     **({"unit": unit} if unit is not None else {}))
        except TypeError:                                 # a metispy before loop-ui: no unit= (the drop lacks it)
            r = Repl(path, seed=self.seed, stdout=io.StringIO(), plugin=spec, host=bool(spec))
        r._served_note = note if unit is not None else None
        # the served program is the program plus its extensions (human-loop step 1)
        extensions = [{"name": p.stem, "source": p.read_text()} for p in self.checkout_extensions(path)]
        reports = self._merge_extensions(r, extensions)
        label = rel + (f" + {spec}" if spec else "")
        if reports:
            label += f" + {len(reports)} extension{'s' if len(reports) != 1 else ''}"
        return r, label, reports

    def _merge_extensions(self, r, extensions) -> list:
        """Each extension `{source, name}` gated as an extension against the program and
        merged into THIS session (llp → gate → accept); the reports. Raises
        ValueError with the findings when one is not admitted."""
        reports = []
        for k, pk in enumerate(extensions, 1):
            psrc = str(pk.get("source") or "")
            pname = str(pk.get("name") or f"extension {k}")
            if not psrc.strip():
                continue
            r.cmd_text(self._extension_text(psrc))
            r.cmd_llp(psrc)
            rep = r.cmd_gate("")
            if not rep.get("ok"):
                found = rep.get("findings") or [rep.get("error", "rejected")]
                raise ValueError(f"extension '{pname}' not admitted: " +
                                 "; ".join(map(str, found))[:1500])
            acc = r.cmd_accept("")
            reports.append({"name": pname, "ok": True,
                            "key": acc.get("key")})
            r.loop.text = ""
        return reports

    def checkout_extensions(self, path: Path) -> list:
        """A checkout program's extensions, from the domain manifest beside it
        only (runtime-binding Q1; the SDK's catalog.extensions_of): its served
        files after the program when the program is the first of them, else
        none; none for a program no manifest names."""
        return catalog.extensions_of(path, self.root)

    @staticmethod
    def _carry_loop(old, new):
        """A re-open after an edit keeps the session's loop: the sunk records, the
        selected record (its scene restored by selecting it again) and the
        loop's text — Claude checks a candidate against the record it
        explains (human-loop step 1, the architect's A6 finding)."""
        lo = getattr(old, "loop", None)
        if lo is None or not lo.records:
            return
        new.loop.records = list(lo.records)
        i = lo.rec_idx
        if i is not None and 0 <= i < len(lo.records):
            new.cmd_record(str(i))
        if lo.text:
            new.loop.text = lo.text

    def open_session(self, sid: str, doc: dict) -> dict:
        """Bind an interpreter to sessions/{sid} from `{llp: name}` (a checkout
        catalog). The live interpreter is replaced only when everything
        compiles and every extension is admitted; a failure comes back as
        {status: "closed", error} and leaves an existing session as it was."""
        try:
            r, llp, reports = self.build(doc)
        except Exception as e:                      # noqa: BLE001
            return {"status": "closed", "error": self.scrub(str(e)),
                    "last_ts": _now()}
        if doc.get("keep_loop") and sid in self.shells:     # an edit written: the loop goes on
            self._carry_loop(self.shells[sid], r)
        self.shells[sid] = r
        self.epochs[sid] = 1
        out = self._fields(sid)
        out["llp"] = llp
        if getattr(r, "_served_note", None):          # a unit opened: its includer served, and why (loop-ui I5)
            out["served"] = r._served_note
        if reports:
            out["extensions"] = reports
        return out

    def serve_one(self, sid: str, cmd: str) -> dict:
        """One queued intent: {posting: the intent doc's update
        (intent_posting + epoch + done_ts), session: the session doc's
        update (epoch bumped on reset / key change)}."""
        from metis.loop.wire import intent_posting
        if sid not in self.shells:
            return {"posting": {"status": "error",
                                "result": f"no open session '{sid}'",
                                "json": {"ok": False}, "done_ts": _now()},
                    "session": None}
        r = self.shells[sid]
        line = cmd.strip()
        line = line if line.startswith(":") else ":" + line
        key = r.key
        posting = intent_posting(r, line, session=sid)
        verb = line[1:].split(" ", 1)[0]
        if posting["status"] == "done" and (verb == "reset"
                                            or r.key != key):
            self.epochs[sid] += 1
        session = self._fields(sid)
        posting.update({"epoch": self.epochs[sid], "done_ts": _now()})
        return {"posting": self.scrub(posting), "session": session}

    # -- e2e-workflow step 1: new, save (the records listing and the sink went with their docks, loop-ui 2.4) --

    def _under(self, rel: str, must: str = "") -> Path:
        p = (self.root / (rel or "")).resolve()
        if not p.is_relative_to(self.root.resolve()) or (must and must not in p.as_posix()):
            raise ValueError(f"'{rel}' is not a {must.strip('/') or 'checkout'} file of the checkout")
        return p

    NAME = __import__("re").compile(r"^[a-z][a-z0-9_]{1,31}$")

    def new_domain(self, name: str, line: str = "") -> str:
        """domains/<name>/: domain.yaml (the package's keys: its name is
        the directory's, README.md by convention), a skeleton <name>.llp
        (the header, #init, one commented rule with its %% line), README.md
        with the display line. Returns the program's name for open."""
        name = (name or "").strip()
        if not self.NAME.match(name):
            raise ValueError("a domain name is lower case, a-z 0-9 _, 2–32 characters, a letter first")
        d = self.root / "domains" / name
        if d.exists():
            raise ValueError(f"domains/{name} exists already — open it from the list")
        line = " ".join((line or f"the {name} domain").split())[:160]
        catalog.new(name, SKELETON.format(name=name, line=line.replace('"', "'"), date=time.strftime("%Y-%m-%d")),
                    r=self.root,       # a package the catalog lacks (its program checked, the manifest by the loader)
                    manifest=f"display: the {name}\nline: {json.dumps(line)}\nvoice: third\n"
                             f"program: {name}.llp\nrecords: records/\n",
                    readme=f"# {name} — {line}\n\nA new domain, made in the loop console. "
                           "Describe what there is, what can happen and what the person can ask.\n")
        return f"domains/{name}/{name}"

    # -- the gate: every write is a plan the person confirms (docs/LOOP.md) ----------

    def files_of(self, sid: str) -> dict:
        """The EDITOR's files of a session (workspace-files s-9ea4cfa4): its program and its domain's
        extensions as they are on disk, {program, files: [{path, text, role}]}, paths relative to the root."""
        sh = self.shells.get(sid)
        if sh is None:
            raise ValueError(f"no open session '{sid}'")
        root = self.root.resolve()
        prog = Path(sh.path).resolve()
        out = [{"path": prog.relative_to(root).as_posix(), "text": prog.read_text(), "role": "program"}]
        exts = [Path(e).resolve() for e in self.checkout_extensions(prog)]
        for e in exts:
            if e.is_relative_to(root):
                out.append({"path": e.relative_to(root).as_posix(), "text": e.read_text(), "role": "extension"})
        # a bundle member's rule files (the alf drive's L5): what its program includes inside the composition's directory,
        # a generated (DERIVED) file shown as its source, the one copy an edit changes (metispy's includes(within=))
        bundle = catalog.bundle_dir(prog.parent, self.root)
        if bundle is not None:
            try:
                inc = catalog.includes(prog.parent, [prog, *exts], self.root, within=bundle)
            except ValueError:
                inc = {}
            for rel in sorted(inc):
                f = (prog.parent / rel).resolve()
                if prog.parent in f.parents or not f.is_relative_to(root) or not f.is_file():
                    continue
                text = f.read_text()
                if text.startswith("% DERIVED from"):
                    continue                        # generated (make): its source is listed instead
                out.append({"path": f.relative_to(root).as_posix(), "text": text, "role": "bundle"})
        return {"program": out[0]["path"], "files": out}

    def _domain_file(self, rel: str):
        """(the domain, the path inside its directory) of a checkout file `rel` (relative to the root)."""
        p = self._under(rel)
        dirs = [Path(d).parent.resolve() for d in catalog.walk("domain.yaml", self.root)]
        mine = [dd for dd in dirs if dd in p.parents]
        if not mine:
            raise ValueError(f"'{rel}' is not a file of a domain of this catalog")
        dd = max(mine, key=lambda x: len(x.parts))      # nina: the nearest manifest, so a nested package is its own
        return dd.name, p.relative_to(dd).as_posix(), p

    def _plan_edit(self, domain: str, path: str, old: str, new: str) -> dict:
        """The edit's dry run (metispy's catalog.edit, dry_run=True): {path, diff, findings: [{level, code, line, msg,
        …}], ok (no finding refuses), since_diff?: what changed since the person refused this file's last plan}."""
        pl = catalog.edit(domain, path, old, new, r=self.root, dry_run=True, since=self.gate.refused(self.root))
        out = {"path": path, "diff": pl.get("diff", ""), "findings": list(pl.get("findings") or []), "ok": bool(pl.get("ok"))}
        since = next((f.get("since_diff") for f in pl.get("files") or [] if f.get("since_diff")), None)
        if since:
            out["since_diff"] = since
        return out

    def edit_plan(self, rel: str, old: str, new: str, sid: str = None) -> dict:
        """The EDITOR's save (workspace-files s-9ea4cfa4): one exact edit of a checkout file `rel`, old → new,
        planned: {path, diff, findings, ok, token?}. ok = no error-level finding; only then the console's gate
        holds a plan (its token) that confirm writes (gate_confirm). Lint rows show, never refuse."""
        p = self._under(rel)
        sh = self.shells.get(sid) if sid else None
        d = Path(sh.path).resolve().parent if sh is not None else None
        bundle = catalog.bundle_dir(d, self.root) if d is not None else None
        if d is not None and d not in p.parents and bundle is not None and bundle in p.parents:
            # a file of the session member's bundle (its ../x.llp): planned from that member (nina: only then; any
            # other file is its own domain's, as without a session)
            domain, path = d.name, Path(os.path.relpath(p, d)).as_posix()
        else:
            domain, path, _ = self._domain_file(rel)
        try:
            pl = self._plan_edit(domain, path, old, new)
        except ValueError as e:
            raise ValueError(self.scrub(str(e))) from None
        out = {"path": rel, "domain": domain, "diff": pl["diff"], "findings": pl["findings"], "ok": pl["ok"],
               **({"since_diff": pl["since_diff"]} if pl.get("since_diff") else {})}
        if out["ok"]:
            try:
                g = self.gate.propose("edit", domain, self.root, path=path, old=old, new=new)
            except Refused as e:
                out["ok"] = False
                out["findings"] = out["findings"] + [{"level": "error", "code": "gate", "line": None, "msg": str(e)}]
            else:
                out["token"] = g["token"]
        return self.scrub(out)

    def gate_plan(self, kind: str, domain: str, args: dict) -> dict:
        """A plan of one of the console's writes (the loop's kinds, docs/LOOP.md):
        edit {path, old, new, replace_all?} — one exact edit of a file on disk (README,
        domain.yaml, intent.yaml, the host, an included file; a .llp edit adds no
        diagnostic); readme {text, title?}; intents {text?} (without text: the skeleton
        from the program's cmd_* atoms, no model); take — the domain into the operator's
        other catalog ([console] take_into); new / ask as the gate has them. readme and
        intents are drafted by metispy's helpers and planned as an edit of the file
        (workspace-files s-9ea4cfa4). Refusals come with the rule's words."""
        a = dict(args or {})
        if kind == "take":
            if not self.take_into:
                raise ValueError("take writes into another catalog: set [console] take_into (a directory)")
            pl = self.gate.propose("take", domain, self.take_into, src=str(self.root))
        elif kind in ("edit", "ask", "new"):
            try:
                pl = self.gate.propose(kind, domain, self.root, **a)
            except Refused as e:
                raise ValueError(str(e)) from None
        elif kind in ("readme", "intents"):
            try:
                pl = self._drafted(kind, domain, a)
            except Refused as e:
                raise ValueError(str(e)) from None
            except KeyError:
                raise ValueError(f"no domain {domain} in the catalog yet: {kind} follows its program (new)") from None
            if pl is None:
                return {"kind": "edit", "domain": domain, "files": [], "token": "", "reopen": False,
                        "note": f"nothing to write: the {'README' if kind == 'readme' else 'intent.yaml'} is that already"}
        else:
            raise ValueError(f"the console's writes: edit, readme, intents, take, ask, new; not {kind!r}")
        return self._shown(pl)

    def _drafted(self, kind: str, domain: str, a: dict):
        """README and intents, drafted by metispy's read-only helpers and planned as ONE edit of the file on disk
        (old = its text now, "" when it is missing): readme {text, title?} = catalog.readme's text around the summary;
        intents {text?} = the text, or catalog.skeleton's from the program's cmd_* atoms (no model). None when the
        file is that text already; a plan with a note and no file when the world takes no commands."""
        if kind == "readme":
            if not (a.get("text") or "").strip():
                raise Refused("readme: text is the summary paragraph (what the program tells; the SDK writes the rest)")
            text, rel = catalog.readme(domain, self.root, None, a["text"], a.get("title")), "README.md"
        else:
            text, rel = (a["text"] if a.get("text") is not None else catalog.skeleton(domain, self.root)), "intent.yaml"
            if text is None:
                return {"kind": "edit", "domain": domain, "root": str(self.root), "reopen": False, "files": [],
                        "token": "", "note": "no intent.yaml: the world takes no commands (its program has no cmd_* atom), "
                                              "so the agents open it with no verbs"}
        f = Path(catalog.get(domain, self.root).dir) / rel
        old = f.read_text() if f.is_file() else ""
        if old == text:
            return None
        return self.gate.propose("edit", domain, self.root, path=rel, old=old, new=text)

    def gate_asks(self) -> list:
        """The asks waiting for the person (loop-policy, docs/LOOP.md): the console's own gate's
        and the gate of the loop in [console] loop_state, each with `where` it waits."""
        out = [dict(a, where="console") for a in self.gate.asks()]
        if self.loop_state and (self.loop_state / "gate.json").is_file():
            with Gate.locked(self.loop_state) as g:
                out += [dict(a, where="loop") for a in g.asks()]
        return self.scrub(out)

    def gate_answer(self, token: str, instruction) -> dict:
        """The person's instruction for the ask `token`, in the gate that holds it (the loop reads
        it when it re-engages)."""
        token = str(token or "")
        try:
            if any(a["token"] == token for a in self.gate.asks()):
                return self.scrub(self.gate.answer(token, instruction))
            if self.loop_state and (self.loop_state / "gate.json").is_file():
                with Gate.locked(self.loop_state) as g:
                    return self.scrub(g.answer(token, instruction))
            raise Refused("no such ask: it was answered, or never asked")
        except Refused as e:
            raise ValueError(str(e)) from None

    def gate_confirm(self, token: str) -> dict:
        """Write exactly the plan `token` names (the gate's confirm: a source changed since
        the plan refuses, nothing written)."""
        try:
            return self.gate.confirm(str(token or ""))
        except Refused as e:
            raise ValueError(str(e)) from None

    def gate_refuse(self, token: str) -> dict:
        try:
            return self.gate.refuse(str(token or ""))
        except Refused as e:
            raise ValueError(str(e)) from None

    def _shown(self, pl: dict) -> dict:
        """A plan as the page shows it: the files without their text (the diffs), the token."""
        out = public(pl)
        out["files"] = [{k: v for k, v in f.items() if k != "text"} for f in pl["files"]]
        return out

    def seed_plan(self, name: str, seed: str, line: str = "") -> dict:
        """A new domain from a seed (the new-domain form's seed field): a package
        directory (one with a domain.yaml) is taken into the catalog whole; an .llp
        file becomes domains/<name>/ with its manifest. Either way a plan the person
        confirms."""
        p = Path(str(seed or "")).expanduser()
        if not p.exists():
            raise ValueError(f"no seed at {seed}: a package directory (with domain.yaml) or an .llp file")
        if p.is_dir():
            if not (p / "domain.yaml").is_file():
                raise ValueError(f"{seed} is a directory without domain.yaml: not a package")
            if p.parent.name != "domains":
                raise ValueError(f"{seed}: a package seed is a catalog's domains/<name>/ (take brings it from there)")
            return self._shown(self.gate.propose("take", p.name, self.root, src=str(p.parent.parent)))
        if p.suffix != ".llp":
            raise ValueError(f"{seed}: a package directory or an .llp file")
        name = (name or "").strip() or p.stem
        if not self.NAME.match(name):
            raise ValueError("a domain name is lower case, a-z 0-9 _, 2–32 characters, a letter first")
        if (self.root / "domains" / name).exists():
            raise ValueError(f"domains/{name} exists already — open it from the list")
        line = " ".join((line or "").split())[:160]
        return self._shown(self.gate.propose("new", name, self.root, text=p.read_text(),
                                             **({"line": line} if line else {})))

    def close_session(self, sid: str) -> dict:
        self.shells.pop(sid, None)
        self.epochs.pop(sid, None)
        return {"status": "closed", "last_ts": _now()}
