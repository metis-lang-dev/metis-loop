"""repl's host (console-nav s-b923ebfe): a websocket client of the loop console's gateway
(metis-loop loop/gateway.py, docs/CONSOLE-WS.md). A fired rule's event is the frame the
page would send; the gateway's answers come back, at the next tick, as the reports the
program waits for (README.md has the table). Copies, not deps: it speaks the wire through
a small stdlib websocket client (no metis-loop import, no websockets package), so it runs
in the domain agent's own venv.

  on_event              the frame sent                          the report at a later tick
  load, load_switch     repl/open {llp, host} (the package from  +opened (the session frame for
                        the payload, found in meta/domains)      that request) | +absent
  run, step             repl/intent ":run N" (N: the payload's  +stopped (posting done) |
                        n, default RUN_N) | ":step"              +run_refused (refused, error)
  undo, reset           repl/intent ":undo" | ":reset"          — (the rule is done already)
  narrate               repl/intent ":narrate"                  +narrated | +narrate_refused
  records               repl/records                            —
  apply                 repl/save with NO token (the plan)      +plan_shown (files) |
                                                                +nothing_to_apply (none)
  stop_*                repl/stop                               —
  tell                  chat/say {text: the payload's text}     +told (the chat's user frame)
                                                                | +tell_refused (chat error)

The pairs the console keeps and the program cannot see change by itself go in as world
lines at the tick: the working copy (source.certified: checkout → clean, else dirty) and
the brain's chat seat (manifest seats.chat → chat_seat | no_chat_seat). The outcome tokens
of the last beat are retracted (the domain agent has read them), as dog_host does.

The sensor face: observe() reads the console's session (loaded | unloaded) when no
request is in flight. A reading the rules did not produce is the watch's surprise: the
person opened or closed a session on the page itself, or the console kept one the program
says it closed.

The payload (the intent's slots the atoms do not carry: package, n, text) rides with the
event that consumes the command: the domain agent hands it over with take_payload(p)
before on_event (metis-agent AgentHost). The page's session: a session this host opens
is its own websocket's, so the page shows it once it attaches (`effects`: {"repl":
"attach", "session": sid} for the page, step 2); attach(sid) adopts the page's session.

  METIS_LOOP_WS       the gateway's socket (default ws://127.0.0.1:8770/ws; ?token=… as the URL has it)
  METIS_LOOP_SESSION  the page's session to attach to at the start (optional)
PURITY: the world changes only in tick/on_event/attach; snapshot is total."""
import base64
import json
import os
import queue
import secrets
import socket
import struct
import threading
import urllib.parse

OUTCOMES = ("done", "refused", "progress")
WAITS = ()                  # no wait ends by itself: every task ends by the gateway's answer
RUN_N = 50                  # a run with no count (README: "default 50"); the gateway caps it
URL = "ws://127.0.0.1:8770/ws"
UNSEEN = "unseen"           # no source frame for the session yet


class Wire:
    """A websocket client (RFC 6455), stdlib only: text frames out (masked), text frames in
    (fragments joined, pings answered, close honoured). recv() blocks; None when closed."""

    def __init__(self, url, timeout=10):
        u = urllib.parse.urlparse(url)
        if u.scheme != "ws":
            raise ValueError(f"{url}: a ws:// URL (the console is local)")
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port or 80}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError(f"{url}: closed during the handshake")
            head += chunk
        head, self.buf = head.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0].decode(errors="replace")
        if " 101 " not in status + " ":
            raise ConnectionError(f"{url}: {status}")
        self.sock.settimeout(None)
        self.lock = threading.Lock()

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _frame(self, op, data):
        mask = secrets.token_bytes(4)
        n = len(data)
        head = bytes([0x80 | op]) + (bytes([0x80 | n]) if n < 126 else
                                     bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else
                                     bytes([0x80 | 127]) + struct.pack(">Q", n))
        with self.lock:
            self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def send(self, obj):
        self._frame(0x1, json.dumps(obj).encode())

    def recv(self):
        parts = []
        while True:
            try:
                b0, b1 = self._read(2)
            except (ConnectionError, OSError):
                return None
            op, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if op == 0x8:                                   # close
                try:
                    self._frame(0x8, data[:2])
                except OSError:
                    pass
                return None
            if op == 0x9:                                   # ping
                self._frame(0xA, data)
                continue
            if op == 0xA:
                continue
            parts.append(data)
            if b0 & 0x80:                                   # FIN: the message is whole
                return json.loads(b"".join(parts).decode())

    def close(self):
        try:
            self._frame(0x8, struct.pack(">H", 1000))
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def _norm(name):
    s = " ".join(str(name or "").lower().replace("-", " ").replace("_", " ").split())
    for article in ("the ", "a ", "an "):
        if s.startswith(article):
            s = s[len(article):]
    return s.replace(" ", "_")


