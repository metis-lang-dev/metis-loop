"""The console's REPL domain (domains/repl, console-nav s-b923ebfe) through metispy's kernel,
no model: its case (cases/repl.llp) in both toolchains, the program's own #init its live start; every state it reaches from
#init under the person's commands, the gateway's reports and the host's pair flips takes each
token by exactly one rule (none stuck, no pair held twice); every rule — each accept and each
refusal — fired by the kernel's own step from a state the exploration reached; the card's
generated files are what the SDK's generator makes. (domains/ui is held: its program is being
redesigned.)"""
import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from console_domains import INJECT_REPL, Explorer

ROOT = Path(__file__).resolve().parents[1]
REPL = ROOT / "domains" / "repl" / "repl.llp"
CASE = ROOT / "cases" / "repl.llp"
RULES = re.compile(r"^\s*(\w+) \[dyn\]", re.M)


@pytest.fixture(scope="module")
def explored():
    return Explorer(str(REPL), INJECT_REPL).run()


def test_one_rule_per_token_in_every_reachable_state(explored):
    ex = explored
    assert len(ex.seen) > 20
    assert ex.conflicts == [], ex.conflicts[:3]
    assert ex.stuck == [], ex.stuck[:3]
    assert ex.internal == [], ex.internal[:3]
    assert ex.broken == [], ex.broken[:3]
    assert set(RULES.findall(REPL.read_text())) == set(ex.fired)      # every rule is reached


def test_every_rule_fires_by_the_kernels_own_step(explored):
    from metis.lang.repl import Repl
    for rule, counts in sorted(explored.witness.items()):
        r = Repl(str(REPL), seed=1, stdout=io.StringIO())
        r.counts = dict(counts)
        r.do_step("")
        assert r.fired and r.fired[-1].split("[")[0] == rule, (rule, counts, r.fired[-1:])


def test_refusals_say_why():
    """Every refusal rule has its %% line (the sentence the person hears)."""
    text = REPL.read_text().splitlines()
    for i, line in enumerate(text):
        m = RULES.match(line)
        if m and "refused(" in line.split("-o", 1)[1]:
            assert text[i - 1].strip().startswith("%%"), m.group(1)


def _metisc():
    return os.environ.get("METISC") or shutil.which("metisc")


@pytest.mark.skipif(not _metisc(), reason="no metisc (METISC)")
def test_the_case_in_both_toolchains():
    """metisc --run of the case file (cases/repl.llp: the program included, a start that fires)
    and metispy's replay of it: the same I/T/F lines; the program's own #init is its live start."""
    from metis.kernel.artifact import served_doc
    from metis.lang.directives import render_run
    out = subprocess.run([_metisc(), "--run", str(CASE)], stdin=subprocess.DEVNULL, capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    doc, case, _ = served_doc(CASE, [])
    py = render_run(CASE.stem, case, doc.catalog.ground(dict(case["init"])))

    def itf(s):
        return [l for l in s.splitlines() if l[:2] in ("I ", "T ", "F ")]
    assert itf(out.stdout) == itf(py) and "T 1 run_nothing" in out.stdout
    assert "cmd_" not in "".join(l for l in REPL.read_text().splitlines() if l.startswith("#init"))   # the live start


def test_the_cards_generated_files_are_the_generators():
    from metis_loop_sdk import catalog
    for n in ("repl",):                      # domains/ui is held (its redesign)
        d = ROOT / "domains" / n
        files = catalog.intent_files(n, (d / "intent.yaml").read_text(), ROOT)
        for name, text in files.items():
            assert (d / "intent" / name).read_text() == text, f"{n}/intent/{name}: regenerate (the SDK's generator)"
