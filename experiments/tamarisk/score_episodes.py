"""Per-atom log-loss of a served world on recorded transitions, against
the generator's floor. At 16 independent observed fluents per step the
joint likelihood is ~1e-3..1e-5 even under the true cpfs (the 0.05 'rare'
threshold flags the TRUE generator ~17-21x per episode), and a sampled
joint below 1/samples reads as 0. So score what sampling resolves: for
each observed fluent, the model's marginal P(observed value) at the
settle readout over M reference-sampler runs (add-1/2 smoothing), summed
as -log over the 16 fluents of the step. The floor is the same sum under
the cpfs' exact marginals (true_likelihood.slot_probs). Also reported:
the fraction of steps where some run matched the whole observation.

    python score_episodes.py WORLD.llp TRANSITIONS.jsonl [--plugin P]
        [--overlay notch.json] [--runs M] [--out score.json]"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main(argv=None):
    from metis.domains.rddl_recorder import (atom_of, load_problem,
                                             neg_of, port_pricer,
                                             read_transitions,
                                             state_vocabulary)
    from metis.kernel.filter import DONE
    from metis.kernel.refsample import run_trace
    from metis.lang import load_llp
    from true_likelihood import names, slot_probs, REACH_OF

    ap = argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("transitions")
    ap.add_argument("--plugin", default="tamarisk_plugin:make")
    ap.add_argument("--overlay", default=None)
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--cap", type=int, default=256)
    ap.add_argument("--out", default="")
    ns = ap.parse_args(argv)

    doc = load_llp(ns.world)
    pricer = port_pricer(doc, ns.plugin, HERE, ns.overlay)
    trs = list(read_transitions(ns.transitions))
    _, env = load_problem(trs[0]["domain"], trs[0]["instance"])
    vocab = state_vocabulary(env)
    model_ll, floor_ll, joint_hit, unsettled = [], [], 0, 0
    per_atom = {}
    for k, tr in enumerate(trs):
        on, on2 = set(tr["state"]), set(tr["next"])
        init = {atom_of(x): 1 for x in tr["state"]}
        init.update({neg_of(x): 1 for x in vocab if x not in on})
        init.update({atom_of(x): 1 for x in tr["action"]})
        init["tick"] = 1
        prog = doc.catalog.ground(init)
        pol = pricer.policy(prog, canonical=True) if pricer else None
        hits = {x: 0 for x in vocab}
        any_joint = False
        for s in range(ns.runs):
            _, (stage, kappa) = run_trace(prog, ns.cap, 104729 * k + s,
                                          policy=pol)
            if stage != DONE:
                unsettled += 1
                continue
            c = dict(kappa)
            ok = True
            for x in vocab:
                m = (c.get(atom_of(x), 0) > 0) == (x in on2)
                hits[x] += m
                ok &= m
            any_joint |= ok
        joint_hit += any_joint
        ll = 0.0
        for x in vocab:
            q = -math.log((hits[x] + 0.5) / (ns.runs + 1))
            ll += q
            per_atom[x] = per_atom.get(x, 0.0) + q
        model_ll.append(ll)
        T, N = names("tamarisk-at", tr["state"]), names("native-at", tr["state"])
        ER, RS = names("eradicate", tr["action"]), names("restore", tr["action"])
        fl = 0.0
        for s in REACH_OF:
            pt, pn = slot_probs(s, T, N, ER, RS)
            for p, hit in ((pt, f"tamarisk-at___{s}" in on2),
                           (pn, f"native-at___{s}" in on2)):
                fl -= math.log(p if hit else 1 - p)
        floor_ll.append(fl)
    n = len(trs)
    out = {"world": ns.world, "transitions": ns.transitions,
           "overlay": ns.overlay, "runs": ns.runs,
           "logloss_per_step": round(sum(model_ll) / n, 3),
           "floor_per_step": round(sum(floor_ll) / n, 3),
           "excess_per_step": round((sum(model_ll) - sum(floor_ll)) / n, 3),
           "joint_hit_frac": round(joint_hit / n, 3),
           "unsettled_runs": unsettled}
    print(json.dumps(out))
    if ns.out:
        out["per_atom"] = {x: round(v / n, 4) for x, v in per_atom.items()}
        Path(ns.out).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
