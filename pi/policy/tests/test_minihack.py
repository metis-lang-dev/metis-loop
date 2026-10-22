"""The third world of the policy driver: MiniHack's room family through its adapter. Needs the world's
venv (.worlds/mh: minihack, metispy) and a metis-worlds checkout with gen_level's lifted base
($METIS_MH_WORLD, else the sibling); skipped without them:

    cd metis-loop/pi && …/.worlds/mh/bin/python -m pytest policy/tests/test_minihack.py -q
"""
import os
import random
import subprocess

import pytest

try:
    import minihack  # noqa: F401
    from policy.minihack import MiniHack, empty_base, rules_of
    from policy import measure, prompts
    HAVE = hasattr(__import__("policy.minihack", fromlist=["_world"])._world()[1], "base_source") or "gen_level has no base_source"
except (Exception, SystemExit) as e:  # noqa: BLE001 — the reason says which: the world's venv, the checkout, the import
    HAVE = "%s: %s" % (type(e).__name__, e)
pytestmark = pytest.mark.skipif(HAVE is not True, reason="no MiniHack world here (%s)" % HAVE)

MOVE = """  %% I step {D}.
  move [dyn] : agent_at(C) * $next(C, D, C2) * floor(C2) -o agent_at(C2) * floor(C2)."""


def tree_with(tmp_path, base):
    tree = tmp_path / "trees" / "current"
    (tree / "base").mkdir(parents=True, exist_ok=True)
    (tree / "base" / "mh.llp").write_text(base)
    return tree


def test_the_empty_base_has_the_perception_and_no_rule():
    text = empty_base("mh")
    assert rules_of(text) == [] and "pred agent_at(cell) : mh." in text and "bwd next(cell, dir, cell)." in text
    assert "type cell" not in text and "stage act {" in text           # the level's types are the instance's


def test_a_level_over_the_empty_base(tmp_path):
    tree = tree_with(tmp_path, empty_base("mh"))
    g = MiniHack.sample("discovery", "room_quiet", 1, seed=1)[0]
    w = MiniHack(g, tree)
    text = w.instance_text()
    assert w.iid.startswith("room_") and w.iid.endswith("_s1") and 'include "../base/mh.llp"' in text and "next(c0_0, e, c1_0)." in text
    if os.environ.get("METISC"):
        out = subprocess.run([os.environ["METISC"], "--diagnostics-json", str(w.path)], capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stdout[-300:] + out.stderr[-200:]
    w.open()
    try:
        w.reset()
        acts = w.actions()
        assert {a["verb"] for a in acts} == {"move", "open", "kick", "apply", "pickup", "eat", "down", "wait", "search"} and len(acts) == 37
        bad = w.unadmissible(random.Random(1), 4)
        assert bad
        for c in bad:                                            # the perception says no: the world changes nothing
            rec = w.step(c)
            assert not rec["admissible"] and rec["added"] == [] and rec["removed"] == []
        at = next(a for a in w.reading() if a.startswith("agent_at("))
        mv = next(a for a in acts if a["verb"] == "move" and a["command"] not in bad and
                  any(l.startswith("next(%s, %s," % (at[9:-1], a["args"]["D"])) for l in text.splitlines()))
        rec = w.step(mv["command"])
        assert rec["admissible"] and at in rec["removed"] and any(x.startswith("agent_at(") for x in rec["added"])
        assert all(not x.startswith(("hp(1", "hp(2")) for x in rec["after"])             # hp(nN): the base's num values
        snap = w.snapshot()
        w.restore(snap)
        assert w.commands == snap["commands"] and next(a for a in w.reading() if a.startswith("agent_at(")) == next(
            x for x in rec["after"] if x.startswith("agent_at("))
        dyn, commands, verbs = MiniHack.vocabulary()
        assert "agent_at" in dyn and "turn" not in dyn and commands["move"] == ("move", "D") and verbs is commands
        facts = MiniHack.task_facts(text)
        assert all(f.startswith("stairs_down(") for f in facts) and (facts or g[0][3] == "closed")   # behind a door: not in sight
        prompts.set_world(MiniHack)
        assert "next(C, D, C2)" in prompts.LANGUAGE and len(MiniHack.statics_for(rec, text)) <= 8
    finally:
        prompts.set_world(type("Alf", (), {}))                   # back to the defaults (ALFWorld's words)
        w.close()
    ep = w.act(tree, steps=5)                                    # the empty base: no rule fires, nothing sent
    assert ep["commands"] == [] and not ep["won"] and ep["steps"] == 0


def test_a_move_rule_predicts_a_step_and_its_refusal(tmp_path):
    """The predictor over the lifted base: a move rule reading the grid predicts the taken steps, and a
    refused move off the level (no next fact) as no event applying; the kernel acting sends moves. The
    first step shows what the agent stood on (the arrival stairs up): terrain the perception REVEALS,
    which a rule is not judged on (UNCOMPARED) — judged on it, no move rule fits that step."""
    empty = empty_base("mh")
    base = empty.replace("stage act {\n}", "stage act {\n" + MOVE + "\n}")
    tree = tree_with(tmp_path, base)
    g = MiniHack.sample("discovery", "room_quiet", 1, seed=1)[0]
    w = MiniHack(g, tree)
    dyn, commands, verbs = MiniHack.vocabulary()
    p = measure.Predictor(tree, {w.iid: w}, dyn, commands, verbs, MiniHack.UNCOMPARED)
    strict = measure.Predictor(tree, {w.iid: w}, dyn, commands, verbs)
    assert p.compiles(w.iid) is None
    w.open()
    try:
        w.reset()
        bads = w.unadmissible(random.Random(3), 12)
        refused = w.step(next((c for c in bads if c.startswith("cmd_move(")), bads[0]))     # a move off the level or into a wall, if any
        floor = lambda: {a[6:-1] for a in w.reading() if a.startswith("floor(")}  # noqa: E731
        taken = []
        for _ in range(2):
            at = next(a for a in w.reading() if a.startswith("agent_at("))[9:-1]
            d = next(l.split(",")[1].strip() for l in w.instance_text().splitlines()
                     if l.startswith("next(%s," % at) and l.split(",")[2].strip(" ).") in floor())
            taken.append(w.step("cmd_move(%s)" % d))
    finally:
        w.close()
    assert p.predicts(dict(refused, game=w.iid)) and all(t["admissible"] and p.predicts(dict(t, game=w.iid)) for t in taken)
    assert any(a.startswith("stairs_up(") for a in taken[0]["added"]) and not strict.predicts(dict(taken[0], game=w.iid))
    ep = w.act(tree, steps=6, seed=1)
    assert ep["commands"] and all(c.startswith("cmd_move(") for c in ep["commands"]) and ep["refused"] == 0
