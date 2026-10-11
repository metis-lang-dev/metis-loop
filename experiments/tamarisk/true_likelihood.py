"""The generator's own likelihood of each recorded transition: the
Tamarisk cpfs (IPPC2014 domain.rddl, instance 1 topology, domain-default
rates) evaluated directly. tamarisk-at' and native-at' are independent
Bernoullis per slot given the start state and action, so a transition's
probability is the product over slots of both. This is the FLOOR of the
surprise metric: what a perfect model would still flag as 'rare' at the
same threshold."""
import collections
import json
import sys

RATE = dict(erad=0.9, rest=0.9, down=0.6, up=0.15, die_t=0.05,
            die_n=0.05, exo_n=0.1, exo_t=0.1, win_n=0.2, win_t=0.8)
# instance 1: slots sRsK on reach rR; DOWNSTREAM-REACH(r(i+1), ri)
REACHES = ["r1", "r2", "r3", "r4"]
SLOTS = {r: [f"s{r[1]}s1", f"s{r[1]}s2"] for r in REACHES}
REACH_OF = {s: r for r, ss in SLOTS.items() for s in ss}
DOWN = {("r2", "r1"), ("r3", "r2"), ("r4", "r3")}  # (first downstream of second)


def names(prefix, lst):
    return {k.split("___")[1] for k in lst if k.startswith(prefix + "___")}


def slot_probs(s, T, N, ER, RS, R=RATE):
    """(P tamarisk-at'(s), P native-at'(s)) per the cpfs."""
    r = REACH_OF[s]
    # The cpfs' guard "~(forall ?s2: SLOT-AT-REACH(?s2,?r) ^ tamarisk-at(?s2))"
    # quantifies over EVERY slot, so it holds only if every slot of the
    # instance were on ?r: never. Eradication is never blocked as written
    # (the data agree: eradicate on a fully invaded reach clears it).
    full = all(x in T and REACH_OF[x] == r for x in REACH_OF)
    erad = r in ER and not full
    if s in T and s in N:
        pt = R["win_t"]
    elif s not in T and erad:
        pt = 0.0
    elif s in T and erad:
        pt = 1 - R["erad"]
    elif s in T:
        pt = 1 - R["die_t"]
    elif s not in N:
        fail = 1.0
        for x in SLOTS[r]:
            if x != s and x in T:
                fail *= 1 - R["down"]
        for r2 in REACHES:
            for x in SLOTS[r2]:
                if x in T and (r, r2) in DOWN:
                    fail *= 1 - R["down"]
                if x in T and (r2, r) in DOWN:
                    fail *= 1 - R["up"]
        pt = R["exo_t"] + (1 - R["exo_t"]) * (1 - fail)
    else:
        pt = 0.0
    if s in T and s in N:
        pn = R["win_n"]
    elif s not in T and s in N and r in RS:
        pn = 1.0
    elif s not in T and s not in N and r in RS:
        pn = R["rest"]
    elif s in N:
        pn = 1 - R["die_n"]
    elif s not in T:
        pn = R["exo_n"]
    else:
        pn = 0.0
    return pt, pn


def true_likelihood(tr, R=RATE):
    T, N = names("tamarisk-at", tr["state"]), names("native-at", tr["state"])
    T2, N2 = names("tamarisk-at", tr["next"]), names("native-at", tr["next"])
    ER, RS = names("eradicate", tr["action"]), names("restore", tr["action"])
    p = 1.0
    for s in REACH_OF:
        pt, pn = slot_probs(s, T, N, ER, RS, R)
        p *= (pt if s in T2 else 1 - pt) * (pn if s in N2 else 1 - pn)
    return p


if __name__ == "__main__":
    rare = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    per, zero, n, eps = collections.Counter(), 0, 0, set()
    for line in open(sys.argv[1]):
        tr = json.loads(line)
        n += 1
        eps.add(tr["episode"])
        p = true_likelihood(tr)
        zero += p == 0
        per[tr["episode"]] += p < rare
    print(json.dumps({"transitions": n, "true_zero": zero,
                      "floor_surprises": sum(per.values()),
                      "floor_per_episode": round(sum(per.values())
                                                 / len(eps), 2)}))
