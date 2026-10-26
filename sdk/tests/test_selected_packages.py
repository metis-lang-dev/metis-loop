"""The loop SDK over the selected packages (catalog-packages s-a2c529d6, part B):
every verb the loop runs on a package, on each of dog (intents + host), plant
(an extension), kitchen (a pair: take refuses it by name), nav (an RDDL world:
the program includes its lifted domain) and bridge (a puzzle world, no host, no
intents). Unit level: the files as the catalog has them, written into scratch
catalogs; no model, no gym.

The catalog is the installed metis-catalog's own (or $METIS_CATALOG)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from metis import catalog

from conftest import installed_catalog

CAT = installed_catalog()
if not (CAT / "domains").is_dir():
    pytest.skip(f"no metis-catalog domains at {CAT} (METIS_CATALOG)", allow_module_level=True)

SELECTED = ["dog", "plant", "kitchen", "nav", "bridge"]   # bridge, not love_triangle: the Ceptre ports are not in the wheel (ceptre-carveout)
# what take refuses, by the manifest key it names (the files take does not carry)
NOT_TAKEN = {"kitchen": "agent, pair, serves"}

METISC = catalog.metisc()
if not METISC and os.environ.get("METIS_LOOP_REQUIRE_METISC"):
    raise RuntimeError("METIS_LOOP_REQUIRE_METISC: no metisc (METISC or PATH)")
needs_metisc = pytest.mark.skipif(not METISC, reason="no metisc (METISC or PATH)")

IGNORE = shutil.ignore_patterns("records", "build", "__pycache__")


def _rel(name):
    """The package's directory in the catalog, as the loader finds it (domains/<name>, or
    nested: the Ceptre ports are domains/ceptre/<name>)."""
    return Path(catalog.loader().get(name, CAT).dir).resolve().relative_to(Path(CAT).resolve())


def _scratch(root, name):
    """A scratch catalog holding the package as the catalog has it, and the intent generator."""
    shutil.copytree(CAT / _rel(name), root / _rel(name), ignore=IGNORE)
    if not (root / "tools").exists():
        shutil.copytree(CAT / "tools", root / "tools", ignore=IGNORE)
    return root


def _tree(d):
    """{path relative to d: bytes} of a package's files (no records/, build/)."""
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*"))
            if p.is_file() and not {"records", "build", "__pycache__"} & set(p.relative_to(d).parts)}


@pytest.fixture(params=SELECTED)
def name(request):
    try:
        _rel(request.param)
    except KeyError:
        pytest.fail(f"{request.param}: not a package in {CAT}: change SELECTED with the catalog")
    return request.param


def test_get_is_the_loaders_and_the_cli_says_it(name):
    mc = catalog.loader()
    d = catalog.get(name, CAT)
    assert d.program == mc.get(name, CAT).program and Path(d.program).is_file()
    assert catalog.fingerprint(name, CAT) == catalog.fingerprint(name, CAT)
    assert any(e["name"] == name and e["kind"] == "domain" for e in catalog.index(CAT))
    r = subprocess.run([sys.executable, "-m", "metis.catalog", "--root", str(CAT), "get", name, "--json"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    import json
    got = json.loads(r.stdout)
    assert got["name"] == name and got["fingerprint"] == catalog.fingerprint(name, CAT)


def test_take_then_apply_writes_the_package_byte_for_byte(name, tmp_path):
    src = _scratch(tmp_path / "src", name)
    dst = tmp_path / "dst"
    shutil.copytree(CAT / "tools", dst / "tools", ignore=IGNORE)
    (dst / "domains").mkdir()
    if name in NOT_TAKEN:
        with pytest.raises(ValueError, match=f"names {NOT_TAKEN[name]}, which take does not carry"):
            catalog.take(name, src, dst)
        return
    if _rel(name) != Path("domains", name):
        # a nested package (the Ceptre ports, domains/ceptre/<name>) is not taken: out of its
        # directory it would leave its license behind (ceptre-carveout s-76664d26)
        with pytest.raises(ValueError, match=f"take brings a domain from domains/{name}/"):
            catalog.take(name, src, dst)
        return
    for p in (src / _rel(name) / "intent").glob("*"):
        if not p.stat().st_size:
            p.unlink()                      # an empty generated file (plant-spoken.txt): take writes none
    kw = catalog.take(name, src, dst)
    out = catalog.apply(name, r=dst, **kw)
    assert out["fingerprint"] == catalog.fingerprint(name, src)
    a, b = _tree(src / _rel(name)), _tree(dst / "domains" / name)      # apply writes a new package at domains/<name>
    carried = {f for f in a if f in b}
    assert {f: b[f] for f in carried} == {f: a[f] for f in carried}
    # what take leaves behind is only what its docstring says it does not carry: intent/ (apply generates
    # it again), the package's own cases/ (its hand-written tests) and documents beside its README
    left = sorted(set(a) - set(b))
    assert all(not f.endswith((".llp", ".py", ".yaml", ".json")) or f.startswith(("intent/", "cases/")) for f in left), left
    # the same write again changes nothing
    assert catalog.plan(name, r=dst, **kw) == []


def test_a_plan_of_the_package_as_it_is_writes_nothing(name, tmp_path):
    r = _scratch(tmp_path, name)
    d = catalog.get(name, r)
    prog = Path(d.program).read_text()
    exts = {Path(e).stem: Path(e).read_text() for e in d.extensions()}
    assert catalog.plan(name, program=prog, extensions=exts or None, r=r) == []


@needs_metisc
def test_an_edit_and_its_reverse_give_back_the_files_bytes(name, tmp_path):
    r = _scratch(tmp_path, name)
    d = catalog.get(name, r)
    p = Path(d.program)
    rel = p.relative_to(d.dir).as_posix()
    before = _tree(r / _rel(name))
    text = p.read_text()
    line = next(l for l in reversed(text.splitlines()) if l.strip() and text.count(l) == 1)
    catalog.apply(name, **catalog.edit(name, rel, line, line + "\n% catalog-packages: an edit", r=r), r=r)
    assert "% catalog-packages: an edit" in p.read_text()
    catalog.apply(name, **catalog.edit(name, rel, line + "\n% catalog-packages: an edit", line, r=r), r=r)
    assert _tree(r / _rel(name)) == before


def test_the_bundle_builds(name, tmp_path):
    r = _scratch(tmp_path, name)
    out = catalog.build(name, r)
    assert out and (r / _rel(name) / "build").is_dir(), out
    assert any((r / _rel(name) / "build").rglob("*.metis")), out
