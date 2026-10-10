"""Step 2a — notch the weight ports FROM EPISODE DATA (subject
rddl-tier1: "count event occurrences vs exposure ticks in the recorded
episodes ... maximum-likelihood per branch: fires/opportunities").

Generic over the catalog — nothing Wildfire-specific below: each
recorded RDDL transition is mapped exactly as the surprise sink maps it
(negatives + tick token, rddl_recorder), the serving world is grounded
on it, and reference-sampler runs (priced by the plugin's BASE binding)
are drawn until one reaches the OBSERVED next state at the settle
readout. Its port-priced events are the transition's sufficient
statistics: each is one draw of its complement pair, attributed to
(port, args, read-scope row) — the session notch's PAIRED estimator
(metis.lang.repl.notch_rows), fed from the episodes instead of the REPL.
A transition no run reaches within the cap is counted and skipped
(never imputed).

    python notch_episodes.py WORLD.llp TRANSITIONS.jsonl [--alpha A]
        [--tries N] [--out notch.json]

Writes the per-row table (port, args, n, fires, prior, posterior/ML)
to --out; prints the row sheet."""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main(argv=None):
    from metis.domains.rddl_recorder import (atom_of, load_problem,
                                             neg_of, port_pricer,
                                             read_transitions,
                                             state_vocabulary)
    from metis.kernel.filter import DONE
    from metis.kernel.refsample import canonical_events, run_trace
    from metis.lang import load_llp
    from metis.lang.repl import notch_rows

    ap = argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("transitions", nargs="+")
    ap.add_argument("--plugin", default="wildfire_plugin:make")
    ap.add_argument("--alpha", type=float, default=0.0,
                    help="Dirichlet prior strength (0 = pure ML)")
    ap.add_argument("--tries", type=int, default=4000)
    ap.add_argument("--cap", type=int, default=256)
    ap.add_argument("--out", default="")
    ns = ap.parse_args(argv)

    doc = load_llp(ns.world)
    pricer = port_pricer(doc, ns.plugin, HERE)
    trs = [t for p in ns.transitions for t in read_transitions(p)]
    _, env = load_problem(trs[0]["domain"], trs[0]["instance"])
    vocab = state_vocabulary(env)
    hows, missed, used = [], 0, 0
    for k, tr in enumerate(trs):
        on, on2 = set(tr["state"]), set(tr["next"])
        init = {atom_of(x): 1 for x in tr["state"]}
        init.update({neg_of(x): 1 for x in vocab if x not in on})
        init.update({atom_of(x): 1 for x in tr["action"]})
        init["tick"] = 1
        obs = {atom_of(x): x in on2 for x in vocab}
        obs.update({neg_of(x): x not in on2 for x in vocab})
        prog = doc.catalog.ground(init)
        events = canonical_events(prog)
        pol = pricer.policy(prog, canonical=True)  # run_trace's order
        hit = None
        for s in range(ns.tries):
            idx, (stage, kappa) = run_trace(
                prog, ns.cap, 7919 * k + s,
                policy=pol)
            if stage != DONE:
                continue
            c = dict(kappa)
            if all((c.get(a, 0) > 0) == v for a, v in obs.items()):
                hit = idx
                break
        if hit is None:
            missed += 1
            continue
        used += 1
        counts = dict(init)
        for i in hit:
            kind, _, ev = events[i]
            site = pricer.site(ev.name)
            if site is not None:
                factor, args, compl, scope = site
                row = tuple(sorted((a, int(counts.get(a, 0) > 0))
                                   for a in (scope or ())))
                hows.append({"how": "sampled",
                             "site": (factor, args, compl, row,
                                      pricer.raw(ev.name, counts))})
            for q, m in ev.consume.items():
                counts[q] = counts.get(q, 0) - m
            for q, m in ev.produce.items():
                counts[q] = counts.get(q, 0) + m
            counts = {q: m for q, m in counts.items() if m > 0}
    fit = notch_rows(hows, ns.alpha, doc.ports)
    print(fit["sheet"].rstrip())
    print(f"(transitions {len(trs)}: explained by a sampled run {used}, "
          f"not reached within {ns.tries} tries {missed}; "
          f"{fit['n']} port draws)")
    if ns.out:
        rows = [{"port": f, "args": list(a), "row": [list(r) for r in row],
                 "n": n, "fires": s_, "prior": p0, "notched": post}
                for (f, a, row), (p0, post, n, s_) in sorted(
                    fit["rows"].items())]
        Path(ns.out).write_text(json.dumps(
            {"world": ns.world, "transitions": ns.transitions,
             "alpha": ns.alpha, "explained": used, "missed": missed,
             "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
