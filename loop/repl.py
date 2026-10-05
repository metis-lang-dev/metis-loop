"""Compatibility shim — the loop REPL merged into the metis shell
(one kernel REPL; every UI a wrapper). Interactive: `metis FILE.llp`
(the loop verbs are plain commands there: gate, accept, mine,
narrate, ...). The JSON wire: `metis --json FILE.llp`. The intent
policy and wire dispatcher live in metis.loop.wire; a loop session
drains a queued intent with `intent_posting(shell, line, session)`
and posts the {status, result, json} it returns (CONSOLE §4)."""
from metis.loop.wire import (INTENT_VERBS, dispatch,  # noqa: F401
                             intent_posting, parse_intent, run_intent,
                             serve_json)


def main(argv=None):
    print(__doc__)
    return 2
