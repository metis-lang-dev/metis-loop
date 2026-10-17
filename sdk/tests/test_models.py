"""metis_loop_sdk.models offline: no claude -p and no Ollama are run — the
claude seat's process is stubbed, Ollama is a local stand-in server."""
import asyncio
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from metis_loop_sdk.models import claude, ollama
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
