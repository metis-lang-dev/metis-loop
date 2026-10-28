"""policy-tuning steps 2 and 3 (rewrite.py, scorecard.structural_of): the card comparison, the
journal's digest, the md block; and (slow, ALFWorld, METIS_POLICY_SLOW=1) one rewrite round on the
scripted brain — the edited skill scored as a variant, the verdict and its reason in history.json."""
import json
import os
from pathlib import Path

import pytest

from policy import rewrite

HERE = Path(__file__).resolve().parent


def card(variant, rows, usd=0.0, rules=10):
    return {"variant": variant, "rows": rows, "usd": usd, "rules": rules}


def row(world, flat, director=None, guards=None, exercised=None):
    return {"world": world, "seed": 1, "heldout_flat": flat, "heldout_director": director,
            "structural": {"guards": guards, "exercised": exercised}}


def test_better_is_wins_on_every_world_then_structure_then_cost():
    kept = card("k", [row("alfworld", "5/10"), row("scienceworld", "2/10")], usd=0.2)
    assert rewrite.better(card("c", [row("alfworld", "6/10"), row("scienceworld", "2/10")]), kept)[0]
    ok, why = rewrite.better(card("c", [row("alfworld", "9/10"), row("scienceworld", "1/10")]), kept)
    assert not ok and "scienceworld" in why                       # a world down: not better, whatever the sum
    same = [row("alfworld", "5/10", guards=True, exercised=4), row("scienceworld", "2/10", guards=True, exercised=3)]
    kept2 = card("k", [row("alfworld", "5/10", guards=True, exercised=3), row("scienceworld", "2/10", guards=True, exercised=3)], usd=0.2)
    assert rewrite.better(card("c", same), kept2) == (True, "domains exercised 7 vs 6")
    unguarded = [row("alfworld", "5/10", guards=False, exercised=9), row("scienceworld", "2/10")]
    ok, why = rewrite.better(card("c", unguarded, usd=0.1), kept2)
    assert ok and why.startswith("usd/rule")                     # a structure without its guards is not judged
    assert rewrite.won(card("x", [row("alfworld", "3/10", "4/10"), row("alfworld", "error: x")])) == {"alfworld": 7}


