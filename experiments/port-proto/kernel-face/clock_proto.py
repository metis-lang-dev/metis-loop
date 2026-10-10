"""Time fixture (PLUGIN-PORTS.md target 3): a clock-world driven
through the LIVE Repl. The env's tick injects exogenous atoms as
do-interventions on a schedule (business hours, customer arrivals) —
the INPUT face as an intervention stream, first-class in the ledger,
so log/why see them. The REPL plugin loop (opus: subject
port-plugins) will do exactly this natively on '#plugin'."""
import io
import re
from pathlib import Path

from metis.lang.repl import Repl

HERE = Path(__file__).parent


class ShopClock:
    """The plugin twin's tick face: open 9-12, customers on schedule."""
    OPEN, SHUT = 9, 13
    ARRIVALS = {10: 1, 11: 2, 14: 1}      # hour -> customers

    def tick(self, hour, counts):
        dos = []
        if hour == self.OPEN:
            dos += ["-doorshut", "+dooropen"]
        if hour == self.SHUT:
            dos += ["-dooropen", "+doorshut"]
        dos += ["+customer"] * self.ARRIVALS.get(hour, 0)
        return dos


out = io.StringIO()
r = Repl(HERE / "clock.llp", seed=3, stdout=out)
env = ShopClock()
for hour in range(8, 16):
    for d in env.tick(hour, r.counts):
        r.onecmd("do " + d)
    # let the world settle: serve/lose fire while enabled. GUARD,
    # don't probe-step: do_step at quiescence latches stage=DONE
    # (repl.py) and the world never revives — FINDING for the plugin
    # work: exogenous tick input must revive a quiescent world.
    while r._candidates():
        r.onecmd("step")
    print(f"{hour:02d}:00  "
          f"open={r.counts.get('dooropen', 0)} "
          f"sales={r.counts.get('sale', 0)} "
          f"missed={r.counts.get('missed', 0)}")

assert r.counts.get("sale", 0) == 3, r.counts
assert r.counts.get("missed", 0) == 1, r.counts

# the interventions are first-class: the ledger and the causal
# instruments see them
out.truncate(0), out.seek(0)
r.onecmd("log")
log = out.getvalue()
print("\n-- ledger tail (exogenous dos + fired events):")
print("\n".join(log.strip().splitlines()[-8:]))
out.truncate(0), out.seek(0)
r.onecmd("why missed")
why = out.getvalue()
print("\n-- why missed:")
print(why.strip()[:400])
assert re.search(r"do \+customer|lose", why)
print("\nOK: 3 sales in hours, 1 missed after close — exogenous "
      "time-driven input, visible to the instruments.")
