"""The direction rule (brief/repo-alignment.md §1): the SDK imports
metis_catalog and metispy (`metis`) and nothing else of ours. CI's
`sdk-alone` job also installs it into a fresh venv without the human loop,
so an import of `loop` would fail there as well."""
import ast
import importlib
import pkgutil
from pathlib import Path

import metis_loop_sdk

PKG = Path(metis_loop_sdk.__file__).parent
OURS_FORBIDDEN = {"loop", "metis_agent", "tools", "console"}


def _imports(path: Path):
    tree = ast.parse(path.read_text(), str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_the_sdk_imports_nothing_of_ours_but_the_catalog_and_metispy():
    bad = {(str(p.relative_to(PKG)), m) for p in PKG.rglob("*.py")
           for m in _imports(p) if m in OURS_FORBIDDEN}
    assert not bad, f"the SDK imports a consumer: {sorted(bad)}"


def test_every_module_imports():
    for m in pkgutil.walk_packages([str(PKG)], "metis_loop_sdk."):
        importlib.import_module(m.name)


def test_version():
    assert metis_loop_sdk.__version__ == "0.1.0"
