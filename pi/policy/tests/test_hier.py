"""The refactoring moves (loop-policy step 2b, pi/policy/hier.py): prune, split, the conventions, the
director. The unit tests read texts only; the run (ALFWorld, skipped without it) takes the base the
loop built from the empty domain in step 2's dry run (fixtures/built-base.llp) through the refactor
phase with a scripted conventions answer (conventions-script.jsonl): the prune refused by the
likelihood, the split by verb accepted (the replay the same, the vector far down), the conventions
accepted (the records replay), the director generated from the ports accepted (it replays the manual
switch), and the director's hierarchy wins the held-out games."""
import json
import os
import shutil
from pathlib import Path

import pytest

from policy import hier

HERE = Path(__file__).resolve().parent
BUILT = (HERE / "fixtures" / "built-base.llp").read_text()
DYN = {"at", "objat", "inrecep", "opened", "closed", "holds", "holding", "handsfree", "checked"}


class World:
    """The ALFWorld adapter's vocabulary, without the world (the unit tests read texts only)."""
    DOMAINS = {"go": "nav", "open": "access", "take": "grasp", "put": "place"}
    COMMANDS = {"go": ("go", "L2", "R"), "go_obj": ("go", "L2", "O"), "go_target": ("go", "L2", "R"), "open_obj": ("open", "R"),
                "open_target": ("open", "R"), "open_closed": ("open", "R"), "take_open": ("take", "O", "R"),
                "take_plain": ("take", "O", "R"), "put_open": ("put", "O", "R"), "put_plain": ("put", "O", "R")}

    @classmethod
    def vocabulary(cls):
        return DYN, cls.COMMANDS, None


def test_the_rules_nothing_can_enable_are_found_by_a_fixpoint():
    """`go` and `open_closed` need `explore`, which only they produce: never firing (F6)."""
    assert sorted(hier.never_firing(BUILT, DYN)) == ["go", "open_closed"]


def test_the_split_by_verb_its_ports_and_its_ambiguity():
    sp = hier.split_by_verb(BUILT, World)
    assert sp.model == ["go", "open_closed"]                       # kept as the world model, out of the hierarchy
    assert sp.domains["task"] == ["choose", "here_target"] and sp.domains["grasp"] == ["take_plain", "take_open"]
    assert sp.goal["grasp"] == {"tofetch"} and sp.out["grasp"] == {"todeliver"} and sp.finished == {"placed"}
    assert set(sp.ambiguous()["tofetch"]) == {"nav", "access", "grasp"}       # a director cannot route it: the conventions
    text = hier.annotate(BUILT, sp)
    back = hier.Split.of(text, World)
    assert back.domains == sp.domains and back.model == sp.model
    assert "% @grasp" in next(l for l in text.splitlines() if l.strip().startswith("take_open"))
    assert "take_open" not in back.base_of("nav") and "go_obj" in back.base_of("nav")


def test_the_director_is_written_from_the_ports():
    from policy.brain import block_of, splice
    conv = json.loads((HERE / "conventions-script.jsonl").read_text().splitlines()[0])["text"]
    text = splice(hier.annotate(BUILT, hier.split_by_verb(BUILT, World)), block_of(conv))[0]
    sp = hier.Split.of(text, World)
    assert sp.ambiguous() == {}
    d, kinds = hier.director_text(sp, "director_domain.llp")
    assert "handles(grasp, grab)." in d and "handles(task, got)." in d and "finished(placed)." in d
    assert "planner(task)." in d and "#init inactive(place) 1" in d and "grab" in kinds


def test_an_activation_sees_only_its_goals_things():
    inst = "type object {a1 b1 c1}.\ntype receptacle {r1 r2}.\notype(a1, a_t).\notype(b1, b_t).\nrecat(r1, l1).\n#init inrecep(b1, r1) 1\n#init at(l1) 1\n"
    out = hier.narrow(inst, {"object": {"a1"}})
    assert "type object {a1}." in out and "otype(b1" not in out and "inrecep(b1" not in out and "recat(r1, l1)." in out


