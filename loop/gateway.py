"""The console gateway (docs/CONSOLE-WS.md §1, §2, §4, §7): a standing
backend for the Loop Console — plain `websockets` + stdlib-shaped HTTP
on ONE port (D1), grown from console/dev_serve.py.

    GET /            the page (loop_console.html) with the gateway flag
    GET /healthz     liveness
    GET /lib/<name>  the console's shell, console/lib/ (shell_lib; no token: public code)
    GET /sdk/catalog/<name>  the CATALOG widget (catalog.js, catalog.css) from the installed
                     loop SDK (metis_loop_sdk.web.WIDGET_DIR; no token: public code)
    GET /sdk/workspace/<name>  the workspace widgets (io.js, workspace.css, bundle/trace/
                     rulings/loop.js: metis_loop_sdk.web.WS_WIDGET_DIR; public code)
    WS  /ws          one multiplexed socket per browser window

Frames (JSON, one per message):

    page -> gw   {ch:"repl", type:"open",   llp, req}      new session
                 {ch:"repl", type:"open",   llp, host:true, req}  …with the host the index names
                 {ch:"repl", type:"open",   session}       re-attach
                 {ch:"repl", type:"intent", session, id, cmd, actor}
                 {ch:"repl", type:"stop",   session}
                 {ch:"repl", type:"edit", session, path, old, new, req}  -> {type:"edit", op:"plan", path, diff,
                                    findings:[{level,code,line,msg}], ok, token?} one exact edit of a checkout file
                                    (the EDITOR's save, workspace-files s-9ea4cfa4: the workspace owns the file)
                 {ch:"repl", type:"files", session, req}  -> the files frame again (the EDITOR's reload)
                 {ch:"repl", type:"edit", op:"confirm"|"refuse", session, token, req}  -> {type:"edit",
                                    op:"written"|"refused"}; written: the session re-opened (epoch + 1), its files again
                 {ch:"repl", type:"new", name, line, req}  domains/<name>/ made, then opened
                 {ch:"repl", type:"new", name?, line?, seed, req}  -> {type:"gate", plan} a new domain from a
                                    seed (a package dir: taken whole; an .llp: its program), confirmed by gate
                 {ch:"repl", type:"gate", op:"propose", session?, kind, domain, args, req}  -> {type:"gate", plan}
                                    kind edit | readme | intents | take | program (loop-parity step 2)
                 {ch:"repl", type:"gate", op:"confirm"|"refuse", token, req}  -> {type:"gate", written | refused}
    gw -> page   {ch:"meta", type:"manifest", ...}  {ch:"meta", type:"catalogs", names}
                 {ch:"meta", type:"readme", readme}  the root's README.md, {path, text,
                                          links: {href: package path}} or null
                 {ch:"meta", type:"domains", domains}  the CATALOG panel
                                          (the SDK's catalog.index: line, has, readme_text)
                 {ch:"repl", type:"session", session, req?, …fields, busy, running, queued}
                 {ch:"repl", type:"queued",  session, id, cmd, actor, ts}
                 {ch:"repl", type:"posting", session, id, cmd, actor, ts, …intent_posting}
                 {ch:"repl", type:"files",   session, program, files:[{path, text, role}]}  the EDITOR's
                                          files of the session, as they are on disk (after open and every write)
                 {ch:"repl", type:"notice",  session, text}  a word for the session's page (an edit wrote
                                          its file while it ran: it re-opens when the command ends)
                 {ch:"…",    type:"error",   error, session?, id?}

The posting payload is `intent_posting` verbatim (via ConsoleServer.
serve_one): the page's renderers do not change, and the whitelist is
the same `parse_intent` — approval verbs and paths cannot arrive.

Session Manager = ConsoleServer + per-session command QUEUE (one
command at a time, on the session's own worker thread), busy/stop
(stop interrupts the running command and drops the queue), and the
`[console]` caps. Mode manifest (§4): `personal` (own host) and `shared`
(an optional URL token (D2), per-IP session caps and a rate limit).

No brain (loop-workspace s-5b4be5fa, docs/WORKSPACE.md §3, §7): the agent
chat and the console's own seats are retired with loop/brain.py, and the
REPL's `formalize` is refused in every mode: a surprise is dropped to the
workspace and the pi loop formalizes and rules it. `narrate` and `llm` are
the REPL's own again (the user, 2026-11-04): the REPL's model (metispy
metis.loop.llm), set with `llm` and saved in the host's dot file, the same
in every mode (the user, 2026-11-05: there is no local/remote backend; the
REPL's narration is the metis host config's). The OpenRouter key comes from the environment, or the person's private key
file loaded at start (load_key_file), never printed.

Privacy (D4): sessions and postings live in MEMORY only; nothing a
visitor types or runs is written to the operator's disk."""
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

