#!/usr/bin/env bash
# smoke_wheel.sh DIST [WITH...] — the built SDK wheel in DIST installed into a
# fresh venv outside any checkout, and run there (pi-release s-8e13f6a8): its
# dependencies by name (metispy and metis-catalog from PyPI, unless WITH names
# what satisfies them instead: a sibling checkout before metis-catalog is
# published), metis_loop_sdk from site-packages at pyproject's version, the
# human loop absent, the widget's and the TypeScript face's files in the wheel
# (the face where `catalog ts` says: the agentic loop resolves it from there),
# and the catalog CLI on the installed catalog: root, list, get, intents
# (--skeleton: the root's tools/intents.py), fingerprint. publish.yml runs it.
set -euo pipefail
DIST=$(cd "$1" && pwd)
shift
WITH=()
for w in "$@"; do WITH+=("$(realpath "$w")"); done
HERE=$(cd "$(dirname "$0")/.." && pwd)
V=$(python3 -c "import tomllib, sys; print(tomllib.load(open(sys.argv[1], 'rb'))['project']['version'])" "$HERE/pyproject.toml")
W=$(mktemp -d)
trap 'rm -r "$W"' EXIT
"${PYTHON:-python3}" -m venv "$W/venv"
"$W/venv/bin/pip" install -q "$DIST"/*.whl "${WITH[@]}"
cd "$W"                                   # no checkout on the path
env -u METIS_CATALOG -u PYTHONPATH "$W/venv/bin/python" - "$V" "$HERE/../web/catalog" <<'PY'
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import metis_loop_sdk
from metis_loop_sdk import catalog

version, web = sys.argv[1], Path(sys.argv[2])
assert "site-packages" in metis_loop_sdk.__file__, metis_loop_sdk.__file__
assert metis_loop_sdk.__version__ == version, (metis_loop_sdk.__version__, version)
assert importlib.util.find_spec("loop") is None, "the human loop is installed with the SDK"
for f in catalog.WIDGET_FILES:
    assert (catalog.WIDGET_DIR / f).read_bytes() == (web / f).read_bytes(), f


def cli(*args):
    r = subprocess.run([sys.executable, "-m", "metis_loop_sdk.catalog", *args, "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 0, (args, r.stderr[-800:])
    return json.loads(r.stdout)


ts = cli("ts")
assert "site-packages" in ts["dir"] and (Path(ts["dir"]) / "catalog.ts").is_file(), ts
root = Path(cli("root")["root"])
assert "site-packages" in str(root) and (root / "domains" / "dog" / "domain.yaml").is_file(), root
names = {e["name"] for e in cli("list") if e["kind"] == "domain"}
assert {"dog", "wildfire", "kitchen"} <= names, sorted(names)
assert cli("get", "dog")["name"] == "dog"
assert Path(cli("intents", "dog")["intent"]["spec"]).is_file(), "dog's intent.yaml"
assert "cmd_sit" in cli("intents", "dog", "--skeleton")["commands"], "the root's tools/intents.py"
assert cli("fingerprint", "dog")["fingerprint"]
print("smoke: metis_loop_sdk %s from %s; the face at %s; %d domains at %s"
      % (version, Path(metis_loop_sdk.__file__).parent, ts["dir"], len(names), root))
PY
echo "SMOKE GREEN"
