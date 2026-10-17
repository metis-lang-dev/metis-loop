"""The claude adapter's chat face (brief/repo-alignment.md §3b, face 3): a
local OpenAI-compatible `/v1/chat/completions` over the seat face, the tool
calls emulated (claude.JsonLines). A client that speaks the OpenAI chat API
— pi's `openai-completions` provider — then reaches Claude as an ordinary
provider: no API key (the operator's `claude` login), no client-side
adapter, no OAuth path in the client.

    python -m metis_loop_sdk.models claude-chat [--port 8799] [--model sonnet]

    pi's models.json:  "claude": {"baseUrl": "http://127.0.0.1:8799/v1",
                                  "api": "openai-completions", "apiKey": "local",
                                  "models": [{"id": "sonnet"}]}

How a request maps onto the seat. The client sends the whole conversation
every turn. The endpoint keeps one claude session per conversation, keyed
by the conversation up to its own last reply: when a request extends a
conversation it answered (the new messages after its reply are tool results
and/or the person's words), the seat resumes that session with them;
anything else starts a new session, the history rendered as its first
message. The system prompt (the client's, plus the protocol and the
declarations) goes with every turn, so tools that appear mid-conversation
reach the model at its next turn.

One call per reply: the model calls one tool, reads its result, then
decides (a batch would run in parallel in pi). A call to an unknown tool,
or whose JSON does not parse, is sent back to the model once to write
again. Requests stream (SSE) when they ask to, as pi's do. Loopback only:
the endpoint speaks with the operator's login."""
import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from .claude import JsonLines, Seat

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
MAX_CONVERSATIONS = 64


def _text(content) -> str:
    """An OpenAI message's content (a string or a list of parts) as text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in ("text", "input_text"))


def _calls(m) -> list:
    out = []
    for c in m.get("tool_calls") or []:
        f = c.get("function") or {}
        try:
            args = json.loads(f.get("arguments") or "{}")
        except ValueError:
            args = f.get("arguments")
        out.append((c.get("id"), f.get("name"), args))
    return out


def _canon(messages) -> list:
    """The conversation without the system turns, in a form that survives
    the client's re-serialization (text stripped, arguments as parsed)."""
    out = []
    for m in messages:
        role = m.get("role")
        if role in ("system", "developer"):
            continue
        if role == "assistant":
            out.append(["a", _text(m.get("content")).strip(), _calls(m)])
        elif role == "tool":
            out.append(["t", m.get("tool_call_id"), _text(m.get("content")).strip()])
        else:
            out.append(["u", _text(m.get("content")).strip()])
    return out


def _key(canon) -> str:
    return hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _tool_names(canon) -> dict:
    return {cid: name for e in canon if e[0] == "a" for cid, name, _ in e[2]}


def _render_new(canon, names) -> str:
    """The messages after the endpoint's last reply, as the next user turn."""
    parts = []
    for e in canon:
        if e[0] == "t":
            parts.append("The result of %s:\n%s" % (names.get(e[1], "the tool"), e[2]))
        elif e[0] == "u":
            parts.append(e[1])
    return "\n\n".join(parts)


def _render_history(canon, names) -> str:
    """A conversation the endpoint did not hold, as one first message."""
    if all(e[0] == "u" for e in canon):
        return "\n\n".join(e[1] for e in canon)
    lines = ["(The conversation so far, for context; continue it from its last message.)"]
    for e in canon:
        if e[0] == "u":
            lines.append("[the person]\n" + e[1])
        elif e[0] == "a":
            said = e[1]
            for _, name, args in e[2]:
                said += ("\n" if said else "") + "CALL: %s %s" % (name, json.dumps(args, ensure_ascii=False))
            lines.append("[you]\n" + said)
        else:
            lines.append("[the result of %s]\n%s" % (names.get(e[1], "the tool"), e[2]))
    return "\n\n".join(lines)