from metis_loop_sdk.web import WIDGET_URL, WS_WIDGET_URL, widget_file, ws_widget_file

from . import shell_lib
from .console_serve import ConsoleServer
from .workspace_ch import CHANNELS as WS_CHANNELS, SessionTrace, WorkspaceChannels

CHANNELS = ("repl", "meta") + WS_CHANNELS    # the manifest says them; `chat` is retired

PAGE = Path(__file__).resolve().parent.parent / "console" / "loop_console.html"
VENDOR = PAGE.parent / "vendor"     # the CodeMirror bundle (one instance)

DEFAULTS = {
    "port": 8770, "bind": "127.0.0.1", "mode": "personal", "token": "",
    "max_sessions": 16, "max_sessions_per_ip": 4, "max_run_steps": 500,
    "idle_secs": 1800, "rate_per_min": 120, "history": 300,
    # the band's AGENT field (human-loop step 3): metis-agent's console wire,
    # e.g. "ws://127.0.0.1:8395/ws"; "" = off; never in shared mode
    "metis_agent": "",
    # take (loop-parity step 2): the operator's other catalog a domain is taken into; "" = take is off
    "take_into": "",
    # loop-policy: a loop's state directory (pi's --state) whose asks the GATE shows and answers; "" = the console's own
    "loop_state": "",
}
# the retired formalizer (loop-workspace): formalize moved to the pi loop; narrate and llm STAY with the REPL
# (the user, 2026-11-04: "dropping ollama was mistake… people working on single llp file loosing this feature"):
# the REPL's own model (metispy metis.loop.llm: ollama | openrouter | anthropic | command, set with `llm`, saved in
# the dot file; the OpenRouter key from the environment only)
LLM_VERBS = frozenset(["formalize"])
RETIRED = {     # [console] keys of the retired seats: a dot file that still has one is told, not failed
    "agent", "agent_model", "agent_tool_calls", "agent_cmd_timeout", "agent_max_turns", "agent_gate_timeout",
    "narrate", "narrate_model", "narrate_thinking", "narrate_reasoning", "formalize_model",
    "formalize_thinking", "brain", "openrouter_model", "openrouter_narrate_model", "max_usd", "artifact_url"}
SEATS_GONE = ("formalize moved to the pi loop (loop-workspace, docs/WORKSPACE.md §3): drop a surprise to the "
              "workspace (the REPL's drop, the CHAT's /drop or /mark) and the pi loop formalizes and rules it (pi/loop.sh), or type "
              "in the CHAT; narrate and llm are the REPL's own (`llm` sets the model)")


