"""The real game's adapter (policy/nethack.py), with the script brain, no model. The parts over the records need only the code; the game's
need a seeded build of metis-worlds minihack/ ($METIS_MH_WORLD) and are skipped without it.

    cd metis-loop/pi && METIS_MH_WORLD=…/minihack/world …/.worlds/mh/bin/python -m pytest policy/tests/test_nethack.py -q"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from policy import driver, measure, minihack, nethack

HERE = Path(__file__).resolve().parent


def seeded():
    try:
        world = minihack.world_dir()
    except SystemExit:
        return False
    build = world.parent / "nethack" / "build.sh"
    return "NETHACK_SEED" in build.read_text() and os.access(world.parent / ".nethack" / "install" / "games" / "nethack", os.X_OK)


GAME = pytest.mark.skipif(not seeded(), reason="no seeded game: METIS_MH_WORLD on a minihack/ with nethack/build.sh run")


def test_a_monsters_step_is_the_worlds_and_not_judged():
    before = ["agent_at(c5_5)", "door(c6_5,closed)", "door(c20_5,closed)", "holds(dagger)", "hp(n16)", "monster(newt,c9_9)"]
    after = ["agent_at(c5_5)", "door(c6_5,open)", "door(c20_5,closed)", "door(c30_3,open)", "holds(dagger)", "hp(n14)", "monster(newt,c8_8)"]
    own = nethack.own_record(before, after)
    assert own["world_moved"]
    assert "door(c6_5,open)" in own["own_after"] and "door(c6_5,closed)" in own["own_before"]
    assert not any("c20_5" in a or "c30_3" in a or "monster" in a or "hp" in a for a in own["own_before"] + own["own_after"])
    assert "door(c6_5,open)" in own["judged"] and "monster(newt,c9_9)" in own["judged"] and "door(c30_3,open)" not in own["judged"]
    assert not nethack.own_record(["agent_at(c5_5)"], ["agent_at(c6_5)"])["world_moved"]


def test_down_on_the_stairs_and_off_them_are_two_states():
    on = nethack.own_record(["agent_at(c5_5)", "stairs_down(c5_5)"], ["agent_at(c5_5)", "stairs_down(c5_5)"])
    off = nethack.own_record(["agent_at(c5_5)", "stairs_down(c9_9)"], ["agent_at(c5_5)", "stairs_down(c9_9)"])
    assert on["own_before"] == ["agent_at(c5_5)", "stairs_down(c5_5)"] and off["own_before"] == ["agent_at(c5_5)"]


def test_a_rule_may_need_a_monster_and_is_not_judged_on_one():
    """The ruling on step 0's Q2: monster and hp stay in the vocabulary, a rule's needs read them; only the compare leaves them out."""
    vocabulary = {"agent_at", "monster", "hp", "door", "holds", "obj"}
    assert {"monster", "hp"} <= vocabulary and {"monster", "hp"} <= set(nethack.UNCOMPARED)
    p = measure.Predictor(None, {}, vocabulary, nethack.COMMANDS, nethack.COMMANDS, nethack.UNCOMPARED)
    assert p._cmp(["agent_at(c1_1)", "monster(newt,c2_2)", "hp(n3)"]) == {"agent_at(c1_1)"}


def test_the_same_command_with_the_world_moving_is_no_missing_fact():
    """Out of vocabulary, on the hero's own facts; a record where the world moved is no evidence."""
    rec = lambda t, before, after, moved=False: {"game": "g", "t": t, "command": "cmd_move(e)", "before": ["turn(%d)" % t], "after": [], "added": [],
                                                  "own_before": before, "own_after": after, "world_moved": moved}

    class Run:
        def __init__(self, records):
            self.records = records

        def transitions(self):
            return self.records

    check = driver.Driver.check_vocabulary
    check(Run([rec(1, ["agent_at(c1_1)"], ["agent_at(c2_1)"])]), rec(2, ["agent_at(c1_1)"], ["agent_at(c1_1)"], moved=True))
    with pytest.raises(driver.Disengage):
        check(Run([rec(1, ["agent_at(c1_1)"], ["agent_at(c2_1)"])]), rec(2, ["agent_at(c1_1)"], ["agent_at(c1_1)"]))


