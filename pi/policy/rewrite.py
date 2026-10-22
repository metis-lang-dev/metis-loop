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
from policy.brain import Brain  # noqa: E402

HEADINGS = ("## always", "## explore", "## exploit", "## refactor")


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def digest(card, runs, limit=14000):
    """What the kept skill's runs did, for the brain: per run, its end, and every proposal (phase,
    purpose, verdict, numbers, the gate's reasons; the brain's lines when refused), the fit-repair
    reasons, the disengagement."""
    out = []
    for row in card["rows"]:
        d = Path(runs) / card["variant"] / ("%s-s%d" % (row["world"], row["seed"]))
        out.append("### %s seed %d — phase %s, %s/%s accepted, held-out flat %s director %s, %s" % (
            row["world"], row["seed"], row.get("phase"), row.get("accepted"), row.get("proposals"),
            row.get("heldout_flat"), row.get("heldout_director"), row.get("status")))
        # the brain's calls that a proposal follows (a compile repair, a probe's pick and the rewrite make none)
        answers = [p for p in sorted(jl(d / "prompts.jsonl"), key=lambda p: p.get("call", 0))
                   if not str(p.get("purpose", "")).endswith("-repair") and p.get("purpose") not in ("probe-pick", "rewrite")]
        props = [e for e in jl(d / "state" / "journal.jsonl") if e.get("event") == "proposal"]
        for k, e in enumerate(props):
            nums = {key: v for key, v in (e.get("numbers") or {}).items() if key not in ("vector",)}
            line = "- %s %s: %s %s; why: %s" % (e.get("phase"), e.get("domain"), e.get("verdict"), json.dumps(nums),
                                                  "; ".join((e.get("why") or [])[:3]))
            out.append(line)
            if e.get("verdict") == "refuse" and k < len(answers):
                ans = (answers[k].get("answer") or "").strip().replace("\n", " ")
                out.append("  the brain's lines: " + ans[:300])
        for ev in jl(d / "run.log.jsonl"):
            if ev.get("event") == "fit-repair":
                out.append("- fit-repair (%s): %s" % (ev.get("purpose"), str(ev.get("why"))[:300]))
            if ev.get("event") == "disengaged":
                out.append("- disengaged: %s" % ev.get("reason"))
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
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            body = parts[i]
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
    equal and, when both cards' guards hold, more domains exercised; or then a lower usd/rule."""
    wc, wk = won(cand), won(kept)
    if any(wc.get(w, 0) < wk.get(w, 0) for w in wk):
        return False, "fewer held-out wins on %s" % ", ".join(w for w in wk if wc.get(w, 0) < wk.get(w, 0))
    if sum(wc.values()) > sum(wk.values()):
        return True, "more held-out wins (%d > %d)" % (sum(wc.values()), sum(wk.values()))
    sc, sk = structural(cand), structural(kept)
    if sc is not None and sk is not None and sc != sk:
        return sc > sk, "domains exercised %d vs %d" % (sc, sk)
    uc, uk = usd_per_rule(cand), usd_per_rule(kept)
    return uc < uk, "usd/rule %.4f vs %.4f" % (uc, uk)


def summary(card):
    return {"variant": card["variant"], "skill": card.get("skill"), "won": won(card), "structural": structural(card),
            "usd": card["usd"], "rules": card.get("rules"), "usd_per_rule": round(usd_per_rule(card), 4) if card.get("rules") else None}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy.rewrite", description=__doc__.split("\n")[0])
    scorecard.add_arguments(ap)
    ap.add_argument("--skill", required=True, help="round 0's skill file")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--start-card", help="round 0's card, already scored (its runs under --runs)")
    a = ap.parse_args(argv)
    if a.brain.startswith("openrouter/") and a.budget is None:
        ap.error("a paid brain needs --budget (per run and per rewrite call)")
    runs = Path(a.runs).resolve()
    out = runs / "rewrite"
    (out / "skills").mkdir(parents=True, exist_ok=True)
    skill_path = out / "skills" / "r0.md"
    skill_path.write_text(Path(a.skill).read_text())
    kept = json.loads(Path(a.start_card).read_text()) if a.start_card else scorecard.score_variant(a, "rw0", str(skill_path), runs)
    history = [{"round": 0, "skill": str(skill_path), "card": summary(kept), "kept": True}]
    brain = Brain(a.brain, out, spend=a.budget)
    for k in range(1, a.rounds + 1):
        old = Path(kept.get("skill") or skill_path).read_text()
        text = brain.ask(prompt(old, digest(kept, runs)), "rewrite")
        new = md_block(text)
        missing = [h for h in HEADINGS if h not in new]
        path = out / "skills" / ("r%d.md" % k)
        path.write_text(new)
        diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "r%d" % (k - 1), "r%d" % k))
        if missing or new.strip() == old.strip():
            history.append({"round": k, "skill": str(path), "kept": False, "diff": diff,
                            "why": "the rewrite lost %s" % ", ".join(missing) if missing else "the rewrite changed nothing"})
            print("round %d: not scored (%s)" % (k, history[-1]["why"]), flush=True)
            continue
        card = scorecard.score_variant(a, "rw%d" % k, str(path), runs)
        ok, why = better(card, kept)
        history.append({"round": k, "skill": str(path), "card": summary(card), "kept": ok, "why": why, "diff": diff})
        print("round %d: %s — %s" % (k, "KEPT" if ok else "not kept", why), flush=True)
        if ok:
            kept = card
        (out / "history.json").write_text(json.dumps(history, indent=1))
    (out / "history.json").write_text(json.dumps(history, indent=1))
    print("history: %s; the kept skill: %s; rewrite calls usd %.4f" % (out / "history.json", kept.get("skill"), brain.reported()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