live = pytest.mark.skipif(not os.environ.get("ALFWORLD_DATA"), reason="ALFWorld's games ($ALFWORLD_DATA) and the world's venv")


@live
def test_the_built_base_becomes_the_directed_hierarchy(tmp_path):
    from policy.brain import Brain
    from policy.driver import Driver
    run = tmp_path / "run"
    (run / "catalog" / "domains" / "alf").mkdir(parents=True)
    (run / "catalog" / "domains" / "alf" / "alf.llp").write_text(BUILT)
    (run / "catalog" / "domains" / "alf" / "domain.yaml").write_text('program: alf.llp\ndisplay: x\nline: "y"\n')
    out = []
    d = Driver(run, Brain("script:%s" % (HERE / "conventions-script.jsonl"), run), discovery=2, gate_games=2,
               cfg={"exploit_episodes": 2}, out=out.append)
    assert d.go("refactor") == 0
    props = [e for e in d.gate.journal() if e.get("event") == "proposal"]
    verdicts = [(e["domain"], e["verdict"]) for e in props]
    assert verdicts == [("alf", "refuse"), ("alf", "accept"), ("alf", "accept"), ("director", "accept"),
                        ("tree_director", "accept")], verdicts
    prune, split, conv, direct, comp = props
    # step 2c: the gate judges each move by its own gain (metispy 48e091b); policy-tuning-2: the compose move
    assert [e["why"][0] for e in props] == ["move: prune", "move: split", "move: conventions", "move: direct", "move: compose"]
    assert comp["numbers"]["interface"]["errors"] == 0 and comp["numbers"]["replay_identical"]
    # the compose move is judged outside the run's counters: the card's old columns are the driver's before it
    assert d.state["moves"]["compose"] == "accept" and (d.state["proposals"], d.state["accepted"]) == (4, 3)
    assert any(w.startswith("the interface check passes") for w in comp["why"])
    tree = run / "catalog" / "domains"
    assert (tree / "composition.yaml").exists() and (tree / "tick_types.llp").exists()
    assert "gating: program" in (tree / "grasp" / "domain.yaml").read_text()
    assert "$tick__grant(grasp, motion)" in (tree / "grasp_domain.llp").read_text()
    td = (tree / "tree_director" / "tree_director.llp").read_text()
    # the split's sub-goals and results cross between members: the tree director routes them (the routing base in
    # metispy's iface, the role facts from the ports), as the hand ALFWorld tree
    assert 'include "iface/director_domain.llp".' in td and "planner(task)." in td and "handles(grasp, grab)." in td
    # the planner takes a result once its world copy shows the result's effect (no re-plan on a latched reading)
    assert "near(O) * $at(L2_w) * $objat(O, L2_w) -o tofetch(O)" in (tree / "task_domain.llp").read_text()
    assert conv["numbers"]["ambiguous"]["after"] < conv["numbers"]["ambiguous"]["before"]
    assert conv["numbers"]["vector"]["after"] <= conv["numbers"]["flat"] and direct["numbers"]["ambiguous"]["after"] == 0
    assert prune["numbers"]["likelihood"] < 0                                 # the never-firing rules carry the world model
    assert split["numbers"]["replay_identical"] and split["numbers"]["vector"]["after"] < split["numbers"]["vector"]["before"] / 5
    assert conv["numbers"]["replay_identical"] and direct["numbers"]["replay_identical"]
    # nina's R2: a move journals no call; the conventions, the brain's call whose lines were judged
    logged = [json.loads(l) for l in (run / "run.log.jsonl").read_text().splitlines() if '"proposal"' in l]
    calls = [e.get("call") for e in logged if e.get("event") == "proposal"]
    prompts = (run / "prompts.jsonl").read_text().splitlines()
    assert calls[0] is None and calls[1] is None and calls[3] is None and calls[4] is None and json.loads(prompts[calls[2] - 1])["purpose"] == "conventions"
    assert (run / "catalog" / "domains" / "director" / "director.llp").exists()
    assert d.evaluate("heldout", 2, "director") == 0
    ev = json.loads((run / "records" / "evaluate-heldout-director.json").read_text())
    assert ev["won"] == 2 and all(b > 0 for b in ev["beats"])
