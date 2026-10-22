"""The policy driver (loop-policy step 2). The splice and the empty base need only the world's files;
the runs need ALFWorld (the world's venv, $ALFWORLD_DATA) and are skipped without it:

    cd metis-loop/pi && ALFWORLD_DATA=… …/.worlds/alf/bin/python -m pytest policy/tests -q

The runs use the scripted brain (tests/hand-script.jsonl: answers chosen by the prompt, no model):
explore writes the four action rules from transitions, exploit revises two preconditions from the
world's refusals and the policy from an episode not won, a refactor that changes the commands is
refused; then a run with no answers disengages, the person's note is answered through the gate,
and --resume re-engages with the note in every prompt."""
import json
import os
from pathlib import Path

import pytest

from policy.brain import block_of, splice

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "hand-script.jsonl"
BASE = """catalog alf 1.
pred at(location) : alf.
stage act {
  %% I go.
  go [dyn] : at(L) * $recat(R, L2) * L <> L2 -o at(L2).
}
"""


def test_splice_adds_replaces_and_drops():
    text, info = splice(BASE, block_of("```llp\npred want(object) : alf.\n%% I take {O}.\ntake_plain [dyn] : want(O) -o want(O).\n```"))
    assert info["added"] == ["take_plain"] and info["declared"] == ["want"]
    assert text.index("pred want") < text.index("stage act") and "  %% I take {O}." in text
    text2, info2 = splice(text, ["go [dyn] : at(L) * $recat(R, L2) -o at(L2).", "drop take_plain"])
    assert info2["replaced"] == ["go"] and info2["dropped"] == ["take_plain"]
    assert "take_plain" not in text2 and "L <> L2" not in text2 and text2.count("%% I go.") == 0
    assert splice(text2, ["pred want(object) : alf."])[0] == text2            # a name declared once


def test_the_empty_base_keeps_the_declarations_and_no_rule():
    try:
        from policy.alfworld import empty_base, rules_of
        text = empty_base()
    except SystemExit:
        pytest.skip("no metis-worlds checkout beside this one")
    assert rules_of(text) == [] and "pred inrecep(object, receptacle)" in text
    assert "pred unchosen" in text and "pred placed" in text and "pred want" not in text and "pred carrying" not in text


live = pytest.mark.skipif(not os.environ.get("ALFWORLD_DATA"), reason="ALFWorld's games ($ALFWORLD_DATA) and the world's venv")


def _run(run, brain, cfg=None, resume=False):
    from policy.brain import Brain
    from policy.driver import Driver
    out = []
    d = Driver(run, Brain(brain, run), discovery=2, gate_games=2, cfg=dict({"explore_steps": 25, "exploit_episodes": 6}, **(cfg or {})),
               out=out.append)
    code = d.resume() if resume else d.go()
    return code, [json.loads(l) for l in out], d


@live
def test_the_scripted_brain_builds_the_family_from_the_empty_domain(tmp_path):
    code, out, d = _run(tmp_path / "run", "script:%s" % SCRIPT)
    assert code == 0
    props = [e for e in d.gate.journal() if e.get("event") == "proposal"]
    explore = [e for e in props if e["phase"] == "explore" and e["verdict"] == "accept"]
    assert len(explore) == 4 and all(e["numbers"]["fits_records"] for e in explore)
    exploit = [e for e in props if e["phase"] == "exploit" and e["verdict"] == "accept"]
    assert any(e["numbers"]["success"] > 0 for e in exploit)                     # the policy: the gate split won
    assert any(e["numbers"]["likelihood"] > 0 and e["numbers"]["success"] == 0 for e in exploit)   # a precondition from a refusal
    ref = [e for e in props if e["phase"] == "refactor"]
    assert ref and all(e["verdict"] == "refuse" and e["numbers"]["replay_identical"] is False for e in ref)
    won = [e["won"] for e in out if e.get("event") == "episode"][-2:]
    assert won == [True, True]
    assert (tmp_path / "run" / "records" / "heldout.jsonl").exists() and (tmp_path / "run" / "cost.jsonl").exists()


@live
def test_a_cornered_run_asks_and_resumes_with_the_answer(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    code, out, d = _run(tmp_path / "run", "script:%s" % empty)
    assert code == 3 and out[-1]["disengaged"]["reason"] == "budget" and out[-1]["disengaged"]["question"]
    snap = json.loads(Path(out[-1]["disengaged"]["snapshot"]).read_text())
    assert snap["phase"] == "explore" and snap["base_sha"]
    note = "the world says Nothing happens when a receptacle is closed"
    d.gate.answer(out[-1]["token"], note)
    code, out2, d2 = _run(tmp_path / "run", "script:%s" % SCRIPT, resume=True)
    assert code == 0 and out2[0]["event"] == "re-engaged" and out2[0]["instruction"]["text"] == note
    prompts = [json.loads(l) for l in (tmp_path / "run" / "prompts.jsonl").read_text().splitlines()]
    assert prompts and all(note in p["prompt"] for p in prompts)
    assert [e["event"] for e in d2.gate.journal()].count("answer") == 1
