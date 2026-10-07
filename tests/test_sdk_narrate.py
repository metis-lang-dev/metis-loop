"""The narrate seat on the SDK (CONSOLE-WS §4, D3): the gateway points a
personal session's LLM endpoint at loop.sdk_narrate through the
kernel's own `command:` backend — kernel untouched, no tools, nothing
persisted; shared mode never gets it; `narrate = "llm"` keeps ollama.
A real Haiku narration is opt-in (METIS_AGENT_LIVE=1)."""
import asyncio
import json
import os

import pytest

pytest.importorskip("websockets")
pytest.importorskip("claude_agent_sdk")

import loop.sdk_narrate as sn  # noqa: E402
from loop.gateway import DEFAULTS, narrate_seat  # noqa: E402
from test_gateway import Running, frames, open3, send  # noqa: E402


def test_options_are_tool_free_and_persist_nothing():
    o = sn.options("claude-haiku-4-5")
    assert o.tools == [] and o.strict_mcp_config and not o.mcp_servers
    assert o.setting_sources == [] and o.max_turns == 1
    assert "no-session-persistence" in o.extra_args
    assert o.model == "claude-haiku-4-5"
    assert o.thinking == {"type": "enabled", "budget_tokens": 1024}
    assert sn.options("m", 0).thinking == {"type": "disabled"}


def test_complete_collects_text_and_raises_on_error(monkeypatch):
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
    import claude_agent_sdk
    monkeypatch.setattr(claude_agent_sdk, "query",
                        fake([AssistantMessage("The pigs ", "built."),
                              ResultMessage()]))
    assert asyncio.run(sn.complete("p")) == "The pigs built."
    monkeypatch.setattr(claude_agent_sdk, "query", fake([ResultMessage(True)]))
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(sn.complete("p"))


def test_seat_is_personal_only_and_configurable():
    label, spec = narrate_seat(dict(DEFAULTS))
    assert label == "claude-haiku-4-5 (SDK)"
    assert spec.startswith("command:") and "loop.sdk_narrate" in spec
    assert spec.endswith("--thinking 1024")
    assert narrate_seat(dict(DEFAULTS, mode="shared")) == (None, None)
    assert narrate_seat(dict(DEFAULTS, narrate="llm")) == ("llm (ollama)", None)


def test_gateway_sets_the_seat_on_personal_sessions_only():
    r = Running(mode="personal")
    try:
        with r.ws() as ws:
            man = json.loads(ws.recv(timeout=5))
            assert man["seats"]["narrate"] == "claude-haiku-4-5 (SDK)"
            sid = open3(ws)["session"]
            assert "loop.sdk_narrate" in r.gw.srv.shells[sid].llm
            # the page cannot move the seat to an arbitrary command
            p = send(ws, sid, ":llm command:sh -c id", "x1")[-1]
            assert p["status"] == "refused"
    finally:
        r.close()
    r = Running(mode="shared")
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            assert "sdk_narrate" not in (r.gw.srv.shells[sid].llm or "")
    finally:
        r.close()


@pytest.mark.skipif(os.environ.get("METIS_AGENT_LIVE") != "1",
                    reason="real Haiku narration on the operator's login: "
                           "opt in with METIS_AGENT_LIVE=1")
def test_live_narration_on_haiku():
    r = Running(mode="personal")
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            send(ws, sid, ":run 3", "r1")
            post = frames(ws, lambda f: f.get("type") == "posting"
                          and f.get("id") == "n1", timeout=120) \
                if ws.send(json.dumps({"ch": "repl", "type": "intent",
                                       "session": sid, "id": "n1",
                                       "cmd": ":narrate"})) is None else []
            p = post[-1]
            assert p["status"] == "done", p["result"]
            assert p["json"]["source"] == "session"
            assert "sdk_narrate" in p["json"]["llm"]
            assert len(p["json"]["narration"]) > 80
            print("\n--- Haiku narration ---\n" + p["json"]["narration"])
    finally:
        r.close()
