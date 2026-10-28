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
