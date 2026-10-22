# pytest from any cwd (metis-loop's root too): pi/ on the path, so the tests' `policy` package imports.
# Without it, a run from the root made the world tests' import guard skip as "no world" (the architect, 2026-10-22).
import sys
from pathlib import Path

HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
