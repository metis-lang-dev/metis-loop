"""identify — what a record identifies of a pack, before it is judged (EXPERIMENT, branch loop-identify; reports/metis-critique: identification is the loop's concern).

A ruling's evidence is observational: one recorded trace of a world that obeyed the OLD program. The judge's replay is the intervention do(program := candidate) on the
recorded inputs, exact to the first differing output and open-loop past it. So three questions decide whether this record can say anything of a pack, each read from
the judge's evidence (metis_agent.trace.judge) and the surprise's tick, none of them a verdict:

  target    does the candidate do something else than the record AT the surprise's tick(s)? If not, the pack is no answer to this surprise, whatever the gate says.
  earlier   does it do something else BEFORE the surprise? Those ticks the person did not report: the pack is broader than the surprise.
  support   is each rule the pack adds or changes ENABLED anywhere on the record (positivity)? A rule never enabled is shown only by what it no longer does;
            what it does when it fires (what it consumes, what it makes) is not in this record.

and one read from the text: a premise the changed rule now CONSUMES that it did not before, and that other rules of the unit need (an effect past the record).

    identification(e, record, pack, unit_text) → {"word", "target", "earlier", "support", "consumes", "lines"}
"""
import re

RULE = re.compile(r"^\s*([a-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\])?\s*:([^.]*?)-o([^.]*)\.", re.M)


def _atoms(side):
    """[(pred, read?)] of one side of a rule: `$x` reads x, a bare atom is consumed; comparisons (`L <> L2`) are no atoms."""
    out = []
    for part in side.split("*"):
        part = part.strip()
        if not part or part == "()" or re.search(r"<>|=|<|>", part):
            continue
        m = re.match(r"(\$?)\s*([a-z_][A-Za-z0-9_]*)", part)
        if m:
            out.append((m.group(2), bool(m.group(1))))
    return out


def rules(text):
    return {m.group(1): (m.group(2), m.group(3)) for m in RULE.finditer(text)}


def window(record):
    """The surprise's ticks (k, or k0..k1) → (k0, k1), or None when the record names none."""
    if record.get("k0") is not None and record.get("k1") is not None:
        return int(record["k0"]), int(record["k1"])
    if record.get("k") is not None:
        return int(record["k"]), int(record["k"])
    return None


def consumes_more(pack, unit_text):
    """For each rule the pack replaces (drop NAME + a rule NAME) or adds: the preds it consumes and does not make again, that the old rule (when there was one) did
    not consume, with the unit's other rules that need them. → [{rule, atom, needed_by}]"""
    old, new = rules(unit_text), rules(pack)
    out = []
    for name, (pre, post) in new.items():
        made = {p for p, _ in _atoms(post)}
        took = {p for p, read in _atoms(pre) if not read} - made
        was = {p for p, read in _atoms(old[name][0]) if not read} if name in old else set()
        for a in sorted(took - was):
            if name not in old and any(a in {p for p, read in _atoms(o[0]) if not read} for o in old.values()):
                continue                       # a new rule consuming what the unit's rules already consume (a goal token): no new loss
            needed = sorted(n for n, (p, _) in old.items() if n != name and a in {x for x, _ in _atoms(p)})
            if needed:
                out.append({"rule": name, "atom": a, "needed_by": needed})
    return out


def identification(e, record, pack, unit_text=""):
    w = window(record)
    lines = []
    if not e.get("baseline") or e.get("gate_error") or e.get("link_failed") or e.get("duplicates") or e.get("not_judged") or "rows" not in e:
        return {"word": "nothing identified", "target": [], "earlier": [], "support": None, "consumes": [], "lines": ["The pack did not reach the replay (it does not link, repeats a rule, or the record does not replay): "
                                                         "nothing is identified. pack_propose says why."]}
    rows = [r for r in e.get("rows") or () if r.get("member") == e.get("member") or len({x.get("member") for x in e["rows"]}) == 1]
    fired = [r for r in rows if "fired" in r or "out" in r]

    def names_of(x):                           # the judge's rows carry lists of rule names: said as names, never as a Python list
        return ", ".join(map(str, x)) if isinstance(x, (list, tuple)) else str(x) if x else ""

    def what(r):
        d = r.get("fired") or r.get("out")
        return "tick %s: the record %s, the candidate %s" % (r["k"], names_of(d.get("record")) or "nothing", names_of(d.get("candidate")) or "nothing")
    target = [r for r in fired if w and w[0] <= r["k"] <= w[1]]
    earlier = [r for r in fired if w and r["k"] < w[0]]
    en = e.get("first_enabled")
    names = sorted(e.get("rules") or ())
    at = "tick %s" % w[0] if w and w[0] == w[1] else "ticks %s..%s" % w if w else "the surprise's tick (the record names none)"
    if not w:
        lines.append("TARGET: unknown: the surprise's record names no tick.")
    elif target:
        lines.append("TARGET: yes. At %s the candidate does something else than the record: %s." % (at, "; ".join(what(r) for r in target[:3])))
    else:
        first = min(r["k"] for r in fired) if fired else None
        lines.append("TARGET: NO. At %s the candidate fires exactly what the record fired%s. The pack does not answer this surprise: "
                     "the rule that fired there still fires there. Change THAT rule (drop it and give it the premise it lacked), or say why another tick is the cause."
                     % (at, "" if first is None else "; its first difference is at tick %s" % first))
    if earlier:
        lines.append("EARLIER: the candidate also changes %d tick(s) before the surprise, which the person did not report: %s. "
                     "The pack is broader than the surprise: find what holds at %s and not at those ticks (trace_count), and read it." % (len(earlier), "; ".join(what(r) for r in earlier[:3]), at))
    if en:
        lines.append("SUPPORT: %s is enabled on this record from tick %s, beside %s%s." % (en["rule"], en["k"], ", ".join(en.get("beside") or ()) or "nothing",
                                                                                         "" if fired else ", and never changes what fires: enabled is not fired, the record says nothing of its effect"))
    else:
        lines.append("SUPPORT: none. %s %s never enabled on this record%s." % (", ".join(names) or "the pack's rule", "is" if len(names) == 1 else "are",
                     ": the record shows only what the pack STOPS at %s; what the rule does when it does fire (what it consumes and makes) is not shown here" % at if target
                     else ", and nothing changes: this record says nothing of the pack"))
        if e.get("reads_absent"):
            lines.append("  It reads %s, which no tick of this record holds." % ", ".join(e["reads_absent"]))
    more = consumes_more(pack, unit_text) if unit_text else []
    for c in more:
        lines.append("CONSUMES: %s now consumes %s (a bare premise is consumed; `$%s` reads it and keeps it) and does not make it again; %s need%s it after. "
                     "This record cannot show that loss%s." % (c["rule"], c["atom"], c["atom"], ", ".join(c["needed_by"][:4]), "s" if len(c["needed_by"]) == 1 else "",
                                                               "" if en else ": the rule is never enabled on it"))
    if w and not target:
        word = "not identified"
    elif not w or earlier or more or not en and not target:      # no tick: the target is unknown, so never whole
        word = "identified in part"
    else:
        word = "identified"
    lines.append("SCOPE: the record is exact to the candidate's first differing output%s; past it the ticks are of a world that obeyed the old program."
                 % (" (tick %s)" % e["open_loop_after"] if e.get("open_loop_after") is not None else ""))
    return {"word": word, "target": [r["k"] for r in target], "earlier": [r["k"] for r in earlier], "support": en, "consumes": more, "lines": lines}


def text(i):
    return "\n".join(["## What this record identifies: %s" % i["word"]] + ["- %s" % x for x in i["lines"]])
