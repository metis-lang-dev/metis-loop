"""The row refactor-from-scripted (policy-tuning-2 s-e075f47f step 2b): a run that starts at the refactor phase from
another run's accepted state — its base, records and level ports handed over, the counters and the meter its own."""
import json

import pytest

from policy.driver import handover


def _src(d, **state):
    (d / "catalog" / "domains" / "alf").mkdir(parents=True)
    (d / "catalog" / "domains" / "alf" / "alf.llp").write_text("catalog alf 1.\n")
    (d / "records").mkdir()
    (d / "records" / "transitions.jsonl").write_text("{}\n")
    (d / "records" / "evaluate-heldout.json").write_text("{}")
    (d / "state").mkdir()
    st = dict({"phase": "exploit", "status": "done", "proposals": 8, "accepted": 7, "seed": 1, "world": "alfworld",
               "family": "pick_and_place_simple", "discovery": 2, "gate_games": 2, "spend_cap": None,
               "levels": {"alf": {"levels": {"place_level": {}}}}, "refactored_at": "abc"}, **state)
    (d / "state" / "run.json").write_text(json.dumps(st))
    return d


def test_a_run_starts_at_refactor_from_the_scripted_state(tmp_path):
    src, run = _src(tmp_path / "src"), tmp_path / "run"
    handover(src, run, skill=None)
    st = json.loads((run / "state" / "run.json").read_text())
    assert st["phase"] == "refactor" and (st["proposals"], st["accepted"]) == (0, 0)          # the brain's alone counted
    assert st["handover"]["accepted"] == 7 and st["levels"] == {"alf": {"levels": {"place_level": {}}}}
    assert "refactored_at" not in st and "spend_cap" not in st                                 # its own marks and meter
    assert (run / "catalog" / "domains" / "alf" / "alf.llp").exists() and (run / "records" / "transitions.jsonl").exists()
    assert not (run / "records" / "evaluate-heldout.json").exists()                           # the source's numbers left
    with pytest.raises(SystemExit, match="has a run already"):
        handover(src, run)


def test_a_source_that_did_not_end_done_is_refused(tmp_path):
    src = _src(tmp_path / "src", status="disengaged", accepted=4)
    with pytest.raises(SystemExit, match="did not end done"):
        handover(src, tmp_path / "run")
