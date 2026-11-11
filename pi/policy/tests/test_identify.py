"""identify (policy/identify.py, EXPERIMENT loop-identify s-5e34eb35): what a record identifies of a pack before it is judged. Synthetic evidence in the judge's
shape (metis_agent.trace.fired_diff: baseline, member, rules, rows [{k, member, fired: {record, candidate}}], first_enabled {k, rule, beside}, open_loop_after),
a record {k} or {k0, k1}; no metis-agent needed."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from policy import identify as I  # noqa: E402

UNIT = """
pred handsfree : alf.
  begin [dyn] : start * $at(L) -o want(O) * seeking.
  take_open [dyn] : want(O) * $at(L) * $recat(R, L) * inrecep(O, R) * objat(O, L) * handsfree * $openable(R) * $opened(R) -o carrying * seeking * holds(O) * holding.
  take_plain [dyn] : want(O) * $at(L) * $recat(R, L) * inrecep(O, R) * objat(O, L) * handsfree * $notopenable(R) -o carrying * seeking * holds(O) * holding.
  go_obj [dyn] : want(O) * at(L) * $objat(O, L2) * L <> L2 * $handsfree -o want(O) * at(L2).
"""


def row(k, record=("take_open",), candidate=(), member="planner"):
    return {"k": k, "member": member, "fired": {"record": list(record), "candidate": list(candidate)}}


def ev(rows=(), enabled=None, **kw):
    e = {"baseline": True, "member": "planner", "rules": ["take_open"], "rows": list(rows), "first_enabled": enabled, "open_loop_after": rows[0]["k"] if rows else None}
    e.update(kw)
    return e


EN = {"k": 40, "rule": "take_open[O=apple]", "beside": ["go_obj"]}


def line(i, head):
    return next((x for x in i["lines"] if x.startswith(head)), None)


# target ------------------------------------------------------------------------------------------------------------------------------------------------

def test_a_row_at_the_surprises_tick_is_a_target():
    i = I.identification(ev([row(40)], EN), {"k": 40}, "")
    assert i["target"] == [40] and i["earlier"] == [] and i["word"] == "identified"
    assert line(i, "TARGET: yes. At tick 40") and "the record take_open, the candidate nothing" in line(i, "TARGET")


def test_a_window_counts_every_tick_in_it():
    i = I.identification(ev([row(41), row(43), row(50)], EN), {"k0": 40, "k1": 45}, "")
    assert i["target"] == [41, 43] and "At ticks 40..45" in line(i, "TARGET")


def test_no_row_at_the_tick_is_not_identified():
    i = I.identification(ev([row(55)], EN), {"k": 40}, "")
    assert i["target"] == [] and i["word"] == "not identified"
    assert line(i, "TARGET: NO. At tick 40") and "first difference is at tick 55" in line(i, "TARGET")


def test_the_first_difference_named_is_the_earliest_whatever_the_rows_order():
    i = I.identification(ev([row(60), row(55)], EN), {"k": 40}, "")
    assert "first difference is at tick 55" in line(i, "TARGET")


def test_another_members_rows_are_not_this_packs_target():
    i = I.identification(ev([row(40, member="road_director"), row(55)], EN), {"k": 40}, "")
    assert i["target"] == [] and i["word"] == "not identified"


def test_a_record_with_no_tick_is_target_unknown_and_never_identified():
    i = I.identification(ev([row(40)], EN), {}, "")
    assert line(i, "TARGET: unknown") and i["target"] == [] and i["word"] != "identified"


# earlier -----------------------------------------------------------------------------------------------------------------------------------------------

def test_a_row_before_the_tick_is_earlier_and_identified_in_part():
    i = I.identification(ev([row(12), row(40)], EN), {"k": 40}, "")
    assert i["earlier"] == [12] and i["target"] == [40] and i["word"] == "identified in part"
    assert line(i, "EARLIER: the candidate also changes 1 tick(s)") and "tick 12" in line(i, "EARLIER")


def test_only_earlier_rows_are_still_not_identified():
    i = I.identification(ev([row(12)], EN), {"k": 40}, "")
    assert i["earlier"] == [12] and i["word"] == "not identified" and line(i, "EARLIER")


# support -----------------------------------------------------------------------------------------------------------------------------------------------

def test_support_names_the_rule_and_where_it_is_enabled():
    i = I.identification(ev([row(40)], EN), {"k": 40}, "")
    assert line(i, "SUPPORT: take_open[O=apple] is enabled on this record from tick 40, beside go_obj.")


def test_enabled_but_never_changing_what_fires_is_said():
    i = I.identification(ev([], EN), {"k": 40}, "")
    assert "enabled is not fired" in line(i, "SUPPORT")


def test_no_support_with_a_target_row_says_only_what_the_pack_stops():
    i = I.identification(ev([row(40)], None, reads_absent=["opened"]), {"k": 40}, "")
    s = line(i, "SUPPORT: none.")
    assert s and "take_open is never enabled on this record" in s and "only what the pack STOPS at tick 40" in s
    assert line(i, "  It reads opened, which no tick of this record holds.")


def test_no_support_and_no_target_row_says_the_record_says_nothing():
    i = I.identification(ev([], None, rules=["a", "b"]), {"k": 40}, "")
    s = line(i, "SUPPORT: none.")
    assert s and "a, b are never enabled" in s and "this record says nothing of the pack" in s and i["word"] == "not identified"


# consumes ----------------------------------------------------------------------------------------------------------------------------------------------

def test_a_replaced_rule_that_now_consumes_handsfree_is_reported():
    pack = "drop begin.\n  begin [dyn] : start * $at(L) * handsfree -o want(O) * seeking.\n"
    c = I.consumes_more(pack, UNIT)
    assert c == [{"rule": "begin", "atom": "handsfree", "needed_by": ["go_obj", "take_open", "take_plain"]}]
    i = I.identification(ev([row(40)], EN), {"k": 40}, pack, UNIT)
    assert i["word"] == "identified in part" and line(i, "CONSUMES: begin now consumes handsfree")


def test_the_same_rule_reading_handsfree_is_not_reported():
    pack = "drop begin.\n  begin [dyn] : start * $at(L) * $handsfree -o want(O) * seeking.\n"
    assert I.consumes_more(pack, UNIT) == []
    assert I.identification(ev([row(40)], EN), {"k": 40}, pack, UNIT)["word"] == "identified"


def test_consuming_and_making_again_is_not_a_loss():
    pack = "drop begin.\n  begin [dyn] : start * $at(L) * handsfree -o want(O) * seeking * handsfree.\n"
    assert I.consumes_more(pack, UNIT) == []


def test_a_new_rule_consuming_a_token_the_units_rules_consume_is_not_reported():
    pack = "  grab [dyn] : want(O) * $at(L) * $handsfree -o holds(O).\n"
    assert I.consumes_more(pack, UNIT) == []


def test_a_new_rule_consuming_what_no_rule_consumes_but_others_read_is_reported():
    pack = "  shut [dyn] : $want(O) * opened(R) -o closed(R).\n"         # opened: every rule of the unit reads it, none consumes it
    assert I.consumes_more(pack, UNIT) == [{"rule": "shut", "atom": "opened", "needed_by": ["take_open"]}]
    pack = "  rest [dyn] : at(L) * $handsfree -o resting.\n"            # at: go_obj already consumes it, so no new loss
    assert I.consumes_more(pack, UNIT) == []


# nothing identified ------------------------------------------------------------------------------------------------------------------------------------

def test_a_pack_that_does_not_reach_the_replay_identifies_nothing():
    for e in (ev([row(40)], EN, gate_error="lint: x"), ev([row(40)], EN, link_failed=True), ev([row(40)], EN, duplicates=["take_open"]),
              {"baseline": True, "member": "planner", "rules": ["take_open"]}, {"baseline": False, "divergence": {"k": 3}}):
        i = I.identification(e, {"k": 40}, "")
        assert i["word"] == "nothing identified", e
        assert i["target"] == [] and i["earlier"] == [] and i["support"] is None and i["consumes"] == []      # the same keys as an identification
        assert "nothing is identified" in I.text(i)


def test_the_text_heads_with_the_word():
    t = I.text(I.identification(ev([row(40)], EN, open_loop_after=40), {"k": 40}, ""))
    assert t.startswith("## What this record identifies: identified\n- TARGET: yes") and "first differing output (tick 40)" in t
