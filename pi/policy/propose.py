"""propose — a hand-written amendment, judged and ruled on (trace-replay s-c111ff41; pi/docs/POLICY.md): the verb the loop lacked, formalize being the only way in.

    propose.sh --pack FILE --member M --trace TRACE --root ROOT --config CONFIG --run DIR [--composition domains] [--unit FILE] [--case CASE ...] [--record R] [--surprise R]
               [--brain openrouter/deepseek/deepseek-v4-flash --budget 0.10] [--closed-loop "CMD"]

The pack takes the place of the model's draft and gets the same judgement (metis_agent.trace.judge): the gate cascade (a repeated rule, the link, the I-checks, the receipt: whose
key moved, ei_key), every member's goldens and the surprises' cases, the fired diff on the composition's replay of the trace (the takes regenerated, no world, no model). The
verdict is the gate's, mechanically. The model then writes the ruling's words from that evidence, and its comments on the rule's text (premises, stage, competition with a rule
already there), and cannot move the verdict; a person reviews after. Written to RUN/ruling.md and RUN/evidence.json, and printed. Exit 0 accepted, 1 refused, 2 not judged: past its time budget, which is no verdict at all."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

RULING = """You review a hand-written amendment to a package of rules, for the person who wrote it and the person who will review it. The gate has already judged it, on a recorded trace with no world;
its verdict is final here. You do not change it: you explain it and comment on the rule's text.

Write, in plain words and short:
1. The ruling: "{verdict}", and why, naming what decided it (the golden, the case, the divergence's tick and member, the receipt) from the evidence alone.
2. For each rule of the pack, one paragraph headed "agree", "agree, with changes" or "reject, as shaped":
   its premises (does each read what its name says; is one missing that a stop or a yield needs; can the rule fire where it demands what it cannot do),
   its stage (is it among the rules it should be, before the ones it must pre-empt), and its competition with a rule already there (which rule is enabled with it, which fires, what that does).
3. What this trace cannot show: it is open-loop past the first differing output: the later ticks are of a world that obeyed the old command.

How to read the rules. A rule is `premises -o effects`; `$x` reads x and keeps it, a bare atom is consumed. A rule whose name is of a command's kind is a command: firing it IS the effect, the
host acts by its name, so `... * now -o ().` is not empty: it spends this period's `now` and gives that command. Rules enabled together in a stage are chosen by the sampler, not by their order; a stage
runs before the next, so a safety rule that fires pre-empts the progress rules by consuming `now`.

The words. A "golden" is a committed case of a package (under `goldens`); a "case" is the surprise's (under `cases`). A family's other users are "consumers". The rows at and after `open_loop_after` are the candidate's
rules differing on RECORDED inputs: never "the world's response", for no world answered them; say so if you speak of them.

Say only what the evidence and the text show. Mark a guess as a guess. No preamble.

The verdict: {verdict}
The gate's reasons:
{reasons}

The pack:
```llp
{pack}
```

The evidence (JSON):
{evidence}

The rules it runs beside:
{beside}

The declarations of what the pack's rules read (a premise's meaning is here: judge it against these, and say when one is not declared where it was looked for):
{declared}
"""


def brief(e, rows=12):
    """The evidence, as the model and a person read it: the diff's first rows, no paths."""
    keep = {k: e.get(k) for k in ("member", "unit", "rules", "pack", "duplicates", "gate_error", "consumers", "moved", "moved_diff", "lint", "reads_absent", "inert", "unjudged", "first_enabled", "first_fired_diff", "first_out_diff", "open_loop_after", "members", "goldens", "cases") if e.get(k) not in (None, [], {}, False)}
    r = e.get("receipt") or {}
    keep["receipt"] = {k: r.get(k) for k in ("moved", "ei_holds", "errors") if r.get(k) is not None}
    if e.get("rows"):
        keep["rows"], keep["rows_total"] = e["rows"][:rows], len(e["rows"])
    return keep


