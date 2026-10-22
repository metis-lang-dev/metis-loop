"""scorecard.py — one policy VARIANT scored across worlds and seeds (policy-tuning s-1caedae5): the
loop from the EMPTY domain through its phases with a brain, then the base as it is on the held-out
split (flat, and through the director when the refactor built one); the numbers that matter in one
row per run and one per variant.

    python -m policy.scorecard --variant baseline [--skill FILE] --worlds alfworld,scienceworld --seeds 1,2 \\
        --brain openrouter/deepseek/deepseek-v4-pro --budget 0.50 --discovery 2 --gate-games 2 --heldout 10

Runs live under RUNS/<variant>/<world>-s<seed>/ (the driver's run directory: its catalog, records,
cost.jsonl, journal); the card at RUNS/<variant>/scorecard.json. A paid brain needs --budget per run
and the key (run.sh: the environment or ~/.config/metis/openrouter.env); every run's spend is in its
cost.jsonl. The per-world venv is run.sh's; this script shells out to it."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_SH = HERE.parent / "run.sh"
FAMILY = {"alfworld": "pick_and_place_simple", "scienceworld": "conductivity", "minihack": "room_quiet"}


def jl(path):
    p = Path(path)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def run(cmd, timeout):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout[-4000:], r.stderr[-2000:], round(time.time() - t0, 1)


def score_one(variant, world, seed, a, runs):
    d = runs / variant / ("%s-s%d" % (world, seed))
    d.mkdir(parents=True, exist_ok=True)
    args = ["--world", world, "--family", FAMILY[world], "--brain", a.brain, "--discovery", str(a.discovery),
            "--gate-games", str(a.gate_games), "--seed", str(seed)]
    if a.budget is not None:
        args += ["--budget", str(a.budget)]
    if a.skill:
        args += ["--skill", str(Path(a.skill).resolve())]
    for kv in a.set:
        args += ["--set", kv]
    row = {"variant": variant, "world": world, "seed": seed, "brain": a.brain}
    rc, out, err, secs = run([str(RUN_SH), "--run", str(d)] + args, a.timeout)
    row.update({"rc": rc, "seconds": secs})
    state = json.loads((d / "state" / "run.json").read_text()) if (d / "state" / "run.json").exists() else {}
    row.update({"phase": state.get("phase"), "status": state.get("status"), "proposals": state.get("proposals"), "accepted": state.get("accepted")})
    cost = jl(d / "cost.jsonl")
    row.update({"calls": len(cost), "usd": round(sum(float(c.get("cost") or 0) for c in cost), 4)})
    events = jl(d / "run.log.jsonl")
    row["disengaged"] = sum(1 for e in events if e.get("what") in ("disengage", "ask"))
    base = d / "catalog" / "domains"
    llp = next(base.glob("*/*.llp"), None)
    if llp:
        sys.path.insert(0, str(HERE.parent))
        from policy.alfworld import rules_of
        text = llp.read_text()
        row["rules"] = len(rules_of(text))
        row["model_rules"] = text.count("@model")
    row["usd_per_rule"] = round(row["usd"] / row["rules"], 4) if row.get("rules") else None
    for mode in ("flat", "director"):
        margs = ["--evaluate", "heldout", "--n", str(a.heldout)] + ([] if mode == "flat" else ["--mode", "director"])
        rc2, out2, err2, _ = run([str(RUN_SH), "--run", str(d), "--world", world, "--family", FAMILY[world]] + margs, a.timeout)
        ev = d / "records" / ("evaluate-heldout%s.json" % ("" if mode == "flat" else "-director"))
        if ev.exists():
            e = json.loads(ev.read_text())
            row["heldout_%s" % mode] = "%d/%d" % (e.get("won", 0), e.get("n", 0))
            row["commands_%s" % mode] = round(sum(e.get("commands", [])) / max(1, len(e.get("commands", []))), 1)
        else:
            last = (err2.strip().splitlines() or ["?"])[-1]
            row["heldout_%s" % mode] = None if rc2 == 0 or "no director" in last else "error: " + last[:120]   # no director yet: not a number
    row["log_tail"] = (out.strip().splitlines() or [""])[-1][:200]
    return row


def structural_of(d, world, a, row):
    """The structural column (step 3): the hierarchy the refactor built — its domains, those exercised on
    the discovery games (an activation with a result; the planner by any activation), the director's
    handles derived (its instance) and declared (the split's ports), the attended miss rate where a
    corpus exists (none for a learned base: no card) — and the guards it is judged under: the split's and
    the director's replay accepted, the director's held-out wins not below the flat program's, every
    domain exercised. Reported always; a comparison reads `exercised` only when `guards` holds."""
    sys.path.insert(0, str(HERE.parent))
    from policy import hier
    from policy.alfworld import rules_of  # noqa: F401
    llp = next((d / "catalog" / "domains").glob("*/*.llp"), None)
    if llp is None or llp.parent.name == "director":
        llp = next((p for p in (d / "catalog" / "domains").glob("*/*.llp") if p.parent.name != "director"), None)
    if llp is None:
        return None
    text = llp.read_text()
    marks = {m.group(1) for m in (hier.ANNOT.search(l) for l in text.splitlines()) if m}
    out = {"domains": None, "exercised": None, "active": None, "handles_derived": None, "handles_declared": None, "miss_rate": None, "guards": None}
    if not marks:
        return dict(out, why="not split")
    rc, _, err, _ = run([str(RUN_SH), "--run", str(d), "--world", world, "--family", FAMILY[world], "--evaluate", "discovery",
                         "--n", str(a.discovery), "--mode", "hier"], a.timeout)
    ev = d / "records" / "evaluate-discovery-hier.json"
    if rc != 0 or not ev.exists():
        return dict(out, why="the discovery hierarchy did not run: " + ((err.strip().splitlines() or ["?"])[-1])[:120])
    e = json.loads(ev.read_text())
    doms = sorted(set(e.get("domains") or []))
    seen, active = set(), set()
    for g in e.get("games", []):
        for act in g.get("activations") or []:
            if act.get("fired"):
                active.add(act["domain"])
            if act.get("results") or (act["domain"] == "task" and act.get("fired")):
                seen.add(act["domain"])            # exercised: an activation that put a result out (the planner: that acted)
    out.update(domains=len(doms), exercised=len(seen & set(doms)), active=len(active & set(doms)))
    dfile = d / "catalog" / "domains" / "director" / "director.llp"
    if dfile.exists():
        dt = dfile.read_text()
        out["handles_derived"] = dt.count("handles(")
        out["handles_declared"] = e.get("handles_declared")
    journal = jl(d / "state" / "journal.jsonl")
    moves = {(x.get("numbers") or {}).get("move"): x for x in journal if x.get("event") == "proposal"}
    replay = all((moves[m]["numbers"].get("replay_identical") and moves[m]["verdict"] == "accept") for m in ("split", "direct") if m in moves)
    def n_won(v):
        return int(v.split("/")[0]) if isinstance(v, str) and "/" in v and not v.startswith("error") else None
    flat, director = n_won(row.get("heldout_flat")), n_won(row.get("heldout_director"))
    heldout_ok = director is None or flat is None or director >= flat
    out["guards"] = bool(replay and heldout_ok and out["exercised"] == out["domains"])
    out["guard_parts"] = {"replay": replay, "heldout_not_down": heldout_ok, "all_exercised": out["exercised"] == out["domains"]}
    return out


def add_arguments(ap):
    ap.add_argument("--worlds", default="alfworld,scienceworld")
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--brain", default="script:/dev/null")
    ap.add_argument("--budget", type=float, default=None, help="USD per run (required for a paid brain)")
    ap.add_argument("--discovery", type=int, default=2)
    ap.add_argument("--gate-games", type=int, default=2)
    ap.add_argument("--heldout", type=int, default=10)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--runs", default=str(HERE.parent / "policy-runs"))
    ap.add_argument("--timeout", type=int, default=3600)


def score_variant(a, variant, skill, runs):
    """One variant's card: every world × seed scored (score_one), the structural column beside it."""
    a.skill = skill
    rows = []
    for world in a.worlds.split(","):
        for seed in (int(x) for x in a.seeds.split(",")):
            row = score_one(variant, world, seed, a, runs)
            row["structural"] = structural_of(runs / variant / ("%s-s%d" % (world, seed)), world, a, row)
            rows.append(row)
            st = row["structural"] or {}
            print("%-12s %-13s s%d  %-9s acc %s/%s  calls %s  usd %s  rules %s  usd/rule %s  heldout flat %s director %s  "
                  "domains %s exercised %s guards %s  %s" % (
                      variant, world, seed, row.get("phase"), row.get("accepted"), row.get("proposals"), row.get("calls"), row.get("usd"),
                      row.get("rules"), row.get("usd_per_rule"), row.get("heldout_flat"), row.get("heldout_director"),
                      st.get("domains"), st.get("exercised"), st.get("guards"), row.get("status")), flush=True)
    card = {"variant": variant, "skill": skill, "brain": a.brain, "rows": rows,
            "usd": round(sum(r["usd"] for r in rows), 4), "rules": sum(r.get("rules") or 0 for r in rows)}
    (runs / variant).mkdir(parents=True, exist_ok=True)
    (runs / variant / "scorecard.json").write_text(json.dumps(card, indent=1))
    print("scorecard: %s  total usd %s" % (runs / variant / "scorecard.json", card["usd"]), flush=True)
    return card


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy.scorecard")
    ap.add_argument("--variant", required=True)
    ap.add_argument("--skill")
    add_arguments(ap)
    a = ap.parse_args(argv)
    if a.brain.startswith("openrouter/") and a.budget is None:
        ap.error("a paid brain needs --budget per run")
    score_variant(a, a.variant, a.skill, Path(a.runs).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
