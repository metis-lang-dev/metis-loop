"""The console's serving half (CONSOLE §5a): one kernel REPL per open
console window, over the metis-catalog checkout.

The artifact db is reachable only by the page's capability or by a
Claude session's ArtifactData tool, so the drain is a Claude session
(skills/metis-loop "Serving the console"); this module is the python
it calls — no db access of its own, no threads, import-light:

  - `catalogs()`           names for meta/catalogs (load chips);
  - `open_session(sid, doc)` binds an interpreter to a sessions doc
                            and returns the fields to write back;
  - `serve_one(sid, cmd)`  runs ONE queued intent line through the
                            run_intent whitelist (`intent_posting`) and
                            returns {posting, session}: the intent
                            doc's update and the session doc's update;
  - `close_session(sid)`;
  - `drain(sessions, intents)` — ALL of the above as one pure
    mapping: db rows in, [{path, data}] update-writes out (and
    `catalogs_doc()` for meta/catalogs). The serving session is glue:
    list, call, batch-apply.

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


def catalog_root() -> Path:
    """$METIS_CATALOG, else the metis-catalog checkout beside this
    package (perotheia-packages/metis-catalog)."""
    env = os.environ.get("METIS_CATALOG")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "metis-catalog"


# `new <name>`: the skeleton program (the header, #init, one commented rule
# with its %% line — the narrator and the mapper read the %% line)
SKELETON = """% {name} — {line}
% Made in the loop console (new). Say in prose what there is, what can
% happen and what the person can ask; formalize writes the rules.
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

MAX_SOURCE = 256 * 1024     # an in-memory catalog's byte cap


