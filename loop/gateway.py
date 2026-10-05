"""The console gateway (docs/CONSOLE-WS.md §1, §2, §4, §7): a standing
backend for the Loop Console — plain `websockets` + stdlib-shaped HTTP
on ONE port (D1), grown from console/dev_serve.py.

    GET /            the page (loop_console.html) with the gateway flag
    GET /healthz     liveness
    WS  /ws          one multiplexed socket per browser window

Frames (JSON, one per message):

    page -> gw   {ch:"repl", type:"open",   llp, req}      new session
                 {ch:"repl", type:"open",   source, name, req}  from catalog
                                          TEXT, compiled in memory (§4a)
                 {ch:"repl", type:"open",   session}       re-attach
                 {ch:"repl", type:"intent", session, id, cmd, actor}
                 {ch:"repl", type:"stop",   session}
                 {ch:"repl", type:"close",  session}
                 {ch:"chat", ...}                          (step 2)
    gw -> page   {ch:"meta", type:"manifest", ...}  {ch:"meta", type:"catalogs", names}
                 {ch:"repl", type:"session", session, req?, …fields, busy, running, queued}
                 {ch:"repl", type:"queued",  session, id, cmd, actor, ts}
                 {ch:"repl", type:"posting", session, id, cmd, actor, ts, …intent_posting}
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

DEFAULTS = {
    "port": 8770, "bind": "127.0.0.1", "mode": "personal", "token": "",
    "max_sessions": 16, "max_sessions_per_ip": 4, "max_run_steps": 500,
    "idle_secs": 1800, "rate_per_min": 120, "history": 300,
    "artifact_url": "",
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


def manifest(cfg: dict) -> dict:
    """What this instance serves — the page renders only these (§4)."""
    shared = cfg["mode"] == "shared"
    return {
        "mode": cfg["mode"],
        "seats": {
            "repl": True,
            "chat": None if shared else "pending",       # step 2: agent
            "narrate": None if shared else "llm",        # step 3: Haiku
            "formalize": None if shared else "llm",
        },
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


class Gateway:
    def __init__(self, cfg: dict, srv: Optional[ConsoleServer] = None):
        self.cfg = cfg
        self.srv = srv or ConsoleServer()
        self.sessions: Dict[str, Sess] = {}
        self.rates: Dict[object, deque] = {}

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
        spec = ({"source": msg["source"], "name": msg.get("name")}
                if msg.get("source") is not None else {"llp": llp})
        fields = await loop.run_in_executor(
            None, self.srv.open_session, sid, spec)
        if fields.get("status") == "closed":
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "req": msg.get("req"),
                                         "error": fields.get("error",
                                                             "cannot open")})
        s = Sess(sid, fields.get("llp", llp), ip, cap["history"])
        s.spec = spec                    # what idle recycling re-opens
        s.subs.add(ws)
        s.worker = asyncio.create_task(self._work(s))
        self.sessions[sid] = s
        await self._send(ws, self._session_frame(s, req=msg.get("req")))

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
        return cmd, None

    async def intent(self, ws, msg):
        s = self.sessions.get(msg.get("session", ""))
        iid = str(msg.get("id") or secrets.token_hex(6))
        if not s:
            return await self._send(ws, {"ch": "repl", "type": "error",
                                         "id": iid, "error": "gone"})
        cmd = str(msg.get("cmd") or "").strip()
        cmd = cmd if cmd.startswith(":") else ":" + cmd
        actor = str(msg.get("actor") or "viewer")[:40]
        item = {"id": iid, "cmd": cmd, "actor": actor, "ts": _now()}
        s.last = time.time()
        await self._broadcast(s, {"ch": "repl", "type": "queued",
                                  "session": s.sid, **item}, log=True)
        refusal = self._gate(cmd)
        if refusal:
            return await self._broadcast(s, {
                "ch": "repl", "type": "posting", "session": s.sid, **item,
                "status": "refused", "result": refusal,
                "json": {"ok": False, "error": refusal},
                "epoch": self.srv.epochs.get(s.sid)}, log=True)
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
            await self._broadcast(s, self._session_frame(s))

    async def stop(self, msg):
        """Interrupt the running command and drop the queued ones."""
        s = self.sessions.get(msg.get("session", ""))
        if not s:
            return
        while not s.queue.empty():
            item = s.queue.get_nowait()
            await self._broadcast(s, {
                "ch": "repl", "type": "posting", "session": s.sid, **item,
                "status": "error", "result": "cancelled (stop)",
                "json": {"ok": False, "error": "cancelled"},
                "epoch": self.srv.epochs.get(s.sid)}, log=True)
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
                    await self._send(ws, {
                        "ch": "chat", "type": "error",
                        "error": "chat is not served on this instance"
                        if self.cfg["mode"] == "shared" else
                        "agent chat arrives with step 2 (CONSOLE-WS §3)"})
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
                elif typ == "intent":
                    await self.intent(ws, msg)
                elif typ == "stop":
                    await self.stop(msg)
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
    q = f"?token={cfg['token']}" if cfg["token"] else ""
    print(f"loop console ({cfg['mode']}): http://{cfg['bind']}:"
          f"{cfg['port']}/{q}", flush=True)
    try:
        asyncio.run(gw.serve())
    except KeyboardInterrupt:
        pass
    return 0