def beside_text(e, unit_texts):
    from metis import trace as T
    names = {x.split("[")[0] for x in ((e.get("first_enabled") or {}).get("beside") or ())}
    names |= {d["other"] for d in e.get("duplicates") or ()}
    rules = {}
    for text in unit_texts.values():
        rules.update(T.rules_of(text))
    return "\n".join("%s" % rules[n] for n in sorted(names) if n in rules) or "(none enabled beside it)"


def declarations(pack, unit_texts):
    """The `pred`, `bwd` lines, with their comments, of what the pack's rules read and make, and the `type` lines of their arguments: a value is not a type, and the type says which values there are;
    the names found nowhere are said."""
    import re
    from metis import trace as T
    names = set()
    for st in T.rules_of(pack).values():
        names |= set(re.findall(r"\$?\b([a-z_][A-Za-z0-9_]*)\b\s*(?:\(|\*|-o|\.|$)", st.split(":", 1)[1]))
    names -= {"o"}
    out, found, wanted, typed = [], set(), set(), set()
    for text in list(unit_texts.values()) + [pack]:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"\s*(?:pred|bwd)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
            if m and m.group(1) in names and m.group(1) not in found:
                found.add(m.group(1))
                above = lines[i - 1].strip() if i and lines[i - 1].strip().startswith("%") else ""
                out.append((above + "\n" if above else "") + line.strip())
                args = re.match(r"\s*(?:pred|bwd)\s+[A-Za-z_]\w*\(([^)]*)\)", line)
                wanted |= {x.strip() for x in args.group(1).split(",")} if args else set()
    for text in list(unit_texts.values()) + [pack]:
        for line in text.splitlines():
            m = re.match(r"\s*type\s+([A-Za-z_]\w*)\s*\{", line)
            if m and m.group(1) in wanted and m.group(1) not in typed:
                typed.add(m.group(1))
                out.append(line.strip())
    missing = sorted(names - found)
    return "\n".join(out + (["Not declared in the units read: %s." % ", ".join(missing)] if missing else [])) or "(none)"


def certificate(e, closed):
    lines = ["**Open-loop:** " + ("every tick of the trace to its first differing output (tick %s), and past it only as a world that obeyed the old command." % e["open_loop_after"] if e.get("open_loop_after") is not None
                                  else "the candidate's outputs on this trace are the record's." if e.get("first_enabled") else "no candidate rule was enabled on this trace: it says nothing of the rule's effect.")]
    if closed:
        lines.append("**Closed-loop:** `%s` %s." % (closed["cmd"], "passed" if closed["code"] == 0 else "failed, exit %d" % closed["code"]))
    else:
        lines.append("**Closed-loop:** not run. This ruling has no world.")
    return lines


HEADER = {"identified": "", "identified in part": " (identified in part)",
          "not identified": " (not identified: it does not change the surprise's tick)"}


def unit_text(root, unit):
    """The text of the unit the pack amends (--unit, under the root or as given), "" when none is given or found: identify.consumes_more reads it."""
    if not unit:
        return ""
    for f in (Path(root) / unit, Path(unit)):
        if f.is_file():
            return f.read_text()
    return ""


