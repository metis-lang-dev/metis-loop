"""The CATALOG panel's index (domain-catalog s-2a2bc758): the catalog's own
loader, metis_catalog (metis-catalog's domain.yaml manifests, and for a
.llp with none what it has read off the checkout) — the list both consoles
show. The page names a catalog, never a host spec: the index's host for that
checkout file is attached as an operator's --host (metispy D4)."""
import sys
from pathlib import Path


SIBLING = Path(__file__).resolve().parents[2] / "metis-catalog"
INSTALL = ("the catalog's loader is missing: pip install -e " + str(SIBLING)
           + "  (metis-loop/run.sh does it; it needs pyyaml)")


def _mc():
    try:
        import metis_catalog
    except ImportError:          # the sibling checkout (perotheia-packages/metis-catalog)
        if str(SIBLING) not in sys.path:
            sys.path.insert(0, str(SIBLING))
        try:
            import metis_catalog
        except ImportError as e:  # the package or its pyyaml
            raise ImportError(f"{INSTALL} — {e}") from None
    return metis_catalog


def check():
    """At startup: the loader imports, or the one-line fix (an ImportError)."""
    _mc()


def index(root):
    return _mc().index(root)


def host_of(root, rel):
    """The host the index names for the checkout catalog rel (no .llp), or None."""
    return next((e["host"] for e in index(root) if e.get("path") == rel), None)


def readme_head(root, rel, limit=1600):
    return _mc().readme_head(rel, limit, r=root)
