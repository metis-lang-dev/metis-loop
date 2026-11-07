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
                 {ch:"loop", type:"state", req}                     -> {type:"state", loops, cost, spend, child}
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


# the REPL session's trace writer is metispy's (metis.session_trace, two-terminals s-065d46d5): ONE writer for the
# console's REPL sessions and the terminal REPL started in a workspace, so a surprise from either replays the same way
from metis.session_trace import CUT_VERBS, SessionTrace  # noqa: E402,F401 — re-exported (gateway.py)


def dot_model():
    """The pi model the dot file's [llm] loop names (metispy metis.loop.llm, llm-config s-07a070ad): what loop.sh
    starts when MODEL is not given, so the console and a terminal start the same one; None when unset (loop.sh then
    refuses, saying how to set it) or on a metispy without the seats."""
    try:
        from metis.loop import config
        from metis.loop.llm import pi_model, seat
    except ImportError:
        return None
    config.load(reload=True)                    # the REPL's `llm loop` may have written it since
    spec, _ = seat("loop")
    try:
        return pi_model(spec)["model"] if spec else None
    except ValueError:
        return None


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
        self.applies = {}             # /apply cards waiting for the person: token -> the plan (loop-ui 2.3)

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
        rec = {k: msg[k] for k in ("reading", "atoms", "words", "window", "k", "k0", "config")
               if msg.get(k) not in (None, "", [])}
        if msg.get("mark") not in (None, "", []):        # the page's mark NUMBER (marks.jsonl): page_mark, since spec 20 §8's
            rec["page_mark"] = msg["mark"]               # `mark` is a confusion record's {n, k0, k1, said} (metispy checks it)
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
            from . import chat
            return {"loops": await self._run(self.ws.loops), "cost": await self._run(self.ws.cost),
                    "spend": await self._run(chat.spend, self.ws), "child": self.child_state()}
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
        if typ in ("confirm", "refuse") and str(msg.get("token") or "") in self.applies:
            return await self._apply_answer(str(msg["token"]), typ == "confirm")
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
        elif name in chat.READ:                          # the workspace's alone: the pi loop's chat_<name> tools answer the same
            out.update(await self._run(chat.answer, self.ws, name, a, self.child_state(), self.budget_next))
            if name == "status":
                out["child"] = self.child_state()
        elif name == "mark" and (s is None or chat.marks_a_run(a.words)):
            # /mark RUN K WORDS: a trace's tick, narrated first (spec 20 §10 item 7): the terminal's (pi's /mark) own answer
            out.update(await self._run(chat.terminal, self.ws, name, a))
        elif name == "narrate":                          # every member's narration of a trace's window, with its context: one mark
            out.update(await self._run(chat.terminal, self.ws, name, a))
        elif name in ("agree", "disagree"):              # the mark's two endings: a pass, or a confusion record on the words
            out.update(await self._run(chat.terminal, self.ws, name, a))
        elif name in ("drop", "mark"):
            # loop-ui 2.2: the REPL's own verb on this page's session (its REPL pane gets the line, as typed there):
            # `drop WORDS` its last tick, `mark K[..K1] WORDS` a tick of its trace; the same code as terminal 1's
            if s is None:
                raise ValueError(f"/{name}: no open session on this page (open a program in the CATALOG"
                                 + (", or /mark RUN K WORDS)" if name == "mark" else ", or /mark RUN K WORDS)"))
            post = await self.gw.submit(s, f"{name} " + " ".join(a.words), "chat")
            if post.get("status") != "done":
                raise ValueError(str(post.get("result") or post.get("status")))
            out["text"] = post.get("result") or ""
        elif name == "apply":
            # loop-ui 2.3 (the user): the judge's merge of the ruling's pack onto its unit (chat.apply_plan, metispy's
            # Workspace.apply_plan), at this console's gate: the card's confirm writes exactly that plan, refuse nothing
            pl, card = await self._run(chat.apply_plan, self.ws, a.id)
            plan = await self._run(lambda: self.gw.srv.gate.propose("edit", pl["domain"], self.ws.root, path=pl["path"],
                                                                    old=pl["old"], new=pl["new"], who="backend"))
            self.applies[plan["token"]] = pl
            out.update(text=card["title"], gate={"token": plan["token"], "plan": card})
        elif name in ("rebuild", "lint"):                # the terminal's answer (pi's /rebuild, /lint): one code
            out.update(await self._run(chat.terminal, self.ws, name, a))
        elif name == "reload":
            if s is None:
                raise ValueError("/reload: no open session on this page")
            await self._bundle(page, "reload", {"session": s.sid})
            out["text"] = f"reloaded {s.sid}: the session is on the files as they are now (epoch + 1)"
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
            if self.child and self.child["state"] == "starting":
                raise ValueError("/take: the pi loop is starting: say it again in a moment")
            if not self.child or self.child["state"] != "running":
                await self.start({"mode": "rpc"})
                started = f"started the pi loop (budget {self.child['budget'] or 'loop.sh default'}); "
            words = f"take surprise {a.id}" if a.id else "take the next surprise"
            await self.child["rpc"].say(words)
            await self._run(lambda: self.ws.journal("backend", "say", chars=len(words), command="take"))
            out.update(text=f"{started}said to pi: {words}", child=self.child_state())
        await self._run(lambda: self.ws.journal("backend", "command", command=name))
        return out

    async def _apply_answer(self, tok, ok):
        """The person's answer to an /apply card: confirm writes the plan (the gate's: a unit changed since refuses,
        nothing written) and journals F1's row, `applied` {surprise, domain, path, old_sha, new_sha}, as pi's apply
        does; refuse writes nothing."""
        import hashlib
        pl = self.applies.pop(tok)
        srv = self.gw.srv
        if not ok:
            await self._run(srv.gate_refuse, tok)
            return {"token": tok, "text": f"not applied: ruling {pl['id']} (nothing written)"}
        out = await self._run(srv.gate_confirm, tok)
        sha = lambda t: hashlib.sha256(t.encode()).hexdigest()   # noqa: E731
        await self._run(lambda: self.ws.journal("backend", "applied", surprise=pl["id"], domain=pl["domain"],
                                                path=pl["path"], old_sha=sha(pl["old"]), new_sha=sha(pl["new"])))
        return {"token": tok, "text": f"applied ruling {pl['id']}: written {', '.join(out.get('written') or []) or 'nothing'}; "
                                      "the bundle is STALE until /rebuild"}

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
        holds the workspace (the TUI's, another backend's) or this one has a child; MODEL as the person names it,
        else loop.sh takes the dot file's [llm] loop, the same one a terminal's loop.sh takes (llm-config; dot_model:
        what the child is said to run)."""
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
        # reasoning stays on (loop-prompt, PROMPT.md §2: the cap is 8192 now); the chat's options turn it off, and
        # loop.sh appends :off to a MODEL without a thinking suffix. Unasked, the operator's METIS_LOOP_THINKING stays
        if msg.get("no_thinking"):
            env["METIS_LOOP_THINKING"] = "off"
        if budget is not None:
            env["METIS_LOOP_BUDGET"] = str(budget)
        rpc = self.pi_factory(_scope() + [str(LOOP_SH), "--mode", "rpc"], str(self.ws.root), env)
        child = {"rpc": rpc, "model": msg.get("model") or dot_model(), "budget": budget, "started": W._ts(),
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
        # the model started, named or the dot file's (gpt-oss F7: the journal said nothing of a dot-file start)
        await self._run(lambda: self.ws.journal("backend", "pi_start", pid=getattr(rpc, "pid", None),
                                                **({"model": child["model"]} if child["model"] else {})))
        return {"child": self.child_state()}

    async def _pump(self, child):
        """The child's events: each journalled (who: pi, pointers and short words), pushed to the pages; a confirm
        request becomes the gate frame, answered by confirm/refuse."""
        turn = {"words": 0, "tools": 0, "stop": None}    # this turn's text, tool calls, last stop (loop-chat step 3)
        try:
            async for ev in child["rpc"].events():
                kind = ev.get("kind")
                if kind == "text" and str(ev.get("text") or "").strip():
                    turn["words"] += 1
                elif kind == "tool_call":
                    turn["tools"] += 1
                elif kind == "usage":
                    turn["stop"] = {k: ev.get(k) for k in ("stop", "reasoning", "output")}
                elif kind == "turn_end":                 # a turn the tester saw no words of says so (the dog drive's F1)
                    if not turn["words"] and not ev.get("aborted"):
                        st = turn["stop"] or {}
                        why = ""
                        if st.get("stop"):              # the alf drive's L1: thinking ate the token cap
                            why = f"; stopped: {st['stop']}" + (f", reasoning {st['reasoning']} tokens" if st.get("reasoning") else "") + ", no words"
                        ev = dict(ev, empty=True, tools=turn["tools"], stop=st.get("stop"),
                                  note=f"pi ended its turn without words ({turn['tools']} tool call{'s' if turn['tools'] != 1 else ''}{why})")
                    turn = {"words": 0, "tools": 0, "stop": None}
                if kind == "gate":
                    child["gates"][str(ev["token"])] = ev.get("plan")
                    await self.gw._send_all({"ch": "loop", "type": "gate", "plan": ev.get("plan"), "token": ev["token"]})
                    row = {"token": ev["token"]}
                else:
                    await self.gw._send_all({"ch": "loop", "type": "pi", "event": ev})
                    row = {k: ev[k] for k in ("name", "id", "ok", "code", "where", "level", "cost", "model", "aborted",
                                              "empty", "tools", "stop", "reasoning") if k in ev}
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