def document(e, comments, closed, spent):
    i = e.get("identification")                # loop-improvement step 3 (s-5e34eb35): what the record identifies, in place of "(inert)"; the verdict stays the gate's
    shown = i if i and i.get("word") != "nothing identified" else None
    if i:
        suffix = HEADER.get(i.get("word"), "") if e["verdict"] == "accepted" else ""
    else:
        suffix = " (inert)" if e.get("inert") else ""
    out = ["# Ruling: %s%s" % (e["verdict"], suffix), ""]
    if e.get("inert") and not i:
        out += ["**Inert:** no candidate rule was enabled on this trace, so this acceptance says nothing of the rule's effect: find a world or a seed where it fires (Search the seeds for a firing).", ""]
    out += ["**%s**, %s; the program unit %s." % (e.get("member"), ", ".join(e.get("rules") or ()) or "no rule", e.get("unit")), ""]
    if e.get("unjudged"):                      # loop-prompt judge-session: a weight port the trace does not carry
        out += ["**Unjudged:** %s declare%s weight ports the trace does not carry: %s choices are the record's, stood in, so %s rows are not this ruling's evidence." % (
            ", ".join(e["unjudged"]), "s" if len(e["unjudged"]) == 1 else "", "its" if len(e["unjudged"]) == 1 else "their", "its" if len(e["unjudged"]) == 1 else "their"), ""]
    if e.get("why") == "kind":                 # spec 20 §5: refused before the cascade, by the record's kind
        out += ["**Kind:** the record is %s, not structural: no pack answers it. Its route: %s." % (e.get("kind"), e.get("route")), ""]
    if shown:
        out += ["## What this record identifies: %s" % shown["word"]] + [x if x.startswith("  ") else "- %s" % x for x in shown.get("lines") or ()] + [""]
    if e["reasons"]:
        out += ["## Why it is %s" % e["verdict"]] + ["- %s" % r for r in e["reasons"]] + [""]
    if e.get("times"):
        out += ["The judgement's time: %s." % ", ".join("%s %s s" % (x["stage"], x.get("seconds", "?")) for x in e["times"]), ""]
    r = e.get("receipt") or {}
    if r.get("moved") is not None:
        ei = "" if r.get("ei_holds") is None else (", ei_key holds" if r["ei_holds"] else ", **ei_key moved**")
        out += ["## The receipt", "Programs moved: %s%s." % (", ".join(r["moved"]) or "none", ei), ""]
    if e.get("first_enabled") or e.get("first_fired_diff"):
        out += ["## The fired diff"]
        if e.get("first_enabled"):
            out.append("- First enabled: tick %s, %s, beside %s." % (e["first_enabled"]["k"], e["first_enabled"]["rule"], ", ".join(e["first_enabled"].get("beside") or ()) or "nothing"))
        else:
            out.append("- Never enabled on this trace.")
        for key, what in (("first_fired_diff", "First fired difference"), ("first_out_diff", "First differing output")):
            d = e.get(key)
            out.append("- %s: %s." % (what, "tick %s, %s: the record %s, the candidate %s" % (d["k"], d["member"], d["record"], d["candidate"]) if d else "none"))
        if e.get("members"):
            out.append("- First difference per member: %s." % ", ".join("%s at %s" % kv for kv in sorted(e["members"].items(), key=lambda x: x[1])))
        out.append("")
    if e.get("cases"):
        out += ["## The cases"]
        for c in e["cases"]:
            comp = c.get("composition")
            out.append("- %s (%s, tick %s): %s in the package's harness%s." % (c["file"], c["member"], c.get("at"), "passes" if c["passed"] else "fails",
                                                                                 "" if not comp else "; %s on the composition%s" % ("passes" if comp["passed"] else "fails", ", open-loop" if comp["open_loop"] else "")))
        out.append("")
    if e.get("goldens"):
        ran = e["goldens"].get("ran") or {}
        total = sum(ran.values())
        out += ["## The goldens", ("**No golden ran**: nothing here holds the candidate to the package's cases." if not total else
                                   "%d cases (%s), none broken, on seeds 1 to 3." % (total, ", ".join("%s %d" % kv for kv in sorted(ran.items()))) if e["goldens"]["ok"]
                                   else "%d of %d cases refused: named above." % (len({(x["file"], x.get("member")) for x in e["goldens"]["failed"]}), total))]
        if e.get("moved"):
            out.append("**Moved with the amendment, held in their new text:** %s. A person reads these." % ", ".join(e["moved"]))
            for d in e.get("moved_diff") or ():
                out.append("- %s: %s." % (d["file"], "a rename only (%s)" % ", ".join(d["keys"]) if d.get("rename_only") else "more than a rename: %s changed" % ", ".join(d["keys"]) if d.get("keys") else d.get("error") or "identical to the case it replaces"))
        if e["goldens"].get("skipped"):
            out.append("Skipped, not this consumer's: %s." % "; ".join("%s of %s (%s)" % (x["file"], x["member"], x["why"]) for x in e["goldens"]["skipped"]))
        if e["goldens"].get("already_failing"):
            out.append("Already failing on the program as it is, so not counted: %s." % "; ".join(e["goldens"]["already_failing"]))
        out.append("")
    if e.get("reads_absent"):
        out += ["## Readings the trace never carries", "The candidate reads %s, and no tick of this trace holds any of them: on this trace the rule is judged as never enabled (Class before reader: a class lands before its reader, on a trace that carries it)." % ", ".join("`%s`" % p for p in e["reads_absent"]), ""]
    if e.get("lint") is not None:
        out += ["## Lint"] + (["```", *e["lint"], "```"] if e["lint"] else ["no lint finding on the amended unit."]) + [""]
    out += ["## The certificate"] + certificate(e, closed) + [""]
    out += ["## The model's words"] + ([comments.strip()] if comments else ["(no model was asked: the verdict and the evidence above stand alone)"]) + [""]
    out += ["A person reviews this. Spend: %.4f USD." % spent, ""]
    return "\n".join(out)


