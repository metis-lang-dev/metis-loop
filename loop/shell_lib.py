"""The console's shell: the page's top bar, docks, strip and colours are
console/lib/shell.css + console/lib/shell.js, this repo's own copy (shell-copy
s-7c739dd7: independent repos keep copies, never a dependency for look and
feel; the metis-agent console keeps its own). The page loads them relative
(lib/…); the gateway serves them at /lib/ from console/lib/.

Behind them, at the same /lib/, fsttm-web's library from the installed fsttm_web package (console-voice
s-dc1f184c: the voice widget in the band and the DIALOG dock, served as metis-agent's console serves it, never
copied): a name console/lib/ lacks is fsttm-web's, when the package is installed.
"""
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "console" / "lib"


def fsttm_lib():
    """fsttm-web's lib/ from the installed fsttm_web package, or None (not installed: the page has no voice)."""
    try:
        import fsttm_web
    except ImportError:
        return None
    d = Path(fsttm_web.LIB)
    return d if d.is_dir() else None
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
    console/lib/ (.js, .css, .json), else of fsttm-web's lib/."""
    if not name or "/" in name or name.startswith("."):
        return None
    t = TYPES.get(Path(name).suffix)
    if not t:
        return None
    for d in (lib_dir(), fsttm_lib()):
        if d is not None and (d / name).is_file():
            return (d / name).read_text(), t
    return None
