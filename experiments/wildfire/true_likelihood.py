"""The generator's own likelihood of each recorded transition — the
Wildfire cpfs (domain.rddl) evaluated directly, per cell, independent
given the start state: the FLOOR of the surprise metric (what a perfect
model would still flag as 'rare' at the same threshold)."""
import collections
import json
import math
import sys


def topology(nf_path):
    nf = json.load(open(nf_path))
    nb, tg = collections.defaultdict(set), set()
    for k in nf:
        a = k.split("___")[1].split("__") if "___" in k else []
        if k.startswith("NEIGHBOR"):
            nb[(a[0], a[1])].add((a[2], a[3]))
        elif k.startswith("TARGET"):
            tg.add((a[0], a[1]))
    return nb, tg


def cells_of(name, lst):
    return {tuple(k.split("___")[1].split("__")) for k in lst
            if k.startswith(name + "___")}


def true_likelihood(tr, nb, tg, cells):
    B, O = cells_of("burning", tr["state"]), cells_of("out-of-fuel",
                                                     tr["state"])
    B2, O2 = cells_of("burning", tr["next"]), cells_of("out-of-fuel",
                                                      tr["next"])
    PO, CO = cells_of("put-out", tr["action"]), cells_of("cut-out",
                                                        tr["action"])
    p = 1.0
    for c in cells:
        if c in PO:
            pb = 0.0
        elif c not in O and c not in B:
            k = len(nb[c] & B)
            pb = 0.0 if (c in tg and k == 0) else 1 / (1 + math.exp(4.5 - k))
        else:
            pb = 1.0 if c in B else 0.0
        p *= pb if c in B2 else 1 - pb
        oof = c in O or c in B or (c not in tg and c in CO)
        p *= 1.0 if (c in O2) == oof else 0.0
    return p


if __name__ == "__main__":
    nb, tg = topology(sys.argv[1])
    cells = sorted(set(nb) | {d for v in nb.values() for d in v})
    rare = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05
    per, zero, n = collections.Counter(), 0, 0
    eps = set()
    for line in open(sys.argv[2]):
        tr = json.loads(line)
        n += 1
        eps.add(tr["episode"])
        p = true_likelihood(tr, nb, tg, cells)
        zero += p == 0
        per[tr["episode"]] += p < rare
    print(json.dumps({"transitions": n, "true_zero": zero,
                      "floor_surprises": sum(per.values()),
                      "floor_per_episode": round(sum(per.values())
                                                 / len(eps), 2)}))
