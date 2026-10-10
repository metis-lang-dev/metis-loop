"""Real-valued fixture plugin (PLUGIN-PORTS.md target 2 shape): the
reservoir's REAL level lives here; the catalog is qualitative (highc
class, inflow/spill/store tokens). prain prices rain from the env's
season clock (time-dependent), pspill from the real level behind the
declared highc read. tick = one day: the day's check token and the
level's class as do-lines. on_event = actuation: storing raises the
level, a dry day draws it down, a near-full level triggers a release
(the env acts back on itself). PURITY: ports read (args, declared
scope, env) only; the env mutates only in tick/on_event."""
import math


class ReservoirEnv:
    DAYS = 14

    def __init__(self, case):
        self.level = 6.0          # meters — REAL, never in the measure
        self.day = 0
        self.releases = ()        # days a release fired (actuation log)

    # -- port bindings (pure given env snapshot) ------------------------
    def prain(self, args, counts):
        season = 0.5 * (1 + math.sin(self.day / 3.0))
        return 0.15 + 0.6 * season

    def pspill(self, args, counts):
        if counts.get("highc", 0) == 0:    # declared-scope read
            return 0.0
        return min(0.9, 0.2 + (self.level - 8.0) / 3.0)

    def bind(self, reg):
        reg.weight("prain", self.prain).weight("pspill", self.pspill)

    # -- the faces --------------------------------------------------------
    def tick(self, counts):
        if self.day + 1 >= self.DAYS:
            return None                    # the 14-day episode is over
        self.day += 1
        dos = ["+ck"]
        high = self.level >= 8.0
        if high and not counts.get("highc"):
            dos.append("+highc")
        elif not high and counts.get("highc"):
            dos.append("-highc")
        return dos

    def on_event(self, name, args):
        if name == "store":
            self.level = min(10.0, self.level + 1.5)
        elif name == "dry":
            self.level = max(0.0, self.level - 0.8)
        if self.level > 9.0:               # actuation: scheduled release
            self.level -= 3.0
            self.releases += (self.day,)

    def snapshot(self):
        return (self.level, self.day, self.releases)

    def restore(self, snap):
        self.level, self.day, self.releases = snap


def make(case):
    return ReservoirEnv(case)
