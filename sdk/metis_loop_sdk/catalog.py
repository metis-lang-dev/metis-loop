"""metis_loop_sdk.catalog — the catalog's access moved into metispy as metis.catalog (metis-packages
s-65778b98), re-exported here for one release (removed at r0.2). What stays metis-loop's own is here:
the TypeScript face (ts/, TS_DIR) and the catalog widget (widget/, WIDGET_DIR, widget_file), which
live in metis_loop_sdk.web (re-exported here), and the CLI's `ts` and `widget` verbs beside
metis.catalog's.

    from metis_loop_sdk import catalog     # → from metis import catalog
    python -m metis_loop_sdk.catalog …     # metis.catalog's CLI, plus ts and widget (the TS face calls this one)
"""
import sys
import warnings
from pathlib import Path

from metis import catalog as _catalog
from metis.catalog import *  # noqa: F401,F403
from metis.catalog import (STATE, Domain, ManifestError, _r, _text, data_dir, describe, generator,  # noqa: F401
                           installed, loader, root, state)

warnings.warn("metis_loop_sdk.catalog is metis.catalog now (metispy >= 0.1.2); it re-exports it until r0.2",
              DeprecationWarning, stacklevel=2)

from .web import TS_DIR, TS_FILES, WIDGET_DIR, WIDGET_FILES, WIDGET_URL, widget_file  # noqa: E402,F401  (the loop's own: metis_loop_sdk.web)


def _installed_tools() -> Path:
    """The installed metis-catalog's tools/ (kept for one release: the intent generator is metis.intents)."""
    return installed()["tools"]


def main(argv=None):
    return _catalog.main(argv, prog="python -m metis_loop_sdk.catalog", extra={
        "widget": ("the catalog widget's directory, URL and files",
                   lambda: {"dir": str(WIDGET_DIR), "url": WIDGET_URL, "files": list(WIDGET_FILES)}),
        "ts": ("the TypeScript face's directory and files", lambda: {"dir": str(TS_DIR), "files": list(TS_FILES)}),
    })


if __name__ == "__main__":
    sys.exit(main())
