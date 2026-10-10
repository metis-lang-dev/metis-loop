"""Merge per-chunk episode notch tables (notch_episodes.py --out) and
print the step-2a acceptance table: per neighbor count k, the
generator's TRUE ignition probability 1/(1+exp(4.5-k)) (the header's
law — ground truth, never read by the fit), the notched pign(k) (ML:
fires/opportunities over the recorded episodes), n, and a 95% Wilson
interval. Writes the merged table as a notch overlay file too."""
import glob
import json
import math
import sys


def wilson(s, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = s / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


acc, explained, missed = {}, 0, 0
for f in sorted(glob.glob(sys.argv[1])):
    t = json.load(open(f))
    explained += t["explained"]
    missed += t["missed"]
    for r in t["rows"]:
        key = (r["port"], tuple(r["args"]), tuple(map(tuple, r["row"])))
        n, s = acc.get(key, (0, 0))
        acc[key] = (n + r["n"], s + r["fires"])
rows = []
print(f"transitions explained {explained}, not reached {missed}")
print("| k | true 1/(1+e^(4.5-k)) | notched pign(k) | 95% CI | n | "
      "fires | true in CI |")
print("|---|---|---|---|---|---|---|")
for (port, args, row), (n, s) in sorted(acc.items(),
                                        key=lambda kv: kv[0][1]):
    k = int(args[0].lstrip("k"))
    true = 1 / (1 + math.exp(4.5 - k))
    lo, hi = wilson(s, n)
    rows.append({"port": port, "args": list(args), "row": list(row),
                 "n": n, "fires": s, "prior": 0.5,
                 "notched": s / n if n else 0.5})
    print(f"| {k} | {true:.4f} | {s / n:.4f} | [{lo:.3f}, {hi:.3f}] | "
          f"{n} | {s} | {'yes' if lo <= true <= hi else 'NO'} |")
if len(sys.argv) > 2:
    json.dump({"rows": rows, "explained": explained, "missed": missed},
              open(sys.argv[2], "w"), indent=1)
