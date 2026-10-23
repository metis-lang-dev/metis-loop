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
    d = Driver(run, Brain(brain, run), discovery=2, gate_games=2, cfg=dict({"explore_steps": 25, "exploit_episodes": 10}, **(cfg or {})),
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


def test_the_spend_meter_survives_a_resume(tmp_path, monkeypatch):
    """nina's R1: a resumed brain keeps the run's first start and its cap (the state), and N2: the
    spent amount is the larger of the key's delta and the reported costs. No network: /key stubbed."""
    from policy import brain as B
    usage = [5.0]
    monkeypatch.setattr(B.Brain, "usage", lambda self: usage[0])
    state = {}
    b1 = B.Brain("openrouter/m", tmp_path, spend=1.0, env={"OPENROUTER_API_KEY": "k"})
    b1.keep(state)
    assert state == {"spend_start": 5.0, "spend_cap": 1.0}
    usage[0] = 5.6
    b2 = B.Brain("openrouter/m", tmp_path, spend=1.0, env={"OPENROUTER_API_KEY": "k"})     # the resume: a new brain
    b2.keep(state)
    assert b2.start_usage == 5.0 and b2.spent() == pytest.approx(0.6)
    b3 = B.Brain("openrouter/m", tmp_path, spend=0.5, env={"OPENROUTER_API_KEY": "k"})     # a resume with a lower --budget
    b3.keep(dict(state))
    assert b3.spend == 0.5                                                # nina's N8: the lower cap holds
    usage[0] = 6.05
    with pytest.raises(B.Budget):
        b2.ask("a prompt", "explore")                                     # stopped before the call: no network
    (tmp_path / "cost.jsonl").write_text(json.dumps({"cost": 1.5}) + "\n")
    usage[0] = 5.1
    assert b2.spent() == pytest.approx(1.5)                               # the key lags: the reported costs win


@live
def test_a_rule_revised_in_vain_twice_is_probed_in_the_same_phase(tmp_path):
    """nina's R2: two refused revises at one rule within one exploit pass send the loop to the probe."""
    code, out, d = _run(tmp_path / "run", "script:%s" % (HERE / "probe-script.jsonl"), cfg={"exploit_episodes": 2, "no_progress": 9})
    revises = [e for e in out if e.get("event") == "proposal" and e.get("phase") == "exploit" and e.get("verdict") == "refuse"]
    assert len(revises) >= 2
    probes = [e for e in out if e.get("event") == "probe"]
    assert probes and probes[0]["records"] > 0


@live
def test_the_persons_edit_is_judged_and_the_tree_follows(tmp_path):
    """nina's R3 and R4: an edit answer goes through the gate like a rule, with the counters and the
    current tree re-synced; R5: a prompt past the per-request cap is an ask, not a traceback."""
    from policy.brain import Brain
    from policy.driver import Driver
    if not os.environ.get("METISC"):                    # the gate checks a .llp edit with metisc (run.sh sets it)
        c = next((p / "metis-lang" / "src" / "metisc" for p in HERE.parents if (p / "metis-lang" / "src" / "metisc").exists()), None)
        if c is None:
            pytest.skip("no metisc: set METISC")
        os.environ["METISC"] = str(c)
    out = []
    d = Driver(tmp_path / "run", Brain("script:%s" % SCRIPT, tmp_path / "run", prompt_chars=500), discovery=2, gate_games=2,
               cfg={"explore_steps": 25}, out=out.append)
    assert d.go() == 3
    ask = json.loads(out[-1])
    assert ask["disengaged"]["reason"] == "budget" and "per-request cap" in ask["disengaged"]["question"]
    rule = "  %% I go to {R}.\n  go [dyn] : at(L) * $recat(R, L2) * L <> L2 -o at(L2)."
    d.gate.answer(ask["token"], {"kind": "edit", "path": "alf.llp", "old": "stage act {", "new": "stage act {\n" + rule})
    out2 = []
    d2 = Driver(tmp_path / "run", Brain("script:%s" % SCRIPT, tmp_path / "run"), discovery=2, gate_games=2,
                cfg={"explore_steps": 25, "exploit_episodes": 2}, out=out2.append)
    d2.resume()
    mine = next(json.loads(l) for l in out2 if '"by": "person"' in l)
    assert mine["verdict"] == "accept" and mine["numbers"]["likelihood"] > 0
    assert "go [dyn]" in (tmp_path / "run" / "trees" / "current" / "base" / "alf.llp").read_text()
    assert d2.state["accepted"] >= 1


def test_explain_names_the_fact_the_rule_consumes_wrongly():
    """policy-tuning: the gate's fits refusal in the brain's terms — a take rule that consumes at(L) is
    told the world keeps it. The predictor is measure.Predictor itself, its sessions faked: explain reads
    the facts as the predictor judges them (_cmp), and a renamed method fails here, not in a paid run
    (the step-1 card's runs died on `Predictor._dyn` after 4c473c6 renamed it)."""
    from policy import measure

    class P(measure.Predictor):
        def __init__(self):
            self.dynamic, self.uncompared = {"at", "handsfree", "inrecep", "holding", "holds"}, set()

        def compiles(self, iid):
            return None

        def events(self, rec, names=None):
            before = set(rec["before"])
            return [("take_plain[O=o1,R=r1,Loc=l1]", self._cmp((before - {"at(l1)", "handsfree", "inrecep(o1,r1)"}) | {"holding", "holds(o1)"}))]

        def table(self, iid):
            return {}

        def contradicted(self, r, names):
            return []
    rec = {"game": "g", "t": 1, "command": "take o1 from r1", "action": {"verb": "take", "args": {"O": "o1", "R": "r1"}},
           "before": ["at(l1)", "handsfree", "inrecep(o1,r1)"], "after": ["at(l1)", "holding", "holds(o1)"]}
    cur = "catalog alf 1.\nstage act {\n}\n"
    cand = "catalog alf 1.\nstage act {\n  %% t\n  take_plain [dyn] : at(L) * handsfree * inrecep(O, R) -o holding * holds(O).\n}\n"
    why = measure.explain(P(), cand, cur, rec, [rec])
    assert "consumes at(l1), which the world keeps" in why, why
    assert "the base already has them" in measure.explain(P(), cur, cur, rec, [rec])

    class Broken(P):                          # a candidate that does not compile: the compiler's words, not "no event binds"
        def compiles(self, iid):
            return "ParseError: 60:6: expected [, got ':'"
    assert "do not compile" in measure.explain(Broken(), cand, cur, rec, [rec]) and "expected [" in measure.explain(Broken(), cand, cur, rec, [rec])


def test_a_misleading_compiler_word_is_said_in_the_brains_terms():
    """policy-tuning step 1: the brain wrote `go : …` (no layer); "expected [, got ':'" made it put the
    variables in brackets twice. The repair prompt names the layer."""
    from policy import prompts
    p = prompts.repair(["go : at(L1) -o at(L2)."], "ParseError: 60:6: expected [, got ':'")
    assert "`NAME [dyn] :`" in p and "LAYER" in p
    assert "LAYER" not in prompts.repair(["go [dyn] : x -o y."], "TypeError: unknown predicate y")
