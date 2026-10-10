"""Drive the TERMINAL `metis` shell natively (the same entry point a
person types into) with a command script; the session keeps its own
lab-notebook transcript in transcripts/. No internal APIs — the
fixtures speak only REPL verbs, '#plugin' attaches the env."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def drive(llp, lines, name, seed=3):
    """Run `metis LLP --seed SEED` with `lines` on stdin, transcript
    ON -> the shell's stdout (the transcript lands in
    transcripts/NAME.md, replaced each run)."""
    t = HERE / "transcripts" / f"{name}.md"
    t.parent.mkdir(exist_ok=True)
    if t.exists():
        t.unlink()
    script = "\n".join([f"transcript transcripts/{name}.md", *lines,
                        "transcript off", "quit"]) + "\n"
    env = dict(os.environ, METIS_CONFIG="")      # hermetic: no dot file
    res = subprocess.run(
        [sys.executable, "-m", "metis.lang.repl", str(llp),
         "--seed", str(seed)],
        input=script, text=True, capture_output=True, cwd=HERE, env=env,
        timeout=600)
    if res.returncode != 0:
        raise SystemExit(f"metis exited {res.returncode}:\n{res.stderr}")
    return res.stdout


def answers(out):
    """The shell's output split per prompt: answers[k] = what command
    k printed (answers[0] is the banner)."""
    return out.split("llp> ")
