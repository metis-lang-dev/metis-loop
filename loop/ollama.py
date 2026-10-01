"""Compatibility shim — moved to metis.loop.ollama (the command
form `python -m loop.ollama` still works)."""
from metis.loop.ollama import *           # noqa: F401,F403
from metis.loop.ollama import main        # noqa: F401

if __name__ == "__main__":
    import sys
    sys.exit(main())