def load_key_file(env=None):
    """The OpenRouter key into the environment for the REPLs' narrate, when it is not there: the person's own
    private key file (METIS_OPENROUTER_ENV, default ~/.config/metis/openrouter.env; owner, mode 600 or 400),
    PARSED for its last OPENROUTER_API_KEY= line (as pi/loop.sh does), never sourced, never printed. → a note
    for the start line, or None."""
    import re
    import stat
    env = os.environ if env is None else env
    if env.get("OPENROUTER_API_KEY"):
        return None
    f = env.get("METIS_OPENROUTER_ENV", os.path.expanduser("~/.config/metis/openrouter.env"))
    if not f or not os.path.isfile(f):
        return None
    try:
        st = os.stat(f)
    except OSError:
        return None
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) not in (0o600, 0o400):
        return f"{f} is not private (mode 600 or 400, yours): not read"
    key = None
    for line in open(f, encoding="utf-8", errors="replace"):
        m = re.match(r"^\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*(.*)$", line.rstrip("\r\n"))
        if m:
            v = m.group(1).strip()
            if v[:1] in ("'", '"'):
                v = v[1:].split(v[0], 1)[0]
            key = v.split()[0] if v.split() else ""
    if not key:
        return f"{f} has no OPENROUTER_API_KEY= line: not read"
    env["OPENROUTER_API_KEY"] = key
    return f"OPENROUTER_API_KEY from {f}"


def load_config(**overrides) -> dict:
    """DEFAULTS < the metis dot file's [console] table < overrides
    (CLI flags; None means 'not given'). A retired seat's key in the dot
    file is ignored and named in cfg["retired"] (the start line says so)."""
    cfg = dict(DEFAULTS)
    retired = []
    try:
        from metis.loop import config
        _, conf = config.load()
        t = conf.get("console")
        if isinstance(t, dict):
            cfg.update({k: v for k, v in t.items() if k in DEFAULTS})
            retired = sorted(k for k in t if k in RETIRED)
    except Exception:                                   # noqa: BLE001
        pass
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    if cfg["mode"] not in ("personal", "shared"):
        raise ValueError(f"[console] mode must be personal|shared, "
                         f"not {cfg['mode']!r}")
    cfg["retired"] = retired
    return cfg


def verb_lines() -> dict:
    """The REPL API's line for each verb it declares to the loop (its
    reads and surprise verbs, metis.loop.wire DECLARED; repl-tools step
    4): a chip's title is the line the orchestrator's model reads."""
    from metis.loop.wire import DECLARED
    return {n: t["description"] for n, t in sorted(DECLARED.items())}


