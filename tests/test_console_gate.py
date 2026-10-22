"""The console's writes through the loop's gate (loop-parity s-72d9d36b step 2, docs/LOOP.md), on a
temp root: save as a plan with the since-diff of a refused proposal, an edit of a file on disk,
the README, the intents skeleton (no model), take into the operator's other catalog, a new domain
from a seed (an .llp or a package), confirm refusing a source changed since the plan; and the
gateway's frames for them (personal mode only). Nothing is committed."""
import json
from pathlib import Path

import pytest

from loop.console_serve import ConsoleServer
from test_gateway import Running, frames, open3


def server(tmp_path, take=True):
    (tmp_path / "cat").mkdir(parents=True, exist_ok=True)
    srv = ConsoleServer(tmp_path / "cat", take_into=(tmp_path / "mine") if take else None)
    srv.new_domain("plant", "a plant that wilts")
    return srv


def work(srv, text=None):
    p = srv.root / "domains/plant/plant.llp"
    return {"name": "domains/plant/plant", "copy": p.read_text() if text is None else text, "extensions": []}


def test_save_is_a_plan_refused_then_shown_with_what_changed_since(tmp_path):
    srv = server(tmp_path)
    prog = srv.root / "domains/plant/plant.llp"
    w = work(srv, prog.read_text().replace("%% I wake up.", "%% I wake up slowly."))
    pl = srv.save_plan(w)
    assert pl["files"][0]["path"] == "domains/plant/plant.llp" and "slowly" in pl["files"][0]["diff"]
    assert "since_diff" not in pl["files"][0] and "text" not in pl["files"][0]
    assert srv.save_refuse(pl["token"]) == {"refused": ["domains/plant/plant.llp"]}
    w["copy"] = w["copy"].replace("slowly", "very slowly")
    again = srv.save_plan(w)
    assert again["files"][0]["since_diff"] and "very slowly" in again["files"][0]["since_diff"]
    with pytest.raises(ValueError, match="the copy changed since the diff was shown"):
        srv.save_apply(dict(w, copy=w["copy"] + "\n% more\n"), again["token"])
    assert "very slowly" not in prog.read_text()
    out = srv.save_apply(w, again["token"])
    assert out["written"] and "very slowly" in prog.read_text()
    assert "since_diff" not in srv.save_plan(dict(w, copy=w["copy"] + "% x\n"))["files"][0]   # a write forgets


def test_save_carries_the_extensions_and_display_line(tmp_path):
    srv = server(tmp_path)
    w = work(srv)
    w["extensions"] = [{"name": "Tired Plant", "source": "% an extension\n"}]
    pl = srv.save_plan(w, display="the plant", line="a plant that wilts and recovers")
    paths = sorted(f["path"] for f in pl["files"])
    assert paths == ["domains/plant/domain.yaml", "domains/plant/extensions/tired_plant.llp"]
    srv.save_apply(w, pl["token"], display="the plant", line="a plant that wilts and recovers")
    y = (srv.root / "domains/plant/domain.yaml").read_text()
    assert "recovers" in y and (srv.root / "domains/plant/extensions/tired_plant.llp").is_file()


def test_edit_readme_and_intents_through_the_gate(tmp_path):
    srv = server(tmp_path)
    readme = srv.root / "domains/plant/README.md"
    pl = srv.gate_plan("edit", "plant", {"path": "README.md", "old": "A new domain", "new": "A plant domain"})
    assert pl["kind"] == "edit" and "A plant domain" in pl["files"][0]["diff"]
    assert srv.gate_confirm(pl["token"])["written"] == ["domains/plant/README.md"]
    assert "A plant domain" in readme.read_text()
    with pytest.raises(ValueError):
        srv.gate_plan("edit", "plant", {"path": "README.md", "old": "no such text", "new": "x"})
    pl = srv.gate_plan("readme", "plant", {"text": "A plant wilts without water and recovers when watered.", "title": "The plant"})
    srv.gate_confirm(pl["token"])
    assert "recovers when watered" in readme.read_text()
    note = srv.gate_plan("intents", "plant", {})                              # the skeleton: no cmd_* atoms here
    assert note["files"] == [] and note.get("note")
    prog = srv.root / "domains/plant/plant.llp"
    prog.write_text(prog.read_text().replace("pred awake : plant.", "pred awake : plant.\npred cmd_water : plant."))
    sk = srv.gate_plan("intents", "plant", {})
    assert any(f["path"].endswith("intent.yaml") for f in sk["files"]) and "WATER" in sk["files"][0]["diff"]


