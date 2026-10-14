"""The console gateway (docs/CONSOLE-WS.md §1, §2, §4, §7): a standing
backend for the Loop Console — plain `websockets` + stdlib-shaped HTTP
on ONE port (D1), grown from console/dev_serve.py.

    GET /            the page (loop_console.html) with the gateway flag
    GET /healthz     liveness
    WS  /ws          one multiplexed socket per browser window

Frames (JSON, one per message):

    page -> gw   {ch:"repl", type:"open",   llp, req}      new session
                 {ch:"repl", type:"open",   llp, host:true, req}  …with the host the index names
                 {ch:"repl", type:"open",   source, name, req}  from catalog
                                          TEXT, compiled in memory (§4a)
                 {ch:"repl", type:"open",   session}       re-attach
                 {ch:"repl", type:"intent", session, id, cmd, actor}
                 {ch:"repl", type:"stop",   session}
                 {ch:"repl", type:"work",   session, copy?, packs?}  the
                                          editor's working copy (§4a)
                 {ch:"repl", type:"recompile", session}  rebuild from it
                 {ch:"repl", type:"close",  session}
                 {ch:"repl", type:"records"} -> {ch:"meta", type:"records", records}
                 {ch:"repl", type:"sink", session, file}  a checkout records file into the session
                 {ch:"repl", type:"new", name, line, req}  domains/<name>/ made, then opened
                 {ch:"repl", type:"save", session[, token]}  -> {type:"save", files:[{path,new,diff}], token[, written]}
                 {ch:"chat", type:"say"|"stop"|"history", session, text}
                                          (personal mode, the agent seat)
    gw -> page   {ch:"meta", type:"manifest", ...}  {ch:"meta", type:"catalogs", names}
                 {ch:"meta", type:"domains", domains}  the CATALOG panel
                                          (catalog_index: line, has, readme_text)
                 {ch:"repl", type:"session", session, req?, …fields, busy, running, queued}
                 {ch:"repl", type:"queued",  session, id, cmd, actor, ts}
                 {ch:"repl", type:"posting", session, id, cmd, actor, ts, …intent_posting}
                 {ch:"repl", type:"source",  session, name, copy, packs,
                                          certified: checkout|local|null, error, key}
                 {ch:"…",    type:"error",   error, session?, id?}

The posting payload is `intent_posting` verbatim (via ConsoleServer.
serve_one): the page's renderers do not change, and the whitelist is
the same `parse_intent` — approval verbs and paths cannot arrive.

Session Manager = ConsoleServer + per-session command QUEUE (one
command at a time, on the session's own worker thread), busy/stop
(stop interrupts the running command and drops the queue), and the
`[console]` caps. Mode manifest (§4): `personal` (own host) keeps the
REPL's LLM seats; `shared` is REPL-only — chat/narrate/formalize/llm
never run on the operator's credentials there — with an optional URL
token (D2), per-IP session caps and a rate limit.

Privacy (D4): sessions, postings and (later) chat live in MEMORY only;
nothing a visitor types or runs is written to the operator's disk."""
import asyncio
import ctypes
import json
import secrets
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

from .console_serve import ConsoleServer

PAGE = Path(__file__).resolve().parent.parent / "console" / "loop_console.html"
VENDOR = PAGE.parent / "vendor"     # the CodeMirror bundle (one instance)

DEFAULTS = {
    "port": 8770, "bind": "127.0.0.1", "mode": "personal", "token": "",
    "max_sessions": 16, "max_sessions_per_ip": 4, "max_run_steps": 500,
    "idle_secs": 1800, "rate_per_min": 120, "history": 300,
    "artifact_url": "",
    # the agent seat (personal mode, step 2 — CONSOLE-WS §3)
    "agent": True, "agent_model": "claude-opus-5-5", "agent_tool_calls": 10,
    "agent_cmd_timeout": 60, "agent_max_turns": 12,
    # the narrate seat (personal mode, step 3 — D3): "sdk" substitutes the
    # session's LLM endpoint with loop.sdk_narrate (Haiku); "llm" keeps
    # the kernel's configured endpoint (ollama)
    "narrate": "sdk", "narrate_model": "claude-haiku-4-5",
    "narrate_thinking": 1024,       # tokens; 0 = off (fast, unfaithful)
}
# the LLM seats: never through the operator's credentials in shared mode
LLM_VERBS = frozenset(["narrate", "formalize", "llm"])


