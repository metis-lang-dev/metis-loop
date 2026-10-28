"""The compose move's product and its card (policy-tuning-2 s-e075f47f step 1, brief v2 §A–§B): the level ports a
brain's ```yaml block declares, the replay reading the records' levels, and the composition card that scores the
loop's product and the hand compositions with the same code (the road, the ALFWorld tree; skipped without metisc
or the checkouts beside this one)."""
import os
import random
from pathlib import Path

import pytest

from policy import acting, compose

HERE = Path(__file__).resolve().parent
WS = next((d for d in HERE.parents if (d / "metis-worlds").is_dir()), None)


def test_a_yaml_block_declares_level_ports_and_a_wrong_one_is_dropped():
    answer = """The split, with the place as a level.
```llp
plan_look [dyn] : tofetch(O) * $place_level(R, high) -o seek(O).
```
```yaml
levels: {place_level: {from: {belief: where}, at: [0.3, 0.7], names: [low, mid, high]}}
beliefs: {where: {port: where, one: R}}
nav:
  levels: {near_level: {from: {evaluate: reach}, at: [0.7, 0.3], names: [low, high]}}
ghost: {levels: {}}
```"""
    decl, findings = compose.levels_of(answer, ["task", "nav"], "task")
    assert decl == {"task": {"levels": {"place_level": {"from": {"belief": "where"}, "at": [0.3, 0.7], "names": ["low", "mid", "high"]}},
                             "beliefs": {"where": {"port": "where", "one": "R"}}}}
    assert any("near_level" in f and "rising" in f for f in findings)          # thresholds falling: dropped
    assert any("ghost" in f for f in findings)                                # no such member
    assert compose.levels_of("no block here", ["task"], "task") == ({}, [])


class _Ev:
    def __init__(self, name):
        self.name, self.produce, self.consume = name, {}, {}


class _Shell:
    """Two command events, one after the other (the stub world's program)."""
    def __init__(self):
        self.events_tbl = [(0, "act", _Ev("go_a")), (1, "act", _Ev("go_b"))]
        self.counts, self.left = {}, ["go_a", "go_b"]

    def _candidates(self):
        return [(i, 1.0) for i, (_, _, e) in enumerate(self.events_tbl) if self.left and e.name == self.left[0]]

    def _fire(self, i, ws=None):
        return self.left.pop(0)


class _Host:
    done = won = False

    def __init__(self, levels):
        self.levels = list(levels)

    def on_event(self, name, args):
        pass


class _World:
    def _before(self, host):
        return None

    def _rule_verb(self, name):
        return "go"

    def _command_of(self, host, name):
        return name

    def _after(self, host, pre, name, rv, ev):
        return {"command": name, "admissible": True}

    def _sync(self, host, counts):        # the host's level this step: what a live instrument would say now
        lv = host.levels.pop(0)
        return ["-%s %d" % (a, n) for a, n in counts.items() if a.startswith("risk(")] + ["+risk(%s) 1" % lv]


def test_a_replay_reads_the_recorded_levels_not_the_host():
    acting.LEVEL_PREDS = {"risk"}
    try:
        rec = {"steps": 0, "transitions": [], "commands": [], "refused": 0}
        acting.fire(_World(), _Host(["low", "high"]), _Shell(), random.Random(1), rec, 5)
        assert [t["levels"] for t in rec["transitions"]] == [{"risk(low)": 1}, {"risk(high)": 1}]
        guide = acting.Guide.of(rec)
        assert list(guide) == ["go_a", "go_b"] and guide.levels == [{"risk(low)": 1}, {"risk(high)": 1}]
        out, sh = {"steps": 0, "transitions": [], "commands": [], "refused": 0}, _Shell()
        acting.fire(_World(), _Host(["mid", "mid"]), sh, random.Random(1), out, 5, guide=guide)
        assert out["commands"] == ["go_a", "go_b"]
        assert [t["levels"] for t in out["transitions"]] == [{"risk(low)": 1}, {"risk(high)": 1}]   # the records', not mid
    finally:
        acting.LEVEL_PREDS = set()


@pytest.mark.parametrize("rel", ["metis-worlds/road/domains/composition.yaml",
                                 "metis-lang/corpus/iface/alfworld/domains/hier/composition.yaml"])
def test_the_hand_compositions_score_full_marks(rel):
    # the reference compositions through the card's code: interface 0 errors, the generic director, every member that
    # holds a resource gating itself (the road routes nothing; the ALFWorld tree routes its kinds)
    metisc = os.environ.get("METISC")
    if not metisc or WS is None or not (WS / rel).exists():
        pytest.skip("metisc ($METISC) and the checkouts beside this one")
    from metis.catalog import protocol_stub
    card = compose.composition_card(WS / rel, metisc, Path(protocol_stub.__file__).resolve().parent)
    assert card["full_marks"] and card["interface"]["errors"] == 0, card
    assert (card["handles"] > 0) == ("alfworld" in rel)