def test_confirm_refuses_a_source_changed_since_the_plan(tmp_path):
    srv = server(tmp_path)
    readme = srv.root / "domains/plant/README.md"
    pl = srv.gate_plan("edit", "plant", {"path": "README.md", "old": "A new domain", "new": "A plant domain"})
    readme.write_text(readme.read_text().replace("Describe", "Tell"))         # someone edits it meanwhile
    with pytest.raises(ValueError, match="changed after the person approved"):
        srv.gate_confirm(pl["token"])
    assert "A plant domain" not in readme.read_text()


def test_take_into_the_operators_other_catalog(tmp_path):
    srv = server(tmp_path)
    pl = srv.gate_plan("take", "plant", {})
    assert pl["root"] == str((tmp_path / "mine").resolve()) and all(f["new"] for f in pl["files"])
    out = srv.gate_confirm(pl["token"])
    assert (tmp_path / "mine/domains/plant/plant.llp").is_file() and "bundle" in out
    with pytest.raises(ValueError, match="take_into"):
        server(tmp_path / "other", take=False).gate_plan("take", "plant", {})


def test_a_new_domain_from_a_seed(tmp_path):
    srv = server(tmp_path)
    seed = tmp_path / "lamp.llp"
    seed.write_text((srv.root / "domains/plant/plant.llp").read_text().replace("catalog plant 1.", "catalog lamp 1.")
                    .replace(": plant.", ": lamp.").replace("namespace plant", "namespace lamp"))
    pl = srv.seed_plan("", str(seed), "a lamp")
    assert pl["kind"] == "program" and pl["domain"] == "lamp"
    assert sorted(f["path"] for f in pl["files"]) == ["domains/lamp/domain.yaml", "domains/lamp/lamp.llp"]
    srv.gate_confirm(pl["token"])
    assert (srv.root / "domains/lamp/lamp.llp").is_file()
    other = ConsoleServer(tmp_path / "other")
    (tmp_path / "other").mkdir()
    pkg = other.seed_plan("", str(srv.root / "domains/plant"))                  # a package directory: taken whole
    assert pkg["kind"] == "take" and pkg["domain"] == "plant"
    other.gate_confirm(pkg["token"])
    assert (tmp_path / "other/domains/plant/plant.llp").is_file()
    with pytest.raises(ValueError, match="no seed"):
        srv.seed_plan("x", str(tmp_path / "nope.llp"))
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "domain.yaml").write_text("program: loose.llp\n")
    with pytest.raises(ValueError, match="domains/<name>/"):
        srv.seed_plan("", str(loose))


def test_the_gateways_frames(tmp_path):
    srv = server(tmp_path)
    r = Running(srv, mode="personal")
    try:
        with r.ws() as ws:
            sid = open3(ws, "domains/plant/plant")["session"]
            text = (srv.root / "domains/plant/plant.llp").read_text().replace("%% I wake up.", "%% I wake up slowly.")
            ws.send(json.dumps({"ch": "repl", "type": "work", "session": sid, "copy": text}))
            ws.send(json.dumps({"ch": "repl", "type": "save", "session": sid}))
            pl = frames(ws, lambda f: f.get("type") == "save")[-1]
            ws.send(json.dumps({"ch": "repl", "type": "refuse", "session": sid, "token": pl["token"]}))
            assert frames(ws, lambda f: f.get("type") == "refused")[-1]["refused"] == ["domains/plant/plant.llp"]
            ws.send(json.dumps({"ch": "repl", "type": "save", "session": sid}))
            again = frames(ws, lambda f: f.get("type") == "save")[-1]
            assert "since_diff" in again["files"][0]
            ws.send(json.dumps({"ch": "repl", "type": "save", "session": sid, "token": again["token"]}))
            done = frames(ws, lambda f: f.get("type") == "save" and f.get("written"))[-1]
            assert done["written"] == ["domains/plant/plant.llp"]
            ws.send(json.dumps({"ch": "repl", "type": "gate", "op": "propose", "kind": "readme", "domain": "plant",
                                "args": {"text": "A plant wilts and recovers."}, "req": 7}))
            g = frames(ws, lambda f: f.get("type") == "gate")[-1]
            assert g["op"] == "plan" and g["req"] == 7 and g["files"][0]["path"] == "domains/plant/README.md"
            ws.send(json.dumps({"ch": "repl", "type": "gate", "op": "confirm", "token": g["token"], "req": 8}))
            w = frames(ws, lambda f: f.get("type") == "gate" and f.get("op") == "written")[-1]
            assert w["written"] == ["domains/plant/README.md"] and w["req"] == 8
            seed = tmp_path / "lamp.llp"
            seed.write_text("catalog lamp 1.\n")
            ws.send(json.dumps({"ch": "repl", "type": "new", "seed": str(seed), "req": 9}))
            sp = frames(ws, lambda f: f.get("type") in ("gate", "error"))[-1]
            assert sp.get("purpose") == "seed" and sp["domain"] == "lamp", sp
            ws.send(json.dumps({"ch": "repl", "type": "gate", "op": "refuse", "token": sp["token"]}))
            assert frames(ws, lambda f: f.get("type") == "gate" and f.get("op") == "refused")[-1]["refused"]
        assert not (srv.root / "domains/lamp").exists()
    finally:
        r.close()
    shared = Running(server(tmp_path / "s"), mode="shared")
    try:
        with shared.ws() as ws:
            frames(ws, lambda f: f.get("type") == "catalogs")
            ws.send(json.dumps({"ch": "repl", "type": "gate", "op": "propose", "kind": "readme", "domain": "plant",
                                "args": {"text": "x"}}))
            err = frames(ws, lambda f: f.get("type") == "error")[-1]
            assert "personal mode only" in err["error"]
    finally:
        shared.close()