def test_a_name_new_to_an_open_session_stays_out_of_it(tmp_path):
    names = tmp_path / "names.json"
    nethack.names_seen(str(names), {"monster(jackal,c1_1)": 1, "holds(dagger)": 1, "hp(n3)": 1})
    have = json.loads(names.read_text())
    assert "jackal" in have["beast"] and "dagger" in have["thing"]
    assert nethack.session_names("\n".join(nethack.type_lines(str(names))))["beast"] == {"jackal", "newt"}
    w = nethack.NetHack.__new__(nethack.NetHack)
    w.session = {"thing": {"dagger"}, "beast": {"newt"}, "trapkind": set()}

    class Host:
        def tick(self, counts):
            return ["+monster(jackal,c1_1) 1", "+monster(newt,c1_2) 1", "-agent_at(c0_0) 1"]
    assert w._sync(Host(), {}) == ["+monster(newt,c1_2) 1", "-agent_at(c0_0) 1"]


def test_the_stairs_and_what_lies_under_the_hero_stay_read():
    Host = nethack.host_class() if seeded() else None
    if Host is None:
        pytest.skip("no world")
    h = Host.__new__(Host)
    h.atoms = {"agent_at(c5_5)"}
    h.carry({"stairs_down(c5_5)", "obj(apple,c5_5)", "obj(rock,c9_9)", "door(c5_5,open)"}, {"events": []})
    assert {"stairs_down(c5_5)", "obj(apple,c5_5)", "door(c5_5,open)"} <= h.atoms and "obj(rock,c9_9)" not in h.atoms
    h.atoms = {"agent_at(c5_5)"}
    h.carry({"obj(apple,c5_5)"}, {"events": ["said(picked)"]})
    assert "obj(apple,c5_5)" not in h.atoms


# nina's review of step 2 (reviews/step2-review-cases.py): the cases that pinned each defect, now saying what is right
VOC = {"agent_at", "floor", "wall", "door", "corridor", "stairs_down", "stairs_up", "obj", "monster", "trap", "unknown", "hp", "holds"}
MOVE = {"move": [("move[D=e]", "move", {"D": "e"}, {"agent_at(c5_5)": 1}, {"agent_at(c5_5)": 1}, {"agent_at(c6_5)": 1})]}
OPEN = {"open": [("open[D=e]", "open", {"D": "e"}, {"door(c6_5,closed)": 1}, {"door(c6_5,closed)": 1}, {"door(c6_5,open)": 1})]}


def pred(table):
    p = measure.Predictor(None, {}, VOC, nethack.COMMANDS, nethack.COMMANDS, nethack.UNCOMPARED)
    p.table = lambda game: table
    return p


def rec(cmd, verb, args, before, after, admissible=True, t=1, events=()):
    return dict({"game": "g", "t": t, "command": cmd, "action": {"verb": verb, "args": args}, "before": before, "after": after, "admissible": admissible, "changed": admissible},
                **nethack.own_record(before, after, events))


def check(*recs):
    class Run:
        def transitions(self):
            return list(recs[:-1])
    driver.Driver.check_vocabulary(Run(), recs[-1])


def test_a_trap_under_the_hero_is_its_own():
    assert "trap(pit,c5_5)" in nethack.own_facts({"agent_at(c5_5)", "trap(pit,c5_5)"}, ["c5_5"])
    assert "trap(pit,c9_9)" not in nethack.own_facts({"agent_at(c5_5)", "trap(pit,c9_9)"}, ["c5_5"])


def test_a_thing_first_seen_is_the_worlds():
    door = rec("cmd_move(e)", "move", {"D": "e"}, ["agent_at(c5_5)", "corridor(c6_5)"], ["agent_at(c6_5)", "corridor(c6_5)", "door(c7_5,closed)"])
    assert "door(c7_5,closed)" not in door["judged"] and pred(MOVE).predicts(door, {"move"}) and not pred(MOVE).contradicted(door, {"move"})
    obj = rec("cmd_move(e)", "move", {"D": "e"}, ["agent_at(c5_5)"], ["agent_at(c6_5)", "obj(apple,c6_5)"])
    assert not pred(MOVE).contradicted(obj, {"move"})
    a = rec("cmd_search", "search", {}, ["agent_at(c5_5)"], ["agent_at(c5_5)"])
    check(a, rec("cmd_search", "search", {}, ["agent_at(c5_5)"], ["agent_at(c5_5)", "door(c6_5,closed)"], t=2))


