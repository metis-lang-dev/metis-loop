"""e2e-workflow s-143c3088 step 1 (b)(c): the loop console's checkout
files — the records the domain agents sank (listed, loaded into a session
with metispy's own sink), `new <name>`, and the EDITOR's save as one edit
of the file (workspace-files s-9ea4cfa4: a plan first, the token of that plan
to write, never a commit). On a scratch checkout."""
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
    from metis import catalog
    assert catalog.get("plant", tmp_path).name == "plant"            # the package's keys only: the loader takes it
    assert "%% I wake up." in (d / "plant.llp").read_text()                 # the rule with its %% line
    assert srv.open_session("s", {"llp": llp})["status"] == "running"
    assert srv.serve_one("s", "run 5")["posting"]["status"] == "done" and srv.shells["s"].counts == {"awake": 1}
    for bad in ("plant", "Plant", "1x", "../x", ""):
        with pytest.raises(ValueError):
            srv.new_domain(bad)
    assert [e["path"] for e in srv.domains() if e["kind"] == "domain"] == ["domains/plant/plant"]


def test_an_edit_shows_the_diff_and_writes_only_what_was_shown(srv, tmp_path):
    llp = srv.new_domain("plant", "a plant")
    path = tmp_path / "domains/plant/plant.llp"
    text = path.read_text()
    plan = srv.edit_plan("domains/plant/plant.llp", text, text.replace("%% I wake up.", "%% I wake up slowly."))
    assert "-  %% I wake up." in plan["diff"] and "+  %% I wake up slowly." in plan["diff"] and plan["ok"]
    path.write_text(text + "\n")                                   # the file changed on disk after the plan
    from metis.gate import Refused
    with pytest.raises((ValueError, Refused)):
        srv.gate_confirm(plan["token"])
    assert "slowly" not in path.read_text()
    path.write_text(text)
    plan = srv.edit_plan("domains/plant/plant.llp", text, text.replace("%% I wake up.", "%% I wake up slowly."))
    assert srv.gate_confirm(plan["token"])["written"] == ["domains/plant/plant.llp"]
    assert "slowly" in path.read_text()
    assert srv.open_session("s", {"llp": llp})["status"] != "closed"


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
    # the EDITOR's files: the program and its extension, as they are on disk
    assert srv.open_session("s", {"llp": llp})["status"] != "closed"
    assert [(f["path"], f["role"]) for f in srv.files_of("s")["files"]] == [
        ("domains/plant/plant.llp", "program"), ("domains/plant/extensions/visitor.llp", "extension")]


def test_an_edit_reopen_keeps_the_sunk_records_and_the_selected_one(srv, tmp_path):
    """The architect's A6 finding: a re-open started a fresh session and
    dropped the sunk records. Now the records, the selection (its scene) and the
    loop's text go on across the re-open after an edit (keep_loop), not across an open."""
    llp = srv.new_domain("plant", "a plant")
    (tmp_path / "domains/plant/plant.llp").write_text(SOIL)
    assert srv.open_session("s", {"llp": llp})["status"] != "closed"
    rec = tmp_path / "domains/plant/records/s1.jsonl"
    rec.parent.mkdir()
    rec.write_text(json.dumps({"kind": "unmodeled", "observed": {"moist": 1}, "init": {"dry": 1},
                               "record": 0, "session": "s1", "mined_text": "a visitor watered it",
                               "close": {"status": "escalated", "beat": 4}}) + "\n")
    sh = srv.shells["s"]
    assert sh.cmd_sink(str(rec))["ok"]                 # the REPL's own sink (the wire's went with the RECORDS dock)
    assert sh.cmd_record("0")["ok"] and sh.loop.rec_idx == 0
    sh.loop.text = "a visitor waters the plant when it is dry"
    d = tmp_path / "domains/plant"
    (d / "extensions").mkdir()
    (d / "extensions/visitor.llp").write_text(VISITOR)           # the edit written: an extension now
    out = srv.open_session("s", {"llp": llp, "keep_loop": True})
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

