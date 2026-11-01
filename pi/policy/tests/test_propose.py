"""propose (policy/propose.py): the ruling a hand-written pack gets: the verdict is the gate's and the model cannot move it; the document names what decided, says it has no
world, and carries the certificate's lines. The judgement itself is metis-agent's tests/test_trace.py (a repeated rule, a golden, a surprise passed), and the road's and the chair's."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
pytest.importorskip("metis.trace")

from policy import propose as P  # noqa: E402

ACCEPTED = {"member": "planner", "unit": "planner/planner.llp", "rules": ["yield_red"], "verdict": "accepted", "reasons": [], "baseline": True, "pack": {"whole": False, "added": ["yield_red"], "dropped": []},
            "receipt": {"moved": ["planner"], "ei_holds": True, "image": None, "interface": {}},
            "first_enabled": {"k": 120, "rule": "yield_red[Z=z1]", "beside": ["accel"]},
            "first_fired_diff": {"k": 120, "member": "planner", "record": ["accel"], "candidate": ["yield_red[Z=z1]"]},
            "first_out_diff": {"k": 120, "member": "planner", "record": ["accel"], "candidate": []}, "open_loop_after": 120, "members": {"planner": 120, "road_director": 121},
            "rows": [{"k": 120, "member": "planner"}] * 30, "goldens": {"ok": True, "failed": [], "ran": {"planner": 9, "responder": 2}},
            "cases": [{"file": "surprise.yaml", "member": "planner", "at": 120, "before": {"passed": False}, "passed": True, "failures": [], "composition": {"passed": True, "failures": [], "open_loop": False}}]}
REFUSED = dict(ACCEPTED, verdict="refused", reasons=["golden arrive.yaml of planner (arrive, seed 1): fired [] expected [drive]"], goldens={"ok": False, "failed": [{"file": "arrive.yaml"}]})


def test_the_document_says_what_decided_and_that_it_has_no_world():
    t = P.document(ACCEPTED, "agree, with changes: it needs can_stop.", None, 0.0123)
    assert t.startswith("# Ruling: accepted") and "yield_red" in t and "ei_key holds" in t
    assert "First enabled: tick 120, yield_red[Z=z1], beside accel" in t and "First differing output: tick 120" in t and "road_director at 121" in t
    assert "surprise.yaml (planner, tick 120): passes in the package's harness; passes on the composition" in t
    assert "**Closed-loop:** not run. This ruling has no world." in t and "tick 120" in t.split("Open-loop")[1] and "agree, with changes" in t and "0.0123 USD" in t


def test_a_refusal_names_the_golden_whatever_the_model_writes():
    t = P.document(REFUSED, "I would accept this.", None, 0.0)
    assert t.startswith("# Ruling: refused") and "golden arrive.yaml of planner" in t.split("## The receipt")[0]


def test_no_golden_ran_is_said_not_passed_over():
    assert "11 cases (planner 9, responder 2), none broken" in P.document(ACCEPTED, None, None, 0)
    assert "**No golden ran**" in P.document(dict(ACCEPTED, goldens={"ok": True, "failed": [], "ran": {"planner": 0}}), None, None, 0)


def test_a_skipped_family_case_is_listed_not_counted():
    g = {"ok": True, "failed": [], "ran": {"planner": 9}, "skipped": [{"file": "lead_lanes_free.yaml", "member": "planner", "why": "it expects change, which this program does not have"}]}
    t = P.document(dict(ACCEPTED, goldens=g), None, None, 0)
    assert "9 cases (planner 9), none broken" in t and "Skipped, not this consumer's: lead_lanes_free.yaml of planner (it expects change" in t


UNIT = """
% the zone ahead comes too late to stop for at this pace
pred late(zclass) : planner.
pred soft(resp) : planner.      % a soft response
pred other : planner.
"""
LATE = "stage safety {\n  %% Late.\n  brake_late [dyn] : $busy * $late(nextzone) * $soft(R) * now -o ().\n}"


def test_the_ruling_reads_the_declarations_of_what_the_rule_reads():
    d = P.declarations(LATE, {"u.llp": UNIT})
    assert "% the zone ahead comes too late to stop for at this pace\npred late(zclass) : planner." in d
    assert "pred soft(resp) : planner.      % a soft response" in d and "pred other" not in d
    assert "Not declared in the units read: busy, now." in d


def test_the_prompt_says_the_words_and_what_the_rows_after_are():
    class Asked:
        def ask(self, prompt, purpose):
            self.prompt = prompt
            return "words"
    b = Asked()
    P.rule(ACCEPTED, LATE, {"u.llp": UNIT}, b)
    assert "pred late(zclass)" in b.prompt and "RECORDED inputs" in b.prompt and 'never "the world\'s response"' in b.prompt
    assert 'A "golden" is a committed case' in b.prompt and '"consumers"' in b.prompt


def test_the_closed_loop_line_only_when_it_ran():
    assert "record --check` passed" in P.document(ACCEPTED, None, {"cmd": "record --check", "code": 0}, 0)
    assert "failed, exit 3" in P.document(ACCEPTED, None, {"cmd": "x", "code": 3}, 0)
    assert "no model was asked" in P.document(ACCEPTED, None, None, 0)


def test_the_prompt_gives_the_verdict_and_the_evidence_not_the_paths():
    class Asked:
        def ask(self, prompt, purpose):
            self.prompt, self.purpose = prompt, purpose
            return "words"
    b = Asked()
    assert P.rule(ACCEPTED, "stage safety {\n}", {"p.llp": "stage s {\n  accel [dyn] : a -o b.\n}"}, b) == "words"
    assert b.purpose == "ruling" and "The verdict: accepted" in b.prompt and "first_enabled" in b.prompt and "accel [dyn] : a -o b." in b.prompt
    assert '"rows_total": 30' in b.prompt and "competition" in b.prompt
    assert json.loads(json.dumps(P.brief(ACCEPTED)))["receipt"] == {"moved": ["planner"], "ei_holds": True}
