"""metis-loop CLI — the first binding of the core (docs/DESIGN.md A).

  metis-loop admit      TEXT.md CAND.llp [--base BASE.llp] [--scenario a=1,b=2]...
  metis-loop formalize  TEXT.md --backend CMD... [--base BASE.llp] [--out CAND.llp]
  metis-loop replay     RECORDS.jsonl CATALOG.llp --init a=1,b=2 [--index -1]

`--backend` is any command reading the prompt on stdin and writing
LLP on stdout, e.g.:  --backend claude -p --model opus
"""
import argparse
import json
import sys
from pathlib import Path

from .core import admit, formalize_loop, load_records, replay


def _kv(s):
    out = {}
    for part in s.split(","):
        k, _, v = part.partition("=")
        out[k.strip()] = int(v or 1)
    return out


def _print_report(rep):
    print(f"ok={rep.ok} classification={rep.classification} "
          f"reads_declared={rep.reads_declared}")
    for w in rep.warnings:
        print(f"  warn: {w}")
    for f in rep.findings:
        print(f"  FINDING: {f}")
    for name, doc in rep.rules:
        print(f"  rule {name}: {doc}")
    for sc in rep.scenarios:
        print(f"  scenario key={sc.key[:16]} support={sc.support}")
        for atom, pb, pm in sc.diffs:
            print(f"    diff {atom}: {pb:.6g} -> {pm:.6g}")
        for e in sc.map_events:
            print(f"    map: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="metis-loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("admit")
    a.add_argument("text"), a.add_argument("llp")
    a.add_argument("--base"), a.add_argument("--steps", type=int, default=6)
    a.add_argument("--scenario", action="append", default=[])

    f = sub.add_parser("formalize")
    f.add_argument("text")
    f.add_argument("--backend", nargs=argparse.REMAINDER, required=True)
    f.add_argument("--base"), f.add_argument("--out")
    f.add_argument("--vocabulary", help="file with the base vocabulary "
                   "summary shown to the formalizer (default: the base "
                   "llp source itself)")
    f.add_argument("--steps", type=int, default=6)
    f.add_argument("--scenario", action="append", default=[])
    f.add_argument("--max-rounds", type=int, default=4)

    r = sub.add_parser("replay")
    r.add_argument("records"), r.add_argument("catalog")
    r.add_argument("--init", required=True)
    r.add_argument("--index", type=int, default=-1)
    r.add_argument("--steps", type=int)

    ns = ap.parse_args(argv)
    if ns.cmd == "admit":
        rep = admit(Path(ns.text).read_text(), Path(ns.llp).read_text(),
                    base_path=ns.base,
                    scenarios=[_kv(s) for s in ns.scenario], steps=ns.steps)
        _print_report(rep)
        return 0 if rep.ok else 1

    if ns.cmd == "formalize":
        vocab = (Path(ns.vocabulary).read_text() if ns.vocabulary
                 else Path(ns.base).read_text() if ns.base else "")
        res = formalize_loop(
            Path(ns.text).read_text(), vocab, ns.backend,
            base_path=ns.base, scenarios=[_kv(s) for s in ns.scenario],
            steps=ns.steps, max_rounds=ns.max_rounds)
        print(f"rounds={res.rounds} ok={res.ok}")
        if res.report:
            _print_report(res.report)
        if res.ok and ns.out:
            Path(ns.out).write_text(res.llp)
            print(f"wrote {ns.out}")
        return 0 if res.ok else 1

    if ns.cmd == "replay":
        rec = load_records(ns.records)[ns.index]
        out = replay(rec, ns.catalog, _kv(ns.init), steps=ns.steps)
        print(json.dumps({k: v for k, v in out.items()
                          if k in ("likelihood", "kind", "explanation",
                                   "key_match", "map")},
                         indent=2, default=str))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
