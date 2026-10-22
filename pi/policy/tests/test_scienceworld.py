"""The second world of the policy driver (world-scienceworld step 3): ScienceWorld through its adapter.
Needs the world's venv (.worlds/sw: scienceworld, metispy) and the metis-worlds checkout; skipped
without them:

    cd metis-loop/pi && …/.worlds/sw/bin/python -m pytest policy/tests/test_scienceworld.py -q
"""
import os
import random
import subprocess
from pathlib import Path

import pytest

try:
    import scienceworld  # noqa: F401
    from policy.scienceworld import ScienceWorld, empty_base, rules_of
    HAVE = True
except Exception:  # noqa: BLE001
    HAVE = False
pytestmark = pytest.mark.skipif(not HAVE, reason="no ScienceWorld (the world's venv) or no metis-worlds checkout")


def test_the_empty_base_has_the_perception_and_no_rule():
    text = empty_base("sw")
    assert rules_of(text) == [] and "pred here(thing) : sw." in text and "pred said(said_kind) : sw." in text and "stage act {" in text


def test_a_variation_over_the_empty_base(tmp_path):
    tree = tmp_path / "trees" / "current"
    (tree / "base").mkdir(parents=True)
    (tree / "base" / "sw.llp").write_text(empty_base("sw"))
    g = ScienceWorld.sample("discovery", "conductivity", 1, seed=1)[0]
    w = ScienceWorld(g, tree)
    assert w.iid.startswith("test_conductivity") and 'include "../base/sw.llp"' in w.instance_text()
    assert ScienceWorld(w.game_dir, tree).iid == w.iid                 # the snapshot's name opens the same game
    if os.environ.get("METISC"):
        out = subprocess.run([os.environ["METISC"], "--diagnostics-json", str(w.path)], capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stdout[-300:] + out.stderr[-200:]
    w.open()
    try:
        acts = w.actions()
        verbs = {a["verb"] for a in acts}
        assert "go" in verbs and all(a["command"] in w.host.valid for a in acts)
        go = next(a for a in acts if a["verb"] == "go")
        rec = w.step(go["command"])
        assert rec["kind"] == "transition" and rec["admissible"] and rec["action"]["verb"] == "go" and "here(%s)" % go["args"]["R"] in rec["after"]
        snap = w.snapshot()
        assert snap["commands"] == [go["command"]]
        w.restore(snap)
        assert "here(%s)" % go["args"]["R"] in w.reading()
        bad = w.unadmissible(random.Random(1), 2)
        assert all(b not in w.host.valid for b in bad)
        dyn, commands, verbs_ = ScienceWorld.vocabulary()
        assert "here" in dyn and commands["connect"] == ("connect", "A", "B") and verbs_ is commands
        assert ScienceWorld.task_facts(w.instance_text())[0].startswith("task(conductivity")
    finally:
        w.close()
    ep = w.act(tree, steps=5)                       # the empty base: no rule fires, nothing sent
    assert ep["commands"] == [] and not ep["won"] and ep["steps"] == 0
