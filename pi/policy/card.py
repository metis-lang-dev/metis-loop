"""card.py — several policy variants scored on one card series, interleaved, under ONE spend cap
(policy-tuning s-1caedae5, step 1's runner; TUNING.md). Each run is scorecard.score_one; before each, the
series' guard (rewrite.Series: the key's usage since the series started or the reported costs, whichever is
larger, plus a headroom of 1.5× the largest run seen) stops the series cleanly when the next run could pass
the cap. The order interleaves the variants (seed, world, variant), so a stop still leaves each variant a
run on each world.

    python -m policy.card --variant fit --variant fit-skill=policy/skills/hierarchy.md --worlds alfworld,scienceworld \\
        --seeds 1,2 --brain openrouter/deepseek/deepseek-v4-pro --budget 0.50 --series-budget 1.00 --discovery 2 --gate-games 2 --heldout 10

Each variant's card is RUNS/<variant>/scorecard.json (score_variant's shape), rewritten after every run."""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from policy import scorecard  # noqa: E402
from policy.rewrite import Series, SeriesStop  # noqa: E402


def variants_of(specs):
    """--variant NAME or NAME=SKILL_FILE → [(name, skill path or None)]."""
    out = []
    for s in specs:
        name, _, skill = s.partition("=")
        out.append((name, str(Path(skill).resolve()) if skill else None))
    return out


def card_of(variant, skill, brain, rows):
    return {"variant": variant, "skill": skill, "brain": brain, "rows": rows,
            "usd": round(sum(r["usd"] for r in rows), 4), "rules": sum(r.get("rules") or 0 for r in rows)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy.card", description=__doc__.split("\n")[0])
    ap.add_argument("--variant", action="append", required=True, help="NAME or NAME=SKILL_FILE (repeat)")
    ap.add_argument("--series-budget", type=float, default=None, help="USD for the whole series (required for a paid brain)")
    scorecard.add_arguments(ap)
    a = ap.parse_args(argv)
    if a.brain.startswith("openrouter/") and (a.budget is None or a.series_budget is None):
        ap.error("a paid brain needs --budget (per run) and --series-budget (the series)")
    runs = Path(a.runs).resolve()
    vs = variants_of(a.variant)
    series = Series(a.brain, a.series_budget, a.budget, runs / "card-series")
    rows = {v: [] for v, _ in vs}
    try:
        for seed in (int(x) for x in a.seeds.split(",")):
            for world in a.worlds.split(","):
                for variant, skill in vs:
                    every = [r for rs in rows.values() for r in rs]
                    series.check("%s %s seed %d" % (variant, world, seed), every)
                    a.skill = skill
                    row = scorecard.score_one(variant, world, seed, a, runs)
                    row["structural"] = scorecard.structural_of(runs / variant / ("%s-s%d" % (world, seed)), world, a, row)
                    rows[variant].append(row)
                    print("%-12s %-13s s%d  %-9s acc %s/%s  calls %s  usd %s  rules %s  held-out flat %s  %s" % (
                        variant, world, seed, row.get("phase"), row.get("accepted"), row.get("proposals"), row.get("calls"),
                        row.get("usd"), row.get("rules"), row.get("heldout_flat"), row.get("status")), flush=True)
                    (runs / variant).mkdir(parents=True, exist_ok=True)
                    (runs / variant / "scorecard.json").write_text(json.dumps(card_of(variant, skill, a.brain, rows[variant]), indent=1))
    except SeriesStop as e:
        print("the series stopped: %s" % e, flush=True)
    every = [r for rs in rows.values() for r in rs]
    print("the series: %d runs, usd %.4f (reported %.4f)" % (len(every), series.spent(every), sum(r["usd"] for r in every)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