def rule(e, pack, unit_texts, brain):
    prompt = RULING.format(verdict=e["verdict"], reasons="\n".join("- %s" % r for r in e["reasons"]) or "- none: every check held", pack=pack.strip(),
                           evidence=json.dumps(brief(e), indent=1, default=str), beside=beside_text(e, unit_texts), declared=declarations(pack, unit_texts))
    return brain.ask(prompt, "ruling")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="propose", description=__doc__.split("\n")[0])
    ap.add_argument("--pack", required=True, help="the hand-written llp: rules in `stage S { }`, `pred` lines, `drop NAME`; or a whole program")
    ap.add_argument("--member", required=True)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--root", required=True, help="the catalog root: judged on a copy, never written")
    ap.add_argument("--config", required=True, help="the run's service config, without its trace")
    ap.add_argument("--run", required=True, help="where the ruling goes")
    ap.add_argument("--composition", help="the composition's directory under the root (for the receipt, and an image's run)")
    ap.add_argument("--unit", help="the file the pack amends (default the member's program); under METIS_HOME: the family's, judged on a copy of it")
    ap.add_argument("--move-golden", action="append", default=[], metavar="FILE", help="a golden the amendment moves with it: FILE replaces the case of its name, on the copy; the ruling lists it, for a person to read")
    ap.add_argument("--consumer", action="append", default=[], metavar="NAME=ROOT[:COMPOSITION]", help="the family's other consumer: it must still link and keep its goldens (spec/18 §5)")
    ap.add_argument("--case", action="append", default=[], help="a surprise's case (metis.trace case)")
    ap.add_argument("--record", help="the surprise's record (JSON, .metis/surprises/ID.json): its kind is read before the cascade (spec 20 §5): "
                                     "a record not structural is refused at once with its kind and route")
    ap.add_argument("--surprise", help="the surprise's record (JSON), read only for its tick (k, or k0..k1): the ruling says what this record identifies of the pack "
                                       "(policy/identify.py: target, earlier, support, consumes). Not --record, which is the kind gate's")
    ap.add_argument("--brain", help="the model that writes the ruling's words: openrouter/<model> (the key from the environment only), script:FILE; none: the evidence alone")
    ap.add_argument("--budget", type=float, default=None, help="a paid brain's spend cap (USD)")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--time-budget", type=float, default=1800, help="seconds for the whole judgement; past it the ruling says not judged, and which stage (default 1800)")
    ap.add_argument("--golden-budget", type=float, default=120, help="seconds for one run of one golden (default 120)")
    ap.add_argument("--closed-loop", help="a command run once on an accepted pack, on the real tree after you apply it: its result is the certificate's second line")
    a = ap.parse_args(argv)
    if a.brain and a.brain.startswith("openrouter/") and a.budget is None:
        ap.error("a paid brain needs --budget (USD)")
    from metis_agent import service as S
    from metis_agent import trace as AT
    run = Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    pack = Path(a.pack).read_text()
    try:                                       # a bad config refused in words (the alf drive's L3: a traceback, then "the gate: 'v3'")
        cfg = S.load_config(a.config)
    except FileNotFoundError:
        sys.exit(f"propose.sh: --config {a.config}: there is no such file")
    except Exception as e:  # noqa: BLE001 — YAML that does not read
        sys.exit(f"propose.sh: --config {a.config} does not read as YAML: {str(e).splitlines()[0][:200]}")
    if not isinstance(cfg, dict) or not isinstance(cfg.get("v3"), dict):
        sys.exit(f"propose.sh: --config {a.config} is not a service config: it has no v3 section (the Live's: its "
                 "composition, its catalog); the judge replays the bundle on it")
    cfg.pop("trace", None)

    def config(root):
        c = copy.deepcopy(cfg)
        if c["v3"].get("image") and a.composition:
            c["v3"]["image"] = str(Path(root) / a.composition)
        return c
    consumers = []
    for c in a.consumer:
        name, _, rest = c.partition("=")
        where, _, comp = rest.partition(":")
        consumers.append((name, where, comp or None))
    kw = {}
    if a.record:
        import inspect
        try:
            record = json.loads(Path(a.record).read_text())
        except (OSError, ValueError) as x:
            sys.exit(f"propose.sh: --record {a.record}: {x}")
        if "record" in inspect.signature(AT.judge).parameters:
            kw["record"] = record
        else:                                  # a metis-agent before the kind gate (surprise-kinds s-7a02c2ac): said, never silent
            print(f"propose.sh: this metis-agent's judge reads no record kind; {a.record} judged as a structural one", file=sys.stderr)
    e = AT.judge(a.trace, a.member, pack, a.root, config, cases=[Path(c) for c in a.case], composition=a.composition, unit=a.unit, consumers=consumers, budget=a.time_budget, golden_budget=a.golden_budget, moved=a.move_golden, **kw)
    if a.surprise and e["verdict"] != "not judged":
        from . import identify as I
        try:
            surprise = json.loads(Path(a.surprise).read_text())
        except (OSError, ValueError) as x:
            sys.exit(f"propose.sh: --surprise {a.surprise}: {x}")
        e["identification"] = I.identification(e, surprise, pack, unit_text(a.root, a.unit))
    (run / "evidence.json").write_text(json.dumps(e, indent=1, default=str))
    closed = None
    if a.closed_loop and e["verdict"] == "accepted":
        closed = {"cmd": a.closed_loop, "code": subprocess.run(a.closed_loop, shell=True).returncode}
    comments, spent = None, 0.0
    if a.brain and e["verdict"] != "not judged":      # no evidence, no ruling's words: nothing is spent on it
        from .brain import Brain
        brain = Brain(a.brain, run, spend=a.budget, max_tokens=a.max_tokens)
        target = Path(a.unit) if a.unit else Path(a.root) / e["unit"]
        try:
            comments = rule(e, pack, AT._closure(target, target.read_text(), ()), brain)
        except Exception as x:  # noqa: BLE001 — the verdict is the gate's: a model that fails loses the words, never the ruling
            comments = "(the model failed: %s: %s)" % (type(x).__name__, str(x)[:200])
        spent = brain.spent()
    text = document(e, comments, closed, spent)
    (run / "ruling.md").write_text(text)
    print(text)
    return {"accepted": 0, "refused": 1}.get(e["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())
