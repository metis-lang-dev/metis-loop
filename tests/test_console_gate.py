"""The console's writes through the loop's gate (loop-parity s-72d9d36b step 2, docs/LOOP.md), on a
temp root: the EDITOR's save as one planned edit of the file on disk (workspace-files s-9ea4cfa4: its diff,
its findings, refused or written), an edit of another file on disk,
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


PROG = "domains/plant/plant.llp"


def test_an_edit_is_a_plan_refused_then_written(tmp_path):
    """workspace-files s-9ea4cfa4 step 2: the EDITOR's save is one exact edit of the file on disk, planned (its
    diff, the gate's findings, the console's token), refused (remembered) or confirmed (written)."""
    srv = server(tmp_path)
    prog = srv.root / PROG
    pl = srv.edit_plan(PROG, "%% I wake up.", "%% I wake up slowly.")
    assert pl["path"] == PROG and pl["domain"] == "plant" and pl["ok"] and pl["token"]
    assert "-  %% I wake up." in pl["diff"] and "+  %% I wake up slowly." in pl["diff"]
    assert all(f["level"] != "error" for f in pl["findings"])
    assert all({"level", "code", "line", "msg"} <= set(f) for f in pl["findings"])     # metispy's carry more
    assert not any(f["code"] == "lint-not-run" for f in pl["findings"]), pl["findings"]     # the lint ran
    assert "since_diff" not in pl                                      # nothing refused yet
    assert srv.gate_refuse(pl["token"]) == {"refused": [PROG]}
    assert "slowly" not in prog.read_text()
    again = srv.edit_plan(PROG, "%% I wake up.", "%% I wake up very slowly.")
    assert "very slowly" in again["since_diff"]                       # what changed since the refused plan (nina's review)
    out = srv.gate_confirm(again["token"])
    assert out["written"] == [PROG] and "very slowly" in prog.read_text()


def test_an_edit_that_breaks_the_program_is_shown_and_never_planned(tmp_path):
    """A finding at error level (metisc's diagnostics of the edited text) is shown with the diff, and no token is
    made: nothing can write it. An old text that is not in the file (changed on disk since it was read) refuses."""
    srv = server(tmp_path)
    prog = srv.root / PROG
    before = prog.read_text()
    bad = srv.edit_plan(PROG, "wake [dyn] : idle -o awake.", "wake [dyn] : idle -o .")
    assert not bad["ok"] and "token" not in bad and bad["diff"]
    assert any(f["level"] == "error" for f in bad["findings"])
    assert prog.read_text() == before
    with pytest.raises(ValueError, match="not in it"):
        srv.edit_plan(PROG, "no such text", "x")
    with pytest.raises(ValueError, match="not a file of a domain"):
        srv.edit_plan("loose.llp", "a", "b")


def test_the_session_files_are_the_disks(tmp_path):
    """No copy: a session's files are its program and its domain's extensions as they are on disk; an in-memory
    catalog is refused."""
    srv = server(tmp_path)
    assert srv.open_session("s", {"llp": "domains/plant/plant"})["status"] != "closed"
    got = srv.files_of("s")
    assert got["program"] == PROG and got["files"] == [{"path": PROG, "text": (srv.root / PROG).read_text(), "role": "program"}]
    out = srv.open_session("t", {"source": "catalog x 1.\n", "name": "x"})
    assert out["status"] == "closed" and "the workspace owns the file" in out["error"]


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
    assert pl["kind"] == "new" and pl["domain"] == "lamp"
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
            o = open3(ws, "domains/plant/plant")
            sid, fs = o["session"], o["_files"]
            assert fs["program"] == PROG and fs["files"][0]["text"] == (srv.root / PROG).read_text()
            text = fs["files"][0]["text"]
            new = text.replace("%% I wake up.", "%% I wake up slowly.")
            ws.send(json.dumps({"ch": "repl", "type": "edit", "session": sid, "path": PROG, "old": text, "new": new, "req": 5}))
            pl = frames(ws, lambda f: f.get("type") == "edit")[-1]
            assert pl["op"] == "plan" and pl["ok"] and pl["req"] == 5 and "slowly" in pl["diff"]
            ws.send(json.dumps({"ch": "repl", "type": "edit", "op": "refuse", "session": sid, "token": pl["token"]}))
            assert frames(ws, lambda f: f.get("type") == "edit")[-1]["op"] == "refused"
            ws.send(json.dumps({"ch": "repl", "type": "edit", "session": sid, "path": PROG, "old": text, "new": new}))
            again = frames(ws, lambda f: f.get("type") == "edit")[-1]
            ws.send(json.dumps({"ch": "repl", "type": "edit", "op": "confirm", "session": sid, "token": again["token"]}))
            got = frames(ws, lambda f: f.get("type") == "files")
            done = [f for f in got if f.get("type") == "edit"][-1]
            assert done["op"] == "written" and done["written"] == [PROG]
            assert [f for f in got if f.get("type") == "session"][-1].get("edited")      # re-opened, epoch + 1
            assert got[-1]["files"][0]["text"] == new == (srv.root / PROG).read_text()
            (srv.root / PROG).write_text(new + "% someone else\n")              # changed on disk: reload reads it
            ws.send(json.dumps({"ch": "repl", "type": "files", "session": sid, "req": 6}))
            again = frames(ws, lambda f: f.get("type") == "files")[-1]
            assert again["req"] == 6 and again["files"][0]["text"].endswith("% someone else\n")
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
            ws.send(json.dumps({"ch": "repl", "type": "edit", "session": "nope", "path": PROG, "old": "a", "new": "b"}))
            err = frames(ws, lambda f: f.get("type") == "error")[-1]
            assert "no open session" in err["error"] or "personal mode only" in err["error"]
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


def test_a_bare_name_is_the_package_not_a_goldens_case(tmp_path):
    """The architect's F3 (loop-chat, dog): 'plant' in the open field is the package's program even when a goldens
    case of the same name is under the root; two packages of one name stay ambiguous."""
    srv = server(tmp_path)
    case = srv.root / "goldens/cases/plant.llp"
    case.parent.mkdir(parents=True)
    case.write_text("catalog plant 1.\n")
    assert srv.resolve("plant") == (srv.root / PROG).resolve()
    assert srv.resolve("goldens/cases/plant") == case.resolve()        # the full name still opens the case file


def test_a_new_extension_is_an_edit_of_a_missing_file(tmp_path):
    """"+ extension" (workspace-files s-9ea4cfa4, the architect's ruling): extensions/<name>.llp is an edit with
    old "" on the missing path, through the same plan and gate (it compiles against the program); after the
    write the session's files carry it."""
    srv = server(tmp_path)
    assert srv.open_session("s", {"llp": "domains/plant/plant"})["status"] != "closed"
    ext = "domains/plant/extensions/tired.llp"
    pl = srv.edit_plan(ext, "", "% the plant tires\ncatalog plant_tired 1.\nextends plant.\n")
    assert pl["ok"] and pl["token"] and "+catalog plant_tired 1." in pl["diff"]
    assert not (srv.root / ext).exists()
    assert srv.gate_confirm(pl["token"])["written"] == [ext]
    assert srv.open_session("s", {"llp": "domains/plant/plant"})["status"] != "closed"
    assert [f["path"] for f in srv.files_of("s")["files"]] == [PROG, ext]


LAMP = """% lamp
catalog lamp 1.
provenance text "a lamp" "2026-11-04".
layers (dyn).
stages (main).
include "../tree/lamp_rules.llp".
#init off 1
"""
RULES = """catalog lamp_rules 1.
namespace lamp produce (dyn).
pred off : lamp.
pred on : lamp.
stage main {
  %% I switch it on.
  switch_on [dyn] : off -o on.
}
"""


def test_a_bundle_members_rule_files_are_the_editors(tmp_path):
    """The alf drive's L5 (and metispy's M1): a bundle member's program includes the bundle's files; the EDITOR's files
    list them (a DERIVED file as its source, the one copy), and a save plans an edit of the source from the session."""
    from metis import catalog
    if not hasattr(catalog, "bundle_dir"):
        pytest.skip("metispy before edit-bundle-includes")
    h = tmp_path / "domains" / "hier"
    (h / "lamp").mkdir(parents=True)
    (h / "tree").mkdir()
    (h / "composition.yaml").write_text("name: lampset\ndirect: lamp\n")
    (h / "lamp_rules.llp").write_text("% the lamp's rules, the one copy\n" + RULES)
    (h / "tree" / "lamp_rules.llp").write_text("% DERIVED from ../lamp_rules.llp by the test: edit that file, never this one.\n" + RULES)
    (h / "lamp" / "domain.yaml").write_text("display: the lamp\nline: a lamp\nprogram: lamp.llp\n")
    (h / "lamp" / "lamp.llp").write_text(LAMP)
    srv = ConsoleServer(tmp_path)
    assert srv.open_session("s", {"llp": "domains/hier/lamp/lamp"})["status"] != "closed"
    got = srv.files_of("s")
    assert [(f["path"], f["role"]) for f in got["files"]] == [
        ("domains/hier/lamp/lamp.llp", "program"), ("domains/hier/lamp_rules.llp", "bundle")]   # not tree/: DERIVED
    if not catalog.metisc():
        pytest.skip("no metisc for the edit's diagnostics")
    pl = srv.edit_plan("domains/hier/lamp_rules.llp", "%% I switch it on.", "%% I switch it on, now.", sid="s")
    assert pl["ok"] and pl["token"] and pl["domain"] == "lamp", pl
    assert srv.gate_confirm(pl["token"])["written"] == ["domains/hier/lamp_rules.llp"]
    assert "now." in (h / "lamp_rules.llp").read_text()


def test_an_edit_of_another_domains_file_is_its_own_with_a_session_open(tmp_path):
    """nina's review of L5: with a session open on plant, an edit of lamp's README is lamp's (as with no session); only
    a file of the session member's bundle is planned from the member."""
    srv = server(tmp_path)
    srv.new_domain("lamp", "a lamp")
    assert srv.open_session("s", {"llp": "domains/plant/plant"})["status"] != "closed"
    readme = "domains/lamp/README.md"
    text = (srv.root / readme).read_text()
    for sid in (None, "s"):
        pl = srv.edit_plan(readme, text.splitlines()[0], text.splitlines()[0] + " (edited)", sid=sid)
        assert pl["ok"] and pl["domain"] == "lamp" and pl["token"], (sid, pl)



def test_a_nested_package_edits_as_its_own(tmp_path):
    """nina's note 3: the nearest manifest above a file names its domain, so a package inside another's directory
    edits as itself, not as the outer one."""
    srv = server(tmp_path)
    inner = srv.root / "domains/plant/inner"
    inner.mkdir()
    (inner / "domain.yaml").write_text("program: inner.llp\n")
    (inner / "README.md").write_text("An inner package.\n")
    assert srv._domain_file("domains/plant/inner/README.md")[:2] == ("inner", "README.md")
    assert srv._domain_file(PROG)[:2] == ("plant", "plant.llp")


def test_a_session_running_elsewhere_is_told_and_reopens_after(tmp_path):
    """nina's note 2: a confirm that writes the file of a session running elsewhere tells that session's page, and the
    session re-opens (epoch + 1, the files frame) when its command ends, not before."""
    import asyncio
    srv = server(tmp_path)
    r = Running(srv, mode="personal")
    try:
        with r.ws() as a, r.ws() as b:
            sa, sb = open3(a, "domains/plant/plant"), open3(b, "domains/plant/plant")
            text = sa["_files"]["files"][0]["text"]
            other = r.gw.sessions[sb["session"]]
            other.running = {"cmd": "a long one"}                     # as if b's command were mid-run
            a.send(json.dumps({"ch": "repl", "type": "edit", "session": sa["session"], "path": PROG, "old": text,
                               "new": text.replace("%% I wake up.", "%% I wake up slowly.")}))
            pl = frames(a, lambda f: f.get("type") == "edit")[-1]
            a.send(json.dumps({"ch": "repl", "type": "edit", "op": "confirm", "session": sa["session"],
                               "token": pl["token"]}))
            got = frames(b, lambda f: f.get("type") == "files")
            note = [f for f in got if f.get("type") == "notice"]
            assert note and "re-opens when it ends" in note[-1]["text"], got
            assert not any(f.get("type") == "session" and f.get("edited") for f in got)     # not while it runs
            assert other.written
            other.running = None
            asyncio.run_coroutine_threadsafe(r.gw._after_run(other), r.loop).result(10)
            after = frames(b, lambda f: f.get("type") == "files")
            assert any(f.get("type") == "session" and f.get("edited") for f in after), after
            assert "slowly" in after[-1]["files"][0]["text"] and not other.written
    finally:
        r.close()