def test_a_things_change_where_the_before_had_it_is_the_heros():
    opened = rec("cmd_open(e)", "open", {"D": "e"}, ["agent_at(c5_5)", "door(c6_5,closed)"], ["agent_at(c5_5)", "door(c6_5,open)"])
    assert opened["added"] == ["door(c6_5,open)"] and opened["removed"] == ["door(c6_5,closed)"] and pred(OPEN).predicts(opened, {"open"})
    took = rec("cmd_pickup", "pickup", {}, ["agent_at(c5_5)", "obj(apple,c5_5)"], ["agent_at(c5_5)", "holds(apple)"])
    assert took["added"] == ["holds(apple)"] and took["removed"] == ["obj(apple,c5_5)"]


def test_one_before_has_one_own_before():
    b4 = ["agent_at(c5_5)", "door(c7_5,closed)"]
    assert nethack.own_record(b4, ["agent_at(c6_5)", "door(c7_5,closed)"])["own_before"] == nethack.own_record(b4, b4)["own_before"]
    went = nethack.own_record(b4, ["agent_at(c6_5)", "door(c7_5,closed)"])
    assert "door(c7_5,closed)" in went["judged"] and went["added"] == ["agent_at(c6_5)"]    # walking away moved no door


def test_added_and_removed_are_the_heros_own():
    r = rec("cmd_wait", "wait", {}, ["agent_at(c5_5)", "turn(n1)", "floor(c1_1)", "monster(newt,c9_9)"], ["agent_at(c5_5)", "turn(n2)", "floor(c1_2)", "monster(newt,c8_8)"])
    assert r["added"] == [] and r["removed"] == [] and r["world_moved"]


def test_the_repair_turn_reads_what_the_gate_judges():
    r = rec("cmd_move(e)", "move", {"D": "e"}, ["agent_at(c5_5)"], ["agent_at(c6_5)", "door(c30_3,open)"])
    p = pred(MOVE)
    p.compiles = lambda g: None
    old, measure.new_rules = measure.new_rules, lambda a, b: {"move"}
    try:
        assert "door(c30_3,open)" not in measure.explain(p, "stage act {\n  move [dyn] : agent_at(C) -o agent_at(C).\n}\n", "", r, [])
    finally:
        measure.new_rules = old


def test_the_worlds_dice_judge_no_rule_and_ask_nothing():
    b4 = ["agent_at(c5_5)", "door(c6_5,closed)"]
    stuck = rec("cmd_open(e)", "open", {"D": "e"}, b4, b4, admissible=False, events=["said(door_stuck)"])
    opened = rec("cmd_open(e)", "open", {"D": "e"}, b4, ["agent_at(c5_5)", "door(c6_5,open)"], t=2)
    assert stuck["world_moved"] and not pred(OPEN).contradicted(stuck, {"open"})
    check(stuck, opened)
    still = ["agent_at(c5_5)", "floor(c6_5)", "monster(lichen,c6_5)"]
    miss = rec("cmd_move(e)", "move", {"D": "e"}, still, still, events=["said(hit)"])
    free = rec("cmd_move(e)", "move", {"D": "e"}, ["agent_at(c5_5)", "floor(c6_5)"], ["agent_at(c6_5)", "floor(c6_5)"], t=2)
    assert miss["world_moved"] and not pred(MOVE).contradicted(miss, {"move"})
    check(miss, free)


def test_a_refusal_not_the_worlds_still_judges_a_rule():
    b4 = ["agent_at(c5_5)", "door(c6_5,closed)"]
    locked = rec("cmd_open(e)", "open", {"D": "e"}, b4, b4, admissible=False, events=["said(door_locked)"])
    assert not locked["world_moved"] and pred(OPEN).contradicted(locked, {"open"}) == ["open[D=e]"]


def test_an_exploit_record_without_added_asks_without_a_keyerror():
    a = rec("cmd_move(e)", "move", {"D": "e"}, ["agent_at(c5_5)"], ["agent_at(c6_5)"])
    b = rec("cmd_move(e)", "move", {"D": "e"}, ["agent_at(c5_5)"], ["agent_at(c5_5)"], t=2)
    del a["added"], b["added"]
    with pytest.raises(driver.Disengage):
        check(a, b)


