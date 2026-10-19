"""The console over the selected packages (catalog-packages s-a2c529d6, part B):
each of dog, plant, kitchen, nav and love_triangle opens from the CATALOG
panel with the host its index row names (none for love_triangle), runs, and
posts. nav's host steps the IPPC gym: it skips where no interpreter has
pyRDDLGym ($METIS_RDDL_PY, else the packages' .venv). The SDK's verbs over the
same packages: sdk/tests/test_selected_packages.py (its own name: one module name per run)."""
import os
import subprocess
from pathlib import Path

import pytest

from metis_loop_sdk.catalog import index
from loop.console_serve import ConsoleServer, catalog_root

SELECTED = ["dog", "plant", "kitchen", "nav", "love_triangle"]


def _gym():
    py = os.environ.get("METIS_RDDL_PY") or str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python")
    try:
        return subprocess.run([py, "-c", "import pyRDDLGym"], capture_output=True).returncode == 0
    except OSError:
        return False


if not _gym() and os.environ.get("METIS_LOOP_REQUIRE_GYM"):      # CI installs it: nav must run there
    raise RuntimeError("METIS_LOOP_REQUIRE_GYM: no interpreter with pyRDDLGym ($METIS_RDDL_PY)")


@pytest.fixture(scope="module")
def srv():
    return ConsoleServer(catalog_root())


@pytest.mark.parametrize("name", [pytest.param(n, marks=pytest.mark.skipif(
    n == "nav" and not _gym(), reason="no interpreter with pyRDDLGym (nav's host steps the gym)")) for n in SELECTED])
def test_a_selected_package_opens_with_its_host_and_runs(srv, name):
    row = next(e for e in index(catalog_root()) if e["name"] == name and e["kind"] == "domain")
    sid = "sel-" + name
    out = srv.open_session(sid, {"llp": row["path"], "host": True})
    assert out.get("status") in ("running", "quiescent"), out
    r = srv.shells[sid]
    assert r.plugin_spec == row["host"] if row["host"] else r.plugin is None
    post = srv.serve_one(sid, "run 20")["posting"]
    assert post["status"] == "done", post
    assert srv.serve_one(sid, "reset")["posting"]["epoch"] == 2
