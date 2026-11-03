"""The backend's workspace channels (docs/WORKSPACE.md §3; loop-workspace s-5b4be5fa step 2): `trace`, `surprise`,
`bundle` and `loop`, over metispy's `metis.catalog.workspace` (the one layout, .metis/ in the catalog root), and
the REPL session's trace writer (§3: `open` with `trace: true`).

    page -> gw   {ch:"trace", type:"list", req}                     -> {type:"list", traces}
                 {ch:"trace", type:"open", run, req}                -> {type:"open", trace: {run, path, k0, k1, checkpoints, header},
                                                                       marks: [{mark, k0, k1, start, stop}]}: the run's marks
                 {ch:"trace", type:"tick", run, member, k, program?, req}
                                                                    -> {type:"tick", k, counts, fired, made, exact}: metis.trace.timeline
                 {ch:"trace", type:"tools", req}                    -> {type:"tools", tools}: metis/trace_tools.json as committed
                 {ch:"trace", type:"verb", name, args, req}         -> {type:"verb", name, code, out, err}: a declared tool, nothing else
                 {ch:"surprise", type:"list", status?, req}         -> {type:"list", surprises}
                 {ch:"surprise", type:"drop", session, k?, window?, atoms?, reading?, words?, req}
                                                                    from a REPL session: its member, its trace when it writes one
                 {ch:"surprise", type:"drop", run, member, k?, window?, mark?, atoms?, reading?, words?, config?, req}
                                                                    from a trace: a window is first kept as its own trace
                                                                    (traces/<run>-mark-N | -w<k0>-<k1>), the run's config.yaml
                                                                    carried
                                                                    -> {type:"dropped", id}, and to every page {type:"dropped", id}
                 {ch:"surprise", type:"get", id, req}               -> {type:"get", surprise, md?, pack?}: the record, its ruling's
                                                                       document and pack
                 {ch:"bundle", type:"state", req}                   -> {type:"state", bundle}: ws.bundle() (None: no composition)
                 {ch:"bundle", type:"reload", session, req}         -> the session re-opened from its catalog (epoch + 1)
                 {ch:"loop", type:"state", req}                     -> {type:"state", loops, cost, child}
                 {ch:"loop", type:"events", since?, req}            -> {type:"events", since, rows}; then {type:"event", n, row} as rows come
                 {ch:"loop", type:"start", mode:"rpc", model, budget?, req}
                                                                    -> the pi loop as this backend's child (refused while a pi loop holds
                                                                       the workspace); {type:"child", state, pid}
                 {ch:"loop", type:"stop" | "say" (text, session?) | "confirm" | "refuse" (token), req}
                                                                    a say whose text starts with "/" is the backend's (loop/chat.py,
                                                                    loop/chat_tools.json: no model, 0 USD) -> {type:"say", command,
                                                                    text, ruling?, draft?, child?}; anything else goes to pi
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

try:
    from .pi_rpc import PiRpcError
except ImportError:                                      # a checkout before loop/pi_rpc.py
    class PiRpcError(RuntimeError):
        pass

CHANNELS = ("trace", "surprise", "bundle", "loop")
WATCH_SECS = 2.0              # the bundle's stale watch and the journal's tail
VERB_SECS = 300               # a trace verb's wall time
VERB_OUT = 256 * 1024         # … and the output a page is sent
LOOP_SH = Path(__file__).resolve().parent.parent / "pi" / "loop.sh"
# verbs that move a REPL session off its recorded course: the trace cuts (a new segment from the session's own state)
CUT_VERBS = frozenset(["undo", "reset", "whatif", "load", "seed", "accept"])


_SCOPE = []                   # the probe's answer, once per process


def _scope():
    """The 6G scope prefix for a child (the rule for every run's child), when a user scope can start here; else [].
    Probed once per process."""
    if not _SCOPE:
        ok = False
        if shutil.which("systemd-run"):
            try:
                ok = subprocess.run(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=6G", "true"],
                                    capture_output=True, timeout=10).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
        _SCOPE.append(["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=6G", "-p", "MemorySwapMax=0"]
                      if ok else [])
    return list(_SCOPE[0])


class SessionTrace:
    """A REPL session's trace (WORKSPACE.md §3): metis.trace's Segments writer in .metis/traces/<session>/, the
    session as ONE member. A command is a tick: the rows it fired, as py Live's Tracer writes a member's rows
    between beats ({"take": do-lines} for an input, {"step": [rules]} for rules fired), so `metis.trace replay`
    reproduces it on the session's program. A command that moves the session off that course (undo, reset, whatif,
    a recompile, or one that changed the state with no row) starts a new segment from the session's own state,
    marked cut: the replay resumes from its checkpoint and never reads across it."""

    def __init__(self, path, shell, member, program=None, extensions=()):
        """PROGRAM: the session's checkout .llp (the workspace owns the file: no in-memory sessions,
        workspace-files s-9ea4cfa4); EXTENSIONS: the names merged into the session (the header says so: a
        replay needs them merged too)."""
        self.path, self.member = Path(path), member
        self.w = T.Segments(self.path, every=0)
        self.k = 0
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
        now = T.session_state(shell)
        moved = now != self.state
        take = self._take_of(cmd, verb, now) if shell is self.shell and n == self.rows and moved else None
        if take is not None:                             # an intervention: the session's input, a take (loop-chat F2)
            self.k += 1
            self.w.line({"k": self.k, "t": round(time.time(), 3),
                         "members": {self.member: {"why": "command", "cmd": cmd[:200],
                                                   "seq": [{"take": take, "by": "person"}], "out": []}}})
            self.state = now
            return
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

    def _take_of(self, cmd, verb, now):
        """`do +ATOM [N]` / `do -ATOM [N]` as the take a replay applies ([its do-line]), when that line on the counts
        before gives exactly the counts now and nothing else of the state moved (stage, quiet, rng); else None (a
        cut, as any other move with no row). The REPL's do appends no row, so without this the session's input
        lived only in a checkpoint and the verbs (replay, fired, the judge) never saw it."""
        if verb != "do":
            return None
        line = cmd.strip().lstrip(":").split(" ", 1)[1].strip() if " " in cmd.strip() else ""
        if not line or line[0] not in "+-":
            return None
        from metis.fw.plugin import exo_event
        try:
            _, after = exo_event([line], dict(self.state["counts"]))
        except Exception:                                # noqa: BLE001 — a line the do-line grammar does not read: a cut
            return None
        same = all(now[k] == self.state[k] for k in now if k != "counts")
        return [line] if same and after == now["counts"] else None

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
        self.budget_next = None       # /budget USD: the next start's, when the start names none

    # -- the socket's side -------------------------------------------------

    async def handle(self, page, msg):
        ch, typ, req = msg.get("ch"), msg.get("type"), msg.get("req")
        try:
            if self.gw.cfg["mode"] == "shared":
                raise ValueError(f"the {ch} channel reads and writes the operator's workspace: personal mode only")
            out = await getattr(self, "_" + ch)(page, typ, msg)
            if out is not None:
                await self.gw._send(page, {"ch": ch, "type": typ, "req": req, **out})
        except (ValueError, KeyError, T.TraceError, OSError) as e:      # OSError: a full disk, a permission (FileNotFoundError too)
            await self.gw._send(page, {"ch": ch, "type": "error", "req": req,
                                       "error": str(e.args[0] if e.args else e)})
        except PiRpcError as e:         # the child is gone or never answered: the page stays, the channel too
            if self.child:
                self.child["state"] = "exited"
                self.child["gates"].clear()
            await self.gw._send(page, {"ch": ch, "type": "error", "req": req,
                                       "error": f"the pi loop is not running: {e}"})

    def drop(self, page):
        self.subs.discard(page)

    async def _run(self, f, *a):
        return await asyncio.get_running_loop().run_in_executor(None, f, *a)

    # -- trace ---------------------------------------------------------------

    async def _trace(self, page, typ, msg):
        if typ == "list":
            return {"traces": await self._run(self.ws.traces)}
        if typ == "open":
            run = str(msg.get("run") or "")
            return {"trace": await self._run(self.ws.trace, run), "marks": await self._run(self.marks_of, run)}
        if typ == "tick":
            return await self._run(self.tick, str(msg.get("run") or ""), str(msg.get("member") or ""),
                                   msg.get("k"), msg.get("program"))
        if typ == "tools":
            return {"tools": W.tools()["tools"]}
        if typ == "verb":
            return await self._run(self.verb, str(msg.get("name") or ""), msg.get("args") or {})
        raise ValueError(f"trace: list | open | tick | tools | verb, not {typ!r}")

    def marks_of(self, run):
        """The run's marks as windows (metis.catalog.workspace marks: the world's marks.jsonl in the trace's k); none on a
        metispy before them."""
        return self.ws.marks(run) if hasattr(self.ws, "marks") else []

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
            md = pack = None
            r = rec.get("ruling") or {}
            if r.get("md") and (self.ws.state / r["md"]).is_file():
                md = (self.ws.state / r["md"]).read_text()
            if r.get("pack") and (self.ws.state / r["pack"]).is_file():
                pack = (self.ws.state / r["pack"]).read_text()
            return {"surprise": rec, "md": md, "pack": pack}
        if typ == "drop":
            sid = await self._run(self.ws.drop_surprise, self.surprise_of(msg))
            await self.gw._send_all({"ch": "surprise", "type": "dropped", "id": sid})
            return {"id": sid}
        raise ValueError(f"surprise: list | get | drop, not {typ!r}")

    def surprise_of(self, msg):
        """The record a drop writes: from a REPL session (its member, its trace when it writes one, k its last tick)
        or from a trace (run and member named). The person's reading or atoms, and words, as given. No `config`: a
        REPL session has no service config, and for a trace the judge falls back to the bundle's (pack_propose:
        the argument, the surprise's, then ws.bundle().config, the architect's order)."""
        rec = {k: msg[k] for k in ("reading", "atoms", "words", "window", "k", "k0", "config", "mark")
               if msg.get(k) not in (None, "", [])}
        if msg.get("session"):
            s = self.gw.sessions.get(str(msg["session"]))
            if s is None:
                raise ValueError("no such session here")
            rec["member"] = str(msg.get("member") or self.gw.member_of(s))
            tr = getattr(s, "trace", None)
            if tr is not None:
                rec["trace"] = "traces/" + tr.path.name
                rec.setdefault("k", tr.last_k())
                if tr.extensions:               # metis.trace replays the program alone: say so on the record
                    rec["trace_note"] = ("the session merged the extensions %s: a replay of the trace's program "
                                         "runs without them" % ", ".join(tr.extensions))
            rec["session"] = s.sid
        elif msg.get("run"):
            run = W._check_run(str(msg["run"]))
            if not self.ws.path("trace", run=run).is_dir():
                raise ValueError(f"no trace {run} in the workspace")
            if not msg.get("member"):
                raise ValueError("a drop from a trace names its member")
            rec["trace"], rec["member"] = "traces/" + run, str(msg["member"])
            w = rec.get("window")
            if w and hasattr(self.ws, "keep_window"):    # a window outlives the writer's ring (WORKSPACE.md §6.1 item 4)
                rec["trace"] = self.kept(run, w, msg.get("mark"))
            cfg = self.ws.state / rec["trace"] / "config.yaml"
            if not rec.get("config") and cfg.is_file():   # the run's own config: the judge replays the run as it was played
                rec["config"] = str(cfg.relative_to(self.ws.root))
        else:
            raise ValueError("a drop names its session or its run")
        if not rec.get("reading") and not rec.get("atoms"):
            raise ValueError("a surprise carries a reading or atoms: what was seen, or what should have held")
        return rec

    def kept(self, run, w, mark=None):
        """The window kept as its own trace, before the surprise points at it: traces/<run>-mark-<N> for a mark, else
        traces/<run>-w<k0>-<k1>; the copy already there for the same window is taken as it is."""
        if not (isinstance(w, list) and len(w) == 2 and all(isinstance(x, int) for x in w)):
            raise ValueError("window %r: [k_start, k_end]" % (w,))
        name = ("mark-%s" % mark) if mark not in (None, "") else "w%d-%d" % (w[0], w[1])
        got = self.ws.path("trace", run=W._check_run("%s-%s" % (run, name)))
        if got.is_dir():
            return "traces/" + got.name
        return self.ws.keep_window(run, w[0], w[1], name)

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
            if self.child["state"] != "exited":
                await self.child["rpc"].stop()
            return {"child": self.child_state()}
        if typ == "say":
            text = str(msg.get("text") or "").strip()
            if not text:
                raise ValueError("say: the person's text")
            if text.startswith("/"):                     # the backend's command (CHAT.md §2), never a model turn
                return await self.command(page, text, msg)
            await self._rpc().say(text)
            await self._run(lambda: self.ws.journal("backend", "say", chars=len(text)))
            return {"ok": True}
        if typ == "commands":                           # the chat's completion: the table as committed
            from . import chat
            return {"commands": [{"name": t["name"], "description": t["description"]} for t in chat.tools()["tools"]]}
        if typ in ("confirm", "refuse"):
            rpc, tok = self._rpc(), str(msg.get("token") or "")
            if tok not in self.child["gates"]:
                raise ValueError("no such gate waits")
            self.child["gates"].pop(tok)
            await rpc.answer(tok, typ == "confirm")
            return {"token": tok}
        raise ValueError(f"loop: state | events | start | stop | say | commands | confirm | refuse, not {typ!r}")

    # -- the chat's /commands (loop-chat s-f6c32d0c step 2, docs/CHAT.md §2; the grammar and table: loop/chat.py) --

    def session_of(self, page, msg):
        """The page's REPL session a command acts on: msg's `session` when it is this page's, else None."""
        s = self.gw.sessions.get(str(msg.get("session") or ""))
        return s if s is not None and page in s.subs else None

    async def command(self, page, text, msg):
        from . import chat
        name, a = chat.parse(text)
        out = {"command": name}
        s = self.session_of(page, msg)
        if name == "help":
            out["text"] = chat.help_text(a.command)
        elif name == "status":
            out["text"] = await self._run(chat.status_text, self.ws, self.child_state(), self.budget_next)
            out["child"] = self.child_state()
        elif name == "surprises":
            out["text"] = await self._run(chat.surprises_text, self.ws, a.status)
        elif name == "replay":
            run, win = a.run, chat.window(a.window) if a.window else None
            if run is not None and win is None and chat.window(run) is not None and a.window is None:
                run, win = None, chat.window(run)         # /replay 412..430: the window of the last surprise's trace
            out.update(await self._run(chat.replay, self.ws, run, win))
        elif name == "why":
            out.update(await self._run(chat.why, self.ws, a.atom, a.at))
        elif name == "diff":
            out.update(await self._run(chat.diff, self.ws, a.id))
        elif name == "ruling":
            sr, r = await self._run(chat.ruling_of, self.ws, a.id)
            out.update(text=chat.ruling_line(sr, r), ruling=sr["id"])
        elif name == "mark":
            sess = None
            if s is not None and s.trace is not None:
                sess = {"session": s.sid, "k": s.trace.last_k()}
            draft = await self._run(chat.mark, self.ws, a.words, sess)
            out.update(draft=draft, text="a surprise draft in SURPRISES: check the member and the tick, then drop it")
        elif name == "drop":
            if s is None:
                raise ValueError("/drop: no open session on this page (open one, or /mark RUN K WORDS)")
            r = await self._surprise(page, "drop", {"session": s.sid, "words": " ".join(a.words)})
            out.update(text=f"dropped {r['id']}: the pi loop takes it from .metis/surprises/", id=r["id"])
        elif name == "rebuild":
            out.update(await self._run(chat.rebuild, self.ws, _scope()))
        elif name == "reload":
            if s is None:
                raise ValueError("/reload: no open session on this page")
            await self._bundle(page, "reload", {"session": s.sid})
            out["text"] = f"reloaded {s.sid}: the session is on the files as they are now (epoch + 1)"
        elif name == "lint":
            rows = []
            for m, prog, mf in await self._run(chat.lint_targets, self.ws, a.member):
                args = {"file": prog, **({"manifest": mf} if mf else {})}
                r = await self._run(self.verb, "lint", args)
                rows.append(f"{m}: " + ((r["out"] + r["err"]).strip() or f"exit {r['code']}"))
            out["text"] = "\n".join(rows)
        elif name == "budget":
            if not (a.usd > 0):
                raise ValueError("/budget USD: a number of USD above 0")
            self.budget_next = a.usd
            out["text"] = f"the next pi start has a budget of {a.usd} USD" + (
                " (the running child keeps its own: /stop, then start again)" if self.child and self.child["state"] == "running" else "")
        elif name == "stop":
            if not self.child or self.child["state"] == "exited":
                raise ValueError("/stop: no pi loop runs from this backend")
            await self.child["rpc"].stop()
            out.update(text="the pi loop is stopping", child=self.child_state())
        elif name == "take":
            started = ""
            if not self.child or self.child["state"] != "running":
                await self.start({"mode": "rpc"})
                started = f"started the pi loop (budget {self.child['budget'] or 'loop.sh default'}); "
            words = f"take surprise {a.id}" if a.id else "take the next surprise"
            await self.child["rpc"].say(words)
            await self._run(lambda: self.ws.journal("backend", "say", chars=len(words), command="take"))
            out.update(text=f"{started}said to pi: {words}", child=self.child_state())
        await self._run(lambda: self.ws.journal("backend", "command", command=name))
        return out

    def _rpc(self):
        if not self.child or self.child["state"] != "running":
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
        self.child = None
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
        if budget is None:
            budget = self.budget_next                    # /budget USD
        if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget <= 0):
            raise ValueError(f"budget {budget!r}: USD, a number above 0 (or none: loop.sh's default)")
        env = dict(os.environ, METIS_CATALOG=str(self.ws.root))
        if msg.get("model"):
            env["MODEL"] = str(msg["model"])
        if budget is not None:
            env["METIS_LOOP_BUDGET"] = str(budget)
        rpc = self.pi_factory(_scope() + [str(LOOP_SH), "--mode", "rpc"], str(self.ws.root), env)
        child = {"rpc": rpc, "model": msg.get("model"), "budget": budget, "started": W._ts(),
                 "gates": {}, "state": "starting"}
        self.child = child
        try:
            await rpc.start()
        except Exception as e:                           # noqa: BLE001 — loop.sh refused, or pi died before it answered
            self.child = None
            await self._run(lambda: self.ws.journal("backend", "pi_start_failed", error=str(e)[:500]))
            raise ValueError(f"the pi loop did not start: {e}") from None
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
                    row = {k: ev[k] for k in ("name", "id", "ok", "code", "where", "level", "cost", "model", "aborted")
                           if k in ev}
                    for k in ("text", "error", "stderr_tail"):        # the words, cut: the journal carries pointers
                        v = ev.get(k)
                        if v:
                            v = "\n".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)
                            row[k] = v[-500:] if k == "stderr_tail" else v[:500]
                await self._run(lambda: self.ws.journal("pi", "rpc_" + str(kind or "event"), **row))
                if kind == "exit":
                    break
        finally:
            child["state"] = "exited"
            child["gates"].clear()                       # no confirm reaches a gone child
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
