"""`intents` in the loop console (e2e-workflow s-143c3088, WORKFLOW.md
stage 3): a domain's intent.yaml drafted by Claude from the program's cmd_*
atoms and %% lines, shown as a diff, written with `intents save` (the
operator's checkout, never committed), its grammar and prompts generated,
and the check: the domain's corpus — or, before it has one, its examples —
through the generated prompt and grammar on the intent model, every answer
mapped to a command atom.

The generator is metispy's metis.intents (CATALOG.md "intent.yaml"),
reached through metis.catalog (the generator, and the write —
catalog.apply); the mapper and the model run in
metis-agent's py venv (metis_agent.intent_check): $METIS_AGENT_PY, else
this python when it has metis_agent.
"""
import difflib
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from metis import catalog


def generator(root):
    try:
        return catalog.generator(root)
    except FileNotFoundError as e:
        raise ValueError(str(e)) from None


def agent_python(root):
    """metis-agent's py venv: (its python, the directory it runs in) —
    $METIS_AGENT_PY (py/.venv/bin/python, run from py/), else this python
    when metis_agent imports here (run in the root); never a sibling."""
    py = os.environ.get("METIS_AGENT_PY")
    if py:
        if not Path(py).exists():
            raise ValueError(f"no metis-agent python at {py} (METIS_AGENT_PY)")
        return py, str(Path(py).parent.parent.parent)     # py/.venv/bin/python → py/
    import importlib.util
    if importlib.util.find_spec("metis_agent") is not None:
        return sys.executable, str(Path(root).resolve())
    raise ValueError("the intents check runs in metis-agent's py venv: set METIS_AGENT_PY "
                     "(<a metis-agent checkout>/py/.venv/bin/python)")


def domain_of(srv, name):
    """The open copy's checkout domain: (its directory, its name). Only a
    domain directory (<name>/<name>.llp with its domain.yaml anywhere under
    the root, or domains/<name>/<name>.llp) carries intents."""
    try:
        prog = srv.resolve(name)
    except ValueError:
        raise ValueError("intents belong to a checkout domain: this copy is in memory only "
                         "(start one with `new`, or open a domain from the catalog)")
    d = prog.parent
    if prog.stem != d.name or not (d.parent.name == "domains" or (d / "domain.yaml").is_file()):
        raise ValueError(f"{prog.relative_to(srv.root.resolve())} is not a domain directory's program "
                         "(domains/<name>/<name>.llp)")
    return d, d.name


def read(srv, name):
    """The domain's intent.yaml, or a draft from its program (skeleton)."""
    d, n = domain_of(srv, name)
    f = d / "intent.yaml"
    if f.is_file():
        return {"domain": n, "draft": False, "text": f.read_text()}
    return {"domain": n, "draft": True, "text": generator(srv.root).skeleton(n)}


def _scratch(d, n, text):
    """A scratch domains/ root: the domain's files linked, intent.yaml the proposal."""
    tmp = Path(tempfile.mkdtemp(prefix="intents-"))
    t = tmp / "domains" / n
    t.mkdir(parents=True)
    for f in d.iterdir():
        if f.name not in ("intent.yaml", "intent"):
            os.symlink(f, t / f.name)
    (t / "intent.yaml").write_text(text)
    return tmp


def _agent(srv, *args):
    py, cwd = agent_python(srv.root)
    r = subprocess.run([py, "-m", "metis_agent.intent_check", *args], cwd=cwd,
                       capture_output=True, text=True, timeout=900)
    out = r.stdout.strip()                      # the rows and the score; the model's log is stderr
    if r.returncode and not out:
        out = r.stderr.strip()[-2000:]
    return r.returncode, out


def propose(srv, name, text):
    """A proposed intent.yaml, checked before it is shown: it generates
    (the grammar, the prompts) and every example maps to a command atom
    of the program (the generic domain agent's mapper). Returns the diff
    against the checkout and the token `intents save` writes it with."""
    d, n = domain_of(srv, name)
    gen = generator(srv.root)
    import yaml
    try:
        spec = yaml.safe_load(text)
        gen.grammar(spec), gen.prompt(spec), gen.spoken(spec)
    except Exception as e:      # the user's text: any failure is the finding
        raise ValueError(f"intent.yaml does not generate: {type(e).__name__}: {e}")
    tmp = _scratch(d, n, text)
    try:
        rc, out = _agent(srv, n, "--no-model", "--root", str(tmp / "domains"))
    finally:
        subprocess.run(["rm", "-rf", str(tmp)])
    prog = d / f"{n}.llp"       # an ask must ask: its command's rules only read the state (CATALOG.md asks)
    asks = gen.asks_problems(spec, prog.read_text()) if prog.is_file() and hasattr(gen, "asks_problems") else []
    f = d / "intent.yaml"
    old = f.read_text() if f.is_file() else ""
    rel = f.relative_to(srv.root.resolve()).as_posix()
    diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), f"a/{rel}", f"b/{rel}"))
    token = hashlib.sha256((rel + "\0" + text).encode()).hexdigest()[:16]
    misses = [l for l in out.splitlines() if l.startswith("MISS")] + ["ASKS " + a for a in asks]
    return {"domain": n, "path": rel, "new": not f.is_file(), "diff": diff, "token": token,
            "mapped": out.splitlines()[-1] if out else "", "misses": misses, "ok": rc == 0 and not asks, "text": text}


def save(srv, pending, token):
    """Write the proposal `token` names, generate its files at their fixed
    names, and name the spec in the manifest (intent: {spec}) so
    metis-agent reads them: the SDK's catalog.apply (the manifest checked by
    the loader). A manifest whose intent: names another spec is the
    operator's: not touched, reported as manifest_lacks."""
    if not pending or pending.get("token") != token:
        raise ValueError("no such proposal — ask Claude for one (`intents`), then `intents save`")
    d, n = domain_of(srv, pending["domain"])
    import yaml
    f = d / "domain.yaml"
    have = (yaml.safe_load(f.read_text()) or {}).get("intent") if f.is_file() else None
    lacking = ["spec"] if isinstance(have, dict) and have.get("spec") != "intent.yaml" else []
    out = catalog.apply(n, intents=pending["text"], r=srv.root)
    written = [pending["path"]] + [p for p in out["written"] if p != pending["path"]]
    res = {"domain": n, "written": written}
    if lacking:
        res["manifest_lacks"] = lacking        # its intent: is the operator's: not touched
    return res


def check(srv, name, model=None):
    """The corpus (domains/<n>/intent/<n>-corpus.tsv), or the examples when
    the domain has none, through the generated prompt and grammar on the
    intent model; every answer mapped. The output: one line per row and
    the score."""
    d, n = domain_of(srv, name)
    if not (d / "intent.yaml").is_file():
        raise ValueError(f"{n} has no intent.yaml yet — `intents`, then `intents save`")
    args = [n, "--root", str(d.parent)]
    if not (d / "intent" / f"{n}-corpus.tsv").is_file():
        args.append("--examples")
    if model:
        args += ["--model", model]
    rc, out = _agent(srv, *args)
    return {"domain": n, "ok": rc == 0, "output": out}
