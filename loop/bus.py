"""Compatibility shim — the loop bus lives with the kernel
(metis.loop.bus): broker on one named pipe, dict-as-blackboard,
(src, epoch, seq) channels. The command form
`python -m loop.bus` still works."""
from metis.loop.bus import *              # noqa: F401,F403
from metis.loop.bus import (Broker, BusClient, Rx, Tx,  # noqa: F401
                            bus_dir, ingress_path, main)

if __name__ == "__main__":
    import sys
    sys.exit(main())
