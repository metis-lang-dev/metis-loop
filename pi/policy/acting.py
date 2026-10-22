"""The kernel acting with a world's host attached, one rule at a time — the loop every world adapter's
act() runs, and the hierarchy's runner (hier.py) runs per activation over one host.

A world adapter gives the four world-specific parts (alfworld.py, scienceworld.py, minihack.py):

    w._host_for(pkg_dir)                 a fresh host for the game (the world as it starts)
    w._before(host)                      what the record needs from before the step (the facts, the commands so far)
    w._after(host, pre, name, rv, ev)    after the fired rule: its transition record when the host sent a command, else None
    w._sync(host, counts)                the do-lines that bring the program's dynamic facts to the world's
    w._rule_verb(name)                   the host's (verb, bindings) for a rule's name, or None

    out = new_out(iid)
    why = fire(w, host, shell, rng, out, steps, stop=None)    # "quiet" | "done" | "won" | "stuck" | "steps" | "stop"
"""
from .alfworld import kind_of


def new_out(iid):
    return {"game": iid, "commands": [], "refused": 0, "won": False, "steps": 0, "stuck": [], "transitions": []}


def apply_lines(counts, lines):
    for line in lines or []:
        sign, rest = line[0], line[1:].split()
        atom, n = rest[0], int(rest[1]) if len(rest) > 1 else 1
        counts[atom] = max(0, counts.get(atom, 0) + (n if sign == "+" else -n))
    return {a: n for a, n in counts.items() if n > 0}


def fire(w, host, sh, rng, out, steps, stop=None):
    """The session's enabled rules fired one at a time (the reference sampler's tier, seeded), each
    command through the host, the world synced back after each; until quiet, the world's end, the
    task's stuck, `steps` firings, or `stop(sh)` (the hierarchy: a result for another domain)."""
    for _ in range(steps):
        ws = sh._candidates()
        if not ws:
            return "quiet"
        if host.done:
            return "done"
        pre = w._before(host)
        i = rng.choices([i for i, _ in ws], weights=[x for _, x in ws])[0]
        name = sh._fire(i, ws=ws)
        out["steps"] += 1
        rv = w._rule_verb(name)
        if rv is not None:
            host.on_event(name, ())
        t = w._after(host, pre, name, rv, sh.events_tbl[i][2])
        if t is not None:
            out["transitions"].append(t)
            out["commands"].append(t["command"])
            out["refused"] += 0 if (t["admissible"] and t.get("changed", True)) else 1
        sh.counts = apply_lines(dict(sh.counts), w._sync(host, dict(sh.counts)))
        out["stuck"] = sorted(a for a in sh.counts if kind_of(a) == "stuck")
        if host.won:
            return "won"
        if out["stuck"]:
            return "stuck"
        if stop is not None and stop(sh):
            return "stop"
    return "steps"