def load_config(**overrides) -> dict:
    """DEFAULTS < the metis dot file's [console] table < overrides
    (CLI flags; None means 'not given')."""
    cfg = dict(DEFAULTS)
    try:
        from metis.loop import config
        _, conf = config.load()
        t = conf.get("console")
        if isinstance(t, dict):
            cfg.update({k: v for k, v in t.items() if k in DEFAULTS})
    except Exception:                                   # noqa: BLE001
        pass
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    if cfg["mode"] not in ("personal", "shared"):
        raise ValueError(f"[console] mode must be personal|shared, "
                         f"not {cfg['mode']!r}")
    return cfg


def agent_seat(cfg: dict):
    """(seat, reason): 'agent' when personal mode can run the Agent
    Service here, else None with why."""
    if cfg["mode"] == "shared":
        return None, "shared instance"
    if not cfg.get("agent", True):
        return None, "agent disabled in [console]"
    from .agent_service import available
    why = available()
    return (None, why) if why else ("agent", None)


def narrate_seat(cfg: dict):
    """(label, endpoint spec or None): the narrate seat this instance
    serves (D3). None spec = leave the kernel's endpoint (ollama)."""
    if cfg["mode"] == "shared":
        return None, None
    if cfg.get("narrate") == "sdk":
        from .agent_service import available
        if available() is None:
            import shlex
            import sys
            argv = [sys.executable, "-m", "loop.sdk_narrate", "--model",
                    str(cfg.get("narrate_model") or "claude-haiku-4-5"),
                    "--thinking", str(int(cfg.get("narrate_thinking", 1024)))]
            return (f"{cfg.get('narrate_model')} (SDK)",
                    "command:" + " ".join(shlex.quote(a) for a in argv))
    return "llm (ollama)", None


