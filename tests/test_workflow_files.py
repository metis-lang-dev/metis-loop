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
    assert "display: the plant" in y and 'line: "a potted plant that dries out"' in y and "program: plant.llp" in y
    from metis_loop_sdk import catalog
    assert catalog.get("plant", tmp_path).name == "plant"            # the package's keys only: the loader takes it
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
            "extensions": [{"name": "Visitor Waters", "source": "% an extension\n"}]}
    plan = srv.save_plan(work)
    assert [f["path"] for f in plan["files"]] == ["domains/plant/plant.llp", "domains/plant/extensions/visitor_waters.llp"]
    assert "-  %% I wake up." in plan["files"][0]["diff"] and "+  %% I wake up slowly." in plan["files"][0]["diff"]
    assert plan["files"][1]["new"]
    with pytest.raises(ValueError, match="changed since"):
        srv.save_apply({**work, "copy": work["copy"] + "\n"}, plan["token"])   # not the diff the viewer saw
    assert "slowly" not in path.read_text()
    out = srv.save_apply(work, plan["token"])
    assert out["written"] == ["domains/plant/plant.llp", "domains/plant/extensions/visitor_waters.llp"]
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
    # the page selects the clicked row by its identity, never by its line
    assert out["ids"] == [[r["record"], r["ts"]] for r in sorted(rows, key=lambda r: r["i"])]
    assert srv.serve_one("s", "record 1")["posting"]["status"] == "done"
    assert srv.shells["s"].loop.text == "a visitor watered it"                # record N adopts the mined text
    for bad in ("domains/plant/plant.llp", "../etc/passwd", "domains/plant/records/nope.jsonl"):
        with pytest.raises(ValueError):
            srv.load_sink("s", bad)


SOIL = """catalog plant 1.
layers (dyn).
stages (main).
namespace plant produce (dyn).
pred moist : plant.
pred dry : plant.
pred sun : plant.
stage main {
  %% The sun dries me out.
  dry_out [dyn] : moist * sun -o dry.
}
#init moist 1
"""
VISITOR = """% a visitor waters the plant
catalog visitor 1.
extends plant.
stage main {
  %% A visitor has watered me.
  visitor_waters [dyn] : dry -o moist.
}
"""


def test_a_domains_extensions_are_opened_with_it(srv, tmp_path):
    """human-loop step 1 (the architect's ruling): the served program is the
    program plus its extensions/*.llp — the one-click open merges them (the key
    is the union), as a session's extensions are; a program no manifest names
    gets none."""
    llp = srv.new_domain("plant", "a plant")
    d = tmp_path / "domains/plant"
    (d / "plant.llp").write_text(SOIL)
    plain_key = srv.build({"llp": llp})[0].key
    (d / "extensions").mkdir()
    (d / "extensions/visitor.llp").write_text(VISITOR)
    r, label, reports = srv.build({"llp": llp})
    assert [x["name"] for x in reports] == ["visitor"] and r.key != plain_key and label.endswith("+ 1 extension")
    assert [p.name for p in srv.checkout_extensions(d / "plant.llp")] == ["visitor.llp"]
    (tmp_path / "loose.llp").write_text(SOIL)
    assert srv.checkout_extensions(tmp_path / "loose.llp") == []
    # save/apply plans nothing for an unchanged copy + its extensions as opened
    work = {"name": llp, "copy": SOIL, "extensions": [{"name": "visitor", "source": VISITOR}]}
    assert srv.save_plan(work)["files"] == []


def test_a_recompile_keeps_the_sunk_records_and_the_selected_one(srv, tmp_path):
    """The architect's A6 finding: a recompile started a fresh session and
    dropped the sunk records — Claude could not check its candidate against
    the selected record. Now the records, the selection (its scene) and the
    loop's text go on across a recompile (keep_loop), not across an open."""
    llp = srv.new_domain("plant", "a plant")
    (tmp_path / "domains/plant/plant.llp").write_text(SOIL)
    assert srv.open_session("s", {"llp": llp})["status"] != "closed"
    rec = tmp_path / "domains/plant/records/s1.jsonl"
    rec.parent.mkdir()
    rec.write_text(json.dumps({"kind": "unmodeled", "observed": {"moist": 1}, "init": {"dry": 1},
                               "record": 0, "session": "s1", "mined_text": "a visitor watered it",
                               "close": {"status": "escalated", "beat": 4}}) + "\n")
    assert srv.load_sink("s", "domains/plant/records/s1.jsonl")["ok"]
    sh = srv.shells["s"]
    assert sh.cmd_record("0")["ok"] and sh.loop.rec_idx == 0
    sh.loop.text = "a visitor waters the plant when it is dry"
    out = srv.open_session("s", {"source": SOIL, "name": llp, "extensions": [{"name": "visitor", "source": VISITOR}],
                                 "keep_loop": True})
    assert out["status"] != "closed"
    new = srv.shells["s"]
    assert new is not sh and len(new.loop.records) == 1 and new.loop.rec_idx == 0
    assert new.loop.text == "a visitor waters the plant when it is dry" and new.case["init"] == {"dry": 1}
    srv.open_session("s", {"llp": llp})                                      # an open is a new session: none
    assert not srv.shells["s"].loop.records


def test_the_manifests_serves_names_the_extensions(srv, tmp_path):
    """runtime-binding Q1 (the architect's ruling): the manifest's `serves:`
    is the served program — the extensions it lists after this program are opened,
    one in extensions/ it leaves out is not; a manifest serving another file (the
    kitchen's pair scene) gives this program none."""
    import yaml
    llp = srv.new_domain("plant", "a plant")
    d = tmp_path / "domains/plant"
    (d / "plant.llp").write_text(SOIL)
    (d / "extensions").mkdir()
    (d / "extensions/visitor.llp").write_text(VISITOR)
    (d / "extensions/zz_draft.llp").write_text(VISITOR)
    man = yaml.safe_load((d / "domain.yaml").read_text())
    (d / "domain.yaml").write_text(yaml.safe_dump({**man, "serves": ["plant.llp", "extensions/visitor.llp"]}))
    assert [p.name for p in srv.checkout_extensions(d / "plant.llp")] == ["visitor.llp"]
    (d / "domain.yaml").write_text(yaml.safe_dump({**man, "serves": ["metis.domains.kitchen:catalogs/kitchen_host.llp"]}))
    assert srv.checkout_extensions(d / "plant.llp") == []


def test_the_navigation_agents_records_are_listed(srv, tmp_path):
    """console-nav step 2: the console's own domains (ui, repl), served by console-nav.sh's
    agent, sink their records in .metis/console-nav/records/<domain>/records/; the RECORDS dock
    lists them; any other .metis/ records stay the loop's own (unlisted)."""
    nav = tmp_path / ".metis/console-nav/records/ui/records/20261022-1.jsonl"
    nav.parent.mkdir(parents=True)
    nav.write_text(json.dumps({"kind": "unmodeled", "record": 0, "ts": "2026-10-22T11:18:48",
                               "observed": {"focused(root)": 1}, "close": {"status": "escalated", "beat": 5}}) + "\n")
    own = tmp_path / ".metis/records/x.jsonl"
    own.parent.mkdir(parents=True)
    own.write_text(json.dumps({"kind": "rare", "record": 0}) + "\n")
    rows = srv.records()
    assert [(r["domain"].split("/")[-1], r["status"]) for r in rows] == [("ui", "escalated")]
