"""The CATALOG panel's index (domain-catalog s-2a2bc758): the catalog's own
loader, metis_catalog (metis-catalog's domain.yaml manifests, and for a
.llp with none what it has read off the checkout) — the list both consoles
show. The page names a catalog, never a host spec: the index's host for that
checkout file is attached as an operator's --host (metispy D4)."""
import sys
from pathlib import Path


def _mc():
    try:
        import metis_catalog
    except ImportError:          # the sibling checkout (perotheia-packages/metis-catalog)
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "metis-catalog"))
        import metis_catalog
    return metis_catalog


def index(root):
    return _mc().index(root)


def host_of(root, rel):
    """The host the index names for the checkout catalog rel (no .llp), or None."""
    return next((e["host"] for e in index(root) if e.get("path") == rel), None)


def readme_head(root, rel, limit=1600):
    return _mc().readme_head(rel, limit, r=root)
