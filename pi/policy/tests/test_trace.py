"""The driver's trace (policy/tracing.py; trace-replay s-c111ff41): acting.fire says what each firing did and the world gave, with the
loop's behaviour unchanged, and an episode replays from its start with no world; the run's lines keep one order, each witness pointing
at its record, each line naming the base that judged it; a resumed run goes on after what is there."""
import json
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
trace = pytest.importorskip("metis.trace")

from metis.repl import Repl  # noqa: E402
from policy import acting, tracing  # noqa: E402

PROGRAM = """
catalog small 1.
provenance text "a small program for the driver's trace" "2026-11-01".
layers (dyn).
stages (main).
namespace small produce (dyn).
pred ready : small.
pred left : small.
pred right : small.
pred cmd_step : small.
stage main {
  %% I step left when ready.
  step_left [dyn] : ready -o left * cmd_step.
  %% I step right when ready.
  step_right [dyn] : ready -o right * cmd_step.
}
#init ready 1
#steps 20
#seeds 1
"""


class Host:
    done, won = False, False

    def __init__(self):
        self.sent, self.left = [], 3

    def on_event(self, name, args):
        self.sent.append(name)
        self.left -= 1


class World:
    """The world gives the program `ready` again while it has steps left: the input a session's rows do not show."""

    def _before(self, host):
        return {"n": len(host.sent)}

    def _rule_verb(self, name):
        return ("step", {})

    def _after(self, host, pre, name, rv, ev):
        return {"kind": "transition", "command": "cmd_step", "admissible": True, "changed": True}

    def _sync(self, host, counts):
        return (["+ready"] if host.left > 0 else []) + (["-cmd_step"] if counts.get("cmd_step") else [])


@pytest.fixture
def program(tmp_path):
    p = tmp_path / "small.llp"
    p.write_text(PROGRAM)
    return p


def act(program, seed):
    sh = Repl.open(program).shell
    out = acting.new_out("g")
    why = acting.fire(World(), Host(), sh, random.Random(seed), out, 20)
    return out, why


def test_a_firing_says_its_rule_and_what_the_world_gave(program):
    out, why = act(program, 3)
    assert why == "quiet" and out["steps"] == 3 == len(out["firings"]) and out["start"] == {"stage": "main", "counts": {"ready": 1}}
    assert all(f["command"] == "cmd_step" for f in out["firings"])
    assert out["firings"][0]["lines"] == ["-cmd_step", "+ready"] and out["firings"][-1]["lines"] == ["-cmd_step"]


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_an_episode_replays_with_no_world(program, seed):
    out, _ = act(program, seed)
    r = trace.replay_firings(program, out["start"], seed, out["firings"])
    assert r.ok, r.divergence
    assert r.rules == 3


def test_another_seed_is_named_as_the_divergence(program):
    runs = {s: [f["name"] for f in act(program, s)[0]["firings"]] for s in range(1, 9)}
    a = next(s for s in runs if runs[s] != runs[1])
    out, _ = act(program, 1)
    r = trace.replay_firings(program, out["start"], a, out["firings"])
    assert not r.ok and r.divergence["what"] == "fired"


def test_the_runs_lines_keep_one_order_and_name_their_base(tmp_path):
    run = tmp_path / "run"
    (run / "records").mkdir(parents=True)
    t = tracing.RunTrace(run, "w", "f", 1)
    t.witness({"phase": "explore", "game": "g", "t": 1, "command": "c"}, "transitions", "base one", {"game": "g", "commands": ["c"]})
    t.witness({"phase": "heldout", "game": "h", "t": 1, "command": "d"}, "heldout", "base one")
    t.witness({"phase": "exploit", "game": "g", "t": 2, "command": "e"}, "surprises", "base two", {"game": "g", "commands": ["e"]}, at_surprise=True)
    t.episode({"start": {"stage": "main", "counts": {}}, "firings": [{"name": "r", "lines": []}]}, "g", 7, "base two", {"game": "g", "commands": []})
    t.close()
    (head, lines), = tracing.read(run)
    assert head["clock"] == "firing" and [x["k"] for x in lines] == list(range(5))
    assert [x["clock"] for x in lines] == ["witness", "witness", "witness", "episode", "firing"]
    assert [x["rec"] for x in lines[:3]] == [0, 0, 0] and [x["file"] for x in lines[:3]] == ["transitions", "heldout", "surprises"]
    assert lines[0]["base"] != lines[2]["base"] and (run / "trace" / "bases" / ("%s.llp" % lines[2]["base"])).read_text() == "base two"
    assert "checkpoint" not in lines[0] and tracing.checkpoint(run, lines[2]["checkpoint"])["world"]["commands"] == ["e"]
    assert tracing.checkpoint(run, lines[3]["checkpoint"])["world"]["game"] == "g"


def test_every_fifty_witnesses_a_checkpoint(tmp_path):
    run = tmp_path / "run"
    (run / "records").mkdir(parents=True)
    t = tracing.RunTrace(run, "w", "f", 1)
    for i in range(120):
        t.witness({"phase": "explore", "game": "g", "t": i, "command": "c"}, "transitions", "b", {"commands": []})
    t.close()
    (_, lines), = tracing.read(run)
    assert [x["k"] for x in lines if "checkpoint" in x] == [49, 99]


def test_a_resumed_run_goes_on_after_what_is_there(tmp_path):
    run = tmp_path / "run"
    (run / "records").mkdir(parents=True)
    t = tracing.RunTrace(run, "w", "f", 1)
    t.witness({"t": 1}, "transitions", "b")
    t.close()
    (run / "records" / "transitions.jsonl").write_text(json.dumps({"t": 1}) + "\n")
    t = tracing.RunTrace(run, "w", "f", 1)
    t.witness({"t": 2}, "transitions", "b")
    t.close()
    parts = tracing.read(run)
    assert [x["k"] for _, ls in parts for x in ls] == [0, 1] and [x["rec"] for _, ls in parts for x in ls] == [0, 1]


@pytest.mark.skipif(not __import__("os").environ.get("ALFWORLD_DATA"), reason="ALFWorld's games ($ALFWORLD_DATA) and the world's venv")
def test_a_scripted_run_on_a_world_replays_its_episodes(tmp_path):
    from policy.brain import Brain
    from policy.driver import Driver
    run = tmp_path / "run"
    d = Driver(run, Brain("script:%s" % (HERE / "hand-script.jsonl"), run), discovery=2, gate_games=2, cfg={"explore_steps": 25, "exploit_episodes": 10}, out=lambda x: None)
    d.go()
    d.trace.close()
    lines = [x for _, ls in tracing.read(run) for x in ls]
    by = {f: [x for x in lines if x.get("file") == f] for f in ("transitions", "surprises", "heldout")}
    for f, xs in by.items():
        p = run / "records" / ("%s.jsonl" % f)
        recs = [json.loads(x) for x in open(p)] if p.exists() else []
        assert [x["rec"] for x in xs] == list(range(len(recs))), f
        assert all(r.get("command") == x["command"] for r, x in zip(recs, xs))
    episodes = tracing.replay_episodes(run, "alf", tmp_path / "at")
    assert episodes and all(r.ok for r in episodes.values()), {k: r.divergence for k, r in episodes.items() if not r.ok}
    assert sum(r.rules for r in episodes.values()) > 0