def test_a_choice_point_shows_what_one_side_alone_offers():
    from policy.parity import compare_choice
    flat = {"choose[O=a]": 1.0, "choose[O=b]": 1.0}
    assert compare_choice(dict(flat), flat)["same"]                                   # an equal distribution
    assert not compare_choice({"choose[O=a]": 1.0, "choose[O=b]": 2.0}, flat)["same"]  # weights differ
    r = compare_choice({"choose[O=a]": 1.0, "choose[O=b]": 1.0}, dict(flat, **{"look[R=r1]": 1.0}))
    assert not r["same"] and r["flat_only"] == {"look[R=r1]": 1.0}                    # recorded, not dropped
    r = compare_choice(dict(flat, **{"wait[X=x]": 1.0}), flat)
    assert not r["same"] and r["tree_only"] == {"wait[X=x]": 1.0}
    assert compare_choice(dict(flat, **{"wait[X=x]": 1.0}), flat, gen={"wait"})["same"]   # compose's own rule


def test_splice_keeps_a_level_ports_type_and_weight():
    from policy.brain import splice
    base = "catalog alf 1.\npred want(object) : alf.\nstage act {\n}\n"
    text, info = splice(base, ["type level {low mid high}.", "pred place_level(level, object, receptacle) : alf.",
                               "weight where(O, R) reads {inrecep(O, R)}.", "pred want(object) : alf.",
                               "%% I go and look.", "go_look [dyn] : want(O) * $place_level(mid, O, R) -o want(O)."])
    assert "type level {low mid high}." in text and "weight where(O, R) reads {inrecep(O, R)}." in text
    assert text.count("pred want(object)") == 1 and info["declared"] == ["level", "place_level", "where"]
    assert text.index("type level") < text.index("stage act")


def test_the_view_world_counts_what_a_command_revealed_as_before():
    from policy.alfworld import AlfViewWorld
    before = ["at(loc1)", "holds(mug1)"]
    after = ["at(loc3)", "inrecep(candle2,toilet1)", "objat(candle2,loc3)", "inrecep(mug1,toilet1)", "holds(x9)"]
    # the candle was there (seen on arrival); the mug was held: putting it is an effect, not a sighting
    assert AlfViewWorld.revealed(before, after) == ["inrecep(candle2,toilet1)", "objat(candle2,loc3)"]
    rec = AlfViewWorld._seen_before(AlfViewWorld.__new__(AlfViewWorld), {"before": before, "after": after, "added": sorted(set(after) - set(before))})
    assert "inrecep(candle2,toilet1)" in rec["before"] and "inrecep(candle2,toilet1)" not in rec["added"]
    assert "inrecep(mug1,toilet1)" in rec["added"]


def test_the_conventions_ask_names_the_gates_rule():
    # policy-tuning-2 2b: flash read "rewrite the rules" as a redesign of the action layer (the replay refused it);
    # the ask now names what the gate keeps, as the flat refactoring's does ("Every command … must stay the same")
    from policy import prompts
    p = prompts.conventions("stage act {\n}", ({}, {}), {}, {"want": ["nav", "grasp"]})
    assert "Change only the tokens that make the goal kinds ambiguous (want is taken by nav and grasp)" in p
    assert "Keep every action rule's world facts, left and right, as they are" in p
    assert "the gate replays the records and refuses any changed command" in p


def test_the_conventions_example_changes_only_the_consumers_left_sides():
    # the worked example in the ask (policy-tuning-2 2b): spliced over its own before, each consumer's rule keeps its
    # world facts and its right side, only the goal token it takes changes; the planner's emits are new rules
    import re
    from policy import prompts
    from policy.alfworld import rules_of
    from policy.brain import splice
    p = prompts.conventions("stage act {\n}", ({}, {}), {}, {"want": ["nav", "grasp"]})
    assert prompts.CONVENTIONS_EXAMPLE in p and p.index("An example of the move") < p.index("Change only the tokens")
    before, after = re.findall(r"```llp\n(.*?)```", prompts.CONVENTIONS_EXAMPLE, re.S)
    base = "pred want(object) : alf.\nstage act {\n%s}\n" % before
    text, info = splice(base, after.strip().splitlines())
    old, new = dict(rules_of(base)), dict(rules_of(text))
    assert set(new) - set(old) == {"ask_seek", "ask_get_plain"} and info["declared"] == ["seek", "get"]
    for name in ("go_obj", "take_plain"):
        lo, ro = old[name].split(" -o ")
        ln, rn = new[name].split(" -o ")
        assert rn == ro and ln.replace("seek(O)", "want(O)").replace("get(O)", "want(O)") == lo
