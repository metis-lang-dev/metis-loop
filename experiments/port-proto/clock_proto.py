"""Time fixture (PLUGIN-PORTS.md target 3), NATIVE: clock.llp carries
'#plugin clock_plugin:make'; the terminal shell's own loop ticks the
env whenever the world is quiet (G6: quiet, not dead) and applies each
beat's do-lines as an [env] row — exogenous input, first-class in the
ledger, the graph and `why`, out of the likelihood. Transcript:
transcripts/clock.md. (The kernel-face driver this replaces is kept
in kernel-face/.)"""
import re

from _drive import HERE, answers, drive

out = drive(HERE / "clock.llp", [
    "events",             # quiescent at 08:00 — the env will tick
    "run 100",            # the whole business day, natively
    "state",
    "log",
    "why missed",
    "graph",
    "whatif 10 do(-doorshut) do(+dooropen) query sale @frame",
    "narrate user",
], "clock")
a = answers(out)
print(out)
assert "the env ticks on step/run" in a[2], a[2]
assert re.search(r"missed\s+·", a[4]) and re.search(r"sale\s+:3", a[4])
log = a[5]
assert "do +customer 2  [env]" in log and "8 env rows" in log, log
assert "likelihood 1 over 4 sampled steps" in log
why = a[6]
assert "do +customer" in why and "lose" in why, why
assert "P = 1" in a[8]            # door held open at #10: the sale
print("\nOK: 3 sales in hours, 1 missed after close — the env's clock "
      "drove the world natively through '#plugin'; the instruments "
      "see the exogenous stream.")
