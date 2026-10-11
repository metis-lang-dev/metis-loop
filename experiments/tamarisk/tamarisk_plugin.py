"""Tamarisk port plugin (rddl-tier1, domain 2): the born catalog
declares its spread/competition rates as weight ports (pdown, pup,
pcompete — the formalizer's own choice, card v2). The BASE binding is
prior-flat 0.5 for every port: the rates are DISCOVERED by notching from
episodes (step 2a), never transcribed. Ground truth for the notch table
= the instance's DYNAMICS non-fluents (DOWNSTREAM-SPREAD-RATE,
UPSTREAM-SPREAD-RATE, COMPETITION-WIN-RATE-*, ...), never the reward
costs. Served as `metis --plugin tamarisk_plugin:make WORLD.llp`."""


class TamariskPorts:
    name = "tamarisk-prior-flat"

    def __init__(self, case):
        pass

    # born (step 1): pdown pup pcompete; iter1 (step 2): the seat's
    # global per-law ports
    PORTS = ("pdown", "pup", "pcompete", "ptcomp", "pncomp", "perad",
             "ptdie", "pndie", "ptborn", "psib", "prest", "pnborn")

    def flat(self, args, counts):
        return 0.5                       # prior-flat: notching fits it

    def bind(self, reg):
        for p in self.PORTS:
            reg.weight(p, self.flat)

    def tick(self, counts):
        return None                      # no env clock in the REPL

    def on_event(self, name, args):
        pass

    def snapshot(self):
        return None

    def restore(self, snap):
        pass


def make(case):
    return TamariskPorts(case)
