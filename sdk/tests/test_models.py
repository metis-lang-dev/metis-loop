"""metis_loop_sdk.models offline: no claude -p and no Ollama are run — the
claude seat's process is stubbed, Ollama is a local stand-in server."""
import asyncio
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from metis_loop_sdk.models import chat, claude, ollama
from metis_loop_sdk.models.__main__ import main as cli


# -- claude: containment and the command face ------------------------------

def test_containment_is_tool_free_and_persists_nothing():
    c = claude.containment()
    assert c == {"tools": [], "strict_mcp_config": True, "setting_sources": [],
                 "extra_args": {"no-session-persistence": None}}
    c["tools"].append("x")
    assert claude.containment()["tools"] == []       # a fresh dict per call


def test_command_face_options():
    pytest.importorskip("claude_agent_sdk")
    o = claude.options("claude-haiku-4-5")
    assert o.tools == [] and o.strict_mcp_config and not o.mcp_servers
    assert o.setting_sources == [] and o.max_turns == 1
    assert "no-session-persistence" in o.extra_args
    assert o.model == "claude-haiku-4-5"
    assert o.thinking == {"type": "enabled", "budget_tokens": 1024}
    assert claude.options("m", 0).thinking == {"type": "disabled"}
    assert claude.options().model == claude.DEFAULT_MODEL == "claude-haiku-4-5"


def test_command_face_collects_text_and_raises_on_error(monkeypatch):
    sdk = pytest.importorskip("claude_agent_sdk")

    class TextBlock:
        def __init__(self, t):
            self.text = t

    class AssistantMessage:
        def __init__(self, *ts):
            self.content = [TextBlock(t) for t in ts]

    class ResultMessage:
        def __init__(self, err=False):
            self.is_error, self.subtype, self.result = err, "x", "boom"

    def fake(script):
        async def query(prompt, options):
            assert options.tools == []
            for m in script:
                yield m
        return query
    monkeypatch.setattr(sdk, "query", fake([AssistantMessage("The pigs ", "built."), ResultMessage()]))
    assert asyncio.run(claude.complete("p")) == "The pigs built."
    monkeypatch.setattr(sdk, "query", fake([ResultMessage(True)]))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(claude.complete("p"))


# -- claude: the seat face -------------------------------------------------

def test_seat_argv_is_contained():
    s = claude.Seat(model="opus", cwd="/tmp", session="U")
    assert s.argv("SYS", True) == ["claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config",
                                   "--output-format", "json", "--model", "opus", "--system-prompt", "SYS",
                                   "--session-id", "U"]
    s.effort = "low"
    assert s.argv("SYS", False)[-4:] == ["--effort", "low", "--resume", "U"]


def test_repl_lines_parse():
    p = claude.ReplLines.parse
    assert p("Let me look.\nREPL: state") == ("state", {"arg": ""}, "Let me look.")
    assert p("REPL: step carry[A=near,X=goat,B=far]")[:2] == ("step", {"arg": "carry[A=near,X=goat,B=far]"})
    assert p("`REPL: necessity 1 gone(cabbage)`")[:2] == ("necessity", {"arg": "1 gone(cabbage)"})
    assert p("REPL: why\nREPL: state")[:2] == ("why", {"arg": ""})   # the first line only
    assert p("The goat is on the far bank.") is None


