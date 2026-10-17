"""metis_loop_sdk.models offline: no claude -p and no Ollama are run — the
claude seat's process is stubbed, Ollama is a local stand-in server."""
import asyncio
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from metis_loop_sdk.models import claude, ollama, openai
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
        o.ps = [dict(gpu, size_vram=2 << 30)]
        r = ollama.probe(o.url, "metis-gemma4-e4b")
        assert r["on_gpu"] is False and "split: only 33% of 6144 MiB" in r["why"]
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
    capsys.readouterr()
    assert cli(["ollama-probe", "--url", o.url, "--model", "m"]) == 2      # down: a JSON answer, exit 2
    assert "does not answer" in json.loads(capsys.readouterr().out)["why"]


def test_ollama_probe_ps_failing_is_unknown(monkeypatch):
    def get(url, path, timeout):
        if path == "/api/ps":
            raise OSError("reset by peer")
        return {"version": "0.24.0"}
    monkeypatch.setattr(ollama, "_get", get)
    r = ollama.probe("http://x", "m")
    assert r["up"] and r["on_gpu"] is None and "/api/ps does not answer" in r["why"]


# -- openai: the OpenAI-compatible command face (a local capture server, a fake key) --

FAKE_KEY = "sk-or-v1-" + "0" * 64          # never a real key: the tests talk to 127.0.0.1 only


