"""pi_rpc — the pi loop as the backend's child in RPC mode (docs/WORKSPACE.md §5.2; loop-workspace s-5b4be5fa
step 3, part C). The socket adaptor: pi's own `--mode rpc` (JSON lines on stdin and stdout), driven from the
gateway's asyncio loop. The gateway's `loop` channel owns the child's lifecycle and journals what comes out;
this module speaks the protocol and nothing else (pi's docs/rpc.md, rpc-commands.md, rpc-extension-ui.md,
json.md, pi 1.3.0).

    rpc = PiRpc([".../pi/loop.sh", "--mode", "rpc"], cwd=DIR, env=env)   # the 6G prefix is the caller's, in argv
    await rpc.start()                 # spawns, then waits for pi's first answer; raises with stderr's tail if it dies first
    await rpc.say("take the next surprise")                # the person's turn (queued as a follow-up while pi runs)
    async for ev in rpc.events():     # until {kind: "exit"}
        ...
    await rpc.answer(token, True)     # the person's confirm (the gate's plan), or False to refuse
    await rpc.stop()                  # abort, close stdin (pi's orderly shutdown), SIGTERM after a grace; idempotent
    rpc.pid                           # the child's pid (the pi lock's holder is pi itself, below loop.sh's exec)

The events, one dict each:
    {kind: "text", text}                              an assistant message's text (message_end, the authoritative one)
    {kind: "tool_call", id, name, args}               tool_execution_start
    {kind: "tool_result", id, name, ok, text}         tool_execution_end (ok: not isError; text: the result's text)
    {kind: "gate", token, plan: {title, message}}     an extension's confirm (the catalog's gate): answer(token, ok)
    {kind: "notify", level, text}                     an extension's notify (fire-and-forget)
    {kind: "usage", cost, model}                      an assistant message's cost as pi reports it (USD; 0 for a free one)
    {kind: "turn_end", aborted}                       agent_settled: pi will do nothing more until the next say
    {kind: "error", where, error}                     a refused command, or an extension's handler that threw
    {kind: "exit", code, stderr_tail}                 the child is gone; the iterator ends after it
A dialog other than confirm (select, input, editor) is answered `cancelled` at once and reported as a notify:
the loop's extensions ask nothing else, and a person at the console answers gates only.
Lines are split on LF only (rpc.md's framing: U+2028 inside a JSON string is not a record boundary)."""
import asyncio
import collections
import json
import os
import signal

READY_TIMEOUT = 60.0          # pi loads its extensions (and loop.sh checks the SDK) before it answers
STOP_GRACE = 5.0
TAIL = 40                     # stderr lines kept for an exit's tail


class PiRpcError(RuntimeError):
    pass


def _text(content):
    """The text of a message's or a tool result's content blocks."""
    if isinstance(content, str):
        return content
    return "".join(c.get("text", "") for c in (content or []) if isinstance(c, dict) and c.get("type") == "text")


