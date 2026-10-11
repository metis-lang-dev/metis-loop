"""Step 2a: notch the weight ports from episode data, PER UNIT.

Wildfire's notch_episodes.py imputes each transition's port draws from
ONE sampled run that reaches the WHOLE observed next state. At Tamarisk's
16 fluents per step the joint is ~1e-3..1e-5, and that rejection would
take hours per round. The world's fate events are bound per slot, though
(event name `rule-k[S=slot,...]`; each writes only its own slot's
fluents), so the slots are independent given the start state.
Conditioning factorises: for each unit u (an observed atom's first
argument), the draws of the events whose FIRST binding is u are imputed
from the first run whose unit-u atoms all match. That is an exact
posterior sample for u's draws given u's observation.

One imputed sample per transition under the current binding is a
stochastic-EM step. The noisy-or scan leaves it ambiguous WHICH source
seeded a slot, so the fit is iterated: round r+1 prices the runs with
round r's notched table (--rounds). It uses the session notch's PAIRED
estimator (metis.lang.repl.notch_rows), as notch_episodes does.

    python notch_slots.py WORLD.llp TRANSITIONS.jsonl... [--rounds R]
        [--tries N] [--jobs J] [--out notch.json]"""
import argparse
import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
UNIT = re.compile(r"\[[A-Z][A-Za-z0-9_]*=([^,\]]+)")


def unit_of_atom(a):
    m = re.match(r"[a-z_]+\(([^,)]+)", a)
    return m.group(1) if m else None


def _chunk(job):
    from metis.domains.rddl_recorder import (atom_of, load_problem, neg_of,
                                             port_pricer, state_vocabulary)
    from metis.kernel.filter import DONE
    from metis.kernel.refsample import canonical_events, run_trace
    from metis.lang import load_llp
    world, plugin, overlay, trs, tries, cap, seed0, split = job
    doc = load_llp(world)
    pricer = port_pricer(doc, plugin, HERE, overlay)
    _, env = load_problem(trs[0]["domain"], trs[0]["instance"])
    vocab = state_vocabulary(env)
    hows, missed_units, units_total = [], 0, 0
    for k, tr in enumerate(trs):
        on, on2 = set(tr["state"]), set(tr["next"])
        init = {atom_of(x): 1 for x in tr["state"]}
        init.update({neg_of(x): 1 for x in vocab if x not in on})
        init.update({atom_of(x): 1 for x in tr["action"]})
        init["tick"] = 1
        obs = {atom_of(x): x in on2 for x in vocab}
        by_unit = {}
        for a, v in obs.items():
            by_unit.setdefault(unit_of_atom(a), {})[a] = v
        units_total += len(by_unit)
        prog = doc.catalog.ground(init)
        events = canonical_events(prog)
        pol = pricer.policy(prog, canonical=True)
        todo = dict(by_unit)
        for s in range(tries):
            if not todo:
                break
            idx, (stage, kappa) = run_trace(prog, cap,
                                            seed0 + 7919 * k + s, policy=pol)
            if stage != DONE:
                continue
            c = dict(kappa)
            hit = [u for u, o in todo.items()
                   if all((c.get(a, 0) > 0) == v for a, v in o.items())]
            if not hit:
                continue
            counts = dict(init)
            for i in idx:
                _, _, ev = events[i]
                m = UNIT.search(ev.name)
                site = pricer.site(ev.name)
                if site is not None and m and m.group(1) in hit:
                    factor, args, compl, scope = site
                    row = tuple(sorted((a, int(counts.get(a, 0) > 0))
                                       for a in (scope or ())))
                    if split:   # structure check: one row per binding
                        b = re.search(r"[\[,]%s=([^,\]]+)" % split,
                                      ev.name)
                        args = tuple(args) + ((b.group(1),) if b else ("-",))
                    hows.append({"how": "sampled",
                                 "site": (factor, args, compl, row,
                                          pricer.raw(ev.name, counts))})
                for q, n in ev.consume.items():
                    counts[q] = counts.get(q, 0) - n
                for q, n in ev.produce.items():
                    counts[q] = counts.get(q, 0) + n
                counts = {q: n for q, n in counts.items() if n > 0}
            for u in hit:
                del todo[u]
        missed_units += len(todo)
    return hows, missed_units, units_total


def write_table(path, fit, meta):
    rows = [{"port": f, "args": list(a), "row": [list(r) for r in row],
             "n": n, "fires": s_, "prior": p0, "notched": post}
            for (f, a, row), (p0, post, n, s_) in sorted(fit["rows"].items())]
    Path(path).write_text(json.dumps(dict(meta, rows=rows), indent=1))


def main(argv=None):
    from metis.domains.rddl_recorder import read_transitions
    from metis.lang import load_llp
    from metis.lang.repl import notch_rows

    ap = argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("transitions", nargs="+")
    ap.add_argument("--plugin", default="tamarisk_plugin:make")
    ap.add_argument("--alpha", type=float, default=0.0)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--tries", type=int, default=2000)
    ap.add_argument("--cap", type=int, default=256)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--overlay", default=None,
                    help="start from this notch table instead of the base")
    ap.add_argument("--split", default="",
                    help="structure check: key rows by this rule variable's "
                         "binding too (e.g. R = the reach)")
    ns = ap.parse_args(argv)

    doc = load_llp(ns.world)
    trs = [t for p in ns.transitions for t in read_transitions(p)]
    size = -(-len(trs) // ns.jobs)
    chunks = [trs[i:i + size] for i in range(0, len(trs), size)]
    overlay = ns.overlay
    with mp.Pool(ns.jobs) as pool:
        for r in range(ns.rounds):
            res = pool.map(_chunk, [(ns.world, ns.plugin, overlay, c,
                                     ns.tries, ns.cap, 1000003 * r + 13 * j,
                                     ns.split)
                                    for j, c in enumerate(chunks)])
            hows = [h for x in res for h in x[0]]
            missed = sum(x[1] for x in res)
            total = sum(x[2] for x in res)
            fit = notch_rows(hows, ns.alpha, doc.ports)
            out = f"{ns.out[:-5]}-r{r}.json"
            write_table(out, fit, {"world": ns.world, "round": r,
                                   "transitions": ns.transitions,
                                   "alpha": ns.alpha, "units": total,
                                   "missed_units": missed,
                                   "priced_by": overlay or "base"})
            print(f"round {r}: units {total}, missed {missed}, "
                  f"draws {fit['n']}  -> {out}", flush=True)
            print(fit["sheet"].rstrip(), flush=True)
            overlay = out
    Path(ns.out).write_text(Path(overlay).read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