def test_the_md_block_and_the_digest(tmp_path):
    assert rewrite.md_block("text\n```md\n## always\n1. x\n```\nmore") == "## always\n1. x\n"
    inner = "```md\n## always\n1. e.g.\n```llp\ngo [dyn] : a -o b.\n```\n2. y\n```"
    assert rewrite.md_block(inner) == "## always\n1. e.g.\n```llp\ngo [dyn] : a -o b.\n```\n2. y\n"     # nina's N1
    d = tmp_path / "v" / "alfworld-s1"
    d.mkdir(parents=True)
    # nina's R2: the split (a move, no call) between two brain proposals; the second judged its compile repair's lines
    prompts = [{"purpose": "explore", "answer": "go [dyn] : at(L) -o at(L2)."},
               {"purpose": "conventions", "answer": "broken"}, {"purpose": "conventions-repair", "answer": "the repaired lines"}]
    (d / "prompts.jsonl").write_text("".join(json.dumps(p) + "\n" for p in prompts))
    log = [{"event": "proposal", "phase": "explore", "domain": "alf", "verdict": "refuse", "by": "brain", "call": 1,
            "numbers": {"fits_records": False, "likelihood": 0.0}, "why": ["not: fits"]},
           {"event": "fit-repair", "purpose": "explore", "why": "consumes at(L), which the world keeps"},
           {"event": "proposal", "phase": "refactor", "domain": "alf", "verdict": "refuse", "by": "brain", "call": None, "split": {}},
           {"event": "proposal", "phase": "refactor", "domain": "alf", "verdict": "refuse", "by": "brain", "call": 3}]
    (d / "run.log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))
    c = card("v", [dict(row("alfworld", "0/10"), phase="explore", accepted=0, proposals=3, status="disengaged")])
    text = rewrite.digest(c, tmp_path)
    assert "the brain's lines: go [dyn]" in text and "fit-repair (explore): consumes at(L)" in text
    assert text.count("the brain's lines") == 2 and "the brain's lines: the repaired lines" in text and "broken" not in text
    for e in log:                                         # a run journaled before the call ids: paired in order
        e.pop("call", None)
    (d / "run.log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))
    assert rewrite.digest(c, tmp_path) == text
    assert rewrite.judged_calls(prompts + [{"purpose": "probe-pick"}, {"purpose": "explore-fit"}]) == [1, 3, 5]


def test_the_series_stops_before_its_cap(tmp_path, monkeypatch):
    """nina's R1: the series' spend (the key's /key usage, stubbed here) is checked before every run and
    every rewrite call; one that could pass the cap is not started, and history.json says so."""
    from policy import scorecard
    from policy.brain import Brain
    key = {"usage": 10.0}
    monkeypatch.setattr(Brain, "usage", lambda self: key["usage"])
    runs_scored = []

    def score_one(variant, world, seed, a, runs):
        runs_scored.append((variant, world))
        key["usage"] += 0.3                                 # each run spends 0.30 on the key
        return {"world": world, "seed": seed, "usd": 0.3, "rules": 5, "heldout_flat": "5/10"}

    def ask(self, prompt, purpose=""):
        key["usage"] += 0.05
        return "```md\n## always\n0. new\n## explore\n## exploit\n## refactor\n```"
    monkeypatch.setattr(scorecard, "score_one", score_one)
    monkeypatch.setattr(scorecard, "structural_of", lambda *x: None)
    monkeypatch.setattr(Brain, "ask", ask)
    skill = tmp_path / "skill.md"
    skill.write_text("## always\n## explore\n## exploit\n## refactor\n")
    rc = rewrite.main(["--skill", str(skill), "--rounds", "3", "--worlds", "alfworld,scienceworld", "--brain", "openrouter/x/y",
                       "--budget", "0.5", "--series-budget", "1.2", "--runs", str(tmp_path / "runs")])
    assert rc == 0
    # the headroom (the architect's N4): 1.5× the largest run seen (0.30 → 0.45), at least 0.10, never above --budget.
    # rw0's two runs (0.60), the rewrite call (0.65), rw1's first run (0.95); its second (0.95 + 0.45) could pass 1.2
    assert runs_scored == [("rw0", "alfworld"), ("rw0", "scienceworld"), ("rw1", "alfworld")]
    h = json.loads((tmp_path / "runs" / "rewrite" / "history.json").read_text())
    assert h[1]["round"] == 1 and h[1]["why"] == "the series stopped while its card was scored"
    assert "rw1's next run not started: spent 0.9500 of the series' 1.2000 USD, and it may take up to 0.4500" in h[-1]["stopped"]
    assert h[-1]["spent"] == 0.95
    se = rewrite.Series("script:/dev/null", 1.0, 0.5, tmp_path / "s")
    assert se.headroom() == 0.10 and se.headroom([{"usd": 0.04}]) == 0.10       # the floor
    assert se.headroom([{"usd": 0.2}]) == pytest.approx(0.30) and se.headroom([{"usd": 0.45}]) == 0.5   # never above --budget
    with pytest.raises(SystemExit):                          # a paid brain without a series cap is refused
        rewrite.main(["--skill", str(skill), "--brain", "openrouter/x/y", "--budget", "0.5", "--runs", str(tmp_path / "r2")])


slow = pytest.mark.skipif(not (os.environ.get("ALFWORLD_DATA") and os.environ.get("METIS_POLICY_SLOW")),
                          reason="ALFWorld and METIS_POLICY_SLOW=1 (two scorecard variants, ~20 minutes)")


@slow
def test_one_rewrite_round_scores_the_edited_skill(tmp_path):
    script = HERE / "rewrite-script.jsonl"
    rc = rewrite.main(["--skill", str(HERE.parent / "skills" / "hierarchy.md"), "--rounds", "1", "--worlds", "alfworld",
                       "--seeds", "1", "--brain", "script:%s" % script, "--heldout", "2", "--runs", str(tmp_path),
                       "--set", "exploit_episodes=10", "--set", "explore_steps=25"])
    assert rc == 0
    h = json.loads((tmp_path / "rewrite" / "history.json").read_text())
    assert [x["round"] for x in h] == [0, 1] and h[1]["card"]["variant"] == "rw1" and "why" in h[1]
    assert "+0. Read the record's facts" in h[1]["diff"]
    assert (tmp_path / "rw0" / "scorecard.json").exists() and (tmp_path / "rw1" / "scorecard.json").exists()


def test_a_killed_run_is_said_so(tmp_path, monkeypatch):
    """opus's step 1 review N2: a driver killed before it wrote its end (the 6G scope's OOM) is
    `killed` on the card, not `running`."""
    from types import SimpleNamespace
    from policy import scorecard
    d = tmp_path / "v" / "alfworld-s1" / "state"
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"phase": "explore", "status": "running", "proposals": 3, "accepted": 0}))
    rcs = iter([137, 1, 1])
    monkeypatch.setattr(scorecard, "run", lambda cmd, timeout: (next(rcs), "", "", 1.0))
    a = SimpleNamespace(brain="script:/dev/null", discovery=2, gate_games=2, budget=None, skill=None, set=[], heldout=2, timeout=10)
    assert scorecard.score_one("v", "alfworld", 1, a, tmp_path)["status"] == "killed"


def test_the_cost_tiebreak_never_keeps_fewer_rules():
    # nina's round 1: kept on usd/rule 0.0009 vs 0.0011 while it built 9 rules against 12
    kept = card("k", [row("alfworld", "5/10")], usd=0.0132, rules=12)
    assert rewrite.better(card("c", [row("alfworld", "5/10")], usd=0.0081, rules=9), kept) == (False, "fewer rules built (9 < 12)")
    ok, why = rewrite.better(card("c", [row("alfworld", "5/10")], usd=0.0100, rules=12), kept)
    assert ok and why.startswith("usd/rule")


def test_the_rewrite_call_takes_the_runs_max_tokens(tmp_path):
    # nina's round 3: the rewrite was cut at 2048 and left a stray fence
    from argparse import Namespace
    a = Namespace(brain="script:/dev/null", budget=None, max_tokens=4096)
    assert rewrite.rewrite_brain(a, tmp_path / "r1").max_tokens == 4096
    assert rewrite.rewrite_brain(Namespace(brain="script:/dev/null", budget=None, max_tokens=None), tmp_path / "r2").max_tokens == 2048