class PiRpc:
    def __init__(self, argv, cwd=None, env=None):
        self.argv, self.cwd, self.env = list(argv), cwd, env
        self.proc = None
        self._queue = asyncio.Queue()
        self._stderr = collections.deque(maxlen=TAIL)
        self._pending = {}                # command id -> future of its response
        self._gates = set()               # confirm requests not answered yet
        self._n = 0
        self._tasks = []
        self._exited = None
        self._stopping = False

    @property
    def pid(self):
        return self.proc.pid if self.proc else None

    # ---- lifecycle ---------------------------------------------------------------------------------
    async def start(self):
        if self.proc:
            raise PiRpcError("started already")
        self.proc = await asyncio.create_subprocess_exec(
            *self.argv, cwd=self.cwd, env=self.env, limit=1 << 26,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self._exited = asyncio.get_running_loop().create_future()
        self._tasks = [asyncio.ensure_future(self._read_stdout()), asyncio.ensure_future(self._read_stderr())]
        ready = asyncio.ensure_future(self._command({"type": "get_state"}))
        done, _ = await asyncio.wait({ready, self._exited}, timeout=READY_TIMEOUT, return_when=asyncio.FIRST_COMPLETED)
        if ready not in done:
            ready.cancel()
            code = self._exited.result() if self._exited.done() else None
            if code is None:
                await self.stop()
            raise PiRpcError(f"pi did not answer ({'exit %s' % code if code is not None else 'no answer in %ss' % READY_TIMEOUT}): "
                             + " | ".join(self._stderr))
        r = ready.result()
        if self._exited.done():                       # it died first: its answer is the exit's, say why
            raise PiRpcError(f"pi did not answer (exit {self._exited.result()}): " + " | ".join(self._stderr))
        if not r.get("success"):
            await self.stop()
            raise PiRpcError(f"pi refused get_state: {r.get('error')}")
        self.state = r.get("data") or {}
        return self.state

    async def stop(self):
        """Abort what runs, close stdin (pi's orderly shutdown), SIGTERM after STOP_GRACE, SIGKILL after another."""
        if not self.proc or self._stopping:
            if self._exited is not None:
                await asyncio.shield(self._exited)
            return
        self._stopping = True
        if self.proc.returncode is None:
            try:
                self._write({"type": "abort"})
                self.proc.stdin.close()
            except (BrokenPipeError, ConnectionResetError, RuntimeError):
                pass
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    await asyncio.wait_for(asyncio.shield(self._exited), STOP_GRACE)
                    break
                except asyncio.TimeoutError:
                    try:
                        self.proc.send_signal(sig)
                    except ProcessLookupError:
                        break
        await asyncio.shield(self._exited)

    # ---- the person's side ---------------------------------------------------------------------------
    async def say(self, text):
        """The person's turn: a prompt, queued as a follow-up when pi is running (it is delivered when pi stops)."""
        r = await self._command({"type": "prompt", "message": str(text), "streamingBehavior": "followUp"})
        if not r.get("success"):
            raise PiRpcError(f"pi refused the turn: {r.get('error')}")
        return (r.get("data") or {}).get("disposition")

    async def answer(self, token, ok):
        """The person's answer to a gate (a confirm request): True confirms, False refuses."""
        if token not in self._gates:
            raise PiRpcError(f"no open gate {token!r}")
        self._gates.discard(token)
        self._write({"type": "extension_ui_response", "id": token, "confirmed": bool(ok)})

    async def events(self):
        while True:
            ev = await self._queue.get()
            yield ev
            if ev["kind"] == "exit":
                return

    # ---- the wire ------------------------------------------------------------------------------------
    def _write(self, rec):
        if not self.proc or self.proc.returncode is not None or self.proc.stdin.is_closing():
            raise PiRpcError("pi is not running")
        self.proc.stdin.write((json.dumps(rec) + "\n").encode())

    async def _command(self, rec):
        self._n += 1
        cid = "c%d" % self._n
        fut = asyncio.get_running_loop().create_future()
        self._pending[cid] = fut
        self._write(dict(rec, id=cid))
        await self.proc.stdin.drain()
        return await fut

    def _emit(self, **ev):
        self._queue.put_nowait(ev)

    async def _read_stderr(self):
        while True:
            line = await self.proc.stderr.readline()
            if not line:
                return
            self._stderr.append(line.decode(errors="replace").rstrip("\r\n"))

    async def _read_stdout(self):
        try:
            while True:
                line = await self.proc.stdout.readline()          # LF only
                if not line:
                    break
                s = line.decode(errors="replace").rstrip("\n").rstrip("\r")
                if not s.strip():
                    continue
                try:
                    rec = json.loads(s)
                except ValueError:
                    self._emit(kind="error", where="stdout", error=f"not a protocol record: {s[:200]}")
                    continue
                self._dispatch(rec)
        finally:
            code = await self.proc.wait()
            for t in self._tasks[1:]:
                await t
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result({"success": False, "error": f"pi exited ({code})"})
            self._pending.clear()
            self._emit(kind="exit", code=code, stderr_tail=list(self._stderr))
            if not self._exited.done():
                self._exited.set_result(code)

    def _dispatch(self, rec):
        t = rec.get("type")
        if t == "response":
            fut = self._pending.pop(rec.get("id"), None)
            if fut is not None and not fut.done():
                fut.set_result(rec)
            elif not rec.get("success"):
                self._emit(kind="error", where=rec.get("command") or "response", error=rec.get("error"))
            return
        if t == "message_end":
            m = rec.get("message") or {}
            if m.get("role") == "assistant":
                txt = _text(m.get("content"))
                if txt.strip():
                    self._emit(kind="text", text=txt)
                cost = ((m.get("usage") or {}).get("cost") or {}).get("total") or 0
                self._emit(kind="usage", cost=cost, model=m.get("model"))
            return
        if t == "tool_execution_start":
            self._emit(kind="tool_call", id=rec.get("toolCallId"), name=rec.get("toolName"), args=rec.get("args"))
            return
        if t == "tool_execution_end":
            self._emit(kind="tool_result", id=rec.get("toolCallId"), name=rec.get("toolName"),
                       ok=not rec.get("isError"), text=_text((rec.get("result") or {}).get("content")))
            return
        if t == "agent_settled":
            self._emit(kind="turn_end", aborted=bool(rec.get("aborted")))
            return
        if t == "extension_error":
            self._emit(kind="error", where=f"extension {os.path.basename(str(rec.get('extensionPath')))} {rec.get('event')}",
                       error=rec.get("error"))
            return
        if t == "extension_ui_request":
            m = rec.get("method")
            if m == "confirm":
                self._gates.add(rec["id"])
                self._emit(kind="gate", token=rec["id"], plan={"title": rec.get("title"), "message": rec.get("message")})
            elif m in ("select", "input", "editor"):
                self._write({"type": "extension_ui_response", "id": rec["id"], "cancelled": True})
                self._emit(kind="notify", level="warning", text=f"pi asked a {m} ({rec.get('title')}): answered cancelled")
            elif m == "notify":
                self._emit(kind="notify", level=rec.get("notifyType") or rec.get("level") or "info",
                           text=rec.get("message") or rec.get("title") or "")
            return
        # every other event (message_update deltas, turn and queue events, retries) is pi's own bookkeeping
