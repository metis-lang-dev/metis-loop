"""`intents check` in the loop console (e2e-workflow s-143c3088, WORKFLOW.md
stage 3): the domain's corpus — or, before it has one, its examples —
through the generated prompt and grammar on the intent model, every answer
mapped to a command atom. (The draft, propose and save of intent.yaml went
with the console's agent seat: the pi loop's catalog_new intents=true drafts
it at the gate; loop-ui 2.4.)

The generator is metispy's metis.intents (CATALOG.md "intent.yaml"),
reached through metis.catalog (the generator, and the write —
catalog.apply); the mapper and the model run in
metis-agent's py venv (metis_agent.intent_check): $METIS_AGENT_PY, else
this python when it has metis_agent.
"""
import os
import subprocess
import sys
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
    """The open session's checkout domain: (its directory, its name). Only a
    domain directory (<name>/<name>.llp with its domain.yaml anywhere under
    the root, or domains/<name>/<name>.llp) carries intents."""
    prog = srv.resolve(name)
    d = prog.parent
    if prog.stem != d.name or not (d.parent.name == "domains" or (d / "domain.yaml").is_file()):
        raise ValueError(f"{prog.relative_to(srv.root.resolve())} is not a domain directory's program "
                         "(domains/<name>/<name>.llp)")
    return d, d.name


def _agent(srv, *args):
    py, cwd = agent_python(srv.root)
    r = subprocess.run([py, "-m", "metis_agent.intent_check", *args], cwd=cwd,
                       capture_output=True, text=True, timeout=900)
    out = r.stdout.strip()                      # the rows and the score; the model's log is stderr
    if r.returncode and not out:
        out = r.stderr.strip()[-2000:]
    return r.returncode, out


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
