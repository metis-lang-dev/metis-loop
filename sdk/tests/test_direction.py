"""The direction rule (brief/repo-alignment.md §1): the SDK imports
metispy (`metis`) and nothing else of ours — not even metis_catalog since
metis-packages (the catalog's access is metis.catalog). CI's
`sdk-alone` job also installs it into a fresh venv without the human loop,
so an import of `loop` would fail there as well."""
import ast
import importlib
import pkgutil
from pathlib import Path

import metis_loop_sdk

PKG = Path(metis_loop_sdk.__file__).parent
OURS_FORBIDDEN = {"loop", "metis_agent", "tools", "console", "metis_catalog"}


def _imports(path: Path):
    tree = ast.parse(path.read_text(), str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_the_sdk_imports_nothing_of_ours_but_metispy():
    bad = {(str(p.relative_to(PKG)), m) for p in PKG.rglob("*.py")
           for m in _imports(p) if m in OURS_FORBIDDEN}
    assert not bad, f"the SDK imports a consumer: {sorted(bad)}"


def test_every_module_imports():
    for m in pkgutil.walk_packages([str(PKG)], "metis_loop_sdk."):
        importlib.import_module(m.name)


def test_version():
    """__version__ is pyproject's, the version the sdk-vX.Y.Z tag names (publish.yml)."""
    import tomllib
    pp = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert metis_loop_sdk.__version__ == tomllib.loads(pp.read_text())["project"]["version"] == "0.1.12"
