"""The console gateway (docs/CONSOLE-WS.md §1, §2, §4, §7): a standing
backend for the Loop Console — plain `websockets` + stdlib-shaped HTTP
on ONE port (D1), grown from console/dev_serve.py.

    GET /            the page (loop_console.html) with the gateway flag
    GET /healthz     liveness
    GET /lib/<name>  the console's shell, console/lib/ (shell_lib; no token: public code)
    GET /sdk/catalog/<name>  the CATALOG widget (catalog.js, catalog.css) from the installed
                     loop SDK (metis_loop_sdk.web.WIDGET_DIR; no token: public code)
    WS  /ws          one multiplexed socket per browser window

Frames (JSON, one per message):

    page -> gw   {ch:"repl", type:"open",   llp, req}      new session
                 {ch:"repl", type:"open",   llp, host:true, req}  …with the host the index names
                 {ch:"repl", type:"open",   source, name, req}  from catalog
                                          TEXT, compiled in memory (§4a)
                 {ch:"repl", type:"open",   session}       re-attach
                 {ch:"repl", type:"intent", session, id, cmd, actor}
                 {ch:"repl", type:"stop",   session}
                 {ch:"repl", type:"work",   session, copy?, extensions?}  the
                                          editor's working copy (§4a)
                 {ch:"repl", type:"recompile", session}  rebuild from it
                 {ch:"repl", type:"close",  session}
                 {ch:"repl", type:"records"} -> {ch:"meta", type:"records", records}
                 {ch:"repl", type:"sink", session, file}  a checkout records file into the session
                 {ch:"repl", type:"new", name, line, req}  domains/<name>/ made, then opened
                 {ch:"repl", type:"new", name?, line?, seed, req}  -> {type:"gate", plan} a new domain from a
                                    seed (a package dir: taken whole; an .llp: its program), confirmed by gate
                 {ch:"repl", type:"save", session[, token][, display, line]}  -> {type:"save", files:[{path,new,diff,
                                    since_diff?}], token[, written]} (the gate's plan: docs/LOOP.md)
                 {ch:"repl", type:"refuse", session, token}  the person said no: remembered (the next plan's since_diff)
                 {ch:"repl", type:"gate", op:"propose", session?, kind, domain, args, req}  -> {type:"gate", plan}
                                    kind edit | readme | intents | take | program (loop-parity step 2)
                 {ch:"repl", type:"gate", op:"confirm"|"refuse", token, req}  -> {type:"gate", written | refused}
                 {ch:"chat", type:"say"|"stop"|"history", session, text}
                                          (personal mode, the agent seat)
    gw -> page   {ch:"meta", type:"manifest", ...}  {ch:"meta", type:"catalogs", names}
                 {ch:"meta", type:"readme", readme}  the root's README.md, {path, text,
                                          links: {href: package path}} or null
                 {ch:"meta", type:"domains", domains}  the CATALOG panel
                                          (the SDK's catalog.index: line, has, readme_text)
                 {ch:"repl", type:"session", session, req?, …fields, busy, running, queued}
                 {ch:"repl", type:"queued",  session, id, cmd, actor, ts}
                 {ch:"repl", type:"posting", session, id, cmd, actor, ts, …intent_posting}
                 {ch:"repl", type:"source",  session, name, copy, extensions,
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
import os
import secrets
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

from metis_loop_sdk.web import WIDGET_URL, widget_file

from . import brain, shell_lib
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
    # session's LLM endpoint with the loop SDK's claude command face
    # (metis_loop_sdk.models claude-command, Haiku); "llm" keeps
    # the kernel's configured endpoint (ollama)
    "narrate": "sdk", "narrate_model": "claude-haiku-4-5",
    "narrate_thinking": 1024,       # tokens; 0 = off (fast, unfaithful)
    # formalize on the claude brain (brain-choice): its own key, the same Haiku by default
    "formalize_model": "claude-haiku-4-5", "formalize_thinking": 1024,
    # the band's AGENT field (human-loop step 3): metis-agent's console wire,
    # e.g. "ws://127.0.0.1:8395/ws"; "" = off; never in shared mode
    "metis_agent": "",
    # the brain (brain-choice s-c59b7b51, loop/brain.py): claude | openrouter[:MODEL] |
    # ollama; "" = by what is here (claude, else OpenRouter with a key, else ollama)
    "brain": "", "openrouter_model": "deepseek/deepseek-v4-pro",
    "openrouter_narrate_model": "deepseek/deepseek-v4-flash",
    "max_usd": 1.00,                # per session, OpenRouter's reported cost
    # take (loop-parity step 2): the operator's other catalog a domain is taken into; "" = take is off
    "take_into": "",
    # loop-policy: a loop's state directory (pi's --state) whose asks the GATE shows and answers; "" = the console's own
    "loop_state": "",
    # the agent seat's writes wait for the person's confirm this long, then count as refused (seconds)
    "agent_gate_timeout": 600,
    "narrate_reasoning": "low",     # OpenRouter's narrate (formalize: off); off invented events
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
    if cfg["narrate_reasoning"] not in brain.REASONING:
        raise ValueError(f"[console] narrate_reasoning must be {'|'.join(brain.REASONING)}, "
                         f"not {cfg['narrate_reasoning']!r}")
    if not float(cfg["max_usd"]) > 0:
        raise ValueError(f"[console] max_usd must be above 0, not {cfg['max_usd']!r}")
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
    if why:
        return None, why
    b = brain.resolve(cfg)["name"]
    if b != "claude":                   # brain-choice: the agent seat is Claude's
        return None, f"needs claude (the brain is {b}: --brain claude)"
    return "agent", None


def narrate_seat(cfg: dict, sid: str = "", log=None):
    """(label, endpoint spec or None): the narrate seat this instance
    serves (D3), on the brain's provider (loop/brain.py). None spec =
    leave the kernel's endpoint (ollama)."""
    return brain.seats(cfg, sid, log)["narrate"]


