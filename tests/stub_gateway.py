"""A stub of the loop console's gateway (loop/gateway.py, docs/CONSOLE-WS.md)
for the console-nav hosts' tests (console-nav s-b923ebfe): a real websocket server on
an ephemeral port that speaks the frames a page speaks to, from memory, and records
every frame a client sends. No kernel, no model: a scripted console.

    gw = StubGateway(domains=["plant", "dog"]).start()     # gw.url: ws://127.0.0.1:PORT/ws
    ...                                                     # the host under test connects
    gw.received          # every frame a client sent, in order
    gw.stop()

The frames (the gateway's, as its module docstring lists them):

  on connect  meta/manifest {mode, seats, chat_unavailable}, meta/domains {domains},
              meta/readme {readme}, meta/catalogs {names} (the last of the greeting)
  repl/open {llp, req}          -> repl/session {session, req, llp, name, status, busy,
                                   running, queued} + repl/source {certified}; an
                                   unknown package -> repl/error {req, error}
  repl/open {session}           re-attach: the socket subscribes to the session (its
                                   session and source frames to it)
  repl/intent {session, id, cmd, actor}
                                -> repl/queued, then repl/posting {status, result, json}
                                   (status done | error | refused; `script` decides)
  repl/stop {session}           -> repl/session (busy false)
  repl/records                  -> meta/records {records}
  repl/save {session}           -> repl/save {files, token} (the plan: the page shows its
                                   APPLY dialog); with a token it would write — the stub
                                   records it as `written` so a test can assert it never is
  chat/say {session, text}      -> chat/user, chat/done (the agent seat), or chat/error
                                   "agent chat unavailable here: needs claude …" when
                                   chat=False (a brain without the seat, brain-choice)

As the gateway: queued, posting, session (after stop) and the chat's user/done frames go
to every socket subscribed to the session; a save plan and a chat error go to the socket
that asked only.

`script(cmd, session) -> (status, result) | None` answers an intent; None is the
default ("done", "ok"). `push(frame)` sends a frame to every connected client (the
console's own broadcasts: a session frame going busy, the person's own command)."""
import asyncio
import json
import threading

try:
    from websockets.asyncio.server import serve
except ImportError:                     # the tests importorskip websockets
    serve = None


