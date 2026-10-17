"""metis_loop_sdk.catalog (catalog-sdk s-bc1718e3): the facade reads what the
loader reads, apply is the one validated write (into a scratch catalog here),
the CLI says the same in JSON, the widget ships as package data.

The catalog is the metis-catalog checkout beside metis-loop (or
$METIS_CATALOG); the writes go to a scratch copy of its dog and plant."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from metis_loop_sdk import catalog

CAT = Path(os.environ.get("METIS_CATALOG") or Path(__file__).resolve().parents[3] / "metis-catalog")
if not (CAT / "domains").is_dir():
    pytest.skip(f"no metis-catalog checkout at {CAT} (METIS_CATALOG)", allow_module_level=True)


@pytest.fixture
def scratch(tmp_path):
    """A scratch catalog: the dog and the plant, and the intent generator."""
    for d in ("dog", "plant"):
        shutil.copytree(CAT / "domains" / d, tmp_path / "domains" / d,
                        ignore=shutil.ignore_patterns("records", "__pycache__"))
    shutil.copytree(CAT / "tools", tmp_path / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def test_root_is_the_env_then_the_config_then_the_checkout(monkeypatch, tmp_path):
    monkeypatch.setenv("METIS_CATALOG", str(tmp_path))
    assert catalog.root("/elsewhere") == tmp_path.resolve()
    monkeypatch.delenv("METIS_CATALOG")
    assert catalog.root(str(tmp_path)) == tmp_path.resolve()
    if catalog.SIBLING.is_dir():
        assert catalog.root() == catalog.SIBLING


def test_the_facade_reads_what_the_loader_reads():
    mc = catalog.loader()
    assert [d.name for d in catalog.domains(CAT)] == [d.name for d in mc.domains(CAT)]
    assert catalog.index(CAT) == mc.index(CAT)
    assert catalog.get("dog", CAT).program == mc.get("dog", CAT).program
    assert catalog.intents("dog", CAT) == mc.get("dog", CAT).intent
    dog = next(e for e in catalog.index(CAT) if e["name"] == "dog")
    assert catalog.readme_head(dog["readme"], r=CAT).startswith("# ")
    assert catalog.host_of(dog["path"], CAT) == dog["host"]


def test_listing_is_the_index_domains_then_each_partner():
    rows = catalog.listing(CAT)
    doms = [e["name"] for e in catalog.index(CAT) if e["kind"] == "domain"]
    assert [e["name"] for e in rows if e["kind"] == "domain"] == doms
    partners = [d.name for d in catalog.domains(CAT) if d.partner_of]
    assert [e["name"] for e in rows if e["kind"] == "partner"] == partners
    assert all(set(e) >= {"name", "kind", "path", "display", "line", "has"} for e in rows)


def test_the_generator_reads_its_root(scratch):
    gen = catalog.generator(scratch)
    assert gen.ROOT == scratch.resolve()
    assert gen.files("dog") == catalog.intent_files("dog", (scratch / "domains/dog/intent.yaml").read_text(), scratch)


def test_the_fingerprint_moves_with_what_a_reload_takes(scratch):
    fp = catalog.fingerprint("dog", scratch)
    (scratch / "domains/dog/records").mkdir(exist_ok=True)
    (scratch / "domains/dog/records/s.jsonl").write_text("{}\n")          # not watched
    (scratch / "domains/dog/notes.md").write_text("x")
    assert catalog.fingerprint("dog", scratch) == fp
    p = scratch / "domains/dog/dog.llp"
    p.write_text(p.read_text() + "\n% a comment\n")
    assert catalog.fingerprint("dog", scratch) != fp


def test_apply_writes_the_program_and_an_extension_never_outside(scratch):
    prog = (scratch / "domains/dog/dog.llp").read_text()
    new = prog + "\n% applied\n"
    files = catalog.plan("dog", program=new, extensions={"Pet Tricks": "% an extension\n"}, r=scratch)
    assert [f["path"] for f in files] == ["domains/dog/dog.llp", "domains/dog/extensions/pet_tricks.llp"]
    assert not (scratch / "domains/dog/extensions/pet_tricks.llp").exists()      # plan writes nothing
    before = catalog.fingerprint("dog", scratch)
    out = catalog.apply("dog", program=new, extensions={"Pet Tricks": "% an extension\n"}, r=scratch)
    assert out["written"] == [f["path"] for f in files]
    assert "+% applied" in out["diff"]
    assert (scratch / "domains/dog/dog.llp").read_text() == new
    assert out["fingerprint"] == catalog.fingerprint("dog", scratch) != before
    assert catalog.apply("dog", program=new, r=scratch)["written"] == []          # unchanged: nothing
    with pytest.raises(ValueError):
        catalog.plan("../../etc/x", program="", r=scratch)


def test_apply_intents_generates_and_names_the_spec(scratch):
    d = scratch / "domains/plant"
    (d / "intent.yaml").unlink(missing_ok=True)
    shutil.rmtree(d / "intent", ignore_errors=True)
    mf = d / "domain.yaml"
    mf.write_text("".join(l for l in mf.read_text().splitlines(True) if not l.startswith("intent:")))
    text = catalog.skeleton("plant", scratch)
    out = catalog.apply("plant", intents=text, r=scratch)
    assert set(out["written"]) == {"domains/plant/intent.yaml", "domains/plant/domain.yaml",
                                   *("domains/plant/intent/" + f for f in catalog.generator(scratch).files("plant"))}
    assert mf.read_text().endswith("intent: {spec: intent.yaml}\n")
    gen = catalog.generator(scratch)
    for fn, t in gen.files("plant").items():                  # what `tools/intents.py gen` writes
        assert (d / "intent" / fn).read_text() == t
    with pytest.raises(ValueError):
        catalog.plan("plant", intents="not: [a, mapping", r=scratch)


def test_the_manifest_goes_through_the_loaders_check(scratch):
    with pytest.raises(ValueError, match="unknown key"):
        catalog.plan("dog", manifest={"colour": "brown"}, r=scratch)
    mf = scratch / "domains/dog/domain.yaml"
    old = mf.read_text()
    files = catalog.plan("dog", manifest={"reload": "auto", "line": "a dog: it sits"}, r=scratch)
    text = files[0]["text"]
    assert text.endswith("reload: auto\n") and "line: 'a dog: it sits'\n" in text
    assert text.count("\n") == old.count("\n") + 1                # one line replaced, one appended
    with pytest.raises(ValueError, match="reload is propose or auto"):
        catalog.plan("dog", manifest={"reload": "sometimes"}, r=scratch)


def test_a_new_domain(scratch):
    out = catalog.apply("lamp", program="% the lamp\n", manifest={"display": "the lamp", "records": "records/"},
                        r=scratch)
    assert out["written"] == ["domains/lamp/lamp.llp", "domains/lamp/domain.yaml"]
    assert (scratch / "domains/lamp/domain.yaml").read_text() == \
        "display: the lamp\nrecords: records/\nprogram: lamp.llp\n"
    assert catalog.get("lamp", scratch).program == (scratch / "domains/lamp/lamp.llp").resolve()
    whole = "display: the bell\nprogram: bell.llp\n"
    catalog.apply("bell", program="% the bell\n", manifest=whole, r=scratch)
    assert (scratch / "domains/bell/domain.yaml").read_text() == whole


def _cli(*args, root=None, stdin=None):
    env = dict(os.environ)
    if root:
        env["METIS_CATALOG"] = str(root)
    r = subprocess.run([sys.executable, "-m", "metis_loop_sdk.catalog", *args], capture_output=True, text=True,
                       env=env, input=stdin, timeout=120)
    return r.returncode, json.loads(r.stdout) if r.stdout.strip().startswith(("{", "[")) else r.stdout, r.stderr


def test_the_cli_in_json(scratch):
    rc, rows, _ = _cli("list", "--json", root=scratch)
    assert rc == 0 and json.loads(json.dumps(catalog.index(scratch), default=str)) == rows
    rc, rows, _ = _cli("list", "--consoles", "--json", root=scratch)
    assert rc == 0 and rows == json.loads(json.dumps(catalog.listing(scratch), default=str))
    rc, dog, _ = _cli("get", "dog", "--json", root=scratch)
    assert rc == 0 and dog["fingerprint"] == catalog.fingerprint("dog", scratch) and dog["has"]["intent"]
    rc, sk, _ = _cli("intents", "plant", "--skeleton", "--json", root=scratch)
    assert rc == 0 and sk["skeleton"] == catalog.skeleton("plant", scratch)
    prog = (scratch / "domains/dog/dog.llp").read_text() + "% cli\n"
    rc, dry, _ = _cli("apply", "dog", "--program", "-", "--dry-run", "--json", root=scratch, stdin=prog)
    assert rc == 0 and dry["dry_run"] and [f["path"] for f in dry["files"]] == ["domains/dog/dog.llp"]
    assert "% cli" not in (scratch / "domains/dog/dog.llp").read_text()
    rc, out, _ = _cli("apply", "dog", "--program", "-", "--json", root=scratch, stdin=prog)
    assert rc == 0 and out["written"] == ["domains/dog/dog.llp"] and out["fingerprint"]
    rc, err, _ = _cli("apply", "dog", "--manifest", '{"colour": 1}', "--json", root=scratch)
    assert rc == 1 and "unknown key" in err["error"]
    rc, err, _ = _cli("get", "nosuch", "--json", root=scratch)
    assert rc == 1 and "nosuch" in err["error"]


def test_the_widget_is_package_data():
    for f in catalog.WIDGET_FILES:
        assert (catalog.WIDGET_DIR / f).is_file()
    assert "window.MetisCatalog" in (catalog.WIDGET_DIR / "catalog.js").read_text()
    rc, w, _ = _cli("widget")
    assert rc == 0 and w["url"] == catalog.WIDGET_URL and Path(w["dir"]) == catalog.WIDGET_DIR


def test_the_widget_is_web_catalogs_bytes():
    """The widget lives in metis-loop web/catalog/ (the shared web widgets);
    the SDK carries the same bytes, here (editable: the link) and in an
    installed wheel (CI's sdk-alone job runs this from outside the checkout)."""
    web = Path(os.environ.get("METIS_LOOP_WEB") or Path(__file__).resolve().parents[2] / "web") / "catalog"
    if not web.is_dir():
        pytest.skip(f"no metis-loop web/catalog at {web} (METIS_LOOP_WEB)")
    for f in catalog.WIDGET_FILES:
        assert (catalog.WIDGET_DIR / f).read_bytes() == (web / f).read_bytes()