def test_json_lines_parse():
    p = claude.JsonLines.parse
    assert p('I will advance time.\nCALL: domain_clock {"n": 3}') == ("domain_clock", {"n": 3}, "I will advance time.")
    assert p("CALL: repl_state {}") == ("repl_state", {}, "")
    assert p("CALL: repl_state") == ("repl_state", {}, "")
    assert p('`CALL: repl_text {"arg": "a lamp\\nwith two lines"}`')[1] == {"arg": "a lamp\nwith two lines"}
    assert p('CALL: catalog_apply {"domain": "lamp",\n  "what": "program"}')[1] == {"domain": "lamp", "what": "program"}
    assert p("CALL: x {not json}") == ("x", None, "")
    assert p("CALL: x [1]")[1] is None
    assert p("No call here; the lamp is dark.") is None
    d = claude.JsonLines.declarations([{"name": "domain_clock", "description": "Advance time.",
                                        "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}}}])
    assert d == '- domain_clock: Advance time.\n  arguments (JSON schema): {"type":"object","properties":{"n":{"type":"integer"}}}'


def test_seat_ask_opens_then_resumes():
    s = claude.Seat(cwd="/tmp", protocol=claude.JsonLines)
    sent = []
    replies = iter(['CALL: t {"a": 1}', "done", "again"])
    s._call = lambda sys_text, prompt, first: (sent.append((sys_text, prompt, first)) or (next(replies), "end_turn", 1.0))
    tools = [{"name": "t", "description": "a tool", "parameters": {"type": "object"}}]
    r = s.ask("You help.", tools, "Q?")
    assert r.call == ("t", {"a": 1}, "") and sent[-1][2] is True
    sess = s.session
    r = s.ask("You help.", tools, "result")
    assert r.call is None and r.text == "done" and sent[-1][1:] == ("result", False) and s.session == sess
    assert sent[0][0].startswith("You help.\n\nHow to call a tool") and "- t: a tool" in sent[0][0]
    s.ask("You help.", tools, "Q2?", first=True)
    assert s.session != sess                      # a first turn is a new session


# -- claude: the chat face -------------------------------------------------

class FakeSeat(claude.Seat):
    """A seat whose claude -p is a script; it records what it was sent."""

    def __init__(self, script, sent, **kw):
        super().__init__(cwd="/tmp", protocol=claude.JsonLines, **kw)
        self.script, self.sent = iter(script), sent

    def _call(self, sys_text, prompt, first):
        self.sent.append({"session": self.session, "first": first, "prompt": prompt, "system": sys_text})
        self.usage = {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 5}
        return next(self.script), "end_turn", 1.0


TOOLS = [{"type": "function", "function": {"name": "domain_clock", "description": "Advance time.",
                                           "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}}}},
         {"type": "function", "function": {"name": "domain_state", "description": "Read the state.",
                                           "parameters": {"type": "object", "properties": {}}}}]


def endpoint(script, sent):
    seats = []

    def factory(model):
        seats.append(FakeSeat(script, sent, model=model))
        return seats[-1]
    return chat.Endpoint(model="sonnet", seat_factory=factory), seats


def test_chat_a_conversation_is_one_session_resumed():
    sent = []
    ep, seats = endpoint(['Advancing.\nCALL: domain_clock {"n": 2}', "CALL: domain_state {}", "The lamp is dark."], sent)
    msgs = [{"role": "system", "content": "You run the loop."}, {"role": "user", "content": "Switch it on."}]
    r = ep.complete({"model": "opus", "messages": msgs, "tools": TOOLS})
    cid, name, args = r["tool_call"]
    assert (name, args, r["content"], r["finish_reason"]) == ("domain_clock", {"n": 2}, "Advancing.", "tool_calls")
    assert sent[-1]["first"] and sent[-1]["prompt"] == "Switch it on." and seats[0].model == "opus"
    assert "You run the loop." in sent[-1]["system"] and "- domain_state: Read the state." in sent[-1]["system"]
    assert r["usage"] == {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105,
                          "prompt_tokens_details": {"cached_tokens": 90}}
    # the client echoes the reply (its own serialization) and adds the tool's result
    msgs += [{"role": "assistant", "content": [{"type": "text", "text": "Advancing."}],
              "tool_calls": [{"id": cid, "type": "function",
                              "function": {"name": "domain_clock", "arguments": '{ "n" : 2 }'}}]},
             {"role": "tool", "tool_call_id": cid, "content": "clock: beat 2"}]
    r = ep.complete({"model": "opus", "messages": msgs, "tools": TOOLS})
    assert len(seats) == 1 and not sent[-1]["first"] and sent[-1]["session"] == sent[0]["session"]
    assert sent[-1]["prompt"] == "The result of domain_clock:\nclock: beat 2"
    cid2 = r["tool_call"][0]
    msgs += [{"role": "assistant", "content": None, "tool_calls": [
        {"id": cid2, "type": "function", "function": {"name": "domain_state", "arguments": "{}"}}]},
             {"role": "tool", "tool_call_id": cid2, "content": "dark 1"},
             {"role": "user", "content": "And now?"}]
    r = ep.complete({"model": "opus", "messages": msgs, "tools": TOOLS})
    assert len(seats) == 1 and sent[-1]["prompt"] == "The result of domain_state:\ndark 1\n\nAnd now?"
    assert r["tool_call"] is None and r["content"] == "The lamp is dark." and r["finish_reason"] == "stop"


def test_chat_an_unknown_conversation_starts_a_session_with_its_history():
    sent = []
    ep, seats = endpoint(["Fine."], sent)
    msgs = [{"role": "user", "content": "Hi."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "domain_state", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "dark 1"}]
    ep.complete({"messages": msgs, "tools": TOOLS})
    p = sent[-1]["prompt"]
    assert sent[-1]["first"] and seats[0].model == "sonnet"
    assert "[the person]\nHi." in p and "[you]\nCALL: domain_state {}" in p and "[the result of domain_state]\ndark 1" in p


def test_chat_a_bad_call_is_asked_again_once():
    sent = []
    ep, _ = endpoint(["CALL: repl_check {}", 'CALL: domain_clock {"n": 1}'], sent)
    r = ep.complete({"messages": [{"role": "user", "content": "go"}], "tools": TOOLS})
    assert r["tool_call"][1:] == ("domain_clock", {"n": 1})
    assert "there is no tool 'repl_check'" in sent[1]["prompt"] and "domain_clock, domain_state" in sent[1]["prompt"]
    sent.clear()
    ep, _ = endpoint(["CALL: domain_clock {n: 1}", "CALL: domain_clock {n: 1}"], sent)
    r = ep.complete({"messages": [{"role": "user", "content": "go"}], "tools": TOOLS})
    assert len(sent) == 2 and "not one JSON object" in sent[1]["prompt"]
    assert r["tool_call"] is None and r["finish_reason"] == "stop"   # still bad: the text is the answer


def test_chat_over_http_streams_as_openai_does():
    sent = []
    ep, _ = endpoint(['On it.\nCALL: domain_clock {"n": 4}', "plain answer"], sent)
    box = {}
    t = threading.Thread(target=chat.serve, args=(ep, 0), kwargs={"ready": lambda s: box.update(srv=s)}, daemon=True)
    t.start()
    while "srv" not in box:
        pass
    url = "http://127.0.0.1:%d/v1" % box["srv"].server_port
    try:
        with urllib.request.urlopen(url + "/models", timeout=5) as r:
            assert json.loads(r.read())["data"][0]["id"] == "sonnet"
        body = {"model": "opus", "stream": True, "stream_options": {"include_usage": True}, "tools": TOOLS,
                "messages": [{"role": "user", "content": "go"}]}
        req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.headers["content-type"] == "text/event-stream"
            raw = r.read().decode()
        events = [ln[6:] for ln in raw.split("\n\n") if ln.startswith("data: ")]
        assert events[-1] == "[DONE]"
        chunks = [json.loads(e) for e in events[:-1]]
        assert chunks[0]["choices"][0]["delta"] == {"role": "assistant", "content": "On it."}
        tc = chunks[1]["choices"][0]["delta"]["tool_calls"][0]
        assert tc["index"] == 0 and tc["function"] == {"name": "domain_clock", "arguments": '{"n": 4}'}
        assert chunks[2]["choices"][0]["finish_reason"] == "tool_calls"
        assert chunks[3]["choices"] == [] and chunks[3]["usage"]["total_tokens"] == 105
        body = {"messages": [{"role": "user", "content": "other"}]}
        req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode())
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read())
        assert d["choices"][0]["message"] == {"role": "assistant", "content": "plain answer"}
        assert d["choices"][0]["finish_reason"] == "stop"
    finally:
        box["srv"].shutdown()


def test_chat_is_loopback_only():
    with pytest.raises(ValueError, match="loopback only"):
        chat.serve(chat.Endpoint(), 0, "0.0.0.0")


# -- ollama ------------------------------------------------------------------

class Ollama:
    """A stand-in Ollama: /api/version, /api/ps, /api/generate."""

    def __init__(self, ps=(), loads=None):
        self.ps, self.loads, self.posts = list(ps), loads, []
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, obj):
                b = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("content-length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                self._send({"version": "0.12.3"} if self.path == "/api/version" else {"models": me.ps})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                me.posts.append(body)
                if body["prompt"] == "" and me.loads:
                    me.ps.append(me.loads)
                self._send({"response": "pred lit : lamp."})
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.srv.server_port

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def test_ollama_generate_thinks_off():
    o = Ollama()
    try:
        assert ollama.generate("draft it", "metis-gemma4-e4b", o.url) == "pred lit : lamp."
        assert o.posts[-1] == {"model": "metis-gemma4-e4b", "prompt": "draft it", "stream": False, "think": False,
                               "options": {"temperature": 0, "num_predict": 2048}}
    finally:
        o.close()


def test_ollama_probe():
    gpu = {"name": "metis-gemma4-e4b:latest", "size": 6 << 30, "size_vram": 6 << 30}
    cpu = dict(gpu, size_vram=0)
    o = Ollama(ps=[gpu])
    try:
        r = ollama.probe(o.url, "metis-gemma4-e4b")
        assert r["up"] and r["version"] == "0.12.3" and r["on_gpu"] is True and "100% of 6144 MiB" in r["why"]
        o.ps = [cpu]
        r = ollama.probe(o.url, "metis-gemma4-e4b", gpu_present=lambda: "GPU 0: NVIDIA RTX")
        assert r["on_gpu"] is False and "restart it" in r["why"] and "NVIDIA RTX" in r["why"]
        r = ollama.probe(o.url, "metis-gemma4-e4b", gpu_present=lambda: None)
        assert r["on_gpu"] is False and "no NVIDIA GPU" in r["why"]
        o.ps = []
        r = ollama.probe(o.url, "metis-gemma4-e4b")
        assert r["on_gpu"] is None and "not loaded" in r["why"]
        o.loads = gpu
        r = ollama.probe(o.url, "metis-gemma4-e4b", load=True)
        assert r["on_gpu"] is True and o.posts[-1]["keep_alive"] == "5m"
    finally:
        o.close()
    r = ollama.probe(o.url, "metis-gemma4-e4b")
    assert not r["up"] and "does not answer" in r["why"]


def test_ollama_cli(capsys, monkeypatch):
    import io
    o = Ollama(ps=[{"name": "m:latest", "size": 100, "size_vram": 0}])
    try:
        monkeypatch.setattr("sys.stdin", io.StringIO("draft"))
        assert cli(["ollama-command", "--model", "m", "--url", o.url]) == 0
        assert capsys.readouterr().out == "pred lit : lamp."
        assert o.posts[-1]["think"] is False
        assert cli(["ollama-probe", "--url", o.url, "--model", "m"]) == 3
        assert json.loads(capsys.readouterr().out)["on_gpu"] is False
        assert cli(["ollama-probe", "--url", o.url]) == 2
    finally:
        o.close()
