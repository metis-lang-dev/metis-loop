"""The consoles' shell (domain-catalog s-2a2bc758 step 3): the page's top
bar, docks, strip and colours are fsttm-web's lib/shell.css + lib/shell.js,
one source for this console and the metis-agent console. The page loads
them relative (lib/…); the gateway and dev_serve serve them at /lib/ from:

  $FSTTM_WEB_LIB, else the fsttm_web package (pip install -e ../fsttm-web;
  run.sh does it), else the sibling checkout perotheia-packages/fsttm-web/lib.
"""
import os
from pathlib import Path

SIBLING = Path(__file__).resolve().parents[2] / "fsttm-web" / "lib"
TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json"}


def lib_dir():
    env = os.environ.get("FSTTM_WEB_LIB")
    if env:
        return Path(env)
    try:
        import fsttm_web
        return Path(fsttm_web.LIB)
    except (ImportError, RuntimeError):
        return SIBLING


def check():
    """At startup: the shell is there, or the one-line fix (FileNotFoundError)."""
    d = lib_dir()
    if not (d / "shell.css").is_file() or not (d / "shell.js").is_file():
        raise FileNotFoundError(f"the consoles' shell (fsttm-web lib/shell.css, shell.js) is not at {d}: "
                                "pip install -e ../fsttm-web, or set FSTTM_WEB_LIB")
    return d


def get(name):
    """(text, content type) for /lib/<name>, or None: one flat file of the
    library (.js, .css, .json)."""
    if not name or "/" in name or name.startswith("."):
        return None
    f = lib_dir() / name
    t = TYPES.get(f.suffix)
    if not t or not f.is_file():
        return None
    return f.read_text(), t
