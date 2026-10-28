"""rewrite.py — the skill rewritten from the journals (policy-tuning s-1caedae5, step 2): what learns is
the search policy around a frozen brain, and its instructions are the part the brain can edit itself.

    python -m policy.rewrite --skill skills/hierarchy.md --rounds 3 --worlds alfworld,scienceworld --seeds 1 \\
        --brain openrouter/deepseek/deepseek-v4-pro --budget 0.50 [--start-card RUNS/<variant>/scorecard.json]

Round 0 is the given skill's card (scored here, or read from --start-card). Each round:
  1. the KEPT skill's runs are read: every proposal with its numbers, verdict and the gate's reasons
     (state/journal.jsonl), the fit-repair reasons and disengagements (run.log.jsonl), the brain's own
     lines where a proposal was refused (prompts.jsonl);
  2. the brain proposes the edited skill file (ONE ```md block, the whole file, its `## always /
     explore / exploit / refactor` headings kept) — one call, budgeted like a run, logged in
     RUNS/rewrite/cost.jsonl;
  3. the edited skill is a new variant (rw<k>), scored by the same card (scorecard.score_variant);
  4. the better card is kept: better on every world in held-out wins (flat + director), then — when
     both cards' structural guards hold (step 3) — in the domains exercised, then a lower usd/rule.
A paid brain needs --series-budget too (nina's R1): the series' spend, the key's usage since the
series started or the reported costs (the cards' runs, the rewrite calls), whichever is larger, is
checked before every run and every rewrite call; one that could pass the cap (spent + its headroom:
1.5× the largest run seen so far, at least $0.10, never above --budget — the architect's N4; the
per-run --budget stays the hard cap) is not started, and the series stops there, its history written.
RUNS/rewrite/history.json is the result: each round's skill, its card's summary, the verdict, and the
skill's diff against the one it rewrote."""
import argparse
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from policy import scorecard  # noqa: E402
from policy.brain import Brain, Budget  # noqa: E402

HEADINGS = ("## always", "## explore", "## exploit", "## refactor")


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


MOVES = ("prune", "split", "direct", "edit")     # a proposal no brain call made (a refactoring move, the person's edit)


def judged_calls(prompts):
    """For a run journaled before the call ids (nina's R2): the calls whose lines the gate judged, in
    order — a proposal's call or its last compile repair, then a fit repair's own."""
    out, cand = [], None
    for k, p in enumerate(prompts, 1):
        purpose = str(p.get("purpose", ""))
        if purpose in ("probe-pick", "rewrite"):
            continue
        if purpose.endswith("-repair"):
            cand = k
            continue
        if cand is not None:
            out.append(cand)
        cand = k
    return out + ([cand] if cand is not None else [])


def digest(card, runs, limit=14000):
    """What the kept skill's runs did, for the brain: per run, its end, and every proposal (phase,
    domain, verdict, numbers, the gate's reasons; where refused, the lines the gate judged: the
    proposal's call, by its id), the fit-repair reasons, the disengagement."""
    out = []
    for row in card["rows"]:
        d = Path(runs) / card["variant"] / ("%s-s%d" % (row["world"], row["seed"]))
        out.append("### %s seed %d — phase %s, %s/%s accepted, held-out flat %s director %s, %s" % (
            row["world"], row["seed"], row.get("phase"), row.get("accepted"), row.get("proposals"),
            row.get("heldout_flat"), row.get("heldout_director"), row.get("status")))
        prompts = jl(d / "prompts.jsonl")
        log = jl(d / "run.log.jsonl")
        props = [e for e in log if e.get("event") == "proposal"]
        by_order = None
        if props and not any("call" in e for e in props):     # an older run: its brain proposals paired in order
            calls = iter(judged_calls(prompts))
            by_order = {id(e): next(calls, None) for e in props if e.get("by", "brain") == "brain" and not any(m in e for m in MOVES)}
        for e in log:
            if e.get("event") == "proposal":
                nums = {key: v for key, v in (e.get("numbers") or {}).items() if key not in ("vector",)}
                why = e.get("why")
                why = "; ".join(why[:3]) if isinstance(why, list) else str(why or "")
                out.append("- %s %s: %s %s; why: %s" % (e.get("phase"), e.get("domain") or next((m for m in MOVES if m in e), ""),
                                                      e.get("verdict"), json.dumps(nums), why))
                call = e.get("call") if by_order is None else by_order.get(id(e))
                if e.get("verdict") in ("refuse", "error") and call and call <= len(prompts):
                    ans = (prompts[call - 1].get("answer") or "").strip().replace("\n", " ")
                    out.append("  the brain's lines: " + ans[:300])
            elif e.get("event") == "fit-repair":
                out.append("- fit-repair (%s): %s" % (e.get("purpose"), str(e.get("why"))[:300]))
            elif e.get("event") == "disengaged":
                out.append("- disengaged: %s" % e.get("reason"))
    text = "\n".join(out)
    return text if len(text) <= limit else text[:limit] + "\n[… the journal cut at %d characters]" % limit


