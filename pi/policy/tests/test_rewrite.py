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
    d = tmp_path / "v" / "alfworld-s1"
    (d / "state").mkdir(parents=True)
    (d / "state" / "journal.jsonl").write_text(json.dumps({"event": "proposal", "phase": "explore", "domain": "alf", "verdict": "refuse",
                                                           "numbers": {"fits_records": False, "likelihood": 0.0}, "why": ["not: fits"]}) + "\n")
    (d / "prompts.jsonl").write_text(json.dumps({"call": 1, "purpose": "explore", "answer": "go [dyn] : at(L) -o at(L2)."}) + "\n")
    (d / "run.log.jsonl").write_text(json.dumps({"event": "fit-repair", "purpose": "explore", "why": "consumes at(L), which the world keeps"}) + "\n")
    text = rewrite.digest(card("v", [dict(row("alfworld", "0/10"), phase="explore", accepted=0, proposals=1, status="disengaged")]), tmp_path)
    assert "refuse" in text and "the brain's lines: go [dyn]" in text and "fit-repair (explore): consumes at(L)" in text


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