ASK = {"phase": "exploit", "reason": "no_progress", "tried": ["revise water: refused twice"],
       "believes": ["water needs dry"], "options": ["explore here", "skip this state"],
       "question": "The plant stays dry after `water`: is there a fact I do not read?", "snapshot": "snap/3.json"}


def test_the_loops_asks_shown_and_answered(tmp_path):
    """loop-policy s-dd842f2a: the console's own asks and those of a loop elsewhere ([console]
    loop_state: pi's gate state, written by its CLI), each answered in the gate that holds it."""
    from metis.gate import Gate
    srv = server(tmp_path)
    assert srv.gate_asks() == []
    mine = srv.gate_plan("ask", "plant", ASK)
    assert mine["kind"] == "ask" and mine["files"] == [] and mine["ask"]["question"] == ASK["question"]
    pi = tmp_path / "pi-state"
    with Gate.locked(pi) as g:                                    # pi's CLI, another process in life
        theirs = g.propose("ask", "plant", srv.root, **dict(ASK, reason="budget"))
    srv.loop_state = pi
    asks = srv.gate_asks()
    assert [(a["token"], a["where"]) for a in asks] == [(mine["token"], "console"), (theirs["token"], "loop")]
    with pytest.raises(ValueError, match="answer phase"):
        srv.gate_answer(theirs["token"], {"kind": "phase", "phase": "nap"})
    out = srv.gate_answer(theirs["token"], {"kind": "budget", "beats": 40})
    assert out["instruction"] == {"kind": "budget", "beats": 40}
    with Gate.locked(pi) as g:                                    # pi reads it when it re-engages
        assert g.answers(theirs["token"])["ask"]["snapshot"] == "snap/3.json"
    srv.gate_answer(mine["token"], "look at the pot's drain")
    assert srv.gate_asks() == []
    with pytest.raises(ValueError, match="no such ask"):
        srv.gate_answer(mine["token"], "again")
    with pytest.raises(ValueError, match="reason"):
        srv.gate_plan("ask", "plant", dict(ASK, reason="bored"))


def test_the_gateways_ask_frames(tmp_path):
    srv = server(tmp_path)
    r = Running(srv, mode="personal")
    try:
        with r.ws() as ws, r.ws() as other:
            frames(ws, lambda f: f.get("type") == "catalogs")
            frames(other, lambda f: f.get("type") == "catalogs")
            ws.send(json.dumps({"ch": "repl", "type": "gate", "op": "asks"}))
            assert frames(ws, lambda f: f.get("op") == "asks")[-1]["asks"] == []
            ws.send(json.dumps({"ch": "repl", "type": "gate", "op": "propose", "kind": "ask", "domain": "plant",
                                "args": ASK}))
            seen = frames(other, lambda f: f.get("op") == "asks")[-1]["asks"]     # every page of the person's
            assert [a["ask"]["question"] for a in seen] == [ASK["question"]]
            other.send(json.dumps({"ch": "repl", "type": "gate", "op": "answer", "token": seen[0]["token"],
                                   "instruction": {"kind": "note", "text": "check the drain"}, "req": 4}))
            ans = frames(other, lambda f: f.get("op") == "answered")[-1]
            assert ans["req"] == 4 and ans["instruction"]["text"] == "check the drain"
            # the first page saw the ask broadcast, then the list without it once answered
            seen = [f["asks"] for f in frames(ws, lambda f: f.get("op") == "asks" and not f["asks"]) if f.get("op") == "asks"]
            assert len(seen[-2]) == 1 and seen[-1] == []
    finally:
        r.close()