def formalize_seat(cfg: dict, sid: str = "", log=None):
    """(label, endpoint spec or None): formalize's seat (brain-choice). None
    spec = the session's one endpoint (the narrate seat's, or the kernel's)."""
    return brain.seats(cfg, sid, log)["formalize"]


def verb_lines() -> dict:
    """The REPL API's line for each verb it declares to the loop (its
    reads and surprise verbs, metis.loop.wire DECLARED; repl-tools step
    4): a chip's title is the line the orchestrator's model reads."""
    from metis.loop.wire import DECLARED
    return {n: t["description"] for n, t in sorted(DECLARED.items())}


def manifest(cfg: dict) -> dict:
    """What this instance serves — the page renders only these (§4)."""
    shared = cfg["mode"] == "shared"
    seat, why = agent_seat(cfg)
    s = brain.seats(cfg)
    return {
        "mode": cfg["mode"],
        "brain": s["brain"],                             # brain-choice: {name, model}; None when shared
        "chat_unavailable": why,
        "seats": {
            "repl": True,
            "chat": seat,                                # §3
            "narrate": s["narrate"][0],                   # D3
            "formalize": s["formalize"][0],
        },
        "chat_model": (cfg.get("agent_model") or "the CLI default")
        if seat == "agent" else None,
        "chat_pointer": cfg["artifact_url"] or None,
        "verbs": verb_lines(),
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
        self.gate_wait: Dict[str, asyncio.Future] = {}   # the agent seat's plans waiting for the person
        self.tid: Optional[int] = None
        self.running: Optional[dict] = None
        self.stopping = False
        self.last = time.time()
        self.worker: Optional[asyncio.Task] = None
        self.futs: Dict[str, asyncio.Future] = {}   # submit() waiters


class Gateway:
    def __init__(self, cfg: dict, srv: Optional[ConsoleServer] = None):
        self.cfg = cfg
        self.srv = srv or ConsoleServer(take_into=cfg.get("take_into") or None, loop_state=cfg.get("loop_state") or None)
        if cfg.get("take_into") and not getattr(self.srv, "take_into", None):
            self.srv.take_into = Path(cfg["take_into"]).expanduser()
        if cfg.get("loop_state") and not getattr(self.srv, "loop_state", None):
            self.srv.loop_state = Path(cfg["loop_state"]).expanduser()
        self.sessions: Dict[str, Sess] = {}
        self.rates: Dict[object, deque] = {}
        self.pages = set()
        self.agent_state = None
        self.formalize_llm: Dict[str, Optional[str]] = {}   # sid -> formalize's endpoint (brain-choice)
        self.seated_llm: Dict[str, Optional[str]] = {}      # sid -> the session's endpoint as _seat left it
        if cfg.get("metis_agent") and cfg["mode"] == "personal":
            from .agent_state import AgentState
            self.agent_state = AgentState(cfg["metis_agent"])
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
                 "extensions": msg.get("extensions") or []}
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
    #    a session from it (+ its extensions) cleanly. The page keeps
    #    it in IndexedDB; the gateway mirrors it in MEMORY for the agent's
    #    source tools. Nothing reaches the operator's disk.

    def _init_work(self, s: "Sess", spec: dict):
        if spec.get("source") is not None:
            copy, name = str(spec["source"]), str(spec.get("name") or "")
            extensions = [dict(p) for p in spec.get("extensions") or []]
            cert = "local"
        else:
            path = self.srv.resolve(spec.get("llp", ""))
            # the copy is the checkout's: the program and its extensions (the served program)
            copy, name, extensions, cert = path.read_text(), str(
                path.relative_to(self.srv.root.resolve()).with_suffix("")), \
                [{"name": p.stem, "source": p.read_text()} for p in self.srv.checkout_extensions(path)], "checkout"
        s.work = {"name": name, "copy": copy, "extensions": extensions,
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
        """The page's editor changed the copy or an extension: mirror it (the
        agent sees the same text) and mark it uncertified."""
        s = self.sessions.get(msg.get("session", ""))
        if not s or ws not in s.subs:
            return
        w = s.work
        if "copy" in msg and msg["copy"] != w["copy"]:
            w["copy"], w["certified"] = str(msg["copy"]), None
        if "extensions" in msg and msg["extensions"] != w["extensions"]:
            w["extensions"] = [{"name": str(p.get("name") or f"extension {k}"),
                           "source": str(p.get("source") or "")}
                          for k, p in enumerate(msg["extensions"], 1)]
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
            if typ in ("new", "gate") and self.cfg["mode"] == "shared":
                raise ValueError(f"{typ} writes the operator's checkout: personal mode only")
            if typ == "new" and msg.get("seed"):
                plan = await loop.run_in_executor(None, self.srv.seed_plan, msg.get("name"), msg["seed"], msg.get("line"))
                return await self._send(ws, {"ch": "repl", "type": "gate", "op": "plan", "req": msg.get("req"),
                                             "purpose": "seed", **plan})
            if typ == "gate":
                return await self.gate(ws, msg, s)
            if typ == "new":
                llp = await loop.run_in_executor(None, self.srv.new_domain, msg.get("name"), msg.get("line"))
                await self._send(ws, {"ch": "meta", "type": "domains", "domains": self.srv.domains()})
                return await self.open(ws, ip, {"llp": llp, "req": msg.get("req")})
            if not s or ws not in s.subs:
                raise ValueError("no open session")
            if typ == "sink":
                out = await loop.run_in_executor(s.pool, self.srv.load_sink, s.sid, str(msg.get("file") or ""))
                return await self._send(ws, {"ch": "repl", "type": "sink", "session": s.sid, **out})
            # save: the plan (diffs + token), or with token the write; refuse: the person said no
            if self.cfg["mode"] == "shared":
                raise ValueError("save writes the operator's checkout: personal mode only")
            w = s.work
            shown = {k: msg[k] for k in ("display", "line") if msg.get(k)}
            if typ == "refuse":
                tok = str(msg.get("token") or "")
                out = await loop.run_in_executor(None, self.srv.save_refuse, tok)
                self._decided(s, tok, ("refused", out))
                return await self._send(ws, {"ch": "repl", "type": "refused", "session": s.sid, "token": tok, **out})
            if msg.get("token"):
                tok = str(msg["token"])
                try:
                    out = await loop.run_in_executor(None, lambda: self.srv.save_apply(w, tok, **shown))
                except ValueError as e:
                    self._decided(s, tok, ("error", str(e)))
                    raise
                w["certified"] = "checkout"
                self._decided(s, tok, ("written", out))
                await self._broadcast(s, self._source_frame(s))
                await self._send_all({"ch": "meta", "type": "domains", "domains": self.srv.domains()})
            else:
                out = await loop.run_in_executor(None, lambda: self.srv.save_plan(w, **shown))
            return await self._send(ws, {"ch": "repl", "type": "save", "session": s.sid, **out})
        except ValueError as e:
            return await self._send(ws, {"ch": "repl", "type": "error", "session": msg.get("session"),
                                         "req": msg.get("req"), "error": str(e)})

    async def gate(self, ws, msg, s):
        """The console's other writes through the loop's gate (docs/LOOP.md): propose a plan
        (to the asking socket only), confirm it (the write), refuse it (remembered)."""
        loop, op = asyncio.get_running_loop(), msg.get("op")
        if op == "asks":
            asks = await loop.run_in_executor(None, self.srv.gate_asks)
            return await self._send(ws, {"ch": "repl", "type": "gate", "op": "asks", "asks": asks})
        if op == "propose":
            plan = await loop.run_in_executor(None, self.srv.gate_plan, str(msg.get("kind") or ""),
                                              str(msg.get("domain") or ""), msg.get("args") or {})
            if plan.get("kind") == "ask":              # a takeover request is for every page of the person's
                asks = await loop.run_in_executor(None, self.srv.gate_asks)
                return await self._send_all({"ch": "repl", "type": "gate", "op": "asks", "asks": asks})
            return await self._send(ws, {"ch": "repl", "type": "gate", "op": "plan", "req": msg.get("req"), **plan})
        tok = str(msg.get("token") or "")
        if op == "answer":
            out = await loop.run_in_executor(None, self.srv.gate_answer, tok, msg.get("instruction"))
            await self._send(ws, {"ch": "repl", "type": "gate", "op": "answered", "req": msg.get("req"), **out})
            asks = await loop.run_in_executor(None, self.srv.gate_asks)
            return await self._send_all({"ch": "repl", "type": "gate", "op": "asks", "asks": asks})
        if op == "confirm":
            out = await loop.run_in_executor(None, self.srv.gate_confirm, tok)
            await self._send_all({"ch": "meta", "type": "domains", "domains": self.srv.domains()})
            await self._send(ws, {"ch": "meta", "type": "catalogs", "names": self.srv.catalogs()})
            return await self._send(ws, {"ch": "repl", "type": "gate", "op": "written", "req": msg.get("req"),
                                         "token": tok, **out})
        if op == "refuse":
            out = await loop.run_in_executor(None, self.srv.gate_refuse, tok)
            return await self._send(ws, {"ch": "repl", "type": "gate", "op": "refused", "req": msg.get("req"),
                                         "token": tok, **out})
        raise ValueError(f"gate op: propose | confirm | refuse | asks | answer, not {op!r}")

    async def ask_person(self, s: "Sess", plan: dict) -> tuple:
        """The agent seat's write waits for the person (docs/LOOP.md rule 1, as pi's gate):
        the plan goes to the session's pages as a save plan by the agent; the person's
        save-with-token or refuse decides it. → ("written", out) | ("refused", out) |
        ("error", words) | ("timeout", words)."""
        fut = asyncio.get_running_loop().create_future()
        s.gate_wait[plan["token"]] = fut
        await self._broadcast(s, {"ch": "repl", "type": "save", "session": s.sid, "by": "agent", **plan})
        try:
            return await asyncio.wait_for(fut, float(self.cfg.get("agent_gate_timeout") or 600))
        except asyncio.TimeoutError:
            return ("timeout", "the person did not answer the agent's write")
        finally:
            s.gate_wait.pop(plan["token"], None)

    def _decided(self, s: "Sess", token: str, outcome: tuple):
        fut = s.gate_wait.get(token)
        if fut is not None and not fut.done():
            fut.set_result(outcome)

    async def _send_all(self, frame: dict):
        for ws in list(self.pages):
            await self._send(ws, frame)

    async def recompile(self, s: "Sess") -> dict:
        """Build the session again from the working copy + extensions (in
        memory). Success: a new interpreter, epoch + 1, the copy
        certified (locally); failure: the error, the old world kept."""
        w = s.work
        spec = {"source": w["copy"], "name": w["name"] or "scratch",
                "extensions": w["extensions"], "host": bool((getattr(s, "spec", None) or {}).get("host")),
                "keep_loop": True}          # the sunk records and the selected record go on
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
                "extensions": fields.get("extensions", [])}

    def _seat(self, sid: str):
        """D3: in personal mode the session's narrate seat goes to the
        brain's endpoint (kernel untouched — its `command:` backend runs the
        loop SDK's claude command face, or loop.brain's OpenRouter one);
        formalize's own endpoint, when the brain gives it one, is kept for
        the formalize commands (_work)."""
        s = brain.seats(self.cfg, sid, self.calls_log())
        spec = s["narrate"][1]
        r = self.srv.shells.get(sid)
        if spec and r is not None:
            r.llm = spec
        self.formalize_llm[sid] = s["formalize"][1]
        self.seated_llm[sid] = r.llm if r is not None else None    # what the seats left; a person's `:llm` moves it

    def calls_log(self) -> str:
        """The OpenRouter seats' call log: DIR/.metis/formalize-calls.jsonl (made
        by the first call, through metis.catalog.state(); nothing here)."""
        from metis import catalog
        return str(Path(self.srv.root).resolve() / catalog.STATE / brain.LOG)

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
        "person names things, keep under `asks` only the candidate verbs the person asks as a "
        "question (how it is, where a thing is) and drop the actions, and call intents_propose "
        "with the WHOLE file. Fix what it reports. "
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
                # formalize on its own endpoint for this one command (the kernel has one per session),
                # unless the person moved the session's endpoint (`:llm X`): then both seats are on X, as before
                f = self.formalize_llm.get(s.sid) if cmd.strip().lstrip(":").split(" ", 1)[0] == "formalize" else None
                r = self.srv.shells.get(s.sid) if f else None
                if r is not None and r.llm != self.seated_llm.get(s.sid):
                    r = None
                was = r.llm if r is not None else None
                try:
                    with s.lock:
                        s.tid = threading.get_ident()
                    try:
                        if r is not None:
                            r.llm = f
                        return self.srv.serve_one(s.sid, cmd)
                    finally:
                        if r is not None:
                            r.llm = was
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
        # DIR/README.md, the catalog's context the page lands on (rule 10)
        await self._send(ws, {"ch": "meta", "type": "readme",
                              "readme": self.srv.readme()})
        if self.agent_state:            # the band's AGENT field (step 3)
            await self._send(ws, self.agent_state.frame())
        await self._send(ws, {"ch": "meta", "type": "catalogs",
                              "names": self.srv.catalogs()})
        self.pages.add(ws)
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
                elif typ in ("records", "sink", "new", "save", "refuse", "gate"):    # e2e-workflow step 1; the gate
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
            self.pages.discard(ws)
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
                           "mode": self.cfg["mode"], "pkg": self.cfg.get("pkg") or []})
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
        if route.startswith("/lib/"):                   # the shell: the page's own code, no token
            got = shell_lib.get(route[len("/lib/"):])
            if got is None:
                return respond(HTTPStatus.NOT_FOUND, "not found\n")
            return respond(HTTPStatus.OK, *got)
        if route.startswith(WIDGET_URL):                # the CATALOG widget, from the installed SDK: public code
            got = widget_file(route[len(WIDGET_URL):])
            if got is None:
                return respond(HTTPStatus.NOT_FOUND, "not found\n")
            return respond(HTTPStatus.OK, *got)
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
            ag = None
            if self.agent_state:
                async def to_pages(frame):
                    for ws in list(self.pages):
                        await self._send(ws, frame)
                ag = asyncio.create_task(self.agent_state.run(to_pages))
            if ready:
                ready.set()
            try:
                await (stop.wait() if stop else asyncio.Future())
            finally:
                sw.cancel()
                if ag:
                    ag.cancel()
                for sid in list(self.sessions):
                    await self.close(sid, "server stopped")


