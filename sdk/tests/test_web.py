"""metis_loop_sdk.web: the loop SDK's own after the catalog moved into metispy (metis-packages
s-65778b98) — the catalog widget and the TypeScript face ship as package data, and the CLI says where."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from metis_loop_sdk import web


def _cli(verb):
    r = subprocess.run([sys.executable, "-m", "metis_loop_sdk.web", verb], capture_output=True, text=True, timeout=60)
    return r.returncode, json.loads(r.stdout) if r.returncode == 0 else None


def test_the_widget_is_package_data():
    for f in web.WIDGET_FILES:
        assert (web.WIDGET_DIR / f).is_file()
    assert "window.MetisCatalog" in (web.WIDGET_DIR / "catalog.js").read_text()
    rc, w = _cli("widget")
    assert rc == 0 and w["url"] == web.WIDGET_URL and Path(w["dir"]) == web.WIDGET_DIR
    text, ctype = web.widget_file("catalog.js")
    assert "window.MetisCatalog" in text and ctype.startswith("text/javascript")
    assert web.widget_file("nosuch.js") is None


def test_the_widget_is_web_catalogs_bytes():
    """The widget lives in metis-loop web/catalog/ (the shared web widgets);
    the SDK carries the same bytes, here (editable: the link) and in an
    installed wheel (CI's sdk-alone job runs this from outside the checkout)."""
    w = Path(os.environ.get("METIS_LOOP_WEB") or Path(__file__).resolve().parents[2] / "web") / "catalog"
    if not w.is_dir():
        pytest.skip(f"no metis-loop web/catalog at {w} (METIS_LOOP_WEB)")
    for f in web.WIDGET_FILES:
        assert (web.WIDGET_DIR / f).read_bytes() == (w / f).read_bytes()


def test_the_typescript_face_is_package_data():
    rc, out = _cli("ts")
    assert rc == 0 and out["files"] == ["catalog.ts", "gate.ts"] and Path(out["dir"]) == web.TS_DIR
    assert (web.TS_DIR / "catalog.ts").read_text().startswith("// metis_loop_sdk/ts/catalog.ts")
    assert (web.TS_DIR / "gate.ts").read_text().startswith("// The loop SDK's gate, TypeScript face")


def test_the_shims_are_gone():
    """metis_loop_sdk.catalog and .gate went at sdk 0.1.14 (the r0.2 removal, brought forward):
    the catalog is metispy's metis.catalog, the gate metis.gate."""
    import importlib.util
    assert importlib.util.find_spec("metis_loop_sdk.catalog") is None
    assert importlib.util.find_spec("metis_loop_sdk.gate") is None