def manifest(cfg: dict) -> dict:
    """What this instance serves — the page renders only these (§4)."""
    shared = cfg["mode"] == "shared"
    seat, why = agent_seat(cfg)
    return {
        "mode": cfg["mode"],
        "chat_unavailable": why,
        "seats": {
            "repl": True,
            "chat": seat,                                # §3
            "narrate": narrate_seat(cfg)[0],              # D3
            "formalize": None if shared else "llm",
        },
        "chat_model": (cfg.get("agent_model") or "the CLI default")
        if seat == "agent" else None,
        "chat_pointer": cfg["artifact_url"] or None,
        "caps": {k: cfg[k] for k in ("max_sessions", "max_sessions_per_ip",
                                     "max_run_steps", "idle_secs",
                                     "rate_per_min")},
        "policy": ("shared instance: REPL only — nobody's chat, "
                   "narration or formalization runs on the operator's "
                   "credentials; AI for shared users lives on the "
                   "artifact console, billed to the viewer")
                  if shared else
                  "personal instance: the operator's own host and seats",
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Sess:
    """One console session's gateway-side state (memory only)."""

    def __init__(self, sid: str, llp: str, ip: str, history: int):
        self.sid, self.llp, self.ip = sid, llp, ip
        self.subs = set()
        self.log = deque(maxlen=history)    # queued+posting frames
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pool = ThreadPoolExecutor(max_workers=1,
                                       thread_name_prefix=f"sess-{sid}")
        self.lock = threading.Lock()
        self.tid: Optional[int] = None
        self.running: Optional[dict] = None
        self.stopping = False
        self.last = time.time()
        self.worker: Optional[asyncio.Task] = None
        self.futs: Dict[str, asyncio.Future] = {}   # submit() waiters


class Gateway:
    def __init__(self, cfg: dict, srv: Optional[ConsoleServer] = None):
        self.cfg = cfg
        self.srv = srv or ConsoleServer()
        self.sessions: Dict[str, Sess] = {}
        self.rates: Dict[object, deque] = {}
        self.agent = None
        if agent_seat(cfg)[0] == "agent":
            from .agent_service import AgentService
            self.agent = AgentService(self, cfg)

    # -- frames ----------------------------------------------------------

    @staticmethod
    def _dump(frame) -> str:
        return json.dumps(frame, default=str)

    async def _send(self, ws, frame):
        try:
            await ws.send(self._dump(frame))
        except Exception:                               # noqa: BLE001
            pass

    async def _broadcast(self, s: Sess, frame, log=False):
        if log:
            s.log.append(frame)
        for ws in list(s.subs):
            await self._send(ws, frame)

    def _session_frame(self, s: Sess, **extra) -> dict:
        try:
            fields = self.srv._fields(s.sid)
        except KeyError:
            fields = {"status": "closed"}
        return {"ch": "repl", "type": "session", "session": s.sid,
                "llp": s.llp, **fields, "busy": s.running is not None,
                "running": s.running and s.running["cmd"],
                "queued": s.queue.qsize(), **extra}

    # -- session manager -------------------------------------------------

    def _owned(self, ip) -> int:
        return sum(1 for s in self.sessions.values() if s.ip == ip)

    async def open(self, ws, ip, msg):
        loop = asyncio.get_running_loop()
        sid = msg.get("session")
        if sid:                                          # re-attach
            s = self.sessions.get(sid)
            if not s:
                return await self._send(ws, {
                    "ch": "repl", "type": "error", "session": sid,
                    "error": "gone", "detail": "no such session here (the "
                    "backend restarted or recycled it) — open a catalog"})
            s.subs.add(ws)
            await self._send(ws, self._session_frame(s, req=msg.get("req")))
            for f in list(s.log):
                await self._send(ws, f)
            if self.agent:
                await self._send(ws, self.agent.history(sid))
            await self._send(ws, self._source_frame(s))
            return
        cap = self.cfg
        if len(self.sessions) >= cap["max_sessions"]:
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "req": msg.get("req"),
                                         "error": "too many sessions on this "
                                         "instance — try later"})
        if cap["mode"] == "shared" and \
                self._owned(ip) >= cap["max_sessions_per_ip"]:
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "req": msg.get("req"),
                                         "error": f"session cap reached for "
                                         f"your address "
                                         f"({cap['max_sessions_per_ip']})"})
        sid = "w" + secrets.token_urlsafe(9).replace("-", "x").replace("_", "y")
        llp = str(msg.get("llp") or "")
        spec = ({"source": msg["source"], "name": msg.get("name"),
                 "packs": msg.get("packs") or []}
                if msg.get("source") is not None else {"llp": llp, "host": bool(msg.get("host"))})
        fields = await loop.run_in_executor(
            None, self.srv.open_session, sid, spec)
        if fields.get("status") == "closed":
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "req": msg.get("req"),
                                         "error": fields.get("error",
                                                             "cannot open")})
        s = Sess(sid, fields.get("llp", llp), ip, cap["history"])
        s.spec = spec                    # what idle recycling re-opens
        self._seat(sid)
        self._init_work(s, spec)
        s.subs.add(ws)
        s.worker = asyncio.create_task(self._work(s))
        self.sessions[sid] = s
        await self._send(ws, self._session_frame(s, req=msg.get("req")))
        await self._send(ws, self._source_frame(s))

    # -- the working copy (CONSOLE-WS §4a, the user's simple model) -----
    #    open → the catalog's text is the copy (certified: it IS the
    #    checkout's); edits make it uncertified until a recompile builds
    #    a session from it (+ its extension packs) cleanly. The page keeps
    #    it in IndexedDB; the gateway mirrors it in MEMORY for the agent's
    #    source tools. Nothing reaches the operator's disk.

    def _init_work(self, s: "Sess", spec: dict):
        if spec.get("source") is not None:
            copy, name = str(spec["source"]), str(spec.get("name") or "")
            packs = [dict(p) for p in spec.get("packs") or []]
            cert = "local"
        else:
            path = self.srv.resolve(spec.get("llp", ""))
            copy, name, packs, cert = path.read_text(), str(
                path.relative_to(self.srv.root.resolve()).with_suffix("")), \
                [], "checkout"
        s.work = {"name": name, "copy": copy, "packs": packs,
                  "certified": cert, "error": None}

    def _source_frame(self, s: "Sess") -> dict:
        w = getattr(s, "work", None) or {}
        key = None
        try:
            key = self.srv.shells[s.sid].key
        except KeyError:
            pass
        return {"ch": "repl", "type": "source", "session": s.sid, **w,
                "key": key}

    async def work(self, ws, msg):
        """The page's editor changed the copy or a pack: mirror it (the
        agent sees the same text) and mark it uncertified."""
        s = self.sessions.get(msg.get("session", ""))
        if not s or ws not in s.subs:
            return
        w = s.work
        if "copy" in msg and msg["copy"] != w["copy"]:
            w["copy"], w["certified"] = str(msg["copy"]), None
        if "packs" in msg and msg["packs"] != w["packs"]:
            w["packs"] = [{"name": str(p.get("name") or f"pack {k}"),
                           "source": str(p.get("source") or "")}
                          for k, p in enumerate(msg["packs"], 1)]
            w["certified"] = None
        for other in list(s.subs):
            if other is not ws:
                await self._send(other, self._source_frame(s))

    async def files(self, ws, ip, msg):
        """The checkout's files (e2e-workflow step 1): records sank by
        the domain agents (list; `sink` one into a session), `new`
        domain, `save` the working copy (a diff first, the token of
        that diff to write it). Nothing is committed."""
        typ, loop = msg.get("type"), asyncio.get_running_loop()
        s = self.sessions.get(msg.get("session", ""))
        try:
            if typ == "records":
                rows = await loop.run_in_executor(None, self.srv.records)
                return await self._send(ws, {"ch": "meta", "type": "records", "records": rows})
            if typ == "new":
                if self.cfg["mode"] == "shared":
                    raise ValueError("new writes the operator's checkout: personal mode only")
                llp = await loop.run_in_executor(None, self.srv.new_domain, msg.get("name"), msg.get("line"))
                await self._send(ws, {"ch": "meta", "type": "domains", "domains": self.srv.domains()})
                return await self.open(ws, ip, {"llp": llp, "req": msg.get("req")})
            if not s or ws not in s.subs:
                raise ValueError("no open session")
            if typ == "sink":
                out = await loop.run_in_executor(s.pool, self.srv.load_sink, s.sid, str(msg.get("file") or ""))
                return await self._send(ws, {"ch": "repl", "type": "sink", "session": s.sid, **out})
            # save: the plan (diffs + token), or with token the write
            if self.cfg["mode"] == "shared":
                raise ValueError("save writes the operator's checkout: personal mode only")
            w = s.work
            if msg.get("token"):
                out = await loop.run_in_executor(None, self.srv.save_apply, w, str(msg["token"]))
                w["certified"] = "checkout"
                await self._broadcast(s, self._source_frame(s))
            else:
                out = await loop.run_in_executor(None, self.srv.save_plan, w)
            return await self._send(ws, {"ch": "repl", "type": "save", "session": s.sid, **out})
        except ValueError as e:
            return await self._send(ws, {"ch": "repl", "type": "error", "session": msg.get("session"),
                                         "req": msg.get("req"), "error": str(e)})

    async def recompile(self, s: "Sess") -> dict:
        """Build the session again from the working copy + packs (in
        memory). Success: a new interpreter, epoch + 1, the copy
        certified (locally); failure: the error, the old world kept."""
        w = s.work
        spec = {"source": w["copy"], "name": w["name"] or "scratch",
                "packs": w["packs"], "host": bool((getattr(s, "spec", None) or {}).get("host"))}
        loop = asyncio.get_running_loop()
        ep = self.srv.epochs.get(s.sid, 1)
        fields = await loop.run_in_executor(s.pool, self.srv.open_session,
                                            s.sid, spec)
        if fields.get("status") == "closed":
            w["error"] = fields.get("error")
            await self._broadcast(s, self._source_frame(s))
            return {"ok": False, "error": w["error"]}
        self.srv.epochs[s.sid] = ep + 1
        s.spec, s.llp = spec, fields.get("llp", s.llp)
        self._seat(s.sid)
        w["certified"], w["error"] = "local", None
        s.log.clear()
        await self._broadcast(s, self._session_frame(s, recompiled=True))
        await self._broadcast(s, self._source_frame(s))
        return {"ok": True, "key": self.srv.shells[s.sid].key,
                "packs": fields.get("packs", [])}

    def _seat(self, sid: str):
        """D3: in personal mode the session's narrate seat goes to the
        SDK endpoint (kernel untouched — its `command:` backend runs
        loop.sdk_narrate); the cwd that module needs is this package."""
        spec = narrate_seat(self.cfg)[1]
        r = self.srv.shells.get(sid)
        if spec and r is not None:
            r.llm = spec

    def _gate(self, cmd: str) -> Optional[str]:
        """Gateway-side policy beyond run_intent's whitelist: shared mode
        refuses the LLM seats. Returns the refusal, or None."""
        verb = cmd.strip().lstrip(":").split(" ", 1)[0]
        if self.cfg["mode"] == "shared" and verb in LLM_VERBS:
            return (f"'{verb}' is not served on a shared instance — it "
                    "would run on the operator's credentials. Use the "
                    "artifact console for AI (billed to you).")
        return None

    def _cap_run(self, cmd: str):
        """`run N` above max_run_steps is clamped; returns (cmd, note)."""
        parts = cmd.strip().lstrip(":").split()
        cap = int(self.cfg["max_run_steps"])
        if parts and parts[0] == "run" and len(parts) == 2 and \
                parts[1].isdigit() and int(parts[1]) > cap:
            return f":run {cap}", f"(run capped at {cap} steps)"
        # spec 10: `whatif K do(...) run N` samples too — same cap
        if len(parts) >= 3 and parts[0] == "whatif" and \
                parts[-2] == "run" and parts[-1].isdigit() and \
                int(parts[-1]) > cap:
            return (":" + " ".join(parts[:-1] + [str(cap)]),
                    f"(whatif run capped at {cap} steps)")
        return cmd, None

    async def intent(self, ws, msg):
        s = self.sessions.get(msg.get("session", ""))
        iid = str(msg.get("id") or secrets.token_hex(6))
        if not s:
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "id": iid, "error": "gone"})
        actor = str(msg.get("actor") or "viewer")[:40]
        if actor == "claude":                # only the backend agent is
            actor = "viewer"                 # claude> — never the page
        if str(msg.get("cmd") or "").strip().lstrip(":").split(" ", 1)[0] == "intents":
            return await self.intents(s, str(msg.get("cmd")), actor, iid)
        await self.enqueue(s, msg.get("cmd"), actor, iid)

    INTENTS_ASK = (
        "Draft this domain's intent.yaml (metis-catalog CATALOG.md \"intent.yaml\"): call "
        "intents_read for the current file or a skeleton made from the program's cmd_* atoms and "
        "%% lines, read the program with source_read where the meanings need it, then give the "
        "person a few natural utterances per verb as examples, open-vocabulary slots where the "
        "person names things, and call intents_propose with the WHOLE file. Fix what it reports. "
        "Then tell the person: `intents save` writes it, `intents check` runs the check.")

    async def intents(self, s: "Sess", cmd: str, actor: str, iid: str):
        """`intents` (e2e-workflow step 2, loop/intents.py): Claude drafts
        the domain's intent.yaml; `intents show` the proposal's diff,
        `intents save` writes it and its generated files, `intents check`
        the corpus (or the examples) on the intent model. Gateway-side: it
        never reaches the kernel REPL. Personal mode only (it writes the
        operator's checkout and runs the operator's model)."""
        from . import intents as it
        item = {"id": iid, "cmd": cmd.strip(), "actor": actor, "ts": _now()}
        await self._broadcast(s, {"ch": "repl", "type": "queued", "session": s.sid, **item}, log=True)
        sub = cmd.strip().lstrip(":").split()[1:]
        loop, ok = asyncio.get_running_loop(), True
        try:
            if self.cfg["mode"] == "shared":
                raise ValueError("intents writes the operator's checkout and runs its model: personal mode only")
            name = str(s.work.get("name") or "")
            if not sub:
                if not self.agent:
                    raise ValueError("intents is drafted by Claude: the agent seat is off on this instance")
                err = await self.agent.say(s.sid, self.INTENTS_ASK)
                if err:
                    raise ValueError(err["error"])
                result = "asked Claude to draft intent.yaml — see the chat; then `intents show`, `intents save`"
            elif sub[0] == "show":
                p = getattr(s, "intents_pending", None)
                if not p:
                    raise ValueError("no proposal yet — `intents` asks Claude for one")
                result = self.intents_text(p)
            elif sub[0] == "save":
                out = await loop.run_in_executor(None, it.save, self.srv, getattr(s, "intents_pending", None),
                                                 (getattr(s, "intents_pending", None) or {}).get("token"))
                s.intents_pending = None
                result = "wrote " + ", ".join(out["written"]) + " (not committed)"
            elif sub[0] == "check":
                out = await loop.run_in_executor(None, it.check, self.srv, name)
                ok, result = out["ok"], out["output"]
            else:
                raise ValueError("usage: intents | intents show | intents save | intents check")
        except ValueError as e:
            ok, result = False, str(e)
        post = {"status": "done" if ok else "error", "result": result,
                "json": {"ok": ok}, "epoch": self.srv.epochs.get(s.sid), "done_ts": _now()}
        await self._broadcast(s, {"ch": "repl", "type": "posting", "session": s.sid, **item, **post}, log=True)

    @staticmethod
    def intents_text(p):
        head = "%s intent.yaml proposed (%s) — %s%s" % (
            p["domain"], "new" if p["new"] else "changed", p["mapped"],
            "" if p["ok"] else "; misses:\n  " + "\n  ".join(p["misses"]))
        return head + "\n" + (p["diff"] or "(no change)") + "\n`intents save` writes it"

    async def submit(self, s: "Sess", cmd: str, actor: str) -> dict:
        """Queue a line and await its posting (the Agent Service's repl
        tool): the same queue, whitelist, busy/stop and transcript."""
        iid = "a" + secrets.token_hex(6)
        fut = asyncio.get_running_loop().create_future()
        s.futs[iid] = fut
        await self.enqueue(s, cmd, actor, iid)
        return await fut

    def _resolve(self, s: "Sess", iid: str, posting: dict):
        fut = s.futs.pop(iid, None)
        if fut and not fut.done():
            fut.set_result(posting)

    async def enqueue(self, s: "Sess", cmd, actor: str, iid: str):
        cmd = str(cmd or "").strip()
        cmd = cmd if cmd.startswith(":") else ":" + cmd
        item = {"id": iid, "cmd": cmd, "actor": actor, "ts": _now()}
        s.last = time.time()
        await self._broadcast(s, {"ch": "repl", "type": "queued",
                                  "session": s.sid, **item}, log=True)
        refusal = self._gate(cmd)
        if refusal:
            post = {"status": "refused", "result": refusal,
                    "json": {"ok": False, "error": refusal},
                    "epoch": self.srv.epochs.get(s.sid)}
            await self._broadcast(s, {"ch": "repl", "type": "posting",
                                      "session": s.sid, **item, **post},
                                  log=True)
            return self._resolve(s, iid, post)
        await s.queue.put(item)
        await self._broadcast(s, self._session_frame(s))

    async def _work(self, s: Sess):
        """The session's single runner: one command at a time."""
        loop = asyncio.get_running_loop()
        while True:
            item = await s.queue.get()
            s.running, s.stopping = item, False
            await self._broadcast(s, self._session_frame(s))
            cmd, note = self._cap_run(item["cmd"])

            def run(cmd=cmd):
                try:
                    with s.lock:
                        s.tid = threading.get_ident()
                    try:
                        return self.srv.serve_one(s.sid, cmd)
                    finally:
                        with s.lock:
                            s.tid = None
                except KeyboardInterrupt:
                    return None
            out = await loop.run_in_executor(s.pool, run)
            if out is None:
                posting = {"status": "error", "result": "stopped by the "
                           "viewer — the session may be mid-step; 'undo' or "
                           "'reset' if the state looks off",
                           "json": {"ok": False, "error": "stopped"},
                           "epoch": self.srv.epochs.get(s.sid),
                           "done_ts": _now()}
            else:
                posting = dict(out["posting"])
                if note:
                    posting["result"] = f"{note}\n{posting.get('result', '')}"
            posting.pop("session", None)
            s.running, s.last = None, time.time()
            await self._broadcast(s, {"ch": "repl", "type": "posting",
                                      "session": s.sid, **item, **posting},
                                  log=True)
            self._resolve(s, item["id"], posting)
            await self._broadcast(s, self._session_frame(s))

    async def stop(self, msg):
        """Interrupt the running command and drop the queued ones."""
        s = self.sessions.get(msg.get("session", ""))
        if not s:
            return
        if self.agent:                       # [stop] stops Claude too
            await self.agent.stop(s.sid)
        while not s.queue.empty():
            item = s.queue.get_nowait()
            post = {"status": "error", "result": "cancelled (stop)",
                    "json": {"ok": False, "error": "cancelled"},
                    "epoch": self.srv.epochs.get(s.sid)}
            await self._broadcast(s, {"ch": "repl", "type": "posting",
                                      "session": s.sid, **item, **post},
                                  log=True)
            self._resolve(s, item["id"], post)
        with s.lock:
            if s.tid is not None and not s.stopping:
                s.stopping = True
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_ulong(s.tid), ctypes.py_object(KeyboardInterrupt))
        await self._broadcast(s, self._session_frame(s))

    async def close(self, sid: str, reason="closed"):
        s = self.sessions.pop(sid, None)
        if not s:
            return
        if self.agent:
            await self.agent.close(sid)
        for fut in s.futs.values():
            if not fut.done():
                fut.set_result({"status": "error", "result": "session closed",
                                "json": {"ok": False, "error": "closed"}})
        if s.worker:
            s.worker.cancel()
        s.pool.shutdown(wait=False, cancel_futures=True)
        self.srv.close_session(sid)
        for ws in list(s.subs):
            await self._send(ws, {"ch": "repl", "type": "error",
                                  "session": sid, "error": "gone",
                                  "detail": reason})

    async def sweep(self):
        """Idle recycling (§2): an idle session is reset to its catalog's
        start with epoch + 1 (the page restarts its stream and says so);
        one idle 3× as long with no window attached is dropped — memory
        only, nothing kept (D4)."""
        now, idle = time.time(), float(self.cfg["idle_secs"])
        for s in list(self.sessions.values()):
            if s.running or now - s.last < idle:
                continue
            if not s.subs and now - s.last > 3 * idle:
                await self.close(s.sid, "recycled (idle)")
                continue
            loop = asyncio.get_running_loop()
            ep = self.srv.epochs.get(s.sid, 1)
            await loop.run_in_executor(s.pool, self.srv.open_session,
                                       s.sid, s.spec)
            self._seat(s.sid)
            self.srv.epochs[s.sid] = ep + 1
            s.log.clear()
            s.last = now
            await self._broadcast(s, self._session_frame(
                s, recycled="idle"))

    def _rate_ok(self, key) -> bool:
        q = self.rates.setdefault(key, deque())
        now = time.time()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= int(self.cfg["rate_per_min"]):
            return False
        q.append(now)
        return True

    # -- the socket ------------------------------------------------------

    async def handler(self, ws):
        ip = (ws.remote_address or ("?",))[0]
        await self._send(ws, {"ch": "meta", "type": "manifest",
                              **manifest(self.cfg)})
        # the CATALOG panel's list, then the names (catalogs stays the
        # last frame of the greeting: a page waits for it)
        await self._send(ws, {"ch": "meta", "type": "domains",
                              "domains": self.srv.domains()})
        await self._send(ws, {"ch": "meta", "type": "catalogs",
                              "names": self.srv.catalogs()})
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    await self._send(ws, {"ch": "meta", "type": "error",
                                          "error": "bad json"})
                    continue
                ch, typ = msg.get("ch"), msg.get("type")
                if ch == "chat":
                    await self.chat(ws, ip, msg)
                    continue
                if ch != "repl":
                    await self._send(ws, {"ch": "meta", "type": "error",
                                          "error": f"unknown channel {ch!r}"})
                    continue
                if typ in ("open", "intent") and \
                        self.cfg["mode"] == "shared" and \
                        not self._rate_ok(ip):
                    await self._send(ws, {"ch": "repl", "type": "error",
                                          "id": msg.get("id"),
                                          "req": msg.get("req"),
                                          "error": "rate limit — slow down"})
                    continue
                if typ == "open":
                    await self.open(ws, ip, msg)
                elif typ in ("records", "sink", "new", "save"):    # e2e-workflow step 1
                    await self.files(ws, ip, msg)
                elif typ == "intent":
                    await self.intent(ws, msg)
                elif typ == "stop":
                    await self.stop(msg)
                elif typ == "work":
                    await self.work(ws, msg)
                elif typ == "recompile":
                    s = self.sessions.get(msg.get("session", ""))
                    if s and ws in s.subs:
                        if s.running:
                            await self._send(ws, {
                                "ch": "repl", "type": "error",
                                "session": s.sid, "error": "busy — stop "
                                "the running command before recompiling"})
                        else:
                            await self.recompile(s)
                elif typ == "close":
                    s = self.sessions.get(msg.get("session", ""))
                    if s and (ws in s.subs):
                        await self.close(s.sid)
                else:
                    await self._send(ws, {"ch": "repl", "type": "error",
                                          "error": f"unknown type {typ!r}"})
        finally:
            for s in self.sessions.values():
                s.subs.discard(ws)

    async def chat(self, ws, ip, msg):
        """Chat frames (§1, §3): personal mode with the agent seat only;
        a shared instance refuses them all."""
        sid = msg.get("session", "")
        if not self.agent:
            why = ("chat is not served on this instance"
                   if self.cfg["mode"] == "shared" else
                   "agent chat unavailable here: " +
                   (agent_seat(self.cfg)[1] or "?"))
            return await self._send(ws, {"ch": "chat", "type": "error",
                                         "session": sid, "error": why})
        s = self.sessions.get(sid)
        if not s or ws not in s.subs:
            return await self._send(ws, {"ch": "chat", "type": "error",
                                         "session": sid,
                                         "error": "open a session first"})
        typ = msg.get("type")
        if typ == "say":
            err = await self.agent.say(sid, msg.get("text"))
            if err:
                await self._send(ws, {"ch": "chat", "type": "error",
                                      "session": sid, **err})
        elif typ == "stop":
            await self.stop({"session": sid})
        elif typ == "history":
            await self._send(ws, self.agent.history(sid))
        else:
            await self._send(ws, {"ch": "chat", "type": "error",
                                  "session": sid,
                                  "error": f"unknown chat type {typ!r}"})

    # -- HTTP on the same port -------------------------------------------

    def _token_ok(self, path: str) -> bool:
        tok = self.cfg.get("token") or ""
        if not tok:
            return True
        q = parse_qs(urlparse(path).query)
        return secrets.compare_digest((q.get("token") or [""])[0], tok)

    def page(self) -> str:
        flag = json.dumps({"ws": "/ws", "token": self.cfg.get("token") or "",
                           "mode": self.cfg["mode"]})
        return ("<!doctype html><html><head><meta charset=utf-8><meta "
                "name=viewport content=\"width=device-width,initial-scale=1\">"
                f"<script>window.LOOP_GATEWAY={flag};"
                # no artifact capabilities here: every use() resolves null
                "window.claude=Object.freeze({use:async()=>null});"
                "</script></head><body>" + PAGE.read_text() +
                "</body></html>")

    def process_request(self, connection, request):
        from websockets.datastructures import Headers
        from websockets.http11 import Response
        path = request.path
        route = urlparse(path).path

        def respond(code, body, ctype="text/plain; charset=utf-8"):
            b = body.encode()
            return Response(code.value, code.phrase, Headers([
                ("Content-Type", ctype), ("Content-Length", str(len(b))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff")]), b)
        if route == "/healthz":
            return respond(HTTPStatus.OK, "ok\n")
        if not self._token_ok(path):
            return respond(HTTPStatus.FORBIDDEN,
                           "this console needs its access token "
                           "(?token=…)\n")
        if route == "/ws":
            return None                                 # upgrade
        if route.startswith("/vendor/"):
            name = route[len("/vendor/"):]
            f = VENDOR / name
            if "/" not in name and name.endswith(".js") and f.is_file():
                return respond(HTTPStatus.OK, f.read_text(),
                               "text/javascript; charset=utf-8")
            return respond(HTTPStatus.NOT_FOUND, "not found\n")
        if route in ("/", "/index.html"):
            return respond(HTTPStatus.OK, self.page(),
                           "text/html; charset=utf-8")
        return respond(HTTPStatus.NOT_FOUND, "not found\n")

    async def serve(self, ready: Optional[asyncio.Event] = None,
                    stop: Optional[asyncio.Event] = None):
        from websockets.asyncio.server import serve
        async with serve(self.handler, self.cfg["bind"], int(self.cfg["port"]),
                         process_request=self.process_request,
                         max_size=2 ** 20) as server:
            self.port = server.sockets[0].getsockname()[1]

            async def sweeper():
                while True:
                    await asyncio.sleep(min(60, max(5, float(
                        self.cfg["idle_secs"]) / 4)))
                    await self.sweep()
            sw = asyncio.create_task(sweeper())
            if ready:
                ready.set()
            try:
                await (stop.wait() if stop else asyncio.Future())
            finally:
                sw.cancel()
                for sid in list(self.sessions):
                    await self.close(sid, "server stopped")


def main(argv=None) -> int:
    """`metis-loop console-serve` — see the module docstring."""
    import argparse
    ap = argparse.ArgumentParser(prog="metis-loop console-serve",
                                 description="the Loop Console's standing "
                                 "backend (docs/CONSOLE-WS.md)")
    ap.add_argument("--port", type=int)
    ap.add_argument("--bind")
    ap.add_argument("--mode", choices=["personal", "shared"])
    ap.add_argument("--token")
    ap.add_argument("--mock-agent", action="store_true",
                    help="DEV ONLY: a canned chat client (never a model) "
                         "for driving the page without spending anyone's "
                         "subscription")
    ns = ap.parse_args(argv)
    cfg = load_config(port=ns.port, bind=ns.bind, mode=ns.mode,
                      token=ns.token)
    if cfg["mode"] == "shared" and cfg["bind"] not in ("127.0.0.1",
                                                       "localhost") \
            and not cfg["token"]:
        print("console-serve: shared mode on a non-local bind without a "
              "token — anyone who can reach it can run catalogs (no AI "
              "is ever served in shared mode).")
    gw = Gateway(cfg)
    if ns.mock_agent and gw.agent:
        from .agent_service import MockClient
        gw.agent.client_factory = MockClient
        print("console-serve: --mock-agent — the chat is CANNED (dev only)")
    q = f"?token={cfg['token']}" if cfg["token"] else ""
    print(f"loop console ({cfg['mode']}): http://{cfg['bind']}:"
          f"{cfg['port']}/{q}", flush=True)
    try:
        asyncio.run(gw.serve())
    except KeyboardInterrupt:
        pass
    return 0
