"""Loop-core gates, on the stage-45 benchmark fixtures from the
metis-lang corpus: the admit seam reproduces the harness verdicts,
and the repair loop converges when the backend's first candidate is
broken — the untrusted-formalizer contract, exercised end to end
with a scripted backend (no model needed)."""
import os
import stat
import sys
from pathlib import Path

from loop import admit, formalize_loop

ROOT = Path(__file__).resolve().parents[1]
LANG = Path(os.environ.get(
    "METIS_LANG", ROOT.parent / "metis-lang")).resolve()
TEXT = "%% market coin: a mark trades on the coin flip outcome."


def _fixture(name):
    return (LANG / "corpus" / name).read_text()


def test_admit_pack_ok():
    rep = admit(TEXT, _fixture("packmark.llp"),
                base_path=LANG / "corpus/packbase.llp",
                scenarios=[{"coin": 1, "mkt": 1}], steps=4)
    assert rep.ok, rep.findings
    assert rep.scenarios and rep.scenarios[0].key


def test_admit_vocabulary_drift_caught():
    bad = _fixture("packmark.llp").replace("mkt", "unlock", 1)
    rep = admit(TEXT, bad, base_path=LANG / "corpus/packbase.llp")
    assert not rep.ok and rep.findings


def test_repair_loop_converges(tmp_path):
    """Round 1 emits vocabulary drift; the findings feed back; round
    2 emits the correct pack. The loop must report rounds=2, ok."""
    good = LANG / "corpus/packmark.llp"
    bad = tmp_path / "bad.llp"
    bad.write_text(_fixture("packmark.llp").replace("mkt", "unlock", 1))
    marker = tmp_path / "called"
    backend = tmp_path / "backend.sh"
    backend.write_text(
        "#!/bin/sh\n"
        f"if [ -e {marker} ]; then cat {good}; else touch {marker}; "
        f"cat {bad}; fi\n")
    backend.chmod(backend.stat().st_mode | stat.S_IEXEC)

    res = formalize_loop(TEXT, "coin, heads, tails, mkt", [str(backend)],
                         base_path=LANG / "corpus/packbase.llp",
                         scenarios=[{"coin": 1, "mkt": 1}], steps=4)
    assert res.ok and res.rounds == 2, (res.rounds, res.history)
    assert not res.history[0][1] == []          # round 1 had findings
    assert res.report and res.report.scenarios


def test_cli_admit(tmp_path, capsys):
    from loop.cli import main
    t = tmp_path / "t.md"
    t.write_text(TEXT)
    rc = main(["admit", str(t), str(LANG / "corpus/packmark.llp"),
               "--base", str(LANG / "corpus/packbase.llp"),
               "--scenario", "coin=1,mkt=1", "--steps", "4"])
    out = capsys.readouterr().out
    assert rc == 0 and "ok=True" in out and "diff" in out
