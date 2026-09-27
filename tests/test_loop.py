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


MEADOW = """catalog meadow 1.
provenance text "repl gate: wolf and flock" "2026-09-27".
layers (dyn pack).
stages (hunt rest).
namespace md produce (dyn).
pred wolf : md.
pred sheep : md.
pred night : md.
pred fed : md.
pred hungry : md.
weight pk reads {}.
stage hunt {
  %% catch.
  catch [dyn] : wolf * sheep * night -o wolf * fed  @w pk.
  %% evade.
  evade [dyn] : wolf * night -o wolf * hungry  @w ~pk.
}
%% settle.
qui hr [dyn] : hunt -o rest.
"""
SHEPHERD = """catalog shepherd 1.
extends meadow.
provenance text "repl gate: the tally pack" "2026-09-27".
namespace sh produce (pack).
pred tally : sh.
pred loss : sh.
pred safe : sh.
stage rest {
  %% loss.
  n1 [pack] : tally * $fed -o loss.
  %% safe.
  n2 [pack] : tally * $hungry -o safe.
}
"""


def test_repl_tabula_rasa_cycle():
    """text -> llp -> gate -> accept -> trace/map/marginals ->
    repeat with a pack over the accepted world."""
    from loop.repl import Session
    s = Session()
    assert s.dispatch("init", "wolf=1,sheep=3,night=2,tally=2")["ok"]
    assert s.dispatch("steps", "6")["ok"]
    s.dispatch("text", "%% meadow world")
    s.dispatch("llp", MEADOW)
    g1 = s.dispatch("gate", "")
    assert g1["ok"] and g1["rules"], g1
    assert s.dispatch("accept", "")["ok"]
    tr = s.dispatch("trace", "7")
    assert tr["ok"] and tr["events"][0].startswith("hunt/"), tr
    mp = s.dispatch("map", "")
    assert mp["ok"] and mp["events"][0] == "hunt/catch"
    mg = s.dispatch("marginals", "fed hungry")
    assert abs(mg["marginals"]["hungry"] - 0.5) < 1e-12
    # repeat: the pack extends the accepted world; the measure diff
    # is the instrument.
    s.dispatch("text", "%% shepherd tally")
    s.dispatch("llp", SHEPHERD)
    g2 = s.dispatch("gate", "")
    assert g2["ok"], g2
    diffs = dict((d[0], (d[1], d[2])) for d in g2["scenarios"][0]["diffs"])
    assert diffs["loss"][0] == 0.0 and diffs["loss"][1] > 0.8
    assert s.dispatch("accept", "")["ok"]
    tr2 = s.dispatch("trace", "7")
    assert any(e.startswith("rest/") for e in tr2["events"]), tr2
    # the REPL kernel refuses nonsense instead of guessing
    assert not s.dispatch("nosuch", "")["ok"]
