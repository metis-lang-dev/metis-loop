"""policy.card (policy-tuning step 1's runner): the variants interleaved (seed, world, variant) under one series
cap, each variant's card written after every run, the series stopped cleanly before a run that could pass it.
score_one and structural_of are faked: no world, no brain."""
import json

from policy import card, scorecard


def test_the_card_interleaves_and_stops_at_the_series_cap(tmp_path, monkeypatch):
    order = []

    def one(variant, world, seed, a, runs):
        order.append((variant, world, seed, a.skill))
        return {"variant": variant, "world": world, "seed": seed, "usd": 0.30, "rules": 2, "phase": "exploit", "status": "disengaged"}
    monkeypatch.setattr(scorecard, "score_one", one)
    monkeypatch.setattr(scorecard, "structural_of", lambda d, w, a, row: None)
    skill = tmp_path / "s.md"
    skill.write_text("## always\n")
    card.main(["--variant", "fit", "--variant", "fit-skill=%s" % skill, "--worlds", "alfworld,scienceworld", "--seeds", "1,2",
               "--brain", "script:/dev/null", "--budget", "0.50", "--series-budget", "1.0", "--runs", str(tmp_path / "runs")])
    # interleaved by seed, world, variant; the headroom 1.5 × 0.30 = 0.45: after two runs (0.60) the third could pass 1.0
    assert [(v, w, s) for v, w, s, _ in order] == [("fit", "alfworld", 1), ("fit-skill", "alfworld", 1)]
    assert order[0][3] is None and order[1][3] == str(skill.resolve())
    c = json.loads((tmp_path / "runs" / "fit-skill" / "scorecard.json").read_text())
    assert c["variant"] == "fit-skill" and c["usd"] == 0.3 and len(c["rows"]) == 1 and c["skill"] == str(skill.resolve())
