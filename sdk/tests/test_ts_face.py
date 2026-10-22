"""The TypeScript face (metis_loop_sdk/ts/catalog.ts) against this CLI: tests/ts/catalog.test.ts
under node's test runner (node >= 22.6, --experimental-strip-types). Node: $NODE, else `node`
on PATH (never one beside a checkout: cwd-root s-ddac2cbf); none, the test skips
(METIS_LOOP_REQUIRE_NODE=1, as CI sets it: it fails instead)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import installed_catalog

HERE = Path(__file__).resolve().parent
CAT = installed_catalog()


def node():
    for n in (os.environ.get("NODE"), shutil.which("node")):
        if not n or not Path(n).is_file():
            continue
        v = subprocess.run([str(n), "-p", "process.versions.node"], capture_output=True, text=True).stdout.strip()
        if tuple(int(x) for x in v.split(".")[:2]) >= (22, 6):
            return str(n)
    return None


def test_the_typescript_face_at_parity_with_the_cli():
    n = node()
    if not n:
        if os.environ.get("METIS_LOOP_REQUIRE_NODE") == "1":
            pytest.fail("no node >= 22.6 for the TypeScript face (NODE or PATH)")
        pytest.skip("no node >= 22.6 for the TypeScript face")
    if not (CAT / "domains").is_dir():
        pytest.skip(f"no metis-catalog checkout at {CAT}")
    env = {k: v for k, v in os.environ.items() if k != "METIS_CATALOG"}
    from metis_loop_sdk import catalog
    # the installed face (the sdk-alone job: site-packages), driven against the installed CLI
    env.update(METIS_LOOP_SDK_PY=sys.executable, CAT=str(CAT), METIS_LOOP_SDK_TS=str(catalog.TS_DIR / "catalog.ts"),
               METIS_LOOP_SDK_GATE_TS=str(catalog.TS_DIR / "gate.ts"))
    for t in ("catalog.test.ts", "gate.test.ts"):          # the catalog's face, the gate's (loop-parity)
        p = subprocess.run([n, "--experimental-strip-types", "--no-warnings", "--test", str(HERE / "ts" / t)],
                           capture_output=True, text=True, env=env, timeout=600)
        assert p.returncode == 0, t + ": " + p.stdout[-4000:] + p.stderr[-2000:]
