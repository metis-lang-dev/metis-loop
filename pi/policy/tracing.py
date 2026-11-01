"""tracing — the run's trace (metis.trace; trace-replay s-c111ff41): what the driver did, in one order, under RUN/trace/. It only
reads: the loop decides nothing from it. The driver has no ticks, so the header says clock: firing and each line says its own:

    {"k", "clock": "witness", "file": "transitions"|"surprises"|"heldout", "rec": <its line there>, "phase", "game", "t", "command",
     "base": <the base that judged it>, "checkpoint"?}     a world's step, one record: a walker's, with no program; a surprise's
    {"k", "clock": "episode", "episode": e, "game", "seed", "base", "start": {stage, counts}, "checkpoint"}     an acting episode begins
    {"k", "clock": "firing", "episode": e, "name", "lines", "command"?}     one rule of it: what fired, the lines the world then gave

RUN/trace/bases/<key>.llp: each base a line names. RUN/trace/checkpoints/k<k>.json: the world's snapshot there (the adapter's). The
walk's records stay where they are; a witness points at them. metis.trace.replay_firings replays an episode."""
import hashlib
import json

from metis import trace as T


class RunTrace:
    EVERY = 50                                     # a world's checkpoint every so many witnesses, and at each surprise

    def __init__(self, run, world, family, seed):
        self.seg = T.Segments(run / "trace", every=0, ring=0, keep=True)
        self.k, self.bases, self.episodes = self.seg.last_k() + 1, {}, 0
        (run / "trace" / "bases").mkdir(exist_ok=True)
        self.dir = run / "trace"
        self.lines = {f: self.count(run / "records" / ("%s.jsonl" % f)) for f in ("transitions", "surprises", "heldout")}
        self.seg.open_segment(self.k, {"clock": "firing", "world": world, "family": family, "seed": seed, "protocol": T.protocol_key(),
                                       "members": {}}, {"sessions": {}, "world": None})
        self.since = 0

    @staticmethod
    def count(p):
        return sum(1 for _ in open(p)) if p.exists() else 0

    def base_key(self, text):
        key = hashlib.sha256(text.encode()).hexdigest()[:16]
        if key not in self.bases:
            f = self.dir / "bases" / ("%s.llp" % key)
            if not f.exists():
                f.write_text(text)
            self.bases[key] = True
        return key

    def line(self, rec):
        self.seg.line(dict(rec, k=self.k))
        self.k += 1

    def witness(self, rec, file, base, where=None, at_surprise=False):
        """One record just written to records/FILE.jsonl. WHERE: the world's snapshot (a checkpoint every EVERY, and at a surprise)."""
        i, self.lines[file] = self.lines[file], self.lines[file] + 1
        line = {"clock": "witness", "file": file, "rec": i, "phase": rec.get("phase"), "game": rec.get("game"), "t": rec.get("t"),
                "command": rec.get("command"), "base": self.base_key(base)}
        self.since += 1
        if where is not None and (at_surprise or self.since >= self.EVERY):
            line["checkpoint"] = self.seg.checkpoint(self.k, {"world": where})
            self.since = 0
        self.line(line)

    def episode(self, ep, game, seed, base, where):
        """An acting episode just ended (acting.fire's `start` and `firings`)."""
        self.episodes += 1
        self.line({"clock": "episode", "episode": self.episodes, "game": game, "seed": seed, "base": self.base_key(base), "start": ep.get("start"),
                   "checkpoint": self.seg.checkpoint(self.k, {"world": where})})
        for f in ep.get("firings", ()):
            self.line(dict(f, clock="firing", episode=self.episodes))

    def close(self):
        self.seg.close()


def read(run):
    """All the lines, in order: [(header, lines)] per run of the driver."""
    return [(s.header, s.ticks) for s in T.read(run / "trace")]


def checkpoint(run, name):
    return json.loads((run / "trace" / name).read_text())


def program_at(run, game, base, domain, into):
    """The game's instance over the base a line names, as it stood then, under INTO: → its .llp (the instance stays; only the base moved)."""
    import shutil
    tree = into / base
    if not (tree / game).exists():
        shutil.copytree(run / "trees" / "current" / game, tree / game)
        (tree / "base").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / "trace" / "bases" / ("%s.llp" % base), tree / "base" / ("%s.llp" % domain))
    return tree / game / ("%s.llp" % game)


def replay_episodes(run, domain, into):
    """Every acting episode of the run, each from its start: {(episode's k): metis.trace.Replay}."""
    out = {}
    for _, lines in read(run):
        episodes = {}
        for x in lines:
            if x["clock"] == "episode":
                episodes[x["episode"]] = (x, [])
            elif x["clock"] == "firing":
                episodes[x["episode"]][1].append(x)
        for e, (head, firings) in episodes.items():
            prog = program_at(run, head["game"], head["base"], domain, into)
            out[head["k"]] = T.replay_firings(prog, head["start"], head["seed"], firings, member=head["game"])
    return out
