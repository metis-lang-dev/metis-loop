"""Time fixture plugin (PLUGIN-PORTS.md target 3, clock-world): no
ports — only the TIME face. Each tick is one hour; the door opens at
9 and shuts at 13, customers arrive on schedule. The do-lines are the
exogenous input; the catalog's world has no arrival rules at all."""


class ShopClock:
    OPEN, SHUT, CLOSE = 9, 13, 16
    ARRIVALS = {10: 1, 11: 2, 14: 1}      # hour -> customers

    def __init__(self, case):
        self.hour = 8

    def bind(self, reg):
        pass                               # no weight ports

    def tick(self, counts):
        if self.hour >= self.CLOSE:
            return None                    # the day is over
        h, dos = self.hour, []
        if h == self.OPEN:
            dos += ["-doorshut", "+dooropen"]
        if h == self.SHUT:
            dos += ["-dooropen", "+doorshut"]
        n = self.ARRIVALS.get(h, 0)
        if n:
            dos.append(f"+customer {n}")
        self.hour += 1
        return dos

    def on_event(self, name, args):
        pass

    def snapshot(self):
        return self.hour

    def restore(self, snap):
        self.hour = snap


def make(case):
    return ShopClock(case)
