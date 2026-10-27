"""metis-loop — the Loop Console backend (the web UI for the metispy
REPL; docs/CONSOLE-WS.md).

  metis-loop [--port N] [--bind H] [--mode personal|shared] [--token T] [--pkg NAME …]

serves the console (pip install metis-loop[console]). The word
`console-serve` is accepted and ignored for compatibility. There is
nothing else here: the interactive shell is `metis` (metispy), the
old batch verbs (admit, formalize, replay) merged into its
gate / formalize / replay, and programmatic use imports metis.loop
(loop.* re-exports it)."""
import sys

POINTERS = {
    "repl": "the shell is `metis [FILE.llp]` (metispy) — no indirection",
    "admit": "the REPL's `gate` (metis FILE.llp, then: llp <<EOF … gate)",
    "formalize": "the REPL's `formalize` (llm-endpoint drafting + repair)",
    "replay": "the REPL's `record` + `replay` (sink FILE.jsonl first)",
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["console-serve"]:        # compat spelling
        args = args[1:]
    if args[:1] and args[0] in POINTERS:
        print(f"metis-loop has no `{args[0]}` — {POINTERS[args[0]]}",
              file=sys.stderr)
        return 2
    if args[:1] in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    from .gateway import main as serve_main
    return serve_main(args)


if __name__ == "__main__":
    sys.exit(main())
