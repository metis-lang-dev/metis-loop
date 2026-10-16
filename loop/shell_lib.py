"""The console's shell: the page's top bar, docks, strip and colours are
console/lib/shell.css + console/lib/shell.js, this repo's own copy (shell-copy
s-7c739dd7: independent repos keep copies, never a dependency for look and
feel; the metis-agent console keeps its own). The page loads them relative
(lib/…); the gateway and dev_serve serve them at /lib/ from console/lib/.
"""
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "console" / "lib"
TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json"}


def lib_dir():
    return LIB


def check():
    """At startup: the shell is there, or the one-line fix (FileNotFoundError)."""
    d = lib_dir()
    if not (d / "shell.css").is_file() or not (d / "shell.js").is_file():
        raise FileNotFoundError(f"the console's shell (console/lib/shell.css, shell.js) is not at {d}: "
                                "the checkout is incomplete")
    return d


def get(name):
    """(text, content type) for /lib/<name>, or None: one flat file of
    console/lib/ (.js, .css, .json)."""
    if not name or "/" in name or name.startswith("."):
        return None
    f = lib_dir() / name
    t = TYPES.get(f.suffix)
    if not t or not f.is_file():
        return None
    return f.read_text(), t
