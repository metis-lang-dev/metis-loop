"""metis_loop_sdk.web — what the loop SDK keeps of its own after the catalog moved into metispy
(metis-packages s-65778b98): the catalog widget the consoles serve (widget/, WIDGET_DIR at
WIDGET_URL, widget_file) and the TypeScript face (ts/, TS_DIR). The catalog itself is
`from metis import catalog`.

    from metis_loop_sdk.web import WIDGET_DIR, WIDGET_URL, widget_file
    python -m metis_loop_sdk.web widget          # {dir, url, files} (the Go console reads it)
"""
from pathlib import Path

WIDGET_DIR = (Path(__file__).resolve().parent / "widget").resolve()   # the checkout: ../../web/catalog
WIDGET_URL = "/sdk/catalog/"          # where a console serves WIDGET_DIR
WIDGET_FILES = ("catalog.js", "catalog.css")

# the workspace widgets (loop-workspace step 4, WORKSPACE.md §6): BUNDLE, TRACE, SURPRISES, RULINGS, LOOP over the
# backend's channels, and the wire they share: the pi loop's ONE frontend (§6.1), served to the metis-loop console on every
# workspace; never copied into another page (the road page stays the road's own UI)
WS_WIDGET_DIR = (Path(__file__).resolve().parent / "workspace").resolve()   # the checkout: ../../web/workspace
WS_WIDGET_URL = "/sdk/workspace/"
WS_WIDGETS = ("bundle", "trace", "surprises", "rulings", "loop")
WS_WIDGET_FILES = ("io.js", "workspace.css") + tuple(f"{w}.js" for w in WS_WIDGETS)

TS_DIR = (Path(__file__).resolve().parent / "ts").resolve()          # the TypeScript face
TS_FILES = ("catalog.ts", "gate.ts", "workspace.ts")   # workspace.ts: metis.catalog.workspace's face (loop-workspace)


def widget_file(name):
    """(text, content type) of one widget file for WIDGET_URL<name>, or None."""
    if name not in WIDGET_FILES:
        return None
    return (WIDGET_DIR / name).read_text(), ("text/javascript; charset=utf-8" if name.endswith(".js")
                                             else "text/css; charset=utf-8")


def ws_widget_file(name):
    """(text, content type) of one workspace widget file for WS_WIDGET_URL<name>, or None."""
    if name not in WS_WIDGET_FILES:
        return None
    return (WS_WIDGET_DIR / name).read_text(), ("text/javascript; charset=utf-8" if name.endswith(".js")
                                                else "text/css; charset=utf-8")


def main(argv=None):
    """python -m metis_loop_sdk.web widget|ts: the directory, the URL and the files, as JSON
    (the Go console's WidgetDir reads `widget`)."""
    import json
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    verb = args[0] if args else ""
    if verb == "widget":
        out = {"dir": str(WIDGET_DIR), "url": WIDGET_URL, "files": list(WIDGET_FILES)}
    elif verb == "workspace":
        out = {"dir": str(WS_WIDGET_DIR), "url": WS_WIDGET_URL, "files": list(WS_WIDGET_FILES), "widgets": list(WS_WIDGETS)}
    elif verb == "ts":
        out = {"dir": str(TS_DIR), "files": list(TS_FILES)}
    else:
        print("usage: python -m metis_loop_sdk.web widget|workspace|ts", file=sys.stderr)
        return 2
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
