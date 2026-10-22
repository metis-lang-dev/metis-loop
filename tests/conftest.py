"""The loop's tests (cwd-root s-ddac2cbf): the console serves its cwd, so
a test that reads the catalog's own domains (three_pigs, dog, plant …) names
it — $METIS_CATALOG, else the installed metis-catalog's own catalog (its
checkout installed -e, or the wheel's), never a checkout beside this one.
A test on a scratch root passes it (ConsoleServer(tmp_path)) or chdir's there."""
import os
from pathlib import Path


def installed_catalog() -> Path:
    env = os.environ.get("METIS_CATALOG")
    if env:
        return Path(env).resolve()
    from metis.catalog.manifests import data_dir      # metispy's: the installed catalog's data, unimported
    own = data_dir()
    return own if (own / "domains").is_dir() else own.parent


os.environ["METIS_CATALOG"] = str(installed_catalog())
