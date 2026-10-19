"""The CATALOG panel (domain-catalog s-2a2bc758 step 1): the index of the
metis-catalog checkout (domains first, display line, what each has) and the
one-click open — program + the host the index names + the notch."""
import re
from pathlib import Path

import pytest

from metis_loop_sdk.catalog import index
from loop.console_serve import ConsoleServer, catalog_root

PAGE = (Path(__file__).resolve().parents[1] / "console/loop_console.html").read_text()


@pytest.fixture
def srv():
    return ConsoleServer(catalog_root())


def test_index_lists_the_domains_first_with_what_they_have(srv):
    es = srv.domains()
    by = {e["path"]: e for e in es}
    kinds = [e["kind"] for e in es]
    assert kinds == sorted(kinds, key=lambda k: k != "domain")          # domains first
    assert len(es) == len(srv.catalogs())                                # every .llp listed
    dog, kit, wf = by["domains/dog/dog"], by["domains/kitchen/kitchen"], by["domains/wildfire/wildfire"]
    assert dog["kind"] == kit["kind"] == wf["kind"] == "domain"
    assert dog["host"] == "dog_host.py:make" and dog["readme"] == "domains/dog/README.md"
    assert dog["line"].startswith("a robot dog") and dog["readme_text"].startswith("# dog")      # the manifest's line
    assert kit["host"] == "metis.domains.kitchen.host:make" and kit["line"].startswith("the kitchen: the first cook")
    assert wf["host"] == "wildfire_host.py:make" and wf["notch"] == "wildfire.notch.json"         # an RDDL world (rddl-worlds)
    assert {k: wf["has"][k] for k in ("host", "notch", "readme")} == {"host": True, "notch": True, "readme": True}
    assert wf["manifest"] == "domains/wildfire/domain.yaml" and dog["has"]["intent"] and not wf["has"]["intent"]
    # drafts and plain catalogs are listed, not as domains; a dir's table row
    # is not lent to its several files
    assert by["domains/rddl/wildfire/iter1-world/base"]["kind"] == "catalog"
    assert by["domains/road/scenes/nav4_instance"]["kind"] == "catalog"          # a scene instance in the parked road package (the key gate)
    assert by["domains/road/road_catalog"]["kind"] == "domain"                   # road (road-collapse): parked, no intents, no host
    assert by["domains/three_pigs/three_pigs"]["kind"] == "domain"              # the fiction ports are domains
    assert "conformance fixtures" not in by["domains/ports/port-proto/clock"]["line"]


def _gym():
    """An interpreter with pyRDDLGym for an RDDL world's host (metis-catalog tools/rddl_host.py)."""
    import os
    import subprocess
    py = os.environ.get("METIS_RDDL_PY") or str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python")
    try:
        return subprocess.run([py, "-c", "import pyRDDLGym"], capture_output=True).returncode == 0
    except OSError:
        return False


@pytest.mark.parametrize("path,spec,overlay", [
    ("domains/dog/dog", "dog_host.py:make", None),
    ("domains/kitchen/kitchen", "metis.domains.kitchen.host:make", None),
    pytest.param("domains/wildfire/wildfire", "wildfire_host.py:make", "wildfire.notch.json",
                 marks=pytest.mark.skipif(not _gym(), reason="no interpreter with pyRDDLGym (its host steps the gym)")),
])
def test_one_click_opens_program_host_and_notch(srv, path, spec, overlay):
    out = srv.open_session("s1", {"llp": path, "host": True})
    assert out.get("status") != "closed", out
    r = srv.shells["s1"]
    assert r.plugin is not None and r.plugin_spec == spec
    assert (overlay in r._overlay_names) if overlay else not r._overlay_names
    post = srv.serve_one("s1", "run 20")["posting"]
    assert post["status"] == "done", post                                # a hosted run posts (metispy wire exo rows)


def test_the_wire_never_names_the_host(srv):
    # without host the program opens alone (wildfire's ports stay unbound: refused, as before)
    assert srv.open_session("s2", {"llp": "domains/wildfire/wildfire"})["status"] == "closed"
    # a spec from the page is ignored: only the index's host attaches
    out = srv.open_session("s3", {"llp": "domains/dog/dog", "host": True, "plugin": "os:system"})
    assert srv.shells["s3"].plugin_spec == "dog_host.py:make", out


def test_page_lists_and_opens_from_the_panel():
    assert 'f.type==="domains"' in PAGE and 'db.doc("meta/domains")' in PAGE
    assert re.search(r'wsSend\(\{ch:"repl",type:"open",llp,host,req', PAGE)
    assert "catalog:{shown:true" in PAGE                                  # the panel shows in both transports