@GAME
def test_a_thing_is_named_by_its_look_on_the_floor_and_in_the_pack():
    Host = nethack.host_class()
    h = Host.__new__(Host)
    h.level = {}
    h.atoms = {"obj(elam_ebow_magic_mapping,c1_1)", "holds(scroll_labeled_elam_ebow)"}
    assert set(h.reading()) == {"obj(elam_ebow,c1_1)", "holds(elam_ebow)"}


@GAME
def test_a_restore_keeps_what_lay_under_the_hero():
    Host = nethack.host_class()
    h = Host.__new__(Host)
    h.level, h.cmap, h.key, h.first_dlvl, h.dlvl = {"replay": {}}, None, None, 1, 1
    screen = {"atoms": ["agent_at(c5_5)", "floor(c5_5)"], "events": [], "message": "", "dlvl": 1}
    h.atoms = {"agent_at(c5_5)", "floor(c5_5)", "obj(apple,c5_5)"}
    snap = {"checkpoint": "start", "keys_since": [], "t": 0, "actions": [], "sign": sorted(h.atoms), "beat": 0, "pending": [], "handed": []}
    h._take(dict(screen, atoms=["agent_at(c5_5)", "floor(c5_5)", "holds(apple)"], events=["said(picked)"]))
    assert "obj(apple,c5_5)" not in h.atoms

    class Gym:
        def call(self, op, **k):
            return {"load": {}, "replay": screen}[op]
    h.gym = Gym()
    h.restore(snap)
    assert "obj(apple,c5_5)" in h.atoms and getattr(h, "divergences", 0) == 0


@GAME
def test_the_game_fights_refuses_and_goes_back_to_a_checkpoint(tmp_path):
    """Seed 1 starts with a jackal to the west: a fight taken with the hero in place, a refusal as such, the world's step marked, a probe
    restored from its checkpoint and going on, the new names kept."""
    tree = tmp_path / "trees" / "current"
    tree.mkdir(parents=True)
    w = nethack.NetHack((1, "dlvl1"), tree)
    try:
        w.open()
        w.reset()
        at = nethack.hero_of(w.reading())
        refused = w.step("cmd_open(n)")
        assert not refused["admissible"] and refused["text"] == "You see no door there."
        fight = w.step("cmd_move(w)")
        assert fight["admissible"] and nethack.hero_of(fight["after"]) == at and "jackal" in fight["text"]
        assert any(a.startswith("monster(jackal") for a in fight["before"])
        assert "jackal" in json.loads(Path(w.names).read_text())["beast"]
        moved = [w.step("cmd_move(w)") for _ in range(3)]
        assert any(r["world_moved"] for r in [fight] + moved)
        snap = json.loads(json.dumps(w.snapshot()))
        here = w.reading()
        for c in ("cmd_search", "cmd_move(e)", "cmd_wait"):
            w.step(c)
        w.restore(snap)
        assert w.reading() == here and w.divergences == 0 and len(w.commands) == len(snap["commands"])
        assert w.step("cmd_search")["admissible"]
    finally:
        w.close()


@GAME
def test_thirty_steps_of_explore_with_the_script(tmp_path):
    """The driver, the real game, the script brain: records written, rules accepted, the ask it ends with explained by the script."""
    run = tmp_path / "run"
    env = dict(os.environ, PYTHONPATH=str(HERE.parent.parent))
    p = subprocess.run([sys.executable, "-m", "policy.driver", "--run", str(run), "--world", "nethack", "--family", "dlvl1", "--brain", "script:%s" % (HERE / "nethack-script.jsonl"),
                        "--discovery", "1", "--gate-games", "1", "--phase", "explore", "--set", "explore_steps=30"], cwd=HERE.parent.parent, env=env, capture_output=True, text=True, timeout=400)
    assert p.returncode in (0, 3), p.stderr[-800:]
    recs = [json.loads(l) for l in open(run / "records" / "transitions.jsonl")]
    assert len(recs) >= 30 and all("own_before" in r and "judged" in r for r in recs)
    assert any(not r["admissible"] for r in recs) and any(r["admissible"] for r in recs)
    verdicts = [json.loads(l).get("verdict") for l in open(run / "state" / "journal.jsonl")]
    assert "accept" in verdicts
    assert "move" in (run / "catalog" / "domains" / "nh" / "nh.llp").read_text() or "wait" in (run / "catalog" / "domains" / "nh" / "nh.llp").read_text()