class Endpoint:
    """The request → reply mapping, without HTTP (the server's handler and
    the tests drive it). seat_factory(model) → a Seat with the JSON protocol."""

    def __init__(self, model: str = "sonnet", effort: str = "", seat_factory: Optional[Callable] = None,
                 log: Optional[Callable] = None):
        self.model, self.effort = model, effort
        self.seat_factory = seat_factory or (lambda m: Seat(model=m, effort=self.effort, protocol=JsonLines))
        self.conversations = OrderedDict()      # key of the canon up to our reply -> seat
        self.lock = threading.Lock()
        self.log = log or (lambda rec: None)

    def _model(self, requested: Optional[str]) -> str:
        return requested or self.model

    def complete(self, body: dict) -> dict:
        """One chat completion: {"content", "tool_call": (id, name, args) | None,
        "finish_reason", "usage", "model"}."""
        messages = body.get("messages") or []
        system = "\n\n".join(_text(m.get("content")) for m in messages if m.get("role") in ("system", "developer"))
        tools = [t.get("function") or t.get("custom") or {} for t in body.get("tools") or []
                 if t.get("type") in ("function", "custom", None)]
        known = {t.get("name") for t in tools}
        canon = _canon(messages)
        names = _tool_names(canon)
        last_a = max((i for i, e in enumerate(canon) if e[0] == "a"), default=-1)
        with self.lock:
            seat = self.conversations.pop(_key(canon[:last_a + 1]), None) if last_a >= 0 else None
        if seat is not None:
            prompt, first = _render_new(canon[last_a + 1:], names), False
        else:
            seat = self.seat_factory(self._model(body.get("model")))
            prompt, first = _render_history(canon, names), True
        t0 = time.perf_counter()
        r = seat.ask(system, tools, prompt, first=first)
        retried = False
        if r.call is not None and (r.call[0] not in known or r.call[1] is None):
            why = ("there is no tool %r" % r.call[0]) if r.call[0] not in known else "its arguments are not one JSON object"
            retried = True
            r = seat.ask(system, tools, "That CALL: line cannot be run: %s. The tools are: %s. Write the call again, "
                         "or answer without one." % (why, ", ".join(sorted(n for n in known if n))), first=False)
        if r.call is not None and r.call[0] in known and r.call[1] is not None:
            tool, args, said = r.call
            call = ("call_" + uuid.uuid4().hex[:12], tool, args)
            content, finish = said, "tool_calls"
        else:
            call, content, finish = None, r.text.strip(), "stop"
        reply = ["a", (content or "").strip(), [call] if call else []]
        with self.lock:
            self.conversations[_key(canon + [reply])] = seat
            while len(self.conversations) > MAX_CONVERSATIONS:
                self.conversations.popitem(last=False)
        u = seat.usage
        usage = {"prompt_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                 + u.get("cache_creation_input_tokens", 0),
                 "completion_tokens": u.get("output_tokens", 0),
                 "prompt_tokens_details": {"cached_tokens": u.get("cache_read_input_tokens", 0)}}
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        self.log({"session": seat.session, "resumed": not first, "retried": retried, "tool": call[1] if call else None,
                  "ms": round((time.perf_counter() - t0) * 1e3), "model": seat.model_id or seat.model})
        return {"content": content, "tool_call": call, "finish_reason": finish, "usage": usage,
                "model": seat.model_id or seat.model}

    # -- the OpenAI shapes -------------------------------------------------

    @staticmethod
    def message(r: dict) -> dict:
        m = {"role": "assistant", "content": r["content"] or None}
        if r["tool_call"]:
            cid, name, args = r["tool_call"]
            m["tool_calls"] = [{"id": cid, "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]
        return m

    @classmethod
    def completion(cls, r: dict, rid: str) -> dict:
        return {"id": rid, "object": "chat.completion", "created": int(time.time()), "model": r["model"],
                "choices": [{"index": 0, "message": cls.message(r), "finish_reason": r["finish_reason"]}],
                "usage": r["usage"]}

    @staticmethod
    def chunks(r: dict, rid: str, usage: bool = True) -> list:
        base = {"id": rid, "object": "chat.completion.chunk", "created": int(time.time()), "model": r["model"]}
        out = [dict(base, choices=[{"index": 0, "delta": {"role": "assistant", "content": r["content"] or ""},
                                    "finish_reason": None}])]
        if r["tool_call"]:
            cid, name, args = r["tool_call"]
            out.append(dict(base, choices=[{"index": 0, "finish_reason": None, "delta": {"tool_calls": [
                {"index": 0, "id": cid, "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}}]))
        out.append(dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": r["finish_reason"]}]))
        if usage:
            out.append(dict(base, choices=[], usage=r["usage"]))
        return out


def serve(endpoint: Endpoint, port: int = 8799, bind: str = "127.0.0.1", ready: Optional[Callable] = None):
    """Serve the endpoint until interrupted (loopback only)."""
    if bind not in LOOPBACK:
        raise ValueError("the chat endpoint speaks with the operator's login: loopback only, not %r" % bind)

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path.rstrip("/") in ("/v1/models", "/models"):
                return self._json(200, {"object": "list", "data": [{"id": endpoint.model, "object": "model",
                                                                    "owned_by": "claude -p"}]})
            self._json(404, {"error": {"message": "not found"}})

        def do_POST(self):
            if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
                return self._json(404, {"error": {"message": "not found"}})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
                r = endpoint.complete(body)
            except Exception as e:                              # noqa: BLE001
                return self._json(500, {"error": {"message": "%s: %s" % (type(e).__name__, e), "type": "server_error"}})
            rid = "chatcmpl-" + uuid.uuid4().hex[:16]
            if not body.get("stream"):
                return self._json(200, Endpoint.completion(r, rid))
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("cache-control", "no-cache")
            self.send_header("connection", "close")
            self.end_headers()
            inc = (body.get("stream_options") or {}).get("include_usage", False)
            for c in Endpoint.chunks(r, rid, usage=inc):
                self.wfile.write(b"data: " + json.dumps(c).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True

    srv = ThreadingHTTPServer((bind, port), H)
    srv.daemon_threads = True
    if ready:
        ready(srv)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()
