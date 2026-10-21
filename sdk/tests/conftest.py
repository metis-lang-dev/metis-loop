"""The SDK's tests (cwd-root s-ddac2cbf): the fixture catalog is the
installed metis-catalog's own — never a checkout beside this one."""
import os
from pathlib import Path


def installed_catalog() -> Path:
    """$METIS_CATALOG, else the catalog the installed metis-catalog carries:
    its checkout's (pip install -e) or the wheel's (metis_catalog/domains)."""
    env = os.environ.get("METIS_CATALOG")
    if env:
        return Path(env).resolve()
    import metis_catalog
    own = Path(metis_catalog.__file__).resolve().parent
    return own if (own / "domains").is_dir() else own.parent
