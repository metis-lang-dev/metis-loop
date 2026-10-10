"""Real-valued fixture (PLUGIN-PORTS.md target 2 shape): a reservoir
whose REAL water level lives in the Python env; the catalog is
qualitative (highc class, inflow/spill/store tokens); two ports price
the measure — prain from the env's season clock (time-dependent),
pspill from the real level. The driver below is what the REPL's
plugin loop will do natively (opus: subject port-plugins); here it
drives the kernel API per beat. PURITY: ports read (args, declared
scope, env snapshot) only; env mutates only in tick/on_event."""
import math
import random
from pathlib import Path

from metis.fw.registry import Registry
from metis.kernel import ForwardProjection
from metis.lang import load_llp, weight_policy

HERE = Path(__file__).parent
doc = load_llp(HERE / "reservoir.llp")
cat = doc.catalog


class ReservoirEnv:
    """The plugin twin: real state + classification + actuation."""

    def __init__(self):
        self.level = 6.0          # meters — REAL, never in the measure
        self.day = 0
        self.log = []

    # --- port bindings (pure given env snapshot) ---------------------
    def prain(self, args, counts):
        season = 0.5 * (1 + math.sin(self.day / 3.0))
        return 0.15 + 0.6 * season

    def pspill(self, args, counts):
        if counts.get("highc", 0) == 0:    # declared-scope read
            return 0.0
        return min(0.9, 0.2 + (self.level - 8.0) / 3.0)

    def bind(self, reg):
        reg.weight("prain", self.prain).weight("pspill", self.pspill)
        return reg

    # --- the tick/on_event faces -------------------------------------
    def classify(self):
        return {"ck": 1, **({"highc": 1} if self.level >= 8.0 else {})}

    def on_outcome(self, outcome):
        if "stored" in outcome:
            self.level = min(10.0, self.level + 1.5)
        elif "okday" in outcome:
            self.level = max(0.0, self.level - 0.8)
        if self.level > 9.0:               # actuation: scheduled release
            self.level -= 3.0
            return "release"
        return ""

    def tick(self):
        self.day += 1


env = ReservoirEnv()
reg = env.bind(Registry())
rng = random.Random(7)
spills = []
print(f"{'day':>3} {'level':>6} {'class':>5} {'P.rain':>6} "
      f"{'P.spill|day':>11}  outcome")
for _ in range(14):
    init = env.classify()
    prog = cat.ground(init)
    pol = weight_policy(prog, doc.ports, reg.weight_bindings())
    pr = ForwardProjection(prog, 2, policy=pol)
    dist = [(dict(kappa), p) for (_stage, kappa), p in pr.final.items()]
    p_spill = sum(p for s, p in dist if s.get("spilled"))
    # the driver samples the beat outcome from the EXACT distribution
    r, acc, outcome = rng.random(), 0.0, dist[-1][0]
    for s, p in dist:
        acc += p
        if r <= acc:
            outcome = s
            break
    name = ("spilled" if outcome.get("spilled") else
            "stored" if outcome.get("stored") else "okday")
    act = env.on_outcome(outcome)
    hi = "high" if init.get("highc") else "-"
    print(f"{env.day:>3} {env.level:>6.2f} {hi:>5} "
          f"{env.prain((), {}):>6.3f} {p_spill:>11.4f}  "
          f"{name}{' +' + act if act else ''}")
    if name == "spilled":
        spills.append((env.day, hi))
    env.tick()

assert all(h == "high" for _, h in spills), spills
print(f"\nOK: {len(spills)} spill(s), all under the high class — "
      "the real level priced the hazard, the measure stayed "
      "qualitative.")