class ReplHost:
    def __init__(self, case=None, url=None):
        self.url = url or os.environ.get("METIS_LOOP_WS") or URL
        self.beat, self.due, self.script, self.last = 0, (), {}, None     # AgentHost's hosted-day fields
        self.wire, self.frames = None, queue.Queue()
        self.sid = None
        self.domains = {}           # name -> the meta/domains row (path, host)
        self.certified = UNSEEN     # the session's source.certified (None: edited, uncertified)
        self.chat_ok = None         # the manifest's chat seat (None: not seen yet)
        self.pending = {}           # request id -> the task it answers (load, run, narrate, apply, tell)
        self.reports = []           # do-lines for the next tick
        self.payload = {}
        self.acted = ()             # (beat, event, frame type) — the journal
        self.effects = []           # for the page: {"repl": "attach", "session": sid}
        self.error = None           # the last wire failure, said in the refusal's place
        self._n = 0
        self._attach = os.environ.get("METIS_LOOP_SESSION") or None

    # -- the wire ----------------------------------------------------------

    def connect(self):
        if self.wire is not None:
            return True
        try:
            self.wire = Wire(self.url)
            self.wire.sock.settimeout(10)
            while True:                     # the greeting: manifest, domains, readme, then catalogs
                f = self.wire.recv()
                if f is None:
                    raise ConnectionError("closed during the greeting")
                self._frame_in(f)
                if f.get("type") == "catalogs":
                    break
            self.wire.sock.settimeout(None)
        except (OSError, ValueError, ConnectionError) as e:
            self.wire, self.error = None, f"the loop console at {self.url} did not answer: {e}"
            return False
        threading.Thread(target=self._reader, args=(self.wire,), daemon=True).start()
        if self._attach:
            self.attach(self._attach)
        return True

    def _reader(self, wire):
        while True:
            f = wire.recv()
            if f is None:
                self.frames.put({"ch": "meta", "type": "closed"})
                return
            self.frames.put(f)

    def _send(self, frame):
        self.wire.send(frame)

    def _id(self, kind):
        self._n += 1
        return f"nav-{kind}-{self._n}"

    def attach(self, sid):
        """Adopt the page's session (the page names it): the program learns it at the next tick."""
        self.sid, self._attach = sid, None
        if self.wire is not None:
            self._send({"ch": "repl", "type": "open", "session": sid})
            self.reports += ["-unloaded", "+loaded", "+fresh", "+clean"]

    def close(self):
        """The wire closed (the domain agent's end, a test's)."""
        if self.wire is not None:
            self.wire.close()
            self.wire = None

    def take_payload(self, payload):
        self.payload = dict(payload or {})

    # -- the frames back -------------------------------------------------

    def _drain(self):
        while True:
            try:
                f = self.frames.get_nowait()
            except queue.Empty:
                return
            self._frame_in(f)

    def _report(self, kind, ok):
        on = {"load": ("+opened", "+absent"), "run": ("+stopped", "+run_refused"),
              "narrate": ("+narrated", "+narrate_refused"), "apply": ("+plan_shown", "+nothing_to_apply"),
              "tell": ("+told", "+tell_refused")}
        if kind in on:
            self.reports.append(on[kind][0 if ok else 1])

    def _frame_in(self, f):
        ch, typ = f.get("ch"), f.get("type")
        if ch == "meta" and typ == "manifest":
            self.chat_ok = (f.get("seats") or {}).get("chat") is not None
        elif ch == "meta" and typ == "domains":
            self.domains = {_norm(d.get("name")): d for d in f.get("domains") or [] if d.get("name")}
        elif ch == "meta" and typ == "closed":
            self.wire, self.error = None, "the loop console closed the connection"
            for kind in self.pending.values():
                self._report(kind, False)
            self.pending = {}
        elif ch == "repl" and typ == "session" and f.get("req") in self.pending:
            self.pending.pop(f["req"])
            self.sid = f.get("session")
            self.effects.append({"repl": "attach", "session": self.sid})
            self._report("load", True)
        elif ch == "repl" and typ == "error" and f.get("req") in self.pending:
            self.pending.pop(f["req"])
            self.error = f.get("error")
            self._report("load", False)
        elif ch == "repl" and typ == "source" and f.get("session") == self.sid:
            self.certified = f.get("certified")
        elif ch == "repl" and typ == "posting" and f.get("id") in self.pending:
            self._report(self.pending.pop(f["id"]), f.get("status") == "done")
        elif ch == "repl" and typ == "save" and "apply" in self.pending.values() and not f.get("written"):
            self.pending = {k: v for k, v in self.pending.items() if v != "apply"}
            self._report("apply", bool(f.get("files")))
        elif ch == "chat" and f.get("session") == self.sid and "tell" in self.pending.values() \
                and typ in ("user", "error"):
            self.pending = {k: v for k, v in self.pending.items() if v != "tell"}
            if typ == "error":
                self.error = f.get("error")
            self._report("tell", typ == "user")

    # -- the plugin faces ----------------------------------------------------

    def bind(self, reg):
        pass                    # no weight ports: the console's answers are the reports

    def tick(self, counts):
        if self.last is not None and self.beat >= self.last:
            return None
        self.beat += 1
        self.connect()
        self._drain()
        dos = [f"-{a} {n}" for a, n in sorted(counts.items()) if n and a.split("(")[0] in OUTCOMES]
        dos += [d for b, d in self.due if b == self.beat]
        self.due = tuple(x for x in self.due if x[0] != self.beat)
        dos += self.reports
        self.reports = []
        if self.sid and self.certified != UNSEEN:       # the working copy, as the console has it
            dirty = self.certified != "checkout"
            if dirty and counts.get("clean"):
                dos += ["-clean", "+dirty"]
            elif not dirty and counts.get("dirty"):
                dos += ["-dirty", "+clean"]
        if self.chat_ok is False and counts.get("chat_seat"):
            dos += ["-chat_seat", "+no_chat_seat"]
        elif self.chat_ok and counts.get("no_chat_seat"):
            dos += ["-no_chat_seat", "+chat_seat"]
        return dos + self.script.get(self.beat, [])

    def on_event(self, name, args):
        base = name.split("[")[0].split("-")[0]
        p, self.payload = self.payload, {}
        frame = None
        if self.connect():
            self._drain()                   # the console as it is now (its domains, the session)
        if self.wire is None:
            frame = None
        elif base in ("load", "load_switch"):
            want = _norm(p.get("package"))
            row = self.domains.get(want)
            if row is None:
                self.error = f"no package {p.get('package')!r} in this catalog"
                self.reports.append("+absent")
            else:
                req = self._id("load")
                frame = {"ch": "repl", "type": "open", "llp": row.get("path") or row["name"],
                         "host": bool(row.get("host")), "req": req}
                self.pending[req] = "load"
        elif base in ("run", "step", "narrate", "undo", "reset"):
            n = p.get("n")
            cmd = {"run": f":run {int(n) if isinstance(n, (int, float)) and n >= 1 else RUN_N}",
                   "step": ":step", "narrate": ":narrate", "undo": ":undo", "reset": ":reset"}[base]
            if not self.sid:
                self._report("narrate" if base == "narrate" else "run", False)
            else:
                iid = self._id(base)
                frame = {"ch": "repl", "type": "intent", "session": self.sid, "id": iid, "cmd": cmd, "actor": "nav"}
                if base in ("run", "step", "narrate"):
                    self.pending[iid] = "narrate" if base == "narrate" else "run"
        elif base == "records":
            frame = {"ch": "repl", "type": "records"}
        elif base == "apply":
            if not self.sid:
                self._report("apply", False)
            else:
                frame = {"ch": "repl", "type": "save", "session": self.sid}     # NO token: the plan only
                self.pending[self._id("apply")] = "apply"
        elif base.startswith("stop") and self.sid:
            frame = {"ch": "repl", "type": "stop", "session": self.sid}
            self.pending = {k: v for k, v in self.pending.items() if v not in ("run", "narrate")}
        elif base == "tell":
            text = str(p.get("text") or "").strip()
            if not (self.sid and text):
                self._report("tell", False)
            else:
                frame = {"ch": "chat", "type": "say", "session": self.sid, "text": text}
                self.pending[self._id("tell")] = "tell"
        if frame is not None:
            self._send(frame)
            self.acted += ((self.beat, name, frame["type"]),)
        elif base in ("load", "load_switch", "run", "step", "narrate", "apply", "tell") and self.wire is None:
            # no console: the task ends as the console would refuse it
            self._report({"load_switch": "load", "step": "run"}.get(base, base), False)

    def observe(self, counts):
        if self.pending or self.wire is None:
            return {}               # a request in flight: the console's answer is not in yet
        return {"loaded": 1 if self.sid else 0, "unloaded": 0 if self.sid else 1}

    def snapshot(self):
        return [self.beat, list(self.due), list(self.acted), self.sid, self.certified, self.chat_ok,
                dict(self.pending), list(self.reports)]

    def restore(self, snap):
        beat, due, acted, self.sid, self.certified, self.chat_ok, pending, reports = snap
        self.beat, self.due = beat, tuple((b, d) for b, d in due)
        self.acted = tuple((b, n, t) for b, n, t in acted)
        self.pending, self.reports = dict(pending), list(reports)


def make(case):
    return ReplHost(case)
