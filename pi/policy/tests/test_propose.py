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


def test_not_judged_is_no_verdict_and_says_where_it_stopped():
    e = dict(ACCEPTED, verdict="not judged", reasons=["the judgement passed its budget of 280 s in: the goldens on the candidate"], times=[{"stage": "the baseline's replay", "seconds": 110.0}, {"stage": "the goldens on the candidate"}])
    t = P.document(e, None, None, 0)
    assert t.startswith("# Ruling: not judged") and "## Why it is not judged" in t and "budget of 280 s in: the goldens on the candidate" in t
    assert "the baseline's replay 110.0 s" in t


def test_a_value_is_read_beside_its_type():
    unit = "type prio {ego obj same}.\npred zprio(zone, prio) : planner.    % who has the way\ntype zone {z1}.\n"
    d = P.declarations("stage safety {\n  %% Y.\n  yield_it [dyn] : $zprio(nextzone, P) * now -o ().\n}", {"u.llp": unit})
    assert "pred zprio(zone, prio) : planner.    % who has the way" in d and "type prio {ego obj same}." in d and "type zone {z1}." in d


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


def test_loop_sh_does_not_read_a_stdin_nobody_closes(tmp_path):
    """No terminal: the loop must not sit on a pipe left open (a foreground run under a tool's shell hung so)."""
    import os
    import stat
    import subprocess
    import threading
    stub = tmp_path / "stub-pi"
    stub.write_text("#!/bin/sh\ncat\necho read-to-the-end\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, METIS_LOOP_PI=str(stub), METIS_LOOP_SDK_PY=sys.executable, MODEL="stub/stand-in")
    p = subprocess.Popen(["bash", str(HERE.parent.parent / "loop.sh")], cwd=tmp_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    timer = threading.Timer(60, p.kill)      # stdin stays open all the while: only the loop's own redirect lets this end
    timer.start()
    try:
        out = p.stdout.read()
    finally:
        timer.cancel()
        p.stdin.close()
        p.wait()
    assert p.returncode != -9, "loop.sh sat on the open stdin"
    if "read-to-the-end" not in out:
        pytest.skip("loop.sh stopped before pi here: %s" % out[-200:])


def test_a_bad_config_is_refused_in_words_not_a_traceback(tmp_path):
    """The alf drive's L3: a config that is not a service config (a guessed one) crashed load_config with a traceback in
    the tool's reply, then a ruling refused with "the gate: 'v3'". Now: one line, no ruling run."""
    import subprocess
    pytest.importorskip("metis_agent")
    here = Path(__file__).resolve().parents[1] / "propose.py"
    pack = tmp_path / "p.llp"
    pack.write_text("% a pack\n")
    for body, want in (("{not: yaml: [", "does not read as YAML"), ("trace: {}\n", "no v3 section"), (None, "no such file")):
        cfg = tmp_path / "c.yaml"
        if body is None:
            cfg = tmp_path / "missing.yaml"
        else:
            cfg.write_text(body)
        p = subprocess.run([sys.executable, str(here), "--pack", str(pack), "--member", "m", "--trace", str(tmp_path),
                            "--root", str(tmp_path), "--config", str(cfg), "--run", str(tmp_path / "run")],
                           capture_output=True, text=True, timeout=120)
        assert p.returncode != 0 and want in p.stderr, (body, p.stderr[-400:])
        assert "Traceback" not in p.stderr, p.stderr[-400:]



def test_a_member_with_a_weight_port_the_trace_lacks_is_named_unjudged():
    """loop-prompt judge-session: the judge stands the port in and replays the member's recorded choices; the ruling
    says that member's rows are not its evidence, and the brain's evidence keeps the name."""
    t = P.document(dict(ACCEPTED, unjudged=["task"]), None, None, 0)
    assert "**Unjudged:** task declares weight ports the trace does not carry: its choices are the record's" in t
    assert "Unjudged" not in P.document(ACCEPTED, None, None, 0)
    assert P.brief(dict(ACCEPTED, unjudged=["task"]))["unjudged"] == ["task"]


def test_a_ruling_refused_by_the_records_kind_says_the_kind_and_its_route():
    """spec 20 §5 (surprise-kinds s-7a02c2ac): the judge refuses a record that is not structural before the cascade; the ruling says so."""
    e = {"verdict": "refused", "why": "kind", "kind": "probabilistic", "status": "refused", "member": "planner", "inert": False, "times": [],
         "route": "the fold's bounds, a weight, a belief or a sensor parameter; never a rule",
         "reasons": ["the record's kind is probabilistic, not structural: no pack answers it. the fold's bounds, a weight, a belief or a sensor parameter; never a rule"]}
    text = P.document(e, None, None, 0.0)
    assert text.startswith("# Ruling: refused") and "**Kind:** the record is probabilistic, not structural" in text and "never a rule" in text


# loop-improvement step 3 (s-5e34eb35): the identification in the ruling card. Canned evidence, no judge run.
INERT = dict(ACCEPTED, inert=True, first_enabled=None, first_fired_diff=None, first_out_diff=None, open_loop_after=None, members={}, rows=[])
DROP_BEGIN = "stage act {\n  %% a take begins with free hands\n  begin [dyn] : $take(X0) * idle * $handsfree -o busy * tick__active(grasp).\n}\ndrop begin.\n"
GRASP = "stage act {\n  begin [dyn] : $take(X0) * idle -o busy * tick__active(grasp).\n  release [dyn] : busy * $holding -o idle.\n}\n"


def ident(word):
    lines = {"identified": ["TARGET: yes. At tick 7 the candidate does something else than the record."],
             "identified in part": ["TARGET: yes.", "EARLIER: the candidate also changes 1 tick(s) before the surprise."],
             "not identified": ["TARGET: NO. At tick 7 the candidate fires exactly what the record fired."],
             "nothing identified": ["The pack did not reach the replay."]}[word]
    return {"word": word, "target": [7] if "in" not in word or word == "identified in part" else [], "earlier": [], "support": None, "consumes": [], "lines": lines}


@pytest.mark.parametrize("name,e", [("accepted", ACCEPTED), ("inert", INERT), ("refused", REFUSED)])
def test_without_the_surprise_the_document_is_masters_byte_for_byte(name, e):
    """fixtures/ruling-master-<name>.md: master's document() (2ac2341) on the same evidence, the model's words none."""
    want = (HERE / "fixtures" / ("ruling-master-%s.md" % name)).read_text()
    assert P.document(e, None, None, 0.0) == want


@pytest.mark.parametrize("word,header", [("identified", "# Ruling: accepted\n"),
                                         ("identified in part", "# Ruling: accepted (identified in part)\n"),
                                         ("not identified", "# Ruling: accepted (not identified: it does not change the surprise's tick)\n")])
def test_the_three_headers_of_an_accepted_ruling(word, header):
    for e in (ACCEPTED, INERT):                # an inert acceptance too: the identification replaces "(inert)" and its paragraph
        t = P.document(dict(e, identification=ident(word)), None, None, 0.0)
        assert t.startswith(header), t[:120]
        assert "(inert)" not in t and "**Inert:**" not in t
        sec = "## What this record identifies: %s\n- %s" % (word, ident(word)["lines"][0])
        assert sec in t and t.index("**planner**") < t.index(sec) < t.index("## The receipt")


def test_a_refused_ruling_keeps_its_header_and_gets_the_section_only_past_the_replay():
    t = P.document(dict(REFUSED, identification=ident("not identified")), None, None, 0.0)
    assert t.startswith("# Ruling: refused\n")
    assert t.index("## What this record identifies: not identified") < t.index("## Why it is refused")
    t = P.document(dict(REFUSED, identification=ident("nothing identified")), None, None, 0.0)
    assert t.startswith("# Ruling: refused\n") and "What this record identifies" not in t


def _main(tmp_path, monkeypatch, *extra, verdict="accepted"):
    """propose.main with the judge canned: what it was given, and the evidence it returns."""
    import metis_agent.service as S
    import metis_agent.trace as AT
    seen = {}

    def judge(trace, member, pack, root, config, record=None, **kw):     # `record` in the signature: the kind gate's
        if record is not None:
            seen["record"] = record
        e = dict(ACCEPTED if verdict == "accepted" else REFUSED, unit="grasp_domain.llp", verdict=verdict)
        e["rows"] = [{"k": 7, "member": "planner", "fired": {"record": ["begin"], "candidate": []}}]
        e["first_enabled"] = None
        return e
    monkeypatch.setattr(AT, "judge", judge)
    monkeypatch.setattr(S, "load_config", lambda f: {"v3": {}})
    (tmp_path / "grasp_domain.llp").write_text(GRASP)
    pack = tmp_path / "p.llp"
    pack.write_text(DROP_BEGIN)
    rec = tmp_path / "rec.json"
    rec.write_text(json.dumps({"member": "planner", "k": 7, "kind": "structural"}))
    run = tmp_path / "run"
    code = P.main(["--pack", str(pack), "--member", "planner", "--trace", str(tmp_path), "--root", str(tmp_path), "--config", "c.yaml", "--run", str(run),
                   "--unit", "grasp_domain.llp", *[str(rec) if x == "REC" else x for x in extra]])
    return code, seen, json.loads((run / "evidence.json").read_text()), (run / "ruling.md").read_text()


def test_surprise_puts_the_identification_into_the_evidence_and_the_document(tmp_path, monkeypatch):
    pytest.importorskip("metis_agent")
    code, seen, e, t = _main(tmp_path, monkeypatch, "--surprise", "REC")
    assert code == 0 and "record" not in seen, seen                     # --surprise is not the kind gate's
    i = e["identification"]
    assert i["word"] == "identified" and i["target"] == [7] and i["consumes"] == []
    assert t.startswith("# Ruling: accepted\n") and "## What this record identifies: identified\n- TARGET: yes. At tick 7" in t
    assert "(inert)" not in t


def test_record_alone_only_gates_the_kind(tmp_path, monkeypatch):
    pytest.importorskip("metis_agent")
    code, seen, e, t = _main(tmp_path, monkeypatch, "--record", "REC")
    assert seen["record"]["kind"] == "structural"
    assert "identification" not in e and "What this record identifies" not in t


def test_not_judged_gets_no_identification(tmp_path, monkeypatch):
    pytest.importorskip("metis_agent")
    code, seen, e, t = _main(tmp_path, monkeypatch, "--surprise", "REC", verdict="not judged")
    assert code == 2 and "identification" not in e