class Capture:
    """A stand-in /chat/completions: records each request (path, headers,
    body) and answers from a script of (status, json) pairs, the last
    one repeated."""

    def __init__(self, *script):
        self.script, self.got = list(script) or [(200, {"choices": [{"message": {"content": "ok"}}]})], []
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                me.got.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                               "body": json.loads(self.rfile.read(int(self.headers["content-length"])))})
                status, obj = me.script.pop(0) if len(me.script) > 1 else me.script[0]
                b = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("content-length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d/v1" % self.srv.server_port

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def answer(content, **usage):
    return (200, {"model": "m", "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                  "usage": dict({"prompt_tokens": 10, "completion_tokens": 5}, **usage)})


def test_openai_body_dialects():
    b = openai.body("draft", "deepseek/deepseek-v4-pro", openai.OPENROUTER)
    assert b == {"model": "deepseek/deepseek-v4-pro", "messages": [{"role": "user", "content": "draft"}],
                 "stream": False, "max_tokens": 2048, "temperature": 0,
                 "reasoning": {"effort": "none"}, "provider": {"data_collection": "deny"}}
    b = openai.body("draft", "metis-gemma4-e4b", "http://127.0.0.1:11434/v1")
    assert b["reasoning_effort"] == "none" and "reasoning" not in b and "provider" not in b
    b = openai.body("d", "m", openai.OPENROUTER, reasoning="default", data_collection="allow")
    assert "reasoning" not in b and b["provider"] == {"data_collection": "allow"}
    assert "reasoning_effort" not in openai.body("d", "m", "http://x/v1", reasoning="default")
    assert openai.body("d", "m", "http://x/v1", reasoning="high")["reasoning_effort"] == "high"
    for n in (0, openai.MAX_TOKENS + 1):
        with pytest.raises(ValueError, match="max_tokens"):
            openai.body("d", "m", "http://x/v1", max_tokens=n)
    assert openai.key_env(openai.OPENROUTER) == "OPENROUTER_API_KEY"
    assert openai.key_env("http://127.0.0.1:11434/v1") is None
    assert openai.key_env("http://127.0.0.1:11434/v1", "MY_KEY") == "MY_KEY"


def test_openai_complete_sends_the_key_only_where_named(tmp_path):
    c = Capture(answer("<think>hm</think>\npred lit : lamp.", cost=0.00012))
    log = tmp_path / "records" / "calls.jsonl"          # its directory made on the first call
    try:
        env = {"OPENAI_API_KEY": FAKE_KEY}          # in the environment, but not named: Ollama gets no key
        assert openai.complete("draft", "m", c.url, env=env) == "pred lit : lamp."
        assert c.got[-1]["path"] == "/v1/chat/completions"
        assert "authorization" not in c.got[-1]["headers"]
        assert c.got[-1]["body"]["reasoning_effort"] == "none" and c.got[-1]["body"]["max_tokens"] == 2048
        openai.complete("draft", "m", c.url, key_var="MY_KEY", max_tokens=512, env={"MY_KEY": FAKE_KEY}, log=str(log))
        assert c.got[-1]["headers"]["authorization"] == "Bearer " + FAKE_KEY
        assert c.got[-1]["body"]["max_tokens"] == 512
        rec = json.loads(log.read_text())
        assert rec["cost"] == 0.00012 and rec["completion_tokens"] == 5 and rec["finish_reason"] == "stop"
        assert FAKE_KEY not in log.read_text()
        with pytest.raises(RuntimeError, match="MY_KEY is not set"):
            openai.complete("draft", "m", c.url, key_var="MY_KEY", env={})
    finally:
        c.close()


def test_openai_openrouter_dialect_on_the_wire(monkeypatch):
    c = Capture(answer("pred lit : lamp."))
    monkeypatch.setattr(openai, "is_openrouter", lambda url: True)      # the capture server plays OpenRouter
    try:
        assert openai.complete("draft", "deepseek/deepseek-v4-pro", c.url,
                               env={"OPENROUTER_API_KEY": FAKE_KEY}) == "pred lit : lamp."
        g = c.got[-1]
        assert g["headers"]["authorization"] == "Bearer " + FAKE_KEY
        assert g["body"]["reasoning"] == {"effort": "none"} and g["body"]["provider"] == {"data_collection": "deny"}
        with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
            openai.complete("draft", "m", c.url, env={})
    finally:
        c.close()


def test_openai_errors_are_masked_and_hiccups_retried(monkeypatch):
    monkeypatch.setattr(openai.time, "sleep", lambda s: None)
    env = {"K": FAKE_KEY}
    c = Capture((503, {"error": "busy"}), answer("pred lit : lamp."))
    try:
        assert openai.complete("d", "m", c.url, key_var="K", env=env) == "pred lit : lamp."
        assert len(c.got) == 2                                          # one retry
    finally:
        c.close()
    c = Capture((401, {"error": {"message": "bad key %s" % FAKE_KEY}}))
    try:
        with pytest.raises(RuntimeError) as e:
            openai.complete("d", "m", c.url, key_var="K", env=env)
        assert "HTTP 401" in str(e.value) and FAKE_KEY not in str(e.value) and "sk-…" in str(e.value)
        assert len(c.got) == 1                                          # not retried
    finally:
        c.close()
    c = Capture((200, {"error": {"message": "no provider for this request"}}))
    try:
        with pytest.raises(RuntimeError, match="no provider"):
            openai.complete("d", "m", c.url, env={})
    finally:
        c.close()
    c = Capture((200, {"choices": [{"message": {"content": None, "reasoning": "…"}, "finish_reason": "length"}]}))
    try:
        with pytest.raises(RuntimeError, match="no content.*length"):
            openai.complete("d", "m", c.url, env={})
    finally:
        c.close()
    with pytest.raises(RuntimeError, match="127.0.0.1"):                # nothing listens there now
        openai.complete("d", "m", c.url, env={}, retries=0, timeout=5)


def test_openai_cli(capsys, monkeypatch):
    import io
    c = Capture(answer("pred lit : lamp."), (401, {"error": "bad key %s" % FAKE_KEY}))
    monkeypatch.setenv("K", FAKE_KEY)
    try:
        monkeypatch.setattr("sys.stdin", io.StringIO("draft"))
        assert cli(["openai-command", "--base-url", c.url, "--model", "m", "--key-env", "K", "--max-tokens", "300"]) == 0
        assert capsys.readouterr().out == "pred lit : lamp."
        assert c.got[-1]["body"]["messages"][0]["content"] == "draft" and c.got[-1]["body"]["max_tokens"] == 300
        monkeypatch.setattr("sys.stdin", io.StringIO("draft"))
        assert cli(["openai-command", "--base-url", c.url, "--model", "m", "--key-env", "K"]) == 1
        err = capsys.readouterr().err
        assert "HTTP 401" in err and FAKE_KEY not in err
    finally:
        c.close()
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert cli(["openai-command", "--model", "m"]) == 2
    with pytest.raises(SystemExit):
        cli(["openai-command", "--base-url", c.url, "--model", "m", "--reasoning", "lots"])