def pkg_rows(names) -> list:
    """--pkg NAME… (metis-agent's flag; release-r02 step 1b, D5): each package's domains as the
    CATALOG panel opens them, {name, path, host} (the index's row: the root's path, METIS_HOME's
    absolute), NAME resolved as metispy resolves an include, the catalog root's domains/NAME
    else METIS_HOME's (metis.catalog.package_domains); in order, each once. A page with no
    session opens the first; the rest are the panel's. ValueError on a miss, naming both places."""
    from metis import catalog
    rows = [e for e in catalog.index() if e["kind"] == "domain"]
    out = []
    for n in names:
        try:
            ds = catalog.package_domains(n)
        except (FileNotFoundError, KeyError) as e:
            raise ValueError(f"--pkg {n}: {e.args[0] if e.args else e}") from None
        if not ds:
            raise ValueError(f"--pkg {n}: no domain manifest in {catalog.find_package(n)}")
        for d in ds:
            e = next((e for e in rows if e["name"] == d.name), None)
            if e is not None and all(p["path"] != e["path"] for p in out):
                out.append({"name": d.name, "path": e["path"], "host": bool(e.get("host"))})
    return out


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
    ap.add_argument("--brain", metavar="claude|openrouter[:MODEL]|ollama",
                    help="the LLM seats' provider (loop/brain.py); default: [console] brain, "
                         "else claude when here, else openrouter with $OPENROUTER_API_KEY, else ollama")
    ap.add_argument("--metis-agent", metavar="WS_URL",
                    help="metis-agent's console wire (ws://127.0.0.1:8395/ws): "
                         "the band shows the agent's state of the open domain "
                         "(personal mode)")
    ap.add_argument("--pkg", action="append", default=[], metavar="NAME",
                    help="open the package domains/NAME at the start (the catalog root's, else "
                         "METIS_HOME's): a page with no session opens it; repeatable, the panel "
                         "lists and opens the rest")
    ap.add_argument("--mock-agent", action="store_true",
                    help="DEV ONLY: a canned chat client (never a model) "
                         "for driving the page without spending anyone's "
                         "subscription")
    ns = ap.parse_args(argv)
    cfg = load_config(port=ns.port, bind=ns.bind, mode=ns.mode,
                      token=ns.token, metis_agent=ns.metis_agent, brain=ns.brain)
    if cfg["mode"] == "personal":       # a brain asked for and not here refuses now, naming the fix
        try:
            b = brain.resolve(cfg)
        except brain.BrainError as e:
            print(f"metis-loop: {e}", file=sys.stderr)
            return 2
        cfg["brain"] = b["name"] + (":" + b["model"] if b["name"] == "openrouter" else "")
    if cfg["mode"] == "shared" and cfg["bind"] not in ("127.0.0.1",
                                                       "localhost") \
            and not cfg["token"]:
        print("console-serve: shared mode on a non-local bind without a "
              "token — anyone who can reach it can run catalogs (no AI "
              "is ever served in shared mode).")
    try:                        # the CATALOG panel's loader, before any page connects
        from metis import catalog
        catalog.loader()
    except ImportError as e:
        print(f"console-serve: {e}", file=sys.stderr)
        return 1
    # the catalog root is the workspace (cwd-root s-ddac2cbf): the cwd, or
    # $METIS_CATALOG — then the process runs there, as `cd DIR` would have
    root = catalog.root()
    if not root.is_dir():
        print(f"console-serve: no catalog directory at {root} (METIS_CATALOG)", file=sys.stderr)
        return 1
    os.chdir(root)
    try:                        # --pkg: resolved before any page connects; a miss refuses the start
        cfg["pkg"] = pkg_rows(ns.pkg)
    except ValueError as e:
        print(f"console-serve: {e}", file=sys.stderr)
        return 2
    try:                        # the page's shell (console/lib/shell.css, shell.js)
        shell_lib.check()
    except FileNotFoundError as e:
        print(f"console-serve: {e}", file=sys.stderr)
        return 1
    gw = Gateway(cfg)
    if ns.mock_agent and gw.agent:
        from .agent_service import MockClient
        gw.agent.client_factory = MockClient
        print("console-serve: --mock-agent — the chat is CANNED (dev only)")
    q = f"?token={cfg['token']}" if cfg["token"] else ""
    print(f"loop console ({cfg['mode']}): http://{cfg['bind']}:"
          f"{cfg['port']}/{q}", flush=True)
    print(f"catalog: {root}", flush=True)
    for p in cfg["pkg"]:
        print(f"--pkg: {p['name']} ({p['path']}): a page with no session opens "
              + ("it" if p is cfg["pkg"][0] else "the first; this one is the panel's"), flush=True)
    print(brain.describe(cfg, os.path.relpath(gw.calls_log(), root)
                         if cfg["mode"] == "personal" else None), flush=True)
    try:
        asyncio.run(gw.serve())
    except KeyboardInterrupt:
        pass
    return 0
