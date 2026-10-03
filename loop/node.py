"""Compatibility shim — the bus node shim lives with the kernel
(metis.loop.node): one `metis --json` world served on the bus. The
command form `python -m loop.node NAME WORLD.llp` still works."""
from metis.loop.node import main, serve   # noqa: F401

if __name__ == "__main__":
    import sys
    sys.exit(main())
