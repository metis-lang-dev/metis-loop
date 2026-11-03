"""The backend's workspace channels (docs/WORKSPACE.md §3; loop-workspace s-5b4be5fa step 2): `trace`, `surprise`,
`bundle` and `loop`, over metispy's `metis.catalog.workspace` (the one layout, .metis/ in the catalog root), and
the REPL session's trace writer (§3: `open` with `trace: true`).

    page -> gw   {ch:"trace", type:"list", req}                     -> {type:"list", traces}
                 {ch:"trace", type:"open", run, req}                -> {type:"open", trace: {run, path, k0, k1, checkpoints, header}}
                 {ch:"trace", type:"tick", run, member, k, program?, req}
                                                                    -> {type:"tick", k, counts, fired, made, exact}: metis.trace.timeline
                 {ch:"trace", type:"tools", req}                    -> {type:"tools", tools}: metis/trace_tools.json as committed
                 {ch:"trace", type:"verb", name, args, req}         -> {type:"verb", name, code, out, err}: a declared tool, nothing else
                 {ch:"surprise", type:"list", status?, req}         -> {type:"list", surprises}
                 {ch:"surprise", type:"drop", session, k?, window?, atoms?, reading?, words?, req}
                                                                    from a REPL session: its member, its trace when it writes one
                 {ch:"surprise", type:"drop", run, member, k?, window?, atoms?, reading?, words?, req}
                                                                    from a trace: the run's window
                                                                    -> {type:"dropped", id}, and to every page {type:"dropped", id}
                 {ch:"surprise", type:"get", id, req}               -> {type:"get", surprise, md?}: the record, its ruling's document
                 {ch:"bundle", type:"state", req}                   -> {type:"state", bundle}: ws.bundle() (None: no composition)
                 {ch:"bundle", type:"reload", session, req}         -> the session re-opened from its catalog (epoch + 1)
                 {ch:"loop", type:"state", req}                     -> {type:"state", loops, cost, child}
                 {ch:"loop", type:"events", since?, req}            -> {type:"events", since, rows}; then {type:"event", n, row} as rows come
                 {ch:"loop", type:"start", mode:"rpc", model, budget?, req}
                                                                    -> the pi loop as this backend's child (refused while a pi loop holds
                                                                       the workspace); {type:"child", state, pid}
                 {ch:"loop", type:"stop" | "say" (text) | "confirm" | "refuse" (token), req}
    gw -> page   {ch:"bundle", type:"stale", bundle}                the watch flipped (stale or fresh)
                 {ch:"loop", type:"gate", plan, token}              the child's confirm request: answered by confirm/refuse
                 {ch:"loop", type:"pi", event}                      the child's words, tool calls and results (journalled, who: pi)
                 {ch:"…", type:"error", error, req?}

Every channel here reads or writes the operator's .metis/, so a shared instance refuses them all. The pi loop and the
backend never talk to each other (§2.4): the backend writes the surprise and reads the journal; the child's words are
journalled by this bridge so a TUI run and an rpc one leave the same trail."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from metis import trace as T
from metis.catalog import workspace as W

CHANNELS = ("trace", "surprise", "bundle", "loop")
WATCH_SECS = 2.0              # the bundle's stale watch and the journal's tail
VERB_SECS = 300               # a trace verb's wall time
VERB_OUT = 256 * 1024         # … and the output a page is sent
LOOP_SH = Path(__file__).resolve().parent.parent / "pi" / "loop.sh"
# verbs that move a REPL session off its recorded course: the trace cuts (a new segment from the session's own state)
CUT_VERBS = frozenset(["undo", "reset", "whatif", "load", "seed", "accept"])


def _scope():
    """The 6G scope prefix for a child (the rule for every run's child), when a user scope can start here; else []."""
    if not shutil.which("systemd-run"):
        return []
    try:
        ok = subprocess.run(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=6G", "true"],
                            capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    return ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=6G", "-p", "MemorySwapMax=0"] if ok else []


class SessionTrace:
    """A REPL session's trace (WORKSPACE.md §3): metis.trace's Segments writer in .metis/traces/<session>/, the
    session as ONE member. A command is a tick: the rows it fired, as py Live's Tracer writes a member's rows
    between beats ({"take": do-lines} for an input, {"step": [rules]} for rules fired), so `metis.trace replay`
    reproduces it on the session's program. A command that moves the session off that course (undo, reset, whatif,
    a recompile, or one that changed the state with no row) starts a new segment from the session's own state,
    marked cut: the replay resumes from its checkpoint and never reads across it."""

    def __init__(self, path, shell, member, program=None, extensions=(), source=None):
        """PROGRAM: the session's checkout .llp; SOURCE: an in-memory session's text, written beside the segments
        as program.llp (its includes resolve as METIS_HOME's from there); EXTENSIONS: the names merged into the
        session (the header says so: a replay needs them merged too)."""
        self.path, self.member = Path(path), member
        self.w = T.Segments(self.path, every=0)
        self.k = 0
        if source is not None:
            program = self.path / "program.llp"
            program.write_text(source)
        self.program = Path(program) if program else None
        self.extensions = [str(e) for e in extensions]
        self._attach(shell, cut=None)

    def _header(self, cut):
        m = {"seed": getattr(self.shell, "seed", 1) or 1, "weights": T.weights_of(self.shell), "out": []}
        if self.program is not None and self.program.is_file():
            m["key"], m["program"] = T.program_key(self.program), str(self.program)
        if self.extensions:
            m["extensions"] = list(self.extensions)       # merged into the session: a replay needs them too
        h = {"clock": "command", "composition": None, "image": None, "protocol": T.protocol_key(), "commands": [],
             "clocks": [{"domain": self.member, "n": 1}], "live": "metis-loop-console", "members": {self.member: m}}
        if cut:
            h["cut"] = cut
        return h

    def _attach(self, shell, cut):
        self.shell = shell
        self.rows = len(shell.fired_rows)
        self.w.open_segment(self.k, self._header(cut),
                            {"sessions": {self.member: T.session_state(shell)}, "copies": {}, "world": None})

    def before(self, shell):
        if shell is not self.shell:                      # recompiled: a new interpreter, a new segment
            self.k += 1
            self._attach(shell, "reload")
        self.state = T.session_state(shell)
        self.rows = min(self.rows, len(shell.fired_rows))

    def after(self, shell, cmd):
        """The command's tick, or a cut when the command left the recorded course."""
        verb = cmd.strip().lstrip(":").split(" ", 1)[0]
        n = len(shell.fired_rows)
        moved = T.session_state(shell) != self.state
        if shell is not self.shell or verb in CUT_VERBS or n < self.rows or (n == self.rows and moved):
            self.k += 1
            self._attach(shell, "reload" if shell is not self.shell else "cut")
            return
        if n == self.rows:
            return                                       # a read: nothing moved, no tick
        seq = []
        for kind, _, ev in shell.fired_rows[self.rows:n]:
            if kind == "exo":
                seq.append({"take": list(ev.ops), "by": "tool"})
            elif seq and "step" in seq[-1]:
                seq[-1]["step"].append(ev.name)
            else:
                seq.append({"step": [ev.name], "by": "tool"})
        self.rows = n
        self.k += 1
        self.w.line({"k": self.k, "t": round(time.time(), 3),
                     "members": {self.member: {"why": "command", "cmd": cmd[:200], "seq": seq, "out": []}}})

    def last_k(self):
        return self.k

    def close(self):
        self.w.close()


class WorkspaceChannels:
    """The four channels of one gateway. `pi_factory(argv, cwd, env)` makes the pi loop's rpc client (nina's
    loop/pi_rpc.PiRpc: start, say, events, answer, stop, pid); a test passes a stub."""

    def __init__(self, gw, root=None, pi_factory=None):
        self.gw = gw
        self.ws = W.workspace(root or gw.srv.root)
        self.pi_factory = pi_factory
        self.child = None             # {rpc, model, budget, started, task}
        self.subs = set()             # pages tailing the journal
        self.seen = None              # journal rows pushed so far
        self.stale = None             # the bundle's last stale flag
        self._cache = {}

    # -- the socket's side -------------------------------------------------

    async def handle(self, page, msg):
        ch, typ, req = msg.get("ch"), msg.get("type"), msg.get("req")
        try:
            if self.gw.cfg["mode"] == "shared":
                raise ValueError(f"the {ch} channel reads and writes the operator's workspace: personal mode only")
            out = await getattr(self, "_" + ch)(page, typ, msg)
            if out is not None:
                await self.gw._send(page, {"ch": ch, "type": typ, "req": req, **out})
        except (ValueError, KeyError, T.TraceError, FileNotFoundError) as e:
            await self.gw._send(page, {"ch": ch, "type": "error", "req": req,
                                       "error": str(e.args[0] if e.args else e)})

    def drop(self, page):
        self.subs.discard(page)

    async def _run(self, f, *a):
        return await asyncio.get_running_loop().run_in_executor(None, f, *a)

    # -- trace ---------------------------------------------------------------

    async def _trace(self, page, typ, msg):
        if typ == "list":
            return {"traces": await self._run(self.ws.traces)}
        if typ == "open":
            return {"trace": await self._run(self.ws.trace, str(msg.get("run") or ""))}
        if typ == "tick":
            return await self._run(self.tick, str(msg.get("run") or ""), str(msg.get("member") or ""),
                                   msg.get("k"), msg.get("program"))
        if typ == "tools":
            return {"tools": W.tools()["tools"]}
        if typ == "verb":
            return await self._run(self.verb, str(msg.get("name") or ""), msg.get("args") or {})
        raise ValueError(f"trace: list | open | tick | tools | verb, not {typ!r}")

    def tick(self, run, member, k, program=None):
        """The Tick table at K: metis.trace.timeline of MEMBER (cached per trace and program, by the segments'
        mtimes). PROGRAM: the member's .llp (relative to the workspace), else the one the trace's header names."""
        if not isinstance(k, int):
            raise ValueError(f"k {k!r}: a tick (an integer)")
        d = self.ws.path("trace", run=W._check_run(run))
        head = T.read(d)[0].header
        if member not in head["members"]:
            raise ValueError(f"no member {member!r} in {run} (it has: {', '.join(sorted(head['members']))})")
        prog = program or head["members"][member].get("program")
        if prog:
            prog = str((self.ws.root / prog).resolve()) if not os.path.isabs(prog) else prog
            if not Path(prog).is_file():
                raise ValueError(f"program {program or prog}: no such file")
        stamp = tuple(sorted((p.name, p.stat().st_mtime) for p in d.glob("seg-*.jsonl")))
        key = (run, member, prog)
        hit = self._cache.get(key)
        if not hit or hit[0] != stamp:
            hit = (stamp, T.timeline(d, member, prog))
            self._cache = {key: hit}                     # one at a time: a page reads one trace
        ticks, exact = hit[1]
        t = next((t for t in ticks if t.k == k), None)
        if t is None:
            ks = [t.k for t in ticks]
            raise ValueError(f"no tick {k} in {run} for {member} ({ks[0]}..{ks[-1]})" if ks else f"{run}: no tick")
        return {"run": run, "member": member, "k": k, "counts": t.counts, "fired": t.fired,
                "made": sorted(t.made), "exact": exact}

    def verb(self, name, args):
        """One declared trace tool (metis/trace_tools.json) and nothing else: its argv from the table, a
        `traces/<run>` argument resolved under .metis/, run in the 6G scope for VERB_SECS at most."""
        if not isinstance(args, dict):
            raise ValueError("verb args: an object {param: value}")
        fixed = {k: (str(self.ws.state / v) if isinstance(v, str) and v.startswith("traces/") else v)
                 for k, v in args.items()}
        argv = W.tool_argv(name, fixed)
        try:
            p = subprocess.run(_scope() + argv, cwd=str(self.ws.root), capture_output=True, text=True,
                               timeout=VERB_SECS)
        except subprocess.TimeoutExpired:
            return {"name": name, "code": None, "out": "", "err": f"stopped after {VERB_SECS} s"}
        return {"name": name, "code": p.returncode, "out": p.stdout[-VERB_OUT:], "err": p.stderr[-8192:]}

    # -- surprise -----------------------------------------------------------

    async def _surprise(self, page, typ, msg):
        if typ == "list":
            return {"surprises": await self._run(self.ws.surprises, msg.get("status"))}
        if typ == "get":
            rec = await self._run(self.ws.surprise, str(msg.get("id") or ""))
            md = None
            if rec.get("ruling") and rec["ruling"].get("md"):
                f = self.ws.state / rec["ruling"]["md"]
                md = f.read_text() if f.is_file() else None
            return {"surprise": rec, "md": md}
        if typ == "drop":
            sid = await self._run(self.ws.drop_surprise, self.surprise_of(msg))
            await self.gw._send_all({"ch": "surprise", "type": "dropped", "id": sid})
            return {"id": sid}
        raise ValueError(f"surprise: list | get | drop, not {typ!r}")

    def surprise_of(self, msg):
        """The record a drop writes: from a REPL session (its member, its trace when it writes one, k its last tick)
        or from a trace (run and member named). The person's reading or atoms, and words, as given."""
        rec = {k: msg[k] for k in ("reading", "atoms", "words", "window", "k", "k0") if msg.get(k) not in (None, "", [])}
        if msg.get("session"):
            s = self.gw.sessions.get(str(msg["session"]))
            if s is None:
                raise ValueError("no such session here")
            rec["member"] = str(msg.get("member") or self.gw.member_of(s))
            tr = getattr(s, "trace", None)
            if tr is not None:
                rec["trace"] = "traces/" + tr.path.name
                rec.setdefault("k", tr.last_k())
            rec["session"] = s.sid
        elif msg.get("run"):
            run = W._check_run(str(msg["run"]))
            if not self.ws.path("trace", run=run).is_dir():
                raise ValueError(f"no trace {run} in the workspace")
            if not msg.get("member"):
                raise ValueError("a drop from a trace names its member")
            rec["trace"], rec["member"] = "traces/" + run, str(msg["member"])
        else:
            raise ValueError("a drop names its session or its run")
        if not rec.get("reading") and not rec.get("atoms"):
            raise ValueError("a surprise carries a reading or atoms: what was seen, or what should have held")
        return rec

    # -- bundle --------------------------------------------------------------

    async def _bundle(self, page, typ, msg):
        if typ == "state":
            return {"bundle": await self._run(self.ws.bundle)}
        if typ == "reload":
            s = self.gw.sessions.get(str(msg.get("session") or ""))
            if s is None or page not in s.subs:
                raise ValueError("no such session on this page")
            if s.running:
                raise ValueError("busy: stop the running command before a reload")
            await self.gw.reopen(s, "reload")
            await self._run(lambda: self.ws.journal("backend", "reload", session=s.sid))
            return {"session": s.sid}
        raise ValueError(f"bundle: state | reload, not {typ!r}")

    # -- loop ----------------------------------------------------------------

    async def _loop(self, page, typ, msg):
        if typ == "state":
            return {"loops": await self._run(self.ws.loops), "cost": await self._run(self.ws.cost),
                    "child": self.child_state()}
        if typ == "events":
            since = int(msg.get("since") or 0)
            rows = await self._run(self.ws.events, since)
            self.subs.add(page)
            if self.seen is None:
                self.seen = since + len(rows)
            return {"since": since, "rows": rows}
        if typ == "start":
            return await self.start(msg)
        if typ == "stop":
            if not self.child:
                raise ValueError("no pi loop runs from this backend")
            await self.child["rpc"].stop()
            return {"child": self.child_state()}
        if typ == "say":
            text = str(msg.get("text") or "").strip()
            if not text:
                raise ValueError("say: the person's text")
            await self._rpc().say(text)
            await self._run(lambda: self.ws.journal("backend", "say", chars=len(text)))
            return {"ok": True}
        if typ in ("confirm", "refuse"):
            rpc, tok = self._rpc(), str(msg.get("token") or "")
            if tok not in self.child["gates"]:
                raise ValueError("no such gate waits")
            self.child["gates"].pop(tok)
            await rpc.answer(tok, typ == "confirm")
            return {"token": tok}
        raise ValueError(f"loop: state | events | start | stop | say | confirm | refuse, not {typ!r}")

    def _rpc(self):
        if not self.child:
            raise ValueError("no pi loop runs from this backend: start it (mode rpc)")
        return self.child["rpc"]

    def child_state(self):
        c = self.child
        if not c:
            return None
        return {"pid": getattr(c["rpc"], "pid", None), "model": c["model"], "budget": c["budget"],
                "started": c["started"], "gates": sorted(c["gates"]), "state": c["state"]}

    async def start(self, msg):
        """The pi loop as this backend's child over pi's --mode rpc (WORKSPACE.md §5.2). Refused while any pi loop
        holds the workspace (the TUI's, another backend's) or this one has a child; MODEL as the person names it
        (loop.sh has the default)."""
        if (msg.get("mode") or "rpc") != "rpc":
            raise ValueError("the backend starts the pi loop in rpc mode only (the TUI is a terminal's)")
        if self.child and self.child["state"] != "exited":
            raise ValueError("a pi loop already runs from this backend")
        held = (await self._run(self.ws.loops)).get("pi")
        if held and held.get("alive"):
            raise ValueError(f"a pi loop holds this workspace: pid {held.get('pid')} since {held.get('started')}"
                             f" ({held.get('mode')})")
        if self.pi_factory is None:
            try:
                from .pi_rpc import PiRpc
            except ImportError:
                raise ValueError("the rpc client (loop/pi_rpc.py) is not on this checkout yet") from None
            self.pi_factory = PiRpc
        budget = msg.get("budget")
        if budget is not None and not (isinstance(budget, (int, float)) and budget >= 0):
            raise ValueError(f"budget {budget!r}: USD, a number >= 0")
        env = dict(os.environ, METIS_CATALOG=str(self.ws.root))
        if msg.get("model"):
            env["MODEL"] = str(msg["model"])
        if budget is not None:
            env["METIS_LOOP_BUDGET"] = str(budget)
        rpc = self.pi_factory(_scope() + [str(LOOP_SH), "--mode", "rpc"], str(self.ws.root), env)
        self.child = {"rpc": rpc, "model": msg.get("model"), "budget": budget, "started": W._ts(),
                      "gates": {}, "state": "starting"}
        await rpc.start()
        self.child["state"] = "running"
        self.child["task"] = asyncio.create_task(self._pump(self.child))
        await self._run(lambda: self.ws.journal("backend", "pi_start", pid=getattr(rpc, "pid", None),
                                                **({"model": msg["model"]} if msg.get("model") else {})))
        return {"child": self.child_state()}

    async def _pump(self, child):
        """The child's events: each journalled (who: pi, pointers and short words), pushed to the pages; a confirm
        request becomes the gate frame, answered by confirm/refuse."""
        try:
            async for ev in child["rpc"].events():
                kind = ev.get("kind")
                if kind == "gate":
                    child["gates"][str(ev["token"])] = ev.get("plan")
                    await self.gw._send_all({"ch": "loop", "type": "gate", "plan": ev.get("plan"), "token": ev["token"]})
                    row = {"token": ev["token"]}
                else:
                    await self.gw._send_all({"ch": "loop", "type": "pi", "event": ev})
                    row = {k: ev[k] for k in ("name", "id", "ok", "code") if k in ev}
                    if ev.get("text"):
                        row["text"] = str(ev["text"])[:500]      # the words, cut: the journal carries pointers
                await self._run(lambda: self.ws.journal("pi", "rpc_" + str(kind or "event"), **row))
                if kind == "exit":
                    break
        finally:
            child["state"] = "exited"
            await self.gw._send_all({"ch": "loop", "type": "child", "child": self.child_state()})

    # -- the watch -----------------------------------------------------------

    async def watch(self):
        """Every WATCH_SECS: the bundle's stale flag (a flip is pushed to every page) and the journal's new rows
        (pushed to the pages tailing it)."""
        while True:
            await asyncio.sleep(WATCH_SECS)
            try:
                await self.poll()
            except Exception as e:                           # noqa: BLE001 — a bad file never stops the watch
                print(f"workspace watch: {e}", file=sys.stderr)

    async def poll(self):
        b = await self._run(self.ws.bundle)
        st = bool(b and b["stale"])
        if self.stale is not None and st != self.stale:
            await self.gw._send_all({"ch": "bundle", "type": "stale", "bundle": b})
        self.stale = st
        if self.subs and self.seen is not None:
            rows = await self._run(self.ws.events, self.seen)
            for i, row in enumerate(rows):
                for page in list(self.subs):
                    await self.gw._send(page, {"ch": "loop", "type": "event", "n": self.seen + i, "row": row})
            self.seen += len(rows)

    async def close(self):
        if self.child and self.child["state"] != "exited":
            await self.child["rpc"].stop()
