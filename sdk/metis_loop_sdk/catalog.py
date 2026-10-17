"""metis_loop_sdk.catalog — the one access to metis-catalog (catalog-sdk
s-bc1718e3; brief/repo-alignment.md §3a). Every consumer reads and writes the
catalog here, so a change to the catalog's layout or to domain.yaml touches
metis-catalog and this module, and no consumer.

    from metis_loop_sdk import catalog
    catalog.root()                  # $METIS_CATALOG, else the configured root, else the sibling checkout
    catalog.domains()               # [Domain] — every manifest, by name (metis_catalog's Domain)
    catalog.get("dog")              # Domain: .program .serves() .intent .has() …
    catalog.index()                 # every catalog for a console's list, the domains first
    catalog.listing()               # the agent console's rows: the domains, then each partner as its own row
    catalog.readme_head(rel)        # a README's opening
    catalog.intents("dog")          # the domain's intent material: {spec, grammar, prompt, examples, corpus}
    catalog.generator()             # the intent generator (metis-catalog tools/intents.py) as a module
    catalog.fingerprint("dog")      # the stale detection: a hash over what a reload takes
    catalog.plan("dog", program=…)  # what apply would write, with each file's diff
    catalog.apply("dog", program=…, extensions={…}, intents=…, manifest={…})
                                    # the one validated write: never a commit

    python -m metis_loop_sdk.catalog list|get|intents|fingerprint|apply|widget … --json

The catalog widget (the CATALOG panel both consoles show) lives in
metis-loop's web/catalog/ (web/: the shared web widgets); the SDK carries the
same bytes as package data — metis_loop_sdk/widget is a link to it, and a
built wheel holds its files (the sdk-alone CI job checks them byte for byte).
WIDGET_DIR holds catalog.js and catalog.css, served at WIDGET_URL; its rows
are index() / listing().
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

# perotheia-packages/metis-catalog beside this checkout (sdk/metis_loop_sdk/catalog.py)
SIBLING = Path(__file__).resolve().parents[3] / "metis-catalog"
INSTALL = ("the catalog's loader (metis_catalog) is missing: pip install -e <metis-catalog checkout>"
           "  (metis-loop/run.sh and metis-agent/run.sh do it; it needs pyyaml)")

WIDGET_DIR = (Path(__file__).resolve().parent / "widget").resolve()   # the checkout: ../../web/catalog
WIDGET_URL = "/sdk/catalog/"          # where a console serves WIDGET_DIR
WIDGET_FILES = ("catalog.js", "catalog.css")


# ── the loader and the root ───────────────────────────────────────────────────

def loader():
    """metis_catalog — installed, else from the sibling checkout. The one
    place in every consumer that imports it."""
    try:
        import metis_catalog
    except ImportError:
        if SIBLING.is_dir() and str(SIBLING) not in sys.path:
            sys.path.insert(0, str(SIBLING))
        try:
            import metis_catalog
        except ImportError as e:            # the package or its pyyaml
            raise ImportError(f"{INSTALL} — {e}") from None
    return metis_catalog


def root(config=None) -> Path:
    """The catalog root: $METIS_CATALOG, else `config` (the consumer's
    configured root), else the metis-catalog checkout beside this one, else
    the checkout the loader is installed from (an editable install)."""
    for c in (os.environ.get("METIS_CATALOG"), config):
        if c:
            return Path(c).resolve()
    if (SIBLING / "domains").is_dir():
        return SIBLING
    own = Path(loader().__file__).resolve().parents[1]
    if (own / "domains").is_dir():
        return own
    raise FileNotFoundError("no catalog root: set METIS_CATALOG to a metis-catalog checkout "
                            f"(none beside this one at {SIBLING})")


def _r(r):
    return Path(r).resolve() if r else root()


def domains(r=None):
    """Every domain with a manifest, by name (metis_catalog Domain)."""
    return loader().domains(_r(r))


def get(name, r=None):
    """The domain `name` (KeyError when there is no manifest of it)."""
    return loader().get(name, _r(r))


def index(r=None):
    """Every catalog of the root for a console's list: the domains first
    (their display line, what they have, the host spec), then every other
    .llp (metis_catalog.index)."""
    return loader().index(_r(r))


def listing(r=None):
    """The agent console's rows (py service and Go console alike): the
    index's domains, then each partner (never listed alone in the index) as
    its own row, kind partner."""
    r = _r(r)
    out = [{k: e.get(k) for k in ("name", "kind", "path", "display", "line", "has")}
           for e in index(r) if e["kind"] == "domain"]
    for d in domains(r):
        if d.partner_of:
            out.append({"name": d.name, "kind": "partner", "path": str(d.dir), "display": d.display,
                        "line": d.line, "has": d.has(), "partner_of": d.partner_of})
    return out


def readme_head(rel, limit=1600, r=None):
    """A README's opening (its title and first paragraphs, cut at a paragraph)."""
    return loader().readme_head(rel, limit, r=_r(r))


