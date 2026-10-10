"""Scope fixture (PLUGIN-PORTS.md target 1), NATIVE: sensor.llp
carries '#plugin sensor_plugin:make' — the REAL gap behind the `rss`
port. In the terminal shell: the env's first beat closes the gap
18 m -> 6 m and the SAME qualitative state re-prices P[crash] 0.3 ->
0.9 exactly; `whatif 0` prices both arms under the env AS IT WAS at
#0 (counterfactual honesty — the live env is 6 m); fork/back restore
the env with the world; a notch overlay overrides the base and pops.
Then the G5 teeth: sensor_leaky.llp declares `reads {}` for the same
binding — its gclose read raises in the SAMPLING tier now, as it
always did in the factored tier. Transcripts: transcripts/sensor.md,
transcripts/sensor_leaky.md."""
from _drive import HERE, answers, drive


def p_of(text):
    return float(text.split("] = ")[1].split()[0])


lines = ["ports", "query crash", "tick", "query crash",
         "whatif 0 do(+ck) query crash @2",
         "fork 0", "query crash", "back", "query crash", "undo",
         "query crash"]
for _ in range(25):
    lines += ["step", "reset"]
lines += ["notch", "notch accept", "query crash", "notch pop",
          "query crash"]
out = drive(HERE / "sensor.llp", lines, "sensor")
a = answers(out)
print(out)
assert p_of(a[3]) == 0.3                  # gap 18 m
assert p_of(a[5]) == 0.9                  # gap 6 m: same state, re-priced
assert "P = 0.51" in a[6] and "P = 0.3" in a[6]   # the env at #0
assert p_of(a[8]) == 0.3                  # inside the fork: env at #0
assert p_of(a[10]) == 0.9                 # back: the actual env
assert p_of(a[12]) == 0.3                 # undo of the tick: env too
k = 13 + 2 * 25
assert "rss | gclose=1 : 0.300 ->" in a[k], a[k]
fitted = p_of(a[k + 2])
assert fitted != 0.3                      # the overlay prices
assert p_of(a[k + 4]) == 0.3              # popped: the base again

leaky = drive(HERE / "sensor_leaky.llp", ["query crash", "step",
                                          "findings"], "sensor_leaky")
print(leaky)
b = answers(leaky)
assert "ScopeViolation" in b[2] and "G5" in b[2], b[2]
assert "reads-undeclared" in b[4] or "outside its declared scope" in b[4]
print(f"\nOK: env flip re-priced 0.3 -> 0.9 exactly; whatif/fork priced "
      f"under the forked env; notch overlay {fitted:g} then popped; "
      "the sampling tier enforces `reads` (G5).")
