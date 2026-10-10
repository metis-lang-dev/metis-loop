"""Real-valued fixture (PLUGIN-PORTS.md target 2 shape), NATIVE:
reservoir.llp carries '#plugin reservoir_plugin:make'. The REAL level
lives in the plugin's env; prain is priced from the env's season
clock, pspill from the real level behind the declared highc read.
Each quiet world = one day: tick() brings the day's ck and the level's
class as do-lines; on_event() actuates (store raises the level, a dry
day draws it down, a near-full level triggers a release). Three
14-day episodes (reset returns the env to as-attached), then the
NOTCH row sheet fitted from the session's sampled steps, shipped as an
overlay (never a catalog edit) and popped. Transcript:
transcripts/reservoir.md."""
import re

from _drive import HERE, answers, drive

EPISODES = 3
lines = ["ports", "port prain", "port pspill"]
for _ in range(EPISODES):
    lines += ["run 400", "log", "reset"]
lines += ["notch", "notch accept", "ports", "key", "notch pop", "key"]
out = drive(HERE / "reservoir.llp", lines, "reservoir")
a = answers(out)
print(out)

# `log` lists the whole session (resets move the graph base, not the
# ledger): the last one holds all episodes. Every spill happened while
# the high class held — track the class through the [env] rows.
log = a[6 + 3 * (EPISODES - 1)]
spills, high, days = 0, False, 0
for row in re.findall(r"^\s+\d+\. (.+?)(?:  \[env\])?$", log, re.M):
    if row.startswith("do "):
        ops = row.split()[1:]
        days += "+ck" in ops
        high = "+highc" in ops or (high and "-highc" not in ops)
    elif row == "spill":
        assert high, log
        spills += 1
assert days == 13 * EPISODES, (days, log)   # 14-day episodes: 13 ticks
base = 5 + 3 * EPISODES
sheet = a[base]
assert "prain | (no scope)" in sheet and "pspill | highc=1" in sheet, sheet
assert "+1 overlay(s)" in a[base + 2]
key_on, key_off = a[base + 3], a[base + 5]
assert key_on == key_off                  # an overlay is not an edit
print(f"\nOK: {EPISODES} x 14-day episodes, {spills} spill(s), all under "
      "the high class — the real level priced the hazard, the measure "
      "stayed qualitative; the notch row sheet shipped as an overlay "
      "and popped, the catalog key unchanged.")