def host_of(rel, r=None):
    """The host the index names for the catalog `rel` (its path, no .llp), or None."""
    return next((e["host"] for e in index(r) if e.get("path") == rel), None)


def check_manifest(path):
    """A domain.yaml read and checked by the loader's own rule (ManifestError)."""
    return loader().check_manifest(path)


# ── intents ───────────────────────────────────────────────────────────────────

def generator(r=None):
    """The intent generator, metis-catalog's tools/intents.py, as a module
    reading the root `r`: the root's own tools/intents.py, else the sibling
    checkout's (a scratch catalog of domains/ only). A fresh module per
    call, its ROOT the root."""
    r = _r(r)
    p = r / "tools" / "intents.py"
    if not p.is_file():
        p = SIBLING / "tools" / "intents.py"
    if not p.is_file():
        raise FileNotFoundError(f"no intent generator at {r}/tools/intents.py (metis-catalog tools/intents.py)")
    spec = importlib.util.spec_from_file_location("metis_catalog_intents", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = r
    return mod


def intents(name, r=None):
    """The domain's intent material: {spec, grammar, prompt, examples:
    {template: path}, corpus} — the paths that exist ({} without intent: {spec})."""
    return get(name, r).intent


def intent_files(name, text, r=None):
    """The files the generator makes of intent.yaml `text` for `name`
    ({file name in intent/: text}); raises when the text does not generate."""
    gen = generator(r)
    with tempfile.TemporaryDirectory(prefix="intents-") as tmp:
        d = Path(tmp) / "domains" / name
        d.mkdir(parents=True)
        (d / "intent.yaml").write_text(text)
        gen.ROOT = Path(tmp)
        try:
            if not isinstance(yaml.safe_load(text), dict):
                raise ValueError("intent.yaml is a mapping")
            return gen.files(name)
        except Exception as e:      # the author's text: any failure is the finding
            raise ValueError(f"intent.yaml does not generate: {type(e).__name__}: {e}") from None


def skeleton(name, r=None):
    """A first intent.yaml drafted from the domain's program (its cmd_* atoms and %% lines)."""
    return generator(r).skeleton(name)


# ── the stale detection ──────────────────────────────────────────────────────

def watched(name):
    """What a domain directory holds that a reload takes: the program and its
    extensions, the intents, the host, the overlay, the manifest (metis-agent
    v3reload.go's watched — Go keeps its own, by this rule)."""
    return (Path(name).suffix in (".llp", ".py", ".gbnf") or name in ("intent.yaml", "domain.yaml")
            or name.endswith((".notch.json", "-prompt.txt", "-spoken.txt")))


def snapshot(d):
    """{path relative to the domain directory d: text} of its watched files
    (d, d/intent, d/extensions)."""
    out = {}
    if not d:
        return out
    d = Path(d)
    for sub in (d, d / "intent", d / "extensions"):
        try:
            entries = sorted(sub.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_file() and watched(e.name):
                try:
                    out[str(e.relative_to(d))] = e.read_text(errors="replace")
                except OSError:
                    pass
    return out


def fingerprint(name, r=None):
    """A hash over the domain's watched files (names and contents): it
    changes exactly when a reload would read something else."""
    d = get(name, r).dir
    h = hashlib.sha256()
    for k, v in sorted(snapshot(d).items()):
        h.update(k.encode() + b"\0" + hashlib.sha256(v.encode()).digest())
    return h.hexdigest()


def extensions_of(program, r=None):
    """A program file's extensions, by the manifest beside it only
    (runtime-binding Q1): the domain's served files after the program when
    the program is the first of them (Domain.serves()), else none — none for
    a program no manifest names, or a manifest that does not read (mid-write)."""
    program = Path(program).resolve()
    mf = program.parent / "domain.yaml"
    if not mf.is_file():
        return []
    try:
        d = loader().Domain(program.parent.name, program.parent, check_manifest(mf))
        served = d.serves()
    except Exception:                       # noqa: BLE001 — a manifest mid-write, a missing package
        return []
    return list(served[1:]) if served and served[0] == program else []


def widget_file(name):
    """(text, content type) of one widget file for WIDGET_URL<name>, or None."""
    if name not in WIDGET_FILES:
        return None
    return (WIDGET_DIR / name).read_text(), ("text/javascript; charset=utf-8" if name.endswith(".js")
                                              else "text/css; charset=utf-8")


# ── the one validated write ──────────────────────────────────────────────────

def _program_of(name, r):
    """(the program file, the domain directory or None) for a domain name or
    a catalog's path relative to the root (no .llp)."""
    if "/" in name or name.endswith(".llp"):
        rel = name[:-4] if name.endswith(".llp") else name
        p = (r / (rel + ".llp")).resolve()
        if r not in p.parents:
            raise ValueError(f"{name!r} resolves outside the catalog root")
        d = p.parent if (p.parent / "domain.yaml").is_file() else None
        return p, d
    lc = loader()
    try:
        dom = lc.get(name, r)
    except KeyError:                       # a new domain: domains/<name>/<name>.llp
        d = r / "domains" / name
        return d / f"{name}.llp", d
    return (dom.program or dom.dir / f"{name}.llp"), dom.dir


def _manifest_text(old, keys):
    """domain.yaml's text with `keys` set: a key it has with another value has
    its line replaced (a one-line key only), a key it lacks is appended; its
    comments and order kept."""
    import re
    lines = old.splitlines(True) if old else []
    have = (yaml.safe_load(old) or {}) if old else {}
    for k, v in keys.items():
        if k in have and have[k] == v:
            continue
        line = "%s: %s\n" % (k, yaml.safe_dump(v, default_flow_style=True, width=1 << 16).strip()
                             .removesuffix("\n...").strip())
        at = [i for i, l in enumerate(lines) if re.match(r"^%s\s*:" % re.escape(k), l)]
        if at:
            i = at[0]
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt[:1] in (" ", "\t", "-"):
                raise ValueError(f"domain.yaml: {k} spans lines; set it by hand")
            lines[i] = line
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(line)
    return "".join(lines)


def plan(name, program=None, extensions=None, intents=None, manifest=None, readme=None, r=None):
    """What apply would write: [{path (relative to the root), new, diff,
    text}] for each file whose text changes. `name` is a domain (or a
    catalog's path, no .llp); program the program's text; extensions
    {name: text} written as <dir>/extensions/<name>.llp; intents
    intent.yaml's text (its generated files in intent/, and intent: {spec}
    named in the manifest); manifest {key: value} set in domain.yaml (or
    its whole text, a str); readme the domain's README.md. The
    manifest is checked with the loader's check_manifest and the intents
    must generate before anything is planned."""
    import re
    r = _r(r)
    prog, d = _program_of(name, r)
    files = {}
    if program is not None:
        files[prog] = program
    safe = re.compile(r"[^a-z0-9_]+")
    for k, (en, text) in enumerate((extensions or {}).items(), 1):
        stem = safe.sub("_", str(en or f"extension{k}").lower()).strip("_") or f"extension{k}"
        files[prog.parent / "extensions" / f"{stem}.llp"] = text
    whole = manifest if isinstance(manifest, str) else None      # domain.yaml's whole text
    keys = {} if whole is not None else dict(manifest or {})
    if readme is not None:
        if d is None:
            raise ValueError(f"{name}: a README belongs to a domain directory")
        files[d / "README.md"] = readme
    if intents is not None:
        if d is None:
            raise ValueError(f"{name}: intents belong to a domain directory (domains/<name>/)")
        n = d.name
        for fn, text in intent_files(n, intents, r).items():
            files[d / "intent" / fn] = text
        files[d / "intent.yaml"] = intents
        cur = {}
        if (d / "domain.yaml").is_file():
            cur = yaml.safe_load((d / "domain.yaml").read_text()) or {}
        if not isinstance(cur.get("intent"), dict):
            keys.setdefault("intent", {"spec": "intent.yaml"})
    if whole is not None or keys or (d is not None and program is not None and not (d / "domain.yaml").is_file()
                                     and d.parent == r / "domains"):
        if d is None:
            raise ValueError(f"{name}: a manifest belongs to a domain directory")
        mf = d / "domain.yaml"
        if whole is None and not mf.is_file() and "program" not in keys:   # a new domain: its program named
            keys["program"] = prog.relative_to(d).as_posix()
        text = _manifest_text(whole if whole is not None else (mf.read_text() if mf.is_file() else ""), keys)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as t:
            t.write(text)
        try:
            check_manifest(t.name)
        except Exception as e:
            raise ValueError(str(e).replace(t.name, f"{name}/domain.yaml")) from None
        finally:
            os.unlink(t.name)
        files[mf] = text
    out = []
    for p, text in files.items():
        p = Path(p).resolve()
        if r not in p.parents:
            raise ValueError(f"{p} is outside the catalog root {r}")
        old = p.read_text() if p.is_file() else ""
        if p.is_file() and old == text:
            continue
        rel = p.relative_to(r).as_posix()
        diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), f"a/{rel}", f"b/{rel}"))
        out.append({"path": rel, "new": not p.is_file(), "diff": diff, "text": text})
    return out


