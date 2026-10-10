"""Wildfire port plugin (rddl-tier1 step 2a; architect decision: the
ignition law is a WEIGHT PORT, not literal weights). The BASE binding is
prior-flat — pign(K) = 0.5 for every neighbor count K, the born
catalog's 1:1 — so the law is DISCOVERED by notching from episodes,
never transcribed from the header. The header's logistic
p = 1/(1 + exp(4.5 - k)) is the GROUND TRUTH the notched overlay is
scored against (RESULTS), nothing here reads it.

Served as `metis --plugin wildfire_plugin:make WORLD.llp` (the catalog
file carries no #plugin — it stays metisc-parseable). Pure: no env
state, no time face (episodes arrive through the surprise sink and the
notch, not through tick)."""


class WildfirePorts:
    name = "wildfire-prior-flat"

    def __init__(self, case):
        pass

    def pign(self, args, counts):
        return 0.5                       # prior-flat: notching fits it

    def bind(self, reg):
        reg.weight("pign", self.pign)

    def tick(self, counts):
        return None                      # no env clock in the REPL

    def on_event(self, name, args):
        pass

    def snapshot(self):
        return None

    def restore(self, snap):
        pass


def make(case):
    return WildfirePorts(case)