def manifest(cfg: dict) -> dict:
    """What this instance serves — the page renders only these (§4)."""
    shared = cfg["mode"] == "shared"
    return {
        "mode": cfg["mode"],
        "seats": {"repl": True},                         # the LLM seats are retired (loop-workspace)
        "channels": list(CHANNELS),
        "verbs": verb_lines(),
        "caps": {k: cfg[k] for k in ("max_sessions", "max_sessions_per_ip",
                                     "max_run_steps", "idle_secs",
                                     "rate_per_min")},
        "policy": ("shared instance: the REPL, capped; no model runs here"
                   if shared else "personal instance: the operator's own host"),
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
        self.written = False                        # its files were written while it ran: re-opens when it ends


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
        if cfg.get("metis_agent") and cfg["mode"] == "personal":
            from .agent_state import AgentState
            self.agent_state = AgentState(cfg["metis_agent"])
        self.wsc = WorkspaceChannels(self)                 # trace, surprise, bundle, loop (WORKSPACE.md §3)

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
                "queued": s.queue.qsize(),
                "trace": ("traces/" + s.sid) if getattr(s, "trace", None) is not None else None,
                **({"trace_error": s.trace_error} if getattr(s, "trace_error", None) else {}),
                **({"served": s.served} if getattr(s, "served", None) else {}), **extra}

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
            await self._send(ws, await self._files_frame(s))
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
        if msg.get("source") is not None:
            return await self._send(ws, {"ch": "repl", "type": "error", "req": msg.get("req"),
                                         "error": "a session opens a checkout program (llp): the workspace owns "
                                         "the file, edit it in the EDITOR (no in-memory catalogs)"})
        spec = {"llp": llp, "host": bool(msg.get("host"))}
        fields = await loop.run_in_executor(
            None, self.srv.open_session, sid, spec)
        if fields.get("status") == "closed":
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "req": msg.get("req"),
                                         "error": fields.get("error",
                                                             "cannot open")})
        s = Sess(sid, fields.get("llp", llp), ip, cap["history"])
        s.spec = spec                    # what idle recycling re-opens
        s.served = fields.get("served")  # a unit opened: its includer is served (loop-ui I5)
        if msg.get("trace"):             # the session's trace (WORKSPACE.md §3): .metis/traces/<session>/
            try:
                s.trace = self.session_trace(s, fields)
            except Exception as e:                       # noqa: BLE001 — the session serves without it, and says so
                s.trace_error = f"no trace: {e}"
        s.subs.add(ws)
        s.worker = asyncio.create_task(self._work(s))
        self.sessions[sid] = s
        await self._send(ws, self._session_frame(s, req=msg.get("req")))
        await self._send(ws, await self._files_frame(s))

    # -- the files (workspace-files s-9ea4cfa4): the workspace owns them; the EDITOR edits them in place
    #    through one gated edit (diff + findings, then confirm), never a copy.

    async def _files_frame(self, s: "Sess") -> dict:
        loop = asyncio.get_running_loop()
        try:
            got = await loop.run_in_executor(None, self.srv.files_of, s.sid)
        except (ValueError, OSError) as e:
            return {"ch": "repl", "type": "files", "session": s.sid, "program": None, "files": [], "error": str(e)}
        return {"ch": "repl", "type": "files", "session": s.sid, **got}

    async def edit(self, ws, msg, s):
        """The EDITOR's save: plan one exact edit (to the asking page), confirm it (the gate writes, the
        sessions on that domain re-open, epoch + 1; the bundle's watch says STALE), or refuse it."""
        loop, op = asyncio.get_running_loop(), msg.get("op") or "plan"
        if self.cfg["mode"] == "shared":
            raise ValueError("an edit writes the operator's checkout: personal mode only (a visitor's view reads)")
        if op == "plan":
            out = await loop.run_in_executor(None, self.srv.edit_plan, str(msg.get("path") or ""),
                                             str(msg.get("old") or ""), str(msg.get("new") or ""), s.sid)
            return await self._send(ws, {"ch": "repl", "type": "edit", "op": "plan", "session": s.sid,
                                         "req": msg.get("req"), **out})
        tok = str(msg.get("token") or "")
        if op == "refuse":
            out = await loop.run_in_executor(None, self.srv.gate_refuse, tok)
            return await self._send(ws, {"ch": "repl", "type": "edit", "op": "refused", "session": s.sid,
                                         "req": msg.get("req"), "token": tok, **out})
        if op != "confirm":
            raise ValueError(f"edit op: plan | confirm | refuse, not {op!r}")
        if s.running:
            raise ValueError("busy: stop the running command before the write (the session re-opens after it)")
        out = await loop.run_in_executor(None, self.srv.gate_confirm, tok)
        await self._send(ws, {"ch": "repl", "type": "edit", "op": "written", "session": s.sid,
                              "req": msg.get("req"), "token": tok, **out})
        written = {str(w) for w in out.get("written") or []}
        prog = self.srv.files_of(s.sid)
        mine = {f["path"] for f in prog["files"]}
        for o in list(self.sessions.values()):         # every session whose program or extension was written
            try:
                theirs = {f["path"] for f in self.srv.files_of(o.sid)["files"]}
            except ValueError:
                continue
            if o is s or theirs & (written or mine):
                if o.running:                           # nina: a session running elsewhere is told, and re-opens after
                    o.written = True
                    await self._broadcast(o, {"ch": "repl", "type": "notice", "session": o.sid,
                                              "text": "a file of this session was written while it ran: the "
                                                      "command goes on with the old program; the session "
                                                      "re-opens when it ends"})
                else:
                    await self._reopen_edited(o)
                await self._broadcast(o, await self._files_frame(o))
        await self._send_all({"ch": "meta", "type": "domains", "domains": self.srv.domains()})

    async def _reopen_edited(self, o: "Sess"):
        """Re-open a session whose files an edit wrote (at the write, or when its running command ends)."""
        o.written = False
        try:
            await self.reopen(o, "edited")
        except ValueError as e:
            await self._broadcast(o, {"ch": "repl", "type": "error", "session": o.sid,
                                      "error": f"the file is written; the session did not re-open: {e}"})

    async def _after_run(self, s: "Sess"):
        """After a command: a session written while it ran re-opens now (its queue waits behind it)."""
        if s.written and s.running is None:
            await self._reopen_edited(s)
            await self._broadcast(s, await self._files_frame(s))

    async def files(self, ws, ip, msg):
        """The checkout's files (e2e-workflow step 1): records sank by
        the domain agents (list; `sink` one into a session), `new`
        domain, `edit` a file of the session (a plan first, the token of
        that plan to write it). Nothing is committed."""
        typ, loop = msg.get("type"), asyncio.get_running_loop()
        s = self.sessions.get(msg.get("session", ""))
        try:
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
            if typ == "edit":
                return await self.edit(ws, msg, s)
            raise ValueError(f"unknown type {typ!r}")
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

    def session_trace(self, s: "Sess", fields: dict) -> SessionTrace:
        """The session's trace writer: personal mode only (it writes the operator's .metis/)."""
        if self.cfg["mode"] == "shared":
            raise ValueError("a session's trace writes the operator's workspace: personal mode only")
        sh = self.srv.shells[s.sid]
        member = self.member_of(s)
        exts = [p.stem for p in self.srv.checkout_extensions(sh.path)]
        return SessionTrace(self.wsc.ws.path("trace", run=s.sid), sh, member, program=sh.path, extensions=exts)

    def member_of(self, s: "Sess") -> str:
        """The session's member as the workspace names it: its package (the program's file name, as
        catalog.get finds it)."""
        return Path(self.srv.shells[s.sid].path).stem

    async def reopen(self, s: "Sess", why: str):
        """The session re-opened from its catalog file, epoch + 1: idle recycling, the bundle's reload (STALE →
        reload) and an edit written (the sunk records and the selected one go on)."""
        loop = asyncio.get_running_loop()
        ep = self.srv.epochs.get(s.sid, 1)
        spec = dict(s.spec or {}, **({"keep_loop": True} if why == "edited" else {}))
        fields = await loop.run_in_executor(s.pool, self.srv.open_session, s.sid, spec)
        if fields.get("status") == "closed":
            raise ValueError(fields.get("error") or "cannot re-open")
        self.srv.epochs[s.sid] = ep + 1
        s.log.clear()
        s.last = time.time()
        await self._broadcast(s, self._session_frame(s, **({"recycled": "idle"} if why == "idle" else {why: True})))

    async def _send_all(self, frame: dict):
        for ws in list(self.pages):
            await self._send(ws, frame)

    def _gate(self, cmd: str) -> Optional[str]:
        """Gateway-side policy beyond run_intent's whitelist: formalize (the pi loop's) is refused in every
        mode; narrate and llm are served alike in every mode. Returns the refusal, or None."""
        verb = cmd.strip().lstrip(":").split(" ", 1)[0]
        if verb in LLM_VERBS:
            return f"'{verb}' is not served here: {SEATS_GONE}"
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

    async def intents(self, s: "Sess", cmd: str, actor: str, iid: str):
        """`intents check` (e2e-workflow step 2, loop/intents.py): the corpus
        (or the examples) on the intent model. Gateway-side: it never reaches
        the kernel REPL. Personal mode only (it runs the operator's model).
        Drafting intent.yaml was the agent seat's (retired, loop-workspace):
        it is the pi loop's now (catalog_new intents=true, at the gate)."""
        from . import intents as it
        item = {"id": iid, "cmd": cmd.strip(), "actor": actor, "ts": _now()}
        await self._broadcast(s, {"ch": "repl", "type": "queued", "session": s.sid, **item}, log=True)
        sub = cmd.strip().lstrip(":").split()[1:]
        loop, ok = asyncio.get_running_loop(), True
        try:
            if self.cfg["mode"] == "shared":
                raise ValueError("intents writes the operator's checkout and runs its model: personal mode only")
            name = str(s.llp or "").split(" + ")[0]
            if sub[:1] == ["check"]:
                out = await loop.run_in_executor(None, it.check, self.srv, name)
                ok, result = out["ok"], out["output"]
            elif not sub or sub[0] in ("show", "save"):
                raise ValueError("drafting intent.yaml is the pi loop's (catalog_new intents=true, at the "
                                 "gate; pi/loop.sh): the console's agent seat is retired. Here: intents check")
            else:
                raise ValueError("usage: intents check")
        except ValueError as e:
            ok, result = False, str(e)
        post = {"status": "done" if ok else "error", "result": result,
                "json": {"ok": ok}, "epoch": self.srv.epochs.get(s.sid), "done_ts": _now()}
        await self._broadcast(s, {"ch": "repl", "type": "posting", "session": s.sid, **item, **post}, log=True)

    async def submit(self, s: "Sess", cmd: str, actor: str) -> dict:
        """Queue a line and await its posting (a backend caller's REPL line):
        the same queue, whitelist, busy/stop and transcript."""
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
                        self._attach(s)
                        self._traced(s, "before")
                        out = self.srv.serve_one(s.sid, cmd)
                        self._traced(s, "after", cmd)
                        return out
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
            await self._after_run(s)
            await self._broadcast(s, self._session_frame(s))

    def _attach(self, s: "Sess"):
        """The session's shell with the workspace and the session's own trace attached (loop-ui I6): its REPL then
        serves the workspace verbs (drop, mark, surprises, status) as the terminal's does, pointing at this trace.
        Personal mode only: a session has a trace only there (session_trace), so a shared-mode visitor's shell
        keeps the wire's whitelist. Again after a reopen or a reload (a new shell); a metispy without the
        attach's trace= (before loop-ui) is left as it was."""
        tr = getattr(s, "trace", None)
        sh = self.srv.shells.get(s.sid)
        if tr is None or sh is None or sh.__dict__.get("_ws") is not None:
            return
        try:
            sh.attach_workspace(self.wsc.ws, trace=tr)
        except TypeError:                                # metispy before loop-ui: no trace= (the verbs stay off)
            pass

    def _traced(self, s: "Sess", when: str, cmd: str = ""):
        """The session trace's hook around one command; a writer that fails stops writing (the session goes on)."""
        tr = getattr(s, "trace", None)
        sh = self.srv.shells.get(s.sid)
        if tr is None or sh is None:
            return
        try:
            tr.before(sh) if when == "before" else tr.after(sh, cmd)
        except Exception as e:                           # noqa: BLE001
            tr.close()
            s.trace = None
            print(f"session {s.sid}: the trace stopped: {e}", file=sys.stderr)

    async def stop(self, msg):
        """Interrupt the running command and drop the queued ones."""
        s = self.sessions.get(msg.get("session", ""))
        if not s:
            return
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
        for fut in s.futs.values():
            if not fut.done():
                fut.set_result({"status": "error", "result": "session closed",
                                "json": {"ok": False, "error": "closed"}})
        if s.worker:
            s.worker.cancel()
        if getattr(s, "trace", None) is not None:
            s.trace.close()
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
            await self.reopen(s, "idle")

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
                if ch in WS_CHANNELS:           # the workspace's (loop/workspace_ch.py)
                    await self.wsc.handle(ws, msg)
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
                elif typ in ("new", "gate", "edit"):    # the gate; the edit (records/sink: gone with their docks, loop-ui 2.4)
                    await self.files(ws, ip, msg)
                elif typ == "intent":
                    await self.intent(ws, msg)
                elif typ == "stop":
                    await self.stop(msg)
                elif typ == "files":                     # the EDITOR's reload: the session's files as on disk now
                    s = self.sessions.get(msg.get("session", ""))
                    if s and ws in s.subs:
                        await self._send(ws, dict(await self._files_frame(s), req=msg.get("req")))
                else:
                    await self._send(ws, {"ch": "repl", "type": "error",
                                          "error": f"unknown type {typ!r}"})
        finally:
            self.pages.discard(ws)
            self.wsc.drop(ws)
            for s in self.sessions.values():
                s.subs.discard(ws)

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
        if route.startswith(WS_WIDGET_URL):             # the workspace widgets, from the installed SDK: public code
            got = ws_widget_file(route[len(WS_WIDGET_URL):])
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
            wt = asyncio.create_task(self.wsc.watch())    # the bundle's STALE and the journal's tail
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
                wt.cancel()
                await self.wsc.close()
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
    ap.add_argument("--metis-agent", metavar="WS_URL",
                    help="metis-agent's console wire (ws://127.0.0.1:8395/ws): "
                         "the band shows the agent's state of the open domain "
                         "(personal mode)")
    ap.add_argument("--pkg", action="append", default=[], metavar="NAME",
                    help="open the package domains/NAME at the start (the catalog root's, else "
                         "METIS_HOME's): a page with no session opens it; repeatable, the panel "
                         "lists and opens the rest")
    argv = list(sys.argv[1:] if argv is None else argv)
    gone = [a for a in argv if a.split("=", 1)[0] in ("--brain", "--mock-agent")]
    if gone:                            # the retired seats' flags: said, not silently taken
        print(f"metis-loop: {gone[0].split('=', 1)[0]} is gone: {SEATS_GONE}", file=sys.stderr)
        return 2
    ns = ap.parse_args(argv)
    cfg = load_config(port=ns.port, bind=ns.bind, mode=ns.mode,
                      token=ns.token, metis_agent=ns.metis_agent)
    key_note = load_key_file()           # the REPLs' narrate over openrouter: the key into this process, never printed
    if key_note:
        print(f"[console] {key_note}", file=sys.stderr)
    if cfg["mode"] == "shared" and cfg["bind"] not in ("127.0.0.1",
                                                       "localhost") \
            and not cfg["token"]:
        print("console-serve: shared mode on a non-local bind without a "
              "token — anyone who can reach it can run catalogs.")
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
    if cfg["mode"] == "personal":       # one backend per workspace (WORKSPACE.md §2.3): its lock, or the holder's line
        try:
            gw.wsc.ws.lock("backend", port=int(cfg["port"]))
        except ValueError as e:
            print(f"console-serve: {e}", file=sys.stderr)
            return 2
    q = f"?token={cfg['token']}" if cfg["token"] else ""
    print(f"loop console ({cfg['mode']}): http://{cfg['bind']}:"
          f"{cfg['port']}/{q}", flush=True)
    print(f"catalog: {root}", flush=True)
    for p in cfg["pkg"]:
        print(f"--pkg: {p['name']} ({p['path']}): a page with no session opens "
              + ("it" if p is cfg["pkg"][0] else "the first; this one is the panel's"), flush=True)
    print("no brain here: the pi loop formalizes and rules (pi/loop.sh, the workspace's .metis/)", flush=True)
    if cfg["retired"]:
        print("[console] keys of the retired seats, ignored: " + ", ".join(cfg["retired"]), flush=True)
    import signal                       # run.sh stop's SIGTERM ends it as ^C does: the lock is released

    def _term(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _term)
    try:
        asyncio.run(gw.serve())
    except KeyboardInterrupt:
        pass
    finally:
        if cfg["mode"] == "personal":
            gw.wsc.ws.unlock("backend")
    return 0