def apply(name, program=None, extensions=None, intents=None, manifest=None, readme=None, r=None):
    """The one validated write into a catalog root (a working copy or a
    scratch catalog): plan()'s files written, never a commit. Returns
    {written: [paths], diff, fingerprint} — the fingerprint of the domain
    after the write (None for a catalog no manifest names)."""
    r = _r(r)
    files = plan(name, program, extensions, intents, manifest, readme, r)
    for f in files:
        p = r / f["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["text"])
    _, d = _program_of(name, r)
    fp = None
    if d is not None and (d / "domain.yaml").is_file():
        fp = fingerprint(d.name, r)
    return {"written": [f["path"] for f in files], "diff": "".join(f["diff"] for f in files), "fingerprint": fp}


# ── JSON forms (the CLI) ─────────────────────────────────────────────────────

def _jsonable(o):
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def describe(name, r=None):
    """One domain as JSON: its manifest and what the loader derives of it."""
    d = get(name, r)
    return _jsonable({"name": d.name, "dir": d.dir, "manifest": d.manifest, "display": d.display, "line": d.line,
                      "voice": d.voice, "program": d.program, "extensions": d.extensions(), "serves": d.serves(),
                      "host": d.host_spec_for(), "notch": d.notch, "intent": d.intent, "records": d.records,
                      "clock": d.clock, "pair": d.pair, "partner_of": d.partner_of, "readme": d.readme,
                      "has": d.has(), "fingerprint": fingerprint(name, r)})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m metis_loop_sdk.catalog", description=__doc__.split("\n")[0])
    ap.add_argument("--root", help="the catalog root (default: $METIS_CATALOG, else the sibling checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="every catalog, the domains first (index); --consoles: the agent console's rows")
    ls.add_argument("--domains", action="store_true", help="the domains only")
    ls.add_argument("--consoles", action="store_true", help="the agent console's rows (partners as their own rows)")
    g = sub.add_parser("get", help="one domain: its manifest and what the loader derives")
    g.add_argument("name")
    it = sub.add_parser("intents", help="the domain's intent material; --skeleton: a first intent.yaml")
    it.add_argument("name")
    it.add_argument("--skeleton", action="store_true")
    fp = sub.add_parser("fingerprint", help="the hash over what a reload takes")
    fp.add_argument("name")
    a_ = sub.add_parser("apply", help="the one validated write (never a commit); --dry-run: the plan and its diff")
    a_.add_argument("name", help="a domain, or a catalog's path relative to the root (no .llp)")
    a_.add_argument("--program", metavar="FILE", help="the program's text from FILE (- = stdin)")
    a_.add_argument("--extension", action="append", default=[], metavar="NAME=FILE",
                    help="an extension, written as extensions/NAME.llp")
    a_.add_argument("--intents", metavar="FILE", help="intent.yaml's text from FILE (its files generated)")
    a_.add_argument("--intents-skeleton", action="store_true", help="intent.yaml drafted from the program")
    a_.add_argument("--manifest", metavar="JSON", help="domain.yaml keys to set, as a JSON object")
    a_.add_argument("--dry-run", action="store_true")
    sub.add_parser("root", help="the catalog root")
    sub.add_parser("widget", help="the catalog widget's directory, URL and files")
    for p in (ap, ls, g, it, fp, a_):
        p.add_argument("--json", action="store_true", help="JSON on stdout")
    a = ap.parse_args(argv)
    r = root(a.root) if a.root else None

    def read(f):
        return sys.stdin.read() if f == "-" else Path(f).read_text()

    try:
        if a.cmd == "list":
            rows = listing(r) if a.consoles else [e for e in index(r) if not a.domains or e["kind"] == "domain"]
            if not a.json:
                print("# %s" % _r(r))
                for e in rows:
                    has = " ".join(k for k, v in e["has"].items() if v and k != "program")
                    print("%-7s %-16s %-44s %-28s %s" % (e["kind"], e["name"], e.get("path") or "—", has,
                                                         (e.get("line") or "")[:70]))
                return 0
            out = rows
        elif a.cmd == "get":
            out = describe(a.name, r)
        elif a.cmd == "intents":
            out = {"name": a.name, "skeleton": skeleton(a.name, r)} if a.skeleton else \
                {"name": a.name, "intent": _jsonable(intents(a.name, r))}
        elif a.cmd == "fingerprint":
            out = {"name": a.name, "fingerprint": fingerprint(a.name, r)}
        elif a.cmd == "root":
            out = {"root": str(_r(r))}
        elif a.cmd == "widget":
            out = {"dir": str(WIDGET_DIR), "url": WIDGET_URL, "files": list(WIDGET_FILES)}
        else:
            ext = {}
            for e in a.extension:
                n, sep, f = e.partition("=")
                if not sep:
                    raise ValueError(f"--extension {e!r}: NAME=FILE")
                ext[n] = read(f)
            itext = read(a.intents) if a.intents else (skeleton(a.name, r) if a.intents_skeleton else None)
            kw = dict(program=read(a.program) if a.program else None, extensions=ext, intents=itext,
                      manifest=json.loads(a.manifest) if a.manifest else None, r=r)
            if a.dry_run:
                files = plan(a.name, **kw)
                out = {"dry_run": True, "files": [{k: v for k, v in f.items() if k != "text"} for f in files],
                       "diff": "".join(f["diff"] for f in files)}
            else:
                out = apply(a.name, **kw)
    except (KeyError, ValueError, FileNotFoundError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        if a.json:
            json.dump({"error": msg}, sys.stdout)
            print()
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 1
    if a.json or a.cmd != "list":
        json.dump(out, sys.stdout, indent=1, default=str)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
