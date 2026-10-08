"""metis-loop CLI — the web UI for the metispy REPL.

  metis-loop console-serve [--port N] [--bind H] [--mode personal|shared]
                           [--token T]     the Loop Console backend
                                           (pip install metis-loop[console])
  metis-loop repl [LLP] [--seed N] [--json]
                                           the metis shell (delegation:
                                           one kernel REPL, every UI a
                                           wrapper)

The old batch verbs (admit, formalize, replay) merged into the kernel
REPL (gate / formalize / replay there); programmatic use imports
metis.loop (loop.* re-exports it)."""
import argparse
import sys

LEGACY = {
    "admit": "the REPL's `gate` (metis FILE.llp, then: llp <<EOF … gate)",
    "formalize": "the REPL's `formalize` (llm-endpoint drafting + repair)",
    "replay": "the REPL's `record` + `replay` (sink FILE.jsonl first)",
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["console-serve"]:
        # the console's standing backend (docs/CONSOLE-WS.md); needs the
        # `console` extra (websockets)
        from .gateway import main as serve_main
        return serve_main(args[1:])
    if args[:1] and args[0] in LEGACY:
        print(f"metis-loop {args[0]} merged into the metis shell — use "
              f"{LEGACY[args[0]]}; programmatic use: metis.loop",
              file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser(
        prog="metis-loop",
        description="the web UI for the metispy REPL",
        epilog="also: metis-loop console-serve [--port N] [--bind H] "
               "[--mode personal|shared] [--token T] — the Loop Console "
               "backend (pip install metis-loop[console])")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("repl", help="the metis shell (delegation)")
    rp.add_argument("llp", nargs="?",
                    help="the catalog to serve (none = a blank scratch "
                         "world, as `metis` itself)")
    rp.add_argument("--seed", type=int, default=1)
    rp.add_argument("--json", action="store_true",
                    help="JSON-lines wire (one {op, arg} per line) — "
                         "the protocol every UI wraps")
    ns = ap.parse_args(args)
    # one kernel REPL; every UI a wrapper — this verb delegates there
    from metis.lang.repl import main as metis_shell
    return metis_shell((["--json"] if ns.json else [])
                       + ["--seed", str(ns.seed)]
                       + ([ns.llp] if ns.llp else []))


if __name__ == "__main__":
    sys.exit(main())
