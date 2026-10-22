"""metis_loop_sdk.web — what the loop SDK keeps of its own after the catalog moved into metispy
(metis-packages s-65778b98): the catalog widget the consoles serve (widget/, WIDGET_DIR at
WIDGET_URL, widget_file) and the TypeScript face (ts/, TS_DIR). metis_loop_sdk.catalog re-exports
these until r0.2; the catalog itself is `from metis import catalog`.

    from metis_loop_sdk.web import WIDGET_DIR, WIDGET_URL, widget_file
"""
from pathlib import Path

WIDGET_DIR = (Path(__file__).resolve().parent / "widget").resolve()   # the checkout: ../../web/catalog
WIDGET_URL = "/sdk/catalog/"          # where a console serves WIDGET_DIR
WIDGET_FILES = ("catalog.js", "catalog.css")

TS_DIR = (Path(__file__).resolve().parent / "ts").resolve()          # the TypeScript face
TS_FILES = ("catalog.ts", "gate.ts")


def widget_file(name):
    """(text, content type) of one widget file for WIDGET_URL<name>, or None."""
    if name not in WIDGET_FILES:
        return None
    return (WIDGET_DIR / name).read_text(), ("text/javascript; charset=utf-8" if name.endswith(".js")
                                             else "text/css; charset=utf-8")