def prompt(skill, journal):
    return f"""You are improving the SKILL: the procedures a formalizing brain follows while it builds a world's rules from an empty domain (explore: world rules from transitions; exploit: the policy's tokens from surprises and failed episodes; refactor: a hierarchy). The brain's weights do not change; this file is what it reads in every prompt, by phase. The experimental gate judged every proposal; its journal below says what was accepted, what was refused and why.

The skill as it is:
```md
{skill.strip()}
```

The journal of the runs that used it:
{journal}

Edit the skill so the next runs are refused less and win more held-out games: change only what the journal shows (a procedure the brain broke, a refusal reason that repeats, a missing procedure); keep each procedure short and concrete; keep the headings `## always`, `## explore`, `## exploit`, `## refactor`.

Answer with ONE ```md block: the whole edited skill file."""


def md_block(text):
    """The answer's ```md block: from its opening fence to the LAST fence (nina's N1: an edited skill
    may carry its own ```llp example); else the whole answer."""
    if text.count("```") >= 2:
        head, _, rest = text.partition("```")
        body = rest[:rest.rindex("```")]
        if body.startswith(("md", "markdown")):
            body = body.split("\n", 1)[1] if "\n" in body else ""
        return body.strip() + "\n"
    return text.strip() + "\n"


def won(card):
    """Per world: the held-out wins, flat plus director, summed over its seeds."""
    out = {}
    for r in card["rows"]:
        n = 0
        for k in ("heldout_flat", "heldout_director"):
            v = r.get(k)
            if isinstance(v, str) and "/" in v and not v.startswith("error"):
                n += int(v.split("/")[0])
        out[r["world"]] = out.get(r["world"], 0) + n
    return out


def structural(card):
    """The domains exercised, summed over the runs whose guards hold; None when any run's do not."""
    total = 0
    for r in card["rows"]:
        s = r.get("structural") or {}
        if s.get("guards") is False:
            return None
        total += s.get("exercised") or 0
    return total


def usd_per_rule(card):
    rules = card.get("rules") or 0
    return card["usd"] / rules if rules else float("inf")


def better(cand, kept):
    """The candidate's card is better: no world's held-out wins lower and the sum higher; or the wins
    equal and, when both cards' guards hold, more domains exercised; or then, no fewer rules built, a lower usd/rule."""
    wc, wk = won(cand), won(kept)
    if any(wc.get(w, 0) < wk.get(w, 0) for w in wk):
        return False, "fewer held-out wins on %s" % ", ".join(w for w in wk if wc.get(w, 0) < wk.get(w, 0))
    if sum(wc.values()) > sum(wk.values()):
        return True, "more held-out wins (%d > %d)" % (sum(wc.values()), sum(wk.values()))
    sc, sk = structural(cand), structural(kept)
    if sc is not None and sk is not None and sc != sk:
        return sc > sk, "domains exercised %d vs %d" % (sc, sk)
    rc, rk = cand.get("rules") or 0, kept.get("rules") or 0
    if rc < rk:                    # a cheaper rule is no gain when fewer were built (nina's round 1: 9 kept over 12)
        return False, "fewer rules built (%d < %d)" % (rc, rk)
    uc, uk = usd_per_rule(cand), usd_per_rule(kept)
    return uc < uk, "usd/rule %.4f vs %.4f" % (uc, uk)



def rewrite_brain(a, run_dir):
    """The round's rewrite call: the runs' --max-tokens too (nina's round 3: a skill cut at 2048 left a stray fence)."""
    return Brain(a.brain, run_dir, spend=a.budget, max_tokens=getattr(a, "max_tokens", None) or 2048)


def summary(card):
    return {"variant": card["variant"], "skill": card.get("skill"), "won": won(card), "structural": structural(card),
            "usd": card["usd"], "rules": card.get("rules"), "usd_per_rule": round(usd_per_rule(card), 4) if card.get("rules") else None}


class SeriesStop(RuntimeError):
    """The series' spend would pass its cap: stop cleanly (nina's R1)."""


