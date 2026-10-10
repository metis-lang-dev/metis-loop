"""Scope fixture plugin (PLUGIN-PORTS.md target 1): the REAL gap
behind the `rss` weight port. The env's clock closes the gap 18 m ->
6 m on the first beat — the time face moves the real value; the port
re-prices P[crash] 0.3 -> 0.9 from the same qualitative state.
PURITY: rss reads (args, declared scope {gclose}, env) only; the env
mutates only in tick."""


class SensorEnv:
    GAPS = (18.0, 6.0)             # the real gap per env beat

    def __init__(self, case):
        self.beat = 0

    @property
    def gap_m(self):
        return self.GAPS[min(self.beat, len(self.GAPS) - 1)]

    # -- binding (pure given scope + env) ------------------------------
    def rss(self, args, counts):
        close = counts.get("gclose", 0) > 0     # the declared read
        return 0.9 if (close and self.gap_m < 10) else \
            (0.3 if close else 0.01)

    def bind(self, reg):
        reg.weight("rss", self.rss)

    # -- faces ----------------------------------------------------------
    def tick(self, counts):
        if self.beat >= len(self.GAPS) - 1:
            return None                # the gap schedule is over
        self.beat += 1
        return []                      # a quiet beat: only the gap moved

    def on_event(self, name, args):
        pass                           # no actuation in this fixture

    def snapshot(self):
        return self.beat

    def restore(self, snap):
        self.beat = snap


def make(case):
    return SensorEnv(case)
