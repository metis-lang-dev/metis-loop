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


LEVEL_PREDS = set()      # the level ports the composition declares (manifests' `levels:`): recorded per step, replayed


class Guide(list):
    """The recorded commands to replay, with the level atoms each one's step read (`levels`, aligned): the replay
    reads the records' levels, never the host's — a level is the instrument's number at that tick (brief v2 §B)."""
    def __init__(self, commands=(), levels=None):
        super().__init__(commands)
        self.levels = list(levels) if levels is not None else list(getattr(commands, "levels", []) or [])

    @classmethod
    def of(cls, run):
        """A recorded run's guide: its commands and the levels its transitions recorded."""
        return cls(run["commands"], [t.get("levels") for t in run.get("transitions") or [] if "command" in t])


def levels_in(counts):
    """The level atoms in COUNTS (LEVEL_PREDS)."""
    return {a: n for a, n in counts.items() if n > 0 and kind_of(a) in LEVEL_PREDS} if LEVEL_PREDS else {}


def fire(w, host, sh, rng, out, steps, stop=None, guide=None, feeds=None):
    """The session's enabled rules fired one at a time (the reference sampler's tier, seeded), each
    command through the host, the world synced back after each; until quiet, the world's end, the
    task's stuck, `steps` firings, or `stop(sh)` (the hierarchy: a result for another domain).

    guide: the recorded commands to replay (a list, consumed as they are sent): among the enabled
    events, one that sends the next recorded command first, else one that sends none (bookkeeping) —
    `feeds(ev, command)` (the hierarchy) prefers one that gives the next command's domain its goal —
    else none matches and the replay has diverged ("diverged")."""
    for _ in range(steps):
        ws = sh._candidates()
        if not ws:
            return "quiet"
        if host.done:
            return "done"
        pre = w._before(host)
        if guide is not None:
            i, alt = _guided(w, host, sh, ws, guide, feeds)
            if i is None:
                return "diverged"
            out["alternatives"] = out.get("alternatives", 0) + alt      # nina's N1: another command was enabled beside it
        else:
            i = rng.choices([i for i, _ in ws], weights=[x for _, x in ws])[0]
        name = sh._fire(i, ws=ws)
        out["steps"] += 1
        rv = w._rule_verb(name)
        if rv is not None:
            host.on_event(name, ())
        t = w._after(host, pre, name, rv, sh.events_tbl[i][2])
        recorded = None
        if t is not None and guide is not None and guide:
            guide.pop(0)
            levels = getattr(guide, "levels", None)
            recorded = levels.pop(0) if levels else None
        sh.counts = apply_lines(dict(sh.counts), w._sync(host, dict(sh.counts)))
        if recorded is not None:                     # the replay reads the records' levels at this step, not the host's
            sh.counts = dict({a: n for a, n in sh.counts.items() if kind_of(a) not in LEVEL_PREDS}, **recorded)
        if t is not None:
            if LEVEL_PREDS:
                t["levels"] = levels_in(sh.counts)
            out["transitions"].append(t)
            out["commands"].append(t["command"])
            out["refused"] += 0 if (t["admissible"] and t.get("changed", True)) else 1
        out["stuck"] = sorted(a for a in sh.counts if kind_of(a) == "stuck")
        if host.won:
            return "won"
        if out["stuck"]:
            return "stuck"
        if stop is not None and stop(sh):
            return "stop"
    return "steps"


def _guided(w, host, sh, ws, guide, feeds=None):
    """The enabled event that sends the next recorded command; else one that sends nothing — the one
    whose bindings name the next command's things first (a planner's choice the command follows from).
    → (the event, 1 when another command event was enabled beside the recorded one: the replay shows the
    candidate CAN send the records; `alternatives` counts where it need not)."""
    quiet, hit, other = [], None, 0
    for i, _ in ws:
        name = sh.events_tbl[i][2].name
        cmd = w._command_of(host, name) if w._rule_verb(name) is not None else None
        if cmd is None:
            quiet.append((i, name))
        elif hit is None and guide and cmd == guide[0]:
            hit = i
        else:
            other += 1
    if hit is not None:
        return hit, 1 if other else 0
    if not quiet:
        return None, 0
    if feeds is not None and guide:                 # the hierarchy: a bookkeeping event that feeds the next command's domain first
        fed = [x for x in quiet if feeds(sh.events_tbl[x[0]][2], guide[0])]
        quiet = fed or quiet
    want = set(w._handles_of(host, guide[0])) if guide and hasattr(w, "_handles_of") else set()
    if want:
        best = max(quiet, key=lambda x: len(want & set(v for kv in x[1].partition("[")[2].rstrip("]").split(",")
                                                       for v in [kv.partition("=")[2]] if v)))
        return best[0], 0
    return quiet[0][0], 0
