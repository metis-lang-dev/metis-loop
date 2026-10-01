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
    import loop.core
    import loop.llm
    import loop.narrate
    import loop.ollama
    import loop.repl
    import metis.loop
    assert loop.admit is metis.loop.admit
    assert loop.repl.run_intent.__module__ == "metis.loop.wire"


def test_cli_admit(tmp_path, capsys):
    from loop.cli import main
    t = tmp_path / "t.md"
    t.write_text(TEXT)
    rc = main(["admit", str(t), str(LANG / "corpus/packmark.llp"),
               "--base", str(LANG / "corpus/packbase.llp"),
               "--scenario", "coin=1,mkt=1", "--steps", "4"])
    out = capsys.readouterr().out
    assert rc == 0 and "ok=True" in out and "diff" in out
