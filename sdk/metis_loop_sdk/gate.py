"""metis_loop_sdk.gate — the loop's policy moved into metispy as metis.gate (metis-packages s-65778b98),
re-exported here for one release (removed at r0.2); its CLI stays, as the TypeScript face (ts/gate.ts)
calls it: python -m metis_loop_sdk.gate --state DIR propose|confirm|refuse …

    from metis_loop_sdk import gate     # → from metis import gate
"""
import sys
import warnings

from metis.gate import *  # noqa: F401,F403
from metis.gate import KINDS, NAME, Gate, Refused, main, public  # noqa: F401

warnings.warn("metis_loop_sdk.gate is metis.gate now (metispy >= 0.1.2); it re-exports it until r0.2",
              DeprecationWarning, stacklevel=2)

if __name__ == "__main__":
    sys.exit(main())