def _source_repl(path: Path, source: str, seed: int, plugin=None):
    """A Repl over catalog TEXT, compiled in memory (CONSOLE-WS §4a):
    no temp file, nothing on disk. `path` only names it and anchors
    includes (resolved against the checkout); the kernel is untouched —
    the subclass swaps the one read in `_compile`."""
    from metis.lang import compile_catalog, parse, resolve_includes
    from metis.lang.directives import embedded_case
    from metis.lang.repl import Repl

    class SourceRepl(Repl):
        def _compile(self):
            text = self._source
            ast = parse(text, file=str(self.path))
            doc = compile_catalog(resolve_includes(ast, self.path.parent))
            return text, doc, embedded_case(text)
    r = SourceRepl.__new__(SourceRepl)
    r._source = source
    SourceRepl.__init__(r, path, seed=seed, stdout=io.StringIO(), plugin=plugin, host=bool(plugin))
    return r


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ConsoleServer:
    """{sid: Repl} plus the per-session epoch."""

    def __init__(self, root: Optional[Path] = None, seed: int = 1):
        self.root = Path(root) if root else catalog_root()
        self.seed = seed
        self.shells: Dict[str, object] = {}
        self.epochs: Dict[str, int] = {}
        self._roots = sorted({str(self.root), str(self.root.resolve())},
                             key=len, reverse=True)
        home = str(Path.home())
        self._home = home if len(home) > 1 else ""

    # -- catalogs --------------------------------------------------------

    def catalogs(self):
        """Every .llp under the checkout, as names relative to it
        without the suffix (`domains/fiction/3lp`), sorted."""
        return sorted(str(p.relative_to(self.root).with_suffix(""))
                      for p in self.root.rglob("*.llp")
                      if ".git" not in p.parts)

    def domains(self):
        """The CATALOG panel's list (catalog_index): every catalog with
        its display line and what it has, the domains first; a domain
        carries its README's opening (readme_text) for the panel."""
        from .catalog_index import index, readme_head
        return [{**e, "readme_text": readme_head(self.root, e["readme"])} if e["readme"] else e
                for e in index(self.root)]

    def resolve(self, llp: str) -> Path:
        """A catalog name -> its file in the checkout: the full
        relative name (with or without .llp), or a unique basename
        (`3lp`). Never outside the checkout."""
        name = (llp or "").strip()
        if not name:
            raise ValueError("no catalog named")
        name = name[:-4] if name.endswith(".llp") else name
        names = self.catalogs()
        hits = [n for n in names if n == name] or \
               [n for n in names if n.split("/")[-1] == name] or \
               [n for n in names if n.endswith("/" + name)]
        if not hits:
            raise ValueError(f"no catalog '{llp}' in {self.root}")
        if len(hits) > 1:
            raise ValueError(f"'{llp}' is ambiguous: {', '.join(hits)}")
        path = (self.root / (hits[0] + ".llp")).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"'{llp}' resolves outside the checkout")
        return path

    # -- what leaves for the web -----------------------------------------

    def scrub(self, obj):
        """Web output never names the operator's filesystem: the
        checkout root becomes relative ("domains/fiction/3lp.llp") and
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

    def _source_path(self, name: str) -> Path:
        """Where an in-memory catalog is anchored (names it, resolves its
        includes): a checkout name keeps that file's directory, anything
        else a virtual <root>/scratch/<safe>.llp — never written."""
        try:
            return self.resolve(name)
        except ValueError:
            safe = "".join(c if c.isalnum() or c in "-_." else "_"
                           for c in name.split("/")[-1])[:64]
            return self.root.resolve() / "scratch" / (
                (safe.removesuffix(".llp") or "scratch") + ".llp")

    @staticmethod
    def _pack_text(src: str) -> str:
        """A pack's approved text = its leading `%` comment block (the
        `load` convention) — what its %% docs quote at the gate."""
        head = []
        for line in src.splitlines():
            if line.startswith("%"):
                head.append(line.lstrip("%").strip())
            elif line.strip():
                break
        return "\n".join(head) or "extension pack"

    def build(self, doc: dict):
        """A Repl for `{llp}` (a checkout catalog) or `{source, name,
        packs?}` — catalog TEXT compiled in memory, then each pack
        (`{source, name}`) gated as a pack against it and merged into
        THIS session only (the loop's own llp → gate → accept, called
        here — `accept` stays off the wire; nothing is committed).
        Returns (repl, llp label, pack reports); raises ValueError with
        the findings on any failure."""
        from metis.lang.repl import Repl
        if doc.get("source") is None:
            path = self.resolve(doc.get("llp", ""))
            rel = str(path.relative_to(self.root.resolve()).with_suffix(""))
            # {llp, host: true} — the one-click open of the CATALOG panel:
            # the host the INDEX names for this checkout file (never a
            # spec from the wire: D4), attached as an operator's --host
            spec = None
            if doc.get("host"):
                from .catalog_index import host_of
                spec = host_of(self.root.resolve(), rel)
            r = Repl(path, seed=self.seed, stdout=io.StringIO(), plugin=spec, host=bool(spec))
            # the served program is the program plus its packs (human-loop
            # step 1): a domain's packs/*.llp merged as a session's are
            packs = [{"name": p.stem, "source": p.read_text()} for p in self.checkout_packs(path)]
            reports = self._merge_packs(r, packs)
            label = rel + (f" + {spec}" if spec else "")
            if reports:
                label += f" + {len(reports)} pack{'s' if len(reports) != 1 else ''}"
            return r, label, reports
        src = str(doc["source"])
        packs = list(doc.get("packs") or [])
        total = len(src.encode()) + sum(len(str(p.get("source", "")).encode())
                                        for p in packs)
        if total > MAX_SOURCE:
            raise ValueError(f"catalog source over {MAX_SOURCE // 1024} KiB")
        name = str(doc.get("name") or "scratch").strip() or "scratch"
        anchor = self._source_path(name)
        spec = None
        if doc.get("host") and anchor.is_file():    # a hosted checkout domain recompiled from its copy
            from .catalog_index import host_of
            spec = host_of(self.root.resolve(), anchor.relative_to(self.root.resolve()).with_suffix("").as_posix())
        r = _source_repl(anchor, src, self.seed, plugin=spec)
        reports = self._merge_packs(r, packs)
        label = name.removesuffix(".llp") + " (in memory" + (
            f" + {len(reports)} pack{'s' if len(reports) != 1 else ''}"
            if reports else "") + ")"
        return r, label, reports

    def _merge_packs(self, r, packs) -> list:
        """Each pack `{source, name}` gated as a pack against the program and
        merged into THIS session (llp → gate → accept); the reports. Raises
        ValueError with the findings when one is not admitted."""
        reports = []
        for k, pk in enumerate(packs, 1):
            psrc = str(pk.get("source") or "")
            pname = str(pk.get("name") or f"pack {k}")
            if not psrc.strip():
                continue
            r.cmd_text(self._pack_text(psrc))
            r.cmd_llp(psrc)
            rep = r.cmd_gate("")
            if not rep.get("ok"):
                found = rep.get("findings") or [rep.get("error", "rejected")]
                raise ValueError(f"pack '{pname}' not admitted: " +
                                 "; ".join(map(str, found))[:1500])
            acc = r.cmd_accept("")
            reports.append({"name": pname, "ok": True,
                            "key": acc.get("key")})
            r.loop.text = ""
        return reports

    def checkout_packs(self, path: Path) -> list:
        """A checkout program's packs, from the domain manifest beside it
        only (runtime-binding Q1): its `serves: [files]` after the program
        when the first one is this program, else none; without `serves`,
        packs/*.llp in name order (metis_catalog's Domain.serves() —
        packs/ is where apply writes them); none for a program no manifest
        names."""
        d = path.parent
        m = d / "domain.yaml"
        if not m.is_file():
            return []
        try:
            import yaml
            man = yaml.safe_load(m.read_text()) or {}
        except Exception:                           # noqa: BLE001 — a manifest mid-write: no packs
            return []
        serves = man.get("serves")
        if serves:                                  # a pkg.mod:path is never this checkout's program
            files = [(d / str(f)).resolve() for f in serves]
            return files[1:] if files[0] == path.resolve() else []
        prog = (d / str(man.get("program") or "")).resolve() if man.get("program") else None
        if prog != path.resolve() or not (d / "packs").is_dir():
            return []
        return sorted((d / "packs").glob("*.llp"))

    @staticmethod
    def _carry_loop(old, new):
        """A recompile keeps the session's loop: the sunk records, the
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
        """Bind an interpreter to sessions/{sid} from `{llp: name}` (a
        checkout catalog) or `{source, name, packs?}` (CONSOLE-WS §4a:
        a copy and its extension packs, compiled in memory — never on
        the operator's disk). The live interpreter is replaced only
        when everything compiles and every pack is admitted; a failure
        comes back as {status: "closed", error} and leaves an existing
        session as it was."""
        try:
            r, llp, reports = self.build(doc)
        except Exception as e:                      # noqa: BLE001
            return {"status": "closed", "error": self.scrub(str(e)),
                    "last_ts": _now()}
        if doc.get("keep_loop") and sid in self.shells:     # a recompile: the loop goes on
            self._carry_loop(self.shells[sid], r)
        self.shells[sid] = r
        self.epochs[sid] = 1
        out = self._fields(sid)
        out["llp"] = llp
        if reports:
            out["packs"] = reports
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

    # -- the drain as one pure mapping (the serving session is glue) ----

    # -- e2e-workflow step 1: records from files, new, save -------------

    def records(self):
        """Every surprise record the domain agents sank in the checkout
        (domains/<…>/records/<session>.jsonl, one record per line with
        its close), newest first; escalated ones carry mined_text."""
        out = []
        for f in self.root.rglob("records/*.jsonl"):
            if ".git" in f.parts:
                continue
            rel = f.relative_to(self.root).as_posix()
            dom = f.parent.parent.relative_to(self.root).as_posix()
            try:
                lines = [ln for ln in f.read_text(errors="replace").splitlines()
                         if ln.strip() and not ln.startswith("#")]
            except OSError:
                continue
            for i, ln in enumerate(lines):
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                close = r.get("close") or {}
                out.append({"file": rel, "i": i, "domain": dom, "session": f.stem,
                            "ts": r.get("ts") or close.get("ts") or "",
                            "kind": r.get("kind"), "record": r.get("record"),
                            "status": close.get("status") or ("escalated" if r.get("escalated") else "open"),
                            "escalated": bool(r.get("escalated") or close.get("status") == "escalated"),
                            "mined_text": r.get("mined_text") or "", "beat": close.get("beat", r.get("beat")),
                            "observed": r.get("observed") or {}, "catalog": r.get("catalog_hash") or r.get("program_key") or ""})
        return sorted(out, key=lambda e: (str(e["ts"]), e["file"], e["i"]), reverse=True)

    def _under(self, rel: str, must: str = "") -> Path:
        p = (self.root / (rel or "")).resolve()
        if not p.is_relative_to(self.root.resolve()) or (must and must not in p.as_posix()):
            raise ValueError(f"'{rel}' is not a {must.strip('/') or 'checkout'} file of the checkout")
        return p

    def load_sink(self, sid: str, rel: str) -> dict:
        """`sink` for a session, from a checkout records file (the verb
        takes a path, so it stays off the wire: the server names the file)."""
        p = self._under(rel, "/records/")
        if p.suffix != ".jsonl" or not p.is_file():
            raise ValueError(f"no records file '{rel}'")
        if sid not in self.shells:
            raise ValueError(f"no open session '{sid}'")
        out = self.shells[sid].cmd_sink(str(p))
        # each loaded record's identity (its record number and time, as the
        # Records dock lists it): the page selects the clicked record by it,
        # never by its line (human-loop step 1, the architect's A6 finding)
        out["ids"] = [[r.get("record"), r.get("ts") or (r.get("close") or {}).get("ts") or ""]
                      for r in self.shells[sid].loop.records]
        return self.scrub(out)

    NAME = __import__("re").compile(r"^[a-z][a-z0-9_]{1,31}$")

    def new_domain(self, name: str, line: str = "") -> str:
        """domains/<name>/: domain.yaml, a skeleton <name>.llp (the
        header, #init, one commented rule with its %% line), README.md
        with the display line. Returns the program's name for open."""
        name = (name or "").strip()
        if not self.NAME.match(name):
            raise ValueError("a domain name is lower case, a-z 0-9 _, 2–32 characters, a letter first")
        d = self.root / "domains" / name
        if d.exists():
            raise ValueError(f"domains/{name} exists already — open it from the list")
        line = " ".join((line or f"the {name} domain").split())[:160]
        d.mkdir(parents=True)
        (d / "domain.yaml").write_text(
            f"name: {name}\ndisplay: the {name}\nline: {json.dumps(line)}\nvoice: third\n"
            f"program: {name}.llp\ndocs: README.md\nrecords: records/\n")
        (d / f"{name}.llp").write_text(SKELETON.format(name=name, line=line.replace('"', "'"),
                                                       date=time.strftime("%Y-%m-%d")))
        (d / "README.md").write_text(f"# {name} — {line}\n\nA new domain, made in the loop console. "
                                     "Describe what there is, what can happen and what the person can ask.\n")
        return f"domains/{name}/{name}"

    def save_plan(self, work: dict) -> dict:
        """What `save` would write: the working copy over its checkout
        program, each pack as <domain>/packs/<name>.llp — each with its
        unified diff. `token` names exactly this plan (save checks it)."""
        import difflib
        import hashlib
        name = str(work.get("name") or "")
        try:
            prog = self.resolve(name)
        except ValueError:
            raise ValueError("save writes a checkout domain: this copy is in memory only "
                             "(start one with `new`, or open a catalog from the list)")
        files = []

        def plan(path: Path, text: str):
            old = path.read_text() if path.is_file() else ""
            if old == text:
                return
            rel = path.relative_to(self.root.resolve()).as_posix()
            diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                                f"a/{rel}", f"b/{rel}"))
            files.append({"path": rel, "new": not path.is_file(), "diff": diff, "text": text})
        plan(prog, str(work.get("copy") or ""))
        safe = __import__("re").compile(r"[^a-z0-9_]+")
        for k, pk in enumerate(work.get("packs") or [], 1):
            stem = safe.sub("_", str(pk.get("name") or f"pack{k}").lower()).strip("_") or f"pack{k}"
            plan(prog.parent / "packs" / f"{stem}.llp", str(pk.get("source") or ""))
        token = hashlib.sha256(json.dumps([(f["path"], f["text"]) for f in files]).encode()).hexdigest()[:16]
        return {"files": [{k: v for k, v in f.items() if k != "text"} for f in files], "token": token}

    def save_apply(self, work: dict, token: str) -> dict:
        """Write the plan the viewer saw (its token), never anything else;
        never a git commit (that stays the operator's)."""
        plan = self.save_plan(work)
        if not token or plan["token"] != token:
            raise ValueError("the copy changed since the diff was shown — review the new diff")
        texts = self._plan_texts(work)
        for f in plan["files"]:
            p = self._under(f["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(texts[f["path"]])
        return {"written": [f["path"] for f in plan["files"]], "token": token}

    def _plan_texts(self, work: dict) -> dict:
        prog = self.resolve(str(work.get("name") or ""))
        root = self.root.resolve()
        out = {prog.relative_to(root).as_posix(): str(work.get("copy") or "")}
        safe = __import__("re").compile(r"[^a-z0-9_]+")
        for k, pk in enumerate(work.get("packs") or [], 1):
            stem = safe.sub("_", str(pk.get("name") or f"pack{k}").lower()).strip("_") or f"pack{k}"
            out[(prog.parent / "packs" / f"{stem}.llp").relative_to(root).as_posix()] = str(pk.get("source") or "")
        return out

    def domains_doc(self) -> dict:
        """The `meta/domains` write (the db transport's CATALOG panel)."""
        return {"path": "meta/domains", "data": {"domains": self.domains(), "ts": _now()}}

    def catalogs_doc(self) -> dict:
        """The `meta/catalogs` write: {path, data: {names, ts}}."""
        return {"path": "meta/catalogs",
                "data": {"names": self.catalogs(), "ts": _now()}}

    def drain(self, sessions, intents) -> list:
        """One drain pass: db rows in, writes out — the serving session
        lists `sessions` and `intents` (ArtifactData rows, either
        {id, data: {...}} or flat {id, ...}), calls this, and applies
        each returned {path, data} as an `update` (one batch). Order:
        bind `opening` sessions; re-bind live sessions this process
        has no interpreter for (a restarted server — epoch + 1 so the
        page resets cleanly); then serve `queued` intents oldest
        first. Writes to one doc are merged, in order; values are
        JSON-plain."""
        import json

        def rows(xs):
            for x in xs or []:
                if isinstance(x, (tuple, list)):
                    yield x[0], dict(x[1])
                else:
                    d = x.get("data")
                    yield x["id"], dict(d if isinstance(d, dict) else
                                        {k: v for k, v in x.items()
                                         if k != "id"})
        out: Dict[str, dict] = {}

        def put(path, data):
            out.setdefault(path, {}).update(
                json.loads(json.dumps(data, default=str)))
        for sid, doc in rows(sessions):
            st = doc.get("status")
            if st == "opening":
                put(f"sessions/{sid}", self.open_session(sid, doc))
            elif st in ("running", "quiescent", "done") and \
                    sid not in self.shells:
                fields = self.open_session(sid, doc)
                if fields.get("status") != "closed":
                    self.epochs[sid] = int(doc.get("epoch") or 0) + 1
                    fields = dict(self._fields(sid), llp=fields["llp"],
                                  reopened=_now())
                put(f"sessions/{sid}", fields)
        queued = sorted(((iid, d) for iid, d in rows(intents)
                         if d.get("status") == "queued"),
                        key=lambda r: str(r[1].get("ts")))
        for iid, d in queued:
            res = self.serve_one(d.get("session", ""), d.get("cmd", ""))
            put(f"intents/{iid}", res["posting"])
            if res["session"] is not None:
                put(f"sessions/{d.get('session')}", res["session"])
        return [{"path": p, "data": v} for p, v in out.items()]

    def close_session(self, sid: str) -> dict:
        self.shells.pop(sid, None)
        self.epochs.pop(sid, None)
        return {"status": "closed", "last_ts": _now()}