class StubGateway:
    def __init__(self, domains=("plant",), records=(), chat=True, script=None, readme=None, token=""):
        self.domains = [d if isinstance(d, dict) else {"name": d, "line": f"the {d}", "kind": "domain",
                                                       "path": f"domains/{d}/{d}"} for d in domains]
        self.records, self.chat, self.script = list(records), chat, script
        self.readme, self.token = readme, token
        self.received, self.written = [], []
        self.sessions = {}              # sid -> {"llp", "name", "busy", "subs"}
        self.clients = set()
        self._n = 0

    # -- the frames ------------------------------------------------------

    def manifest(self):
        return {"ch": "meta", "type": "manifest", "mode": "personal",
                "chat_unavailable": None if self.chat else "needs claude (the brain is openrouter: --brain claude)",
                "seats": {"repl": True, "chat": "agent" if self.chat else None,
                          "narrate": "stub", "formalize": "stub"}}

    def session_frame(self, sid, **extra):
        s = self.sessions[sid]
        return {"ch": "repl", "type": "session", "session": sid, "llp": s["llp"], "name": s["name"],
                "status": "open", "busy": s["busy"], "running": None, "queued": 0, **extra}

    def _name(self, llp):
        stem = str(llp).rstrip("/").split("/")[-1].removesuffix(".llp")
        return stem if any(d["name"] == stem for d in self.domains) else None

    async def handle(self, ws, msg):
        """[(frame, to)]: to = "me" (the socket that asked) or "subs" (the session's subscribers)."""
        return [(f, "me") if not isinstance(f, tuple) else f for f in self._handle(ws, msg)]

    def _handle(self, ws, msg):
        ch, typ = msg.get("ch"), msg.get("type")
        if ch == "chat":
            sid = msg.get("session", "")
            if not self.chat:
                return [{"ch": "chat", "type": "error", "session": sid,
                         "error": "agent chat unavailable here: needs claude (the brain is openrouter: --brain claude)"}]
            if sid not in self.sessions:
                return [{"ch": "chat", "type": "error", "session": sid, "error": "open a session first"}]
            return [({"ch": "chat", "session": sid, "type": "user", "text": msg.get("text", "")}, "subs"),
                    ({"ch": "chat", "session": sid, "type": "done", "text": "(stub) I read it.", "error": None}, "subs")]
        if ch != "repl":
            return [{"ch": "meta", "type": "error", "error": f"unknown channel {ch!r}"}]
        if typ == "open" and msg.get("session"):                  # re-attach
            sid = msg["session"]
            if sid not in self.sessions:
                return [{"ch": "repl", "type": "error", "session": sid, "error": "gone"}]
            self.sessions[sid]["subs"].add(ws)
            return [self.session_frame(sid, req=msg.get("req"))]
        if typ == "open":
            name = self._name(msg.get("llp", ""))
            if not name:
                return [{"ch": "repl", "type": "error", "req": msg.get("req"),
                         "error": f"no such catalog file: {msg.get('llp')!r}"}]
            self._n += 1
            sid = f"w{self._n}"
            self.sessions[sid] = {"llp": msg.get("llp"), "name": name, "busy": False, "subs": {ws}}
            return [self.session_frame(sid, req=msg.get("req")),
                    {"ch": "repl", "type": "source", "session": sid, "name": name,
                     "copy": "", "extensions": [], "certified": "checkout", "error": None, "key": "k"}]
        if typ == "records":
            return [{"ch": "meta", "type": "records", "records": self.records}]
        sid = msg.get("session", "")
        if sid not in self.sessions:
            return [{"ch": "repl", "type": "error", "session": sid, "id": msg.get("id"), "error": "gone"}]
        if typ == "intent":
            item = {"id": msg.get("id"), "cmd": msg.get("cmd"), "actor": msg.get("actor", "viewer"), "ts": "t"}
            got = self.script(msg.get("cmd", ""), sid) if self.script else None
            status, result = got or ("done", "ok")
            return [({"ch": "repl", "type": "queued", "session": sid, **item}, "subs"),
                    ({"ch": "repl", "type": "posting", "session": sid, **item, "status": status,
                      "result": result, "json": {"ok": status == "done"}}, "subs")]
        if typ == "stop":
            self.sessions[sid]["busy"] = False
            return [(self.session_frame(sid), "subs")]
        if typ == "save":
            if ws not in self.sessions[sid]["subs"]:
                return [{"ch": "repl", "type": "error", "session": sid, "error": "no open session"}]
            if msg.get("token"):
                self.written.append(msg)
                return [{"ch": "repl", "type": "save", "session": sid, "files": [], "written": True}]
            return [{"ch": "repl", "type": "save", "session": sid, "token": "plan-1",
                     "files": [{"path": f"domains/{self.sessions[sid]['name']}/x.llp", "new": False,
                                "diff": "(stub diff)"}]}]
        return [{"ch": "repl", "type": "error", "error": f"unknown type {typ!r}"}]

    # -- the socket --------------------------------------------------------

    async def _handler(self, ws):
        self.clients.add(ws)
        try:
            for f in (self.manifest(), {"ch": "meta", "type": "domains", "domains": self.domains},
                      {"ch": "meta", "type": "readme", "readme": self.readme},
                      {"ch": "meta", "type": "catalogs", "names": [d["name"] for d in self.domains]}):
                await ws.send(json.dumps(f))
            async for raw in ws:
                msg = json.loads(raw)
                self.received.append(msg)
                for f, to in await self.handle(ws, msg):
                    sid = f.get("session")
                    targets = (self.sessions[sid]["subs"] if to == "subs" and sid in self.sessions else {ws})
                    for t in list(targets):
                        await t.send(json.dumps(f))
        finally:
            self.clients.discard(ws)

    def push(self, frame):
        """Send a frame to every client (the console's own broadcast)."""
        async def go():
            for ws in list(self.clients):
                await ws.send(json.dumps(frame))
        asyncio.run_coroutine_threadsafe(go(), self.loop).result(5)

    def start(self):
        ready = threading.Event()
        self.loop = asyncio.new_event_loop()

        def run():
            asyncio.set_event_loop(self.loop)

            async def main():
                self._stop = asyncio.Event()
                async with serve(self._handler, "127.0.0.1", 0) as server:
                    self.port = server.sockets[0].getsockname()[1]
                    ready.set()
                    await self._stop.wait()
            self.loop.run_until_complete(main())
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert ready.wait(10), "the stub gateway did not start"
        self.url = f"ws://127.0.0.1:{self.port}/ws" + (f"?token={self.token}" if self.token else "")
        return self

    def stop(self):
        self.loop.call_soon_threadsafe(self._stop.set)
        self.thread.join(10)
        self.loop.close()
