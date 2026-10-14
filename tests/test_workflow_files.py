"""e2e-workflow s-143c3088 step 1 (b)(c): the loop console's checkout
files — the records the domain agents sank (listed, loaded into a session
with metispy's own sink), `new <name>`, `save` (a diff first, the token of
that diff to write, never a commit). On a scratch checkout."""
import json

import pytest

from loop.console_serve import ConsoleServer


@pytest.fixture
def srv(tmp_path):
    return ConsoleServer(tmp_path)


def test_new_makes_a_domain_that_opens_and_runs(srv, tmp_path):
    llp = srv.new_domain("plant", "a potted plant that dries out")
    d = tmp_path / "domains/plant"
    assert llp == "domains/plant/plant" and sorted(p.name for p in d.iterdir()) == ["README.md", "domain.yaml", "plant.llp"]
    y = (d / "domain.yaml").read_text()
    assert "name: plant" in y and 'line: "a potted plant that dries out"' in y and "program: plant.llp" in y
    assert "%% I wake up." in (d / "plant.llp").read_text()                 # the rule with its %% line
    assert srv.open_session("s", {"llp": llp})["status"] == "running"
    assert srv.serve_one("s", "run 5")["posting"]["status"] == "done" and srv.shells["s"].counts == {"awake": 1}
    for bad in ("plant", "Plant", "1x", "../x", ""):
        with pytest.raises(ValueError):
            srv.new_domain(bad)
    assert [e["path"] for e in srv.domains() if e["kind"] == "domain"] == ["domains/plant/plant"]


def test_save_shows_the_diff_and_writes_only_what_was_shown(srv, tmp_path):
    llp = srv.new_domain("plant", "a plant")
    path = tmp_path / "domains/plant/plant.llp"
    work = {"name": llp, "copy": path.read_text().replace("%% I wake up.", "%% I wake up slowly."),
            "packs": [{"name": "Visitor Waters", "source": "% a pack\n"}]}
    plan = srv.save_plan(work)
    assert [f["path"] for f in plan["files"]] == ["domains/plant/plant.llp", "domains/plant/packs/visitor_waters.llp"]
    assert "-  %% I wake up." in plan["files"][0]["diff"] and "+  %% I wake up slowly." in plan["files"][0]["diff"]
    assert plan["files"][1]["new"]
    with pytest.raises(ValueError, match="changed since"):
        srv.save_apply({**work, "copy": work["copy"] + "\n"}, plan["token"])   # not the diff the viewer saw
    assert "slowly" not in path.read_text()
    out = srv.save_apply(work, plan["token"])
    assert out["written"] == ["domains/plant/plant.llp", "domains/plant/packs/visitor_waters.llp"]
    assert "slowly" in path.read_text() and srv.save_plan(work)["files"] == []   # saved: nothing left to save
    with pytest.raises(ValueError, match="in memory only"):
        srv.save_plan({"name": "scratch thing", "copy": "x"})


def test_records_listed_newest_first_and_sunk_into_a_session(srv, tmp_path):
    llp = srv.new_domain("plant", "a plant")
    rec = tmp_path / "domains/plant/records/s1.jsonl"
    rec.parent.mkdir()
    base = {"kind": "rare", "observed": {"awake": 1}, "init": {"idle": 1}, "record": 0, "session": "s1"}
    rec.write_text("\n".join(json.dumps(x) for x in [
        {**base, "ts": "2026-10-14T10:00:00", "close": {"status": "open", "beat": 3}},
        {**base, "ts": "2026-10-14T10:00:05", "mined_text": "a visitor watered it", "escalated": {"beat": 4},
         "close": {"status": "escalated", "beat": 4}}]) + "\n")
    rows = srv.records()
    assert [(r["i"], r["status"], r["escalated"]) for r in rows] == [(1, "escalated", True), (0, "open", False)]
    assert rows[0]["domain"] == "domains/plant" and rows[0]["session"] == "s1" and rows[0]["mined_text"] == "a visitor watered it"
    srv.open_session("s", {"llp": llp})
    out = srv.load_sink("s", "domains/plant/records/s1.jsonl")
    assert out["ok"] and len(out["records"]) == 2
    assert srv.serve_one("s", "record 1")["posting"]["status"] == "done"
    assert srv.shells["s"].loop.text == "a visitor watered it"                # record N adopts the mined text
    for bad in ("domains/plant/plant.llp", "../etc/passwd", "domains/plant/records/nope.jsonl"):
        with pytest.raises(ValueError):
            srv.load_sink("s", bad)