class Series:
    """The series' meter: the key's usage since the series started (OpenRouter's /key, a paid brain)
    or the reported costs, whichever is larger. Without a cap (an unpaid brain) it checks nothing."""

    def __init__(self, model, cap, per_call, out):
        self.cap, self.per_call, self.out = cap, per_call, out
        self.done = 0.0                     # the scored cards' usd
        self.largest = 0.0                  # the largest run's usd seen so far (the headroom, N4)
        self.key = Brain(model, out / "series", spend=cap) if cap is not None and model.startswith("openrouter/") else None

    def calls_usd(self):
        return sum(Brain("script:/dev/null", d).reported() for d in sorted((self.out / "calls").glob("r*")))

    def spent(self, rows=()):
        reported = self.done + sum(float(r.get("usd") or 0) for r in rows) + self.calls_usd()
        if self.key is not None:
            return max(self.key.usage() - self.key.start_usage, reported)
        return reported

    def headroom(self, rows=()):
        """What the next run or call may take (the architect's N4): 1.5× the largest run seen, at least
        $0.10, never above the per-run --budget."""
        self.largest = max([self.largest] + [float(r.get("usd") or 0) for r in rows])
        return min(self.per_call or 0, max(0.10, 1.5 * self.largest))

    def check(self, what, rows=()):
        if self.cap is None:
            return
        spent, need = self.spent(rows), self.headroom(rows)
        if spent + need > self.cap:
            raise SeriesStop("%s not started: spent %.4f of the series' %.4f USD, and it may take up to %.4f"
                             % (what, spent, self.cap, need))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy.rewrite", description=__doc__.split("\n")[0])
    scorecard.add_arguments(ap)
    ap.add_argument("--skill", required=True, help="round 0's skill file")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--start-card", help="round 0's card, already scored (its runs under --runs)")
    ap.add_argument("--series-budget", type=float, default=None, help="USD for the whole series (required for a paid brain)")
    a = ap.parse_args(argv)
    if a.brain.startswith("openrouter/") and (a.budget is None or a.series_budget is None):
        ap.error("a paid brain needs --budget (per run and per rewrite call) and --series-budget")
    runs = Path(a.runs).resolve()
    out = runs / "rewrite"
    (out / "skills").mkdir(parents=True, exist_ok=True)
    skill_path = out / "skills" / "r0.md"
    skill_path.write_text(Path(a.skill).read_text())
    series = Series(a.brain, a.series_budget, a.budget, out)
    history, kept = [], None

    def score(variant, path):
        guard = lambda rows: series.check("%s's next run" % variant, rows)   # noqa: E731
        card = scorecard.score_variant(a, variant, str(path), runs, guard=guard)
        series.done += card["usd"]
        return card

    def write():
        (out / "history.json").write_text(json.dumps(history, indent=1))

    try:
        if a.start_card:
            kept = json.loads(Path(a.start_card).read_text())
            # nina's N3: the rounds rewrite r0.md (the --skill copy), which must be the card's skill
            if kept.get("skill") and Path(kept["skill"]).exists() and Path(kept["skill"]).read_text() != skill_path.read_text():
                ap.error("--start-card was scored with %s, not --skill's text" % kept["skill"])
            kept = dict(kept, skill=str(skill_path))
        else:
            kept = score("rw0", skill_path)
        history.append({"round": 0, "skill": str(skill_path), "card": summary(kept), "kept": True})
        write()
        for k in range(1, a.rounds + 1):
            old = Path(kept["skill"]).read_text()
            series.check("round %d's rewrite call" % k)
            try:
                text = rewrite_brain(a, out / "calls" / ("r%d" % k)).ask(prompt(old, digest(kept, runs)), "rewrite")
            except Budget as e:                               # the call's own cap
                raise SeriesStop("round %d's rewrite call: %s" % (k, e)) from None
            new = md_block(text)
            missing = [h for h in HEADINGS if h not in new]
            path = out / "skills" / ("r%d.md" % k)
            path.write_text(new)
            diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "r%d" % (k - 1), "r%d" % k))
            if missing or new.strip() == old.strip():
                history.append({"round": k, "skill": str(path), "kept": False, "diff": diff,
                                "why": "the rewrite lost %s" % ", ".join(missing) if missing else "the rewrite changed nothing"})
                print("round %d: not scored (%s)" % (k, history[-1]["why"]), flush=True)
                write()
                continue
            history.append({"round": k, "skill": str(path), "kept": False, "diff": diff, "why": "scoring"})
            card = score("rw%d" % k, path)
            ok, why = better(card, kept)
            history[-1].update(card=summary(card), kept=ok, why=why)
            print("round %d: %s — %s" % (k, "KEPT" if ok else "not kept", why), flush=True)
            if ok:
                kept = card
            write()
    except SeriesStop as e:
        if history and history[-1].get("why") == "scoring":
            history[-1]["why"] = "the series stopped while its card was scored"
        history.append({"stopped": str(e), "spent": round(series.spent(), 4)})
        print("the series stopped: %s" % e, flush=True)
    write()
    print("history: %s; the kept skill: %s; rewrite calls usd %.4f; the series usd %.4f"
          % (out / "history.json", kept and kept.get("skill"), series.calls_usd(), series.spent()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
