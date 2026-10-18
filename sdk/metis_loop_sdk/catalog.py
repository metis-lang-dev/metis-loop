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
    catalog.apply("dog", program=…, extensions={…}, intents=…, manifest={…}, display=…, line=…)
                                    # the one validated write: never a commit
    catalog.edit("dog", "dog.llp", old, new)   # apply()'s arguments for one exact edit of a file on disk
    catalog.take("lamp", src)       # apply()'s arguments that bring a domain over from another catalog
    catalog.readme("lamp", src, run, summary=…)  # a README for a domain an agentic-loop run made
    catalog.build("lamp")           # the domain's bundle (build/, metispy's emitter)

    python -m metis_loop_sdk.catalog list|get|intents [--spec|--skeleton]|fingerprint|apply|edit|take|readme|build|widget|ts … --json

The TypeScript face (metis_loop_sdk/ts/catalog.ts, TS_DIR) is the same
catalog for a node consumer (the agentic loop's pi extensions): one function
per CLI verb, through this CLI, so both faces are one code and one tag. The
wheel carries it as package data, as it carries the widget; `ts` prints where.

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

TS_DIR = (Path(__file__).resolve().parent / "ts").resolve()          # the TypeScript face
TS_FILES = ("catalog.ts",)


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


# A world whose program has no command atoms (pred cmd_*) takes no commands. With
# INTENTLESS (the default) it gets no intent.yaml at all: the agents open a domain without
# intents with no verbs (agent-no-intent s-7fd29000, metis-agent a0a19e6). Without it (for
# agents before that), it gets an intent.yaml that knows only UNKNOWN, headed as what it
# is rather than as a draft. $METIS_CATALOG_INTENTLESS=0 turns it off.
INTENTLESS = os.environ.get("METIS_CATALOG_INTENTLESS", "1") != "0"
NO_COMMANDS = ("# {n}'s intents: the world takes no commands (its program has no cmd_* atom), so this\n"
               "# file knows only UNKNOWN. It is here because the domain agent opens no domain without\n"
               "# an intent.yaml; a domain with commands drafts its verbs from them (tools/intents.py skeleton).\n")


def commands(name, r=None):
    """The command atoms of the domain's program (pred cmd_X …): ["cmd_X", …]."""
    import re
    prog, _ = _program_of(name, _r(r))
    return re.findall(r"^pred\s+(cmd_\w+)", prog.read_text(), re.M) if prog.is_file() else []


def skeleton(name, r=None, intentless=None):
    """A first intent.yaml drafted from the domain's program (its cmd_* atoms and %% lines);
    for a world with no commands, None with INTENTLESS (`intentless`), else one that knows
    only UNKNOWN (not a draft: NO_COMMANDS is its header)."""
    text = generator(r).skeleton(name)
    if commands(name, r):
        return text
    if INTENTLESS if intentless is None else intentless:
        return None
    body = text.split("\n")
    while body and body[0].startswith("#"):
        body.pop(0)
    return NO_COMMANDS.format(n=name) + "\n".join(body)


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


def _host_file(d, keys, whole):
    """The file a domain's host is in (`file.py:factory`), by the manifest
    plan() writes, else the one there is: beside its domain.yaml, never a
    path out of the domain (`../dog/x.py` would write another domain's file)."""
    spec = (yaml.safe_load(whole) or {}).get("host") if whole is not None else keys.get("host")
    if spec is None and (d / "domain.yaml").is_file():
        spec = (yaml.safe_load((d / "domain.yaml").read_text()) or {}).get("host")
    f, sep, _ = str(spec or "").partition(":")
    if not (sep and f.endswith(".py")):
        raise ValueError(f"{d.name}: a host's text needs a manifest host of the form file.py:factory (it has {spec!r})")
    p = (Path(d) / f).resolve()
    if p.parent != Path(d).resolve():
        raise ValueError(f"{d.name}: the host {f!r} is not beside its domain.yaml: a host's file stays in its domain")
    return p


def plan(name, program=None, extensions=None, intents=None, manifest=None, readme=None, host=None, corpus=None,
         r=None, display=None, line=None, since=None):
    """What apply would write: [{path (relative to the root), new, diff,
    text}] for each file whose text changes. `name` is a domain (or a
    catalog's path, no .llp); program the program's text; extensions
    {name: text} written as <dir>/extensions/<name>.llp; intents
    intent.yaml's text (its generated files in intent/, and intent: {spec}
    named in the manifest); manifest {key: value} set in domain.yaml (or
    its whole text, a str); readme the domain's README.md; host the
    host's Python, written as the file the manifest's host names
    (file.py:factory); corpus intent/<name>-corpus.tsv; display and
    line the manifest's two keys of that name (the console's row: a short
    name, one line on the world). The manifest is checked with the loader's
    check_manifest and the intents must generate before anything is
    planned. A generated intent file whose text is empty is not written
    (a domain's spec without `spoken` has no -spoken.txt).

    since {path: text}: an earlier proposal of a file (the one the person
    refused); a planned file with one gets since_diff, its diff from that
    text, so the person reads what changed since, not the whole file again."""
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
    shown = {k: v for k, v in (("display", display), ("line", line)) if v is not None}
    for k, v in shown.items():
        if not isinstance(v, str) or not v.strip() or "\n" in v:
            raise ValueError(f"{name}: {k} is one line of text")
    if whole is not None and shown:
        whole = _manifest_text(whole, shown)
    keys.update(shown)
    if readme is not None:
        if d is None:
            raise ValueError(f"{name}: a README belongs to a domain directory")
        files[d / "README.md"] = readme
    if corpus is not None:
        if d is None:
            raise ValueError(f"{name}: a corpus belongs to a domain directory")
        files[d / "intent" / f"{d.name}-corpus.tsv"] = corpus
    if host is not None:
        if d is None:
            raise ValueError(f"{name}: a host belongs to a domain directory")
        files[_host_file(d, keys, whole)] = host
    if intents is not None:
        if d is None:
            raise ValueError(f"{name}: intents belong to a domain directory (domains/<name>/)")
        n = d.name
        for fn, text in intent_files(n, intents, r).items():
            if text or (d / "intent" / fn).is_file():     # an empty one that is not there stays away
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
        # checked where it will live: a scratch tree with the package at its
        # depth under the root (domains/…), so the loader's containment rule
        # (its paths stay inside the catalog root) reads it as it will
        with tempfile.TemporaryDirectory(prefix="manifest-") as tmp:
            t = Path(tmp) / Path(d).resolve().relative_to(r) / "domain.yaml"
            t.parent.mkdir(parents=True)
            t.write_text(text)
            try:
                check_manifest(t)
            except Exception as e:
                raise ValueError(str(e).replace(str(t), f"{name}/domain.yaml").replace(tmp, str(r))) from None
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
        f = {"path": rel, "new": not p.is_file(), "diff": diff, "text": text}
        if since and rel in since:
            f["since_diff"] = "".join(difflib.unified_diff(since[rel].splitlines(True), text.splitlines(True),
                                                           f"refused/{rel}", f"b/{rel}"))
        out.append(f)
    return out


def apply(name, program=None, extensions=None, intents=None, manifest=None, readme=None, host=None, corpus=None,
          r=None, display=None, line=None):
    """The one validated write into a catalog root (a working copy or a
    scratch catalog): plan()'s files written, never a commit. Returns
    {written: [paths], diff, fingerprint} — the fingerprint of the domain
    after the write (None for a catalog no manifest names)."""
    r = _r(r)
    files = plan(name, program, extensions, intents, manifest, readme, host, corpus, r, display, line)
    for f in files:
        p = r / f["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["text"])
    _, d = _program_of(name, r)
    fp = None
    if d is not None and (d / "domain.yaml").is_file():
        fp = fingerprint(d.name, r)
    return {"written": [f["path"] for f in files], "diff": "".join(f["diff"] for f in files), "fingerprint": fp}


# ── one exact edit of a file on disk ─────────────────────────────────────────

def metisc():
    """The metis compiler for an edit's diagnostics: $METISC, else metisc on PATH, else
    the metis-lang checkout beside this one (src/metisc); None when there is none."""
    import shutil
    m = os.environ.get("METISC") or shutil.which("metisc")
    if m:
        return m
    sib = SIBLING.parent / "metis-lang" / "src" / "metisc"
    return str(sib) if sib.is_file() else None


def diagnostics(text, filename, base=None):
    """metisc's diagnostics of a program text (an extension's against `base`, the program
    file it extends): [{code, severity, decl, text, line, hint}]. Raises ValueError without
    a metisc, or when metisc fails."""
    import subprocess
    m = metisc()
    if not m:
        raise ValueError("no metisc to check a program's edit: set METISC (metis-lang src/metisc)")
    with tempfile.TemporaryDirectory(prefix="edit-") as tmp:
        f = Path(tmp) / filename
        f.write_text(text)
        p = subprocess.run([m, "--diagnostics-json", str(f), *(["--base", str(base)] if base else [])],
                           capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise ValueError(f"metisc --diagnostics {filename}: exit {p.returncode}: {(p.stderr or p.stdout).strip()[-400:]}")
    out = []
    for l in p.stdout.splitlines():
        if l.strip().startswith("{"):
            d = json.loads(l)
            loc = d.get("loc") or {}
            out.append({"code": d.get("code"), "severity": d.get("severity"), "decl": loc.get("decl"),
                        "text": d.get("text"), "line": loc.get("line"), "hint": d.get("hint")})
    return out


def edited(text, old, new, replace_all=False, what="the file"):
    """`text` with `old` replaced by `new`: exactly one occurrence, or every one with
    replace_all. Refused (ValueError) when old is empty, is not there, is there more than
    once without replace_all, or old == new."""
    if not old:
        raise ValueError(f"{what}: old_string is empty (an edit replaces text that is there)")
    if old == new:
        raise ValueError(f"{what}: old_string and new_string are the same: nothing to change")
    k = text.count(old)
    if k == 0:
        raise ValueError(f"{what}: old_string is not in it (it must match exactly, whitespace and all)")
    if k > 1 and not replace_all:
        raise ValueError(f"{what}: old_string occurs {k} times: give more of the text around it, or replace_all")
    return text.replace(old, new)


def edit(name, path, old, new, replace_all=False, r=None):
    """apply()'s arguments for one exact edit of a file of the domain `name` as it is on
    disk: `path` relative to the domain directory (the program, an extensions/*.llp,
    README.md, intent.yaml, domain.yaml, the host's file, the corpus), old replaced by new
    (edited()). It never goes through formalize or revise: every other byte, comments and
    all, stays. A .llp edit adds no diagnostic (metisc's, before and after; an extension
    against the program it extends). Then `apply(name, **edit(…))`: the program
    and intent.yaml go through apply's own checks, intent/ generated again."""
    from collections import Counter
    r = _r(r)
    dom = get(name, r)
    d = Path(dom.dir).resolve()
    p = (d / path).resolve()
    if d not in p.parents:
        raise ValueError(f"{name}: {path!r} is not inside the domain's directory")
    rel = p.relative_to(d).as_posix()
    if rel.startswith("intent/") and rel != f"intent/{name}-corpus.tsv":
        raise ValueError(f"{name}: {rel} is generated from intent.yaml: edit intent.yaml")
    if not p.is_file():
        raise ValueError(f"{name}: there is no {rel} to edit (a new file is written by apply)")
    prog = Path(dom.program).resolve() if dom.program else None
    exts = {Path(e).resolve(): Path(e).stem for e in dom.extensions()}
    host = None
    if dom.manifest.get("host"):
        try:
            host = _host_file(d, {}, (d / "domain.yaml").read_text())
        except ValueError:
            host = None
    old_text = p.read_text()
    text = edited(old_text, old, new, replace_all, f"{name}/{rel}")
    if p == prog:
        kw = {"program": text}
    elif p in exts:
        kw = {"extensions": {exts[p]: text}}
    elif rel == "README.md":
        kw = {"readme": text}
    elif rel == "intent.yaml":
        kw = {"intents": text}
    elif rel == "domain.yaml":
        kw = {"manifest": text}
    elif p == host:
        kw = {"host": text}
    elif rel == f"intent/{name}-corpus.tsv":
        kw = {"corpus": text}
    else:
        raise ValueError(f"{name}: {rel} is not one of the domain's files an edit changes (its program, "
                         "extensions/*.llp, README.md, intent.yaml, domain.yaml, its host, its corpus)")
    if p.suffix == ".llp":
        base = prog if p in exts else None
        key = lambda x: (x["code"], x["severity"], x["decl"], x["text"])
        before = Counter(key(x) for x in diagnostics(old_text, p.name, base))
        after = diagnostics(text, p.name, base)
        added = Counter(key(x) for x in after) - before
        if added:
            shown = []
            for x in after:
                if added[key(x)] > 0:
                    added[key(x)] -= 1
                    shown.append(x)
            raise ValueError(f"{name}/{rel}: the edit adds {len(shown)} diagnostic(s), so it is refused:\n" + "\n".join(
                f"  {x['severity']} {x['code']} @ line {x['line']} ({x['decl']}): {x['text']}"
                + (f" — {x['hint']}" if x.get("hint") else "") for x in shown))
    return kw


# what take() carries: the manifest's keys whose files it brings, and the ones with no file
TAKEN = ("program", "extensions", "host", "intent", "display", "line", "voice", "clock", "reload", "records")


def take(name, src, r=None, readme=None):
    """apply()'s arguments that bring the domain `name` over from the catalog
    `src` (a scratch catalog: the agentic loop's) into the root r: its
    domain.yaml as it is, the program, the extensions, the host, intent.yaml
    (apply generates intent/ again) and a corpus, and its README (or
    `readme`). Never records/ or build/ (the agents' own). Refused when r has
    the domain already, or the domain names a file take does not carry
    (serves, agent, pair, notch: bring those by hand) or keeps one elsewhere
    than its directory's layout. Then `apply(name, **take(name, src, r))`."""
    r, src = _r(r), Path(src).resolve()
    s = get(name, src)
    if (r / "domains" / name).exists():
        raise ValueError(f"{name}: {r} has domains/{name} already")
    if s.dir.resolve() != src / "domains" / name:
        raise ValueError(f"{name}: take brings a domain from domains/{name}/ (it is at {s.dir})")
    other = sorted(set(s.manifest) - set(TAKEN))
    if other:
        raise ValueError(f"{name}: its manifest names {', '.join(other)}, which take does not carry")
    d = s.dir.resolve()
    if s.program is None or Path(s.program).resolve() != d / f"{name}.llp":
        raise ValueError(f"{name}: take carries the program {name}.llp beside domain.yaml (it names {s.program})")
    ext = {}
    for e in s.extensions():
        e = Path(e).resolve()
        if e.parent != d / "extensions":
            raise ValueError(f"{name}: the extension {e} is not in extensions/")
        ext[e.stem] = e.read_text()
    host = None
    if s.manifest.get("host"):
        host = _host_file(d, {}, (d / "domain.yaml").read_text()).read_text()
    it, cp = d / "intent.yaml", d / "intent" / f"{name}-corpus.tsv"
    if readme is None and (d / "README.md").is_file():
        readme = (d / "README.md").read_text()
    return dict(program=Path(s.program).read_text(), extensions=ext, manifest=(d / "domain.yaml").read_text(),
                intents=it.read_text() if it.is_file() else None, host=host,
                corpus=cp.read_text() if cp.is_file() else None, readme=readme)


def header(prog):
    """A program's leading `%` block, verbatim: its comment lines (and the blank lines
    between them) before the first line that is neither; `%%` (a rule's doc) ends it."""
    out = []
    for l in prog.splitlines():
        if l.startswith("%") and not l.startswith("%%"):
            out.append(l)
        elif not l.strip():
            if out:
                out.append(l)
        else:
            break
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def intents_status(name, r=None):
    """One paragraph on the domain's intents, from its files: the verbs intent.yaml maps
    to (a DRAFT said so), only UNKNOWN for a world with no commands, or no intent.yaml."""
    d = Path(get(name, r).dir)
    it = d / "intent.yaml"
    cmds = commands(name, r)
    if not it.is_file():
        if cmds:
            return (f"The program has command atoms ({', '.join(f'`{c}`' for c in cmds)}) but no intent.yaml yet: "
                    f"draft one with `python3 tools/intents.py skeleton {name}`.")
        return ("The world takes no commands (its program has no `cmd_*` atom), so it has no intent.yaml: "
                "the agents open it with no verbs.")
    text = it.read_text()
    spec = yaml.safe_load(text) or {}
    verbs = []
    for v in spec.get("verbs") or []:
        for x in (v.get("verb") if isinstance(v.get("verb"), list) else [v.get("verb")]):
            if x and x != "UNKNOWN":
                verbs.append(x)
    if not verbs:
        return ("The world takes no commands (its program has no `cmd_*` atom). `intent.yaml` knows only UNKNOWN: "
                "it is there because the domain agent opens no domain without one.")
    draft = "a DRAFT" in text.split("\n", 1)[0]
    return (f"`intent.yaml` maps what the person says to the verbs {', '.join(f'`{v}`' for v in verbs)} (and UNKNOWN)."
            + (" It is the loop's first draft (its DRAFT header): write the meanings and more examples, then "
               f"`python3 tools/intents.py gen {name}`." if draft else "")
            + f" Its check: `python3 tools/intents.py check {name}`.")


def readme(name, src, run=None, summary=None, title=None):
    """A README for the domain `name` of the catalog `src`, written from what an
    agentic-loop run left. The SDK writes every mechanical part: the title line, where it
    came from (from the run directory `run`, loop.sh --scratch DIR: records/formalize-
    calls.jsonl's model and cost, or seed.json's seed), the program's own header (its
    leading `%` block, verbatim), its extensions' rules, how to run the case (its `#`
    lines) and the REPL, and the intents' status. A model writes only `summary` (the
    paragraph after the title) and `title` (what the world is, after "<name> — "). For
    take(readme=…) when the domain has none of its own."""
    import re
    src = Path(src).resolve()
    run = Path(run).resolve() if run else None
    d = src / "domains" / name
    prog = (d / f"{name}.llp").read_text()
    m = re.search(r'provenance text "((?:[^"\\]|\\.)*)"', prog)
    prose = m.group(1) if m else ""
    calls = run / "records" / "formalize-calls.jsonl" if run else None
    rows = [json.loads(l) for l in calls.read_text().splitlines() if l.strip()] if calls and calls.is_file() else []
    seed = run / "seed.json" if run else None
    seed = json.loads(seed.read_text()) if seed and seed.is_file() else None
    if title and title.strip():
        head = f"# {name} — {title.strip()}"
    elif prose:
        first = prose.split(". ")[0].rstrip(".")
        head = f"# {name} — {first[0].lower() + first[1:]}"
    else:
        head = f"# {name}"
    out = [head, ""]
    if summary and summary.strip():
        out += [summary.strip(), ""]
    label = f", run `{run.name}`" if run else ""
    if seed:
        how = (f"seeded from `{seed['seed']}`: the program as it was (its header keeps its origin), made a "
               "catalog domain around it")
    elif rows:
        how = (f"the kernel's formalize drafted the program on `{rows[0]['model']}` (formalize: {len(rows)} calls, "
               f"{sum(r.get('cost') or 0 for r in rows):.4f} USD; pi's own calls are on the key's usage)")
    else:
        how = "the kernel's formalize drafted the program"
    out += [f"**Where it came from:** the agentic loop (metis-agentic-loop){label}: pi drove, and {how}. "
            "Every file was approved at pi's apply gate, and taken into this catalog from the run's.", ""]
    host = (d / f"{name}_host.py").is_file()
    out += [f"**What:** `{name}.llp`" + (" formalizes the person's prose (its provenance line)." if prose else
                                          " is the program.")
            + (f" `{name}_host.py` is the world, written before any program: the loop exercised the program against"
               " it, and the extensions explain what the world did that the program did not say." if host else ""), ""]
    h = header(prog)
    if h:
        out += ["## The program's header", "", f"As it is at the top of `{name}.llp`:", "", "```text", h, "```", ""]
    ext = sorted((d / "extensions").glob("*.llp")) if (d / "extensions").is_dir() else []
    if ext:
        out += ["## The extensions", ""]
        for e in ext:
            rules = [l.strip() for l in e.read_text().splitlines() if re.match(r"\s*\w+\s*\[\w+\]\s*:", l)]
            out.append(f"- `extensions/{e.name}`: " + "; ".join(f"`{r}`" for r in rules))
        out.append("")
    out += ["## Run it", ""]
    case = [l.rstrip() for l in prog.splitlines() if re.match(r"#[a-z]", l)]
    if case:
        out += [f"`metisc --run {name}.llp` runs the case its `#` lines give:", "", "```text", *case, "```", ""]
    out.append(f"- the program in the REPL: `metis {'--plugin ' + name + '_host:make ' if host else ''}{name}.llp`;")
    out += ["- the loop console (metis-loop `run.sh`) and the agents serve the program with its extensions "
            "(domain.yaml: `extensions/*.llp` in name order); the console lists it at its next catalog read.", ""]
    out += ["## Intents", "", intents_status(name, src)]
    return "\n".join(out) + "\n"


def build(name, r=None):
    """The domain's bundle (domains/<name>/build/, git-ignored), by metispy's
    emitter in a child (python -m metis.kernel.artifact): its one-line
    account. Raises ValueError with the emitter's own error."""
    import subprocess
    r = _r(r)
    get(name, r)
    p = subprocess.run([sys.executable, "-m", "metis.kernel.artifact", name], cwd=r, capture_output=True, text=True,
                       env={**os.environ, "METIS_CATALOG": str(r)}, timeout=600)
    if p.returncode:
        raise ValueError(f"{name}: the bundle did not build: {(p.stderr or p.stdout).strip()[-600:]}")
    return p.stdout.strip()


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
    it = sub.add_parser("intents", help="the domain's intent material; --spec: with intent.yaml read; "
                                        "--skeleton: a first intent.yaml")
    it.add_argument("name")
    it.add_argument("--skeleton", action="store_true")
    it.add_argument("--spec", action="store_true", help="intent.yaml itself, read (null without one)")
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
    a_.add_argument("--readme", metavar="FILE", help="the domain's README.md from FILE")
    a_.add_argument("--host", metavar="FILE", help="the host's Python from FILE, written as the file the manifest's host names")
    a_.add_argument("--corpus", metavar="FILE", help="intent/<name>-corpus.tsv from FILE")
    a_.add_argument("--display", metavar="TEXT", help="domain.yaml's display: the world's short name")
    a_.add_argument("--line", metavar="TEXT", help="domain.yaml's line: one line on what the world is")
    a_.add_argument("--dry-run", action="store_true")
    ed = sub.add_parser("edit", help="one exact edit of a domain's file as it is on disk (never formalize); "
                                     "--dry-run: the plan and its diff")
    ed.add_argument("name")
    ed.add_argument("path", help="the file, relative to the domain directory (its program, extensions/X.llp, "
                                 "README.md, intent.yaml, domain.yaml, the host, the corpus)")
    ed.add_argument("--old", required=True, metavar="FILE", help="the text to replace, from FILE (- = stdin)")
    ed.add_argument("--new", required=True, metavar="FILE", help="its replacement, from FILE (- = stdin)")
    ed.add_argument("--replace-all", action="store_true", help="every occurrence (else exactly one)")
    ed.add_argument("--dry-run", action="store_true")
    tk = sub.add_parser("take", help="bring a domain over from another catalog (a scratch one) into the root; "
                                     "--dry-run: the plan and its diff")
    tk.add_argument("name")
    tk.add_argument("--from", dest="src", required=True, metavar="ROOT", help="the catalog the domain is in")
    tk.add_argument("--readme", metavar="FILE", help="its README.md from FILE (- = stdin), else the one it has")
    tk.add_argument("--readme-from-run", metavar="RUN_DIR",
                    help="without a README of its own: readme() from the agentic-loop run in RUN_DIR")
    tk.add_argument("--dry-run", action="store_true")
    rd = sub.add_parser("readme", help="readme(): a README for a domain an agentic-loop run made (from ROOT, the run in DIR)")
    rd.add_argument("name")
    rd.add_argument("--from", dest="src", metavar="ROOT", help="the catalog the domain is in (default: the root)")
    rd.add_argument("--run", metavar="DIR", help="the run's directory (records/formalize-calls.jsonl, seed.json)")
    rd.add_argument("--summary", metavar="FILE", help="the paragraph after the title, from FILE (- = stdin)")
    rd.add_argument("--title", metavar="TEXT", help="what the world is, after '<name> — '")
    bd = sub.add_parser("build", help="the domain's bundle (build/, metispy's emitter)")
    bd.add_argument("name")
    rt = sub.add_parser("root", help="the catalog root")
    ts_ = sub.add_parser("ts", help="the TypeScript face's directory and files")
    wd = sub.add_parser("widget", help="the catalog widget's directory, URL and files")
    for p in (ap, ls, g, it, fp, a_, ed, tk, rd, bd, rt, ts_, wd):     # --json after any verb
        p.add_argument("--json", action="store_true", help="JSON on stdout")
    for p in (a_, ed, tk):
        p.add_argument("--since", metavar="FILE", help="a JSON object {path: text}: earlier proposals (refused); "
                                                      "--dry-run's files then carry since_diff, the diff from each")
    a = ap.parse_args(argv)
    r = Path(a.root).resolve() if a.root else None        # --root wins over $METIS_CATALOG (root() reads it first)

    def read(f):
        return sys.stdin.read() if f == "-" else Path(f).read_text()

    def dry(name, kw):
        since = json.loads(read(a.since)) if getattr(a, "since", None) else None
        files = plan(name, **kw, since=since)
        return {"dry_run": True, "files": files, "diff": "".join(f["diff"] for f in files)}

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
            if a.skeleton:
                out = {"name": a.name, "skeleton": skeleton(a.name, r), "commands": commands(a.name, r)}
            else:
                it_ = intents(a.name, r)
                out = {"name": a.name, "intent": _jsonable(it_)}
                if a.spec:
                    sp = it_.get("spec") or get(a.name, r).dir / "intent.yaml"
                    out["spec"] = yaml.safe_load(sp.read_text()) if sp.is_file() else None
        elif a.cmd == "fingerprint":
            out = {"name": a.name, "fingerprint": fingerprint(a.name, r)}
        elif a.cmd == "root":
            out = {"root": str(_r(r))}
        elif a.cmd == "widget":
            out = {"dir": str(WIDGET_DIR), "url": WIDGET_URL, "files": list(WIDGET_FILES)}
        elif a.cmd == "ts":
            out = {"dir": str(TS_DIR), "files": list(TS_FILES)}
        elif a.cmd == "readme":
            out = {"name": a.name, "readme": readme(a.name, a.src or _r(r), a.run,
                                                    read(a.summary) if a.summary else None, a.title)}
        elif a.cmd == "edit":
            if a.old == "-" and a.new == "-":
                raise ValueError("edit: one text from stdin (-) at most")
            kw = edit(a.name, a.path, read(a.old), read(a.new), a.replace_all, r)
            out = dry(a.name, {**kw, "r": r}) if a.dry_run else apply(a.name, r=r, **kw)
        elif a.cmd == "build":
            out = {"name": a.name, "bundle": build(a.name, r)}
        elif a.cmd == "take":
            if a.readme and a.readme_from_run:
                raise ValueError("take: --readme or --readme-from-run, not both")
            text = read(a.readme) if a.readme else None
            if a.readme_from_run and not (Path(a.src) / "domains" / a.name / "README.md").is_file():
                text = readme(a.name, a.src, a.readme_from_run)
            kw = take(a.name, a.src, r, text)
            if a.dry_run:
                out = dry(a.name, {**kw, "r": r})
            else:
                out = apply(a.name, r=r, **kw)
        else:
            ext, ext_files = {}, []
            for e in a.extension:
                n, sep, f = e.partition("=")
                if not sep:
                    raise ValueError(f"--extension {e!r}: NAME=FILE")
                ext_files.append(f)
            if sum(1 for f in [a.program, a.intents, a.readme, a.host, a.corpus, *ext_files] if f == "-") > 1:
                raise ValueError("apply: one text from stdin (-) at most")
            for e, f in zip(a.extension, ext_files):
                ext[e.partition("=")[0]] = read(f)
            itext = read(a.intents) if a.intents else None
            if a.intents_skeleton:
                itext = skeleton(a.name, r)
                if itext is None:
                    raise ValueError(f"{a.name}: the world takes no commands (its program has no cmd_* atom): "
                                     "no intent.yaml (the agents open it with no verbs)")
            kw = dict(program=read(a.program) if a.program else None, extensions=ext, intents=itext,
                      manifest=json.loads(a.manifest) if a.manifest else None,
                      readme=read(a.readme) if a.readme else None, host=read(a.host) if a.host else None,
                      corpus=read(a.corpus) if a.corpus else None, r=r, display=a.display, line=a.line)
            if a.dry_run:
                out = dry(a.name, kw)
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
