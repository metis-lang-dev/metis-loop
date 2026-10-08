"""Wrapper-repo gates: the compatibility shims resolve to the kernel
(metis.loop), and the CLI bindings still bind. The loop's full suite
lives with the kernel: metispy/tests/loop/."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANG = Path(os.environ.get(
    "METIS_LANG", ROOT.parent / "metis-lang")).resolve()
TEXT = "%% market coin: a mark trades on the coin flip outcome."


def test_shims_resolve_to_the_kernel():
    import loop
    import loop.bus
    import loop.core
    import loop.llm
    import loop.narrate
    import loop.node
    import loop.ollama
    import loop.repl
    import metis.loop.bus
    import metis.loop.node
    import metis.loop
    assert loop.admit is metis.loop.admit
    assert loop.repl.run_intent.__module__ == "metis.loop.wire"
    assert loop.bus.Broker is metis.loop.bus.Broker
    assert loop.node.serve is metis.loop.node.serve


def test_cli_is_the_console_and_points_elsewhere(capsys):
    """metis-loop IS console-serve; repl/admit/formalize/replay say
    where they went instead of pretending to be a second loop."""
    from loop.cli import main
    for verb in ("repl", "admit", "formalize", "replay"):
        rc = main([verb, "x"])
        err = capsys.readouterr().err
        assert rc == 2 and f"no `{verb}`" in err
    assert main(["--help"]) == 0
    assert "Loop Console backend" in capsys.readouterr().out
