"""The Agent Service (docs/CONSOLE-WS.md §3) — hermetic: an injected
fake SDK client drives the REAL tools through a REAL gateway socket.
Containment of the SDK options, the tool-call cap, refusals, stop, the
claude> transcript and in-memory history. A real turn on the
operator's login is opt-in only: METIS_AGENT_LIVE=1 (it spends the
subscription; never in CI)."""
import asyncio
import json
import os

import pytest

pytest.importorskip("websockets")
pytest.importorskip("claude_agent_sdk")

from loop.agent_service import ALLOWED, AgentService, preamble, truncate  # noqa: E402
from test_gateway import Running, frames, open3  # noqa: E402


class StreamEvent:                       # matched by class name
    def __init__(self, text):
        self.event = {"type": "content_block_delta",
                      "delta": {"type": "text_delta", "text": text}}


class ResultMessage:
    is_error, subtype, result = False, "success", ""


class FakeClient:
    """Plays a model: runs `script` tool calls, then streams an answer
    naming each tool result's status."""
    script = [("repl", {"line": ":run 3"})]
    hang = False

    def __init__(self, svc, chat):
        self.fns, self.interrupted = svc.tool_fns(chat), asyncio.Event()

    async def connect(self):
        pass

    async def query(self, prompt):
        self.prompt = prompt

    async def interrupt(self):
        self.interrupted.set()

    async def disconnect(self):
        pass

    async def receive_response(self):
        notes = []
        for name, args in self.script:
            r = await self.fns[name](args)
            notes.append(("ERR " if r.get("is_error") else "ok ") +
                         r["content"][0]["text"][:40])
        if self.hang:
            await self.interrupted.wait()
            raise asyncio.CancelledError
        for chunk in ("Done: ", " | ".join(notes)):
            yield StreamEvent(chunk)
        yield ResultMessage()


@pytest.fixture
def agent():
    r = Running(mode="personal")
    r.gw.agent.client_factory = FakeClient
    yield r
    r.close()


def say(ws, sid, text):
    ws.send(json.dumps({"ch": "chat", "type": "say", "session": sid,
                        "text": text}))
    return frames(ws, lambda f: f.get("ch") == "chat"
                  and f.get("type") in ("done", "error"), timeout=30)


def test_chat_turn_runs_the_repl_as_claude_and_streams(agent):
    FakeClient.script, FakeClient.hang = [("repl", {"line": ":run 3"}),
                                          ("ctx", {}),
                                          ("transcript", {"n": 5})], False
    with agent.ws() as ws:
        man = json.loads(ws.recv(timeout=5))
        assert man["seats"]["chat"] == "agent"
        sid = open3(ws)["session"]
        got = say(ws, sid, "run it")
        chat = [f for f in got if f.get("ch") == "chat"]
        assert chat[0]["type"] == "user" and chat[0]["text"] == "run it"
        tools = [f for f in chat if f["type"] == "tool"]
        assert tools[0]["status"] == "queued" and tools[-1]["status"] == "done"
        post = [f for f in got if f.get("type") == "posting"]
        assert post and post[0]["actor"] == "claude" and \
            post[0]["cmd"] == ":run 3"            # in the transcript
        done = chat[-1]
        assert done["type"] == "done" and done["text"].startswith("Done: ok")
        assert done["text"].count("ok ") == 3
    with agent.ws() as ws2:                       # reload: history back
        frames(ws2, lambda f: f.get("type") == "catalogs")
        ws2.send(json.dumps({"ch": "repl", "type": "open", "session": sid}))
        hist = frames(ws2, lambda f: f.get("type") == "history")[-1]
        assert [t["role"] for t in hist["turns"]] == ["user", "assistant"]
        assert hist["turns"][1]["tools"][0]["line"] == ":run 3"


def test_cap_refusal_and_page_cannot_spoof_claude(agent):
    FakeClient.script = [("repl", {"line": ":accept"})] + \
        [("ctx", {})] * 11
    FakeClient.hang = False
    with agent.ws() as ws:
        sid = open3(ws)["session"]
        done = say(ws, sid, "try")[-1]
        parts = done["text"].split(" | ")
        assert parts[0].startswith("Done: ERR refused by the console")
        assert sum(p.startswith("ok") for p in parts) == 9    # 10 total
        assert parts[-1].startswith("ERR tool-call cap reached (10")
        ws.send(json.dumps({"ch": "repl", "type": "intent", "session": sid,
                            "id": "x1", "cmd": ":ctx", "actor": "claude"}))
        post = frames(ws, lambda f: f.get("type") == "posting"
                      and f.get("id") == "x1")[-1]
        assert post["actor"] == "viewer"           # only the backend is claude>


def test_stop_interrupts_the_turn(agent):
    FakeClient.script, FakeClient.hang = [("ctx", {})], True
    with agent.ws() as ws:
        sid = open3(ws)["session"]
        ws.send(json.dumps({"ch": "chat", "type": "say", "session": sid,
                            "text": "think forever"}))
        frames(ws, lambda f: f.get("type") == "tool"
               and f.get("status") == "queued" or f.get("type") == "user")
        ws.send(json.dumps({"ch": "chat", "type": "stop", "session": sid}))
        done = frames(ws, lambda f: f.get("ch") == "chat"
                      and f.get("type") == "done", timeout=15)[-1]
        assert done["text"].endswith("[stopped]")
        ws.send(json.dumps({"ch": "chat", "type": "say", "session": sid,
                            "text": "again"}))       # not stuck busy
        assert frames(ws, lambda f: f.get("ch") == "chat" and f.get(
            "type") == "user")[-1]["text"] == "again"


def test_sdk_options_are_contained():
    """No built-in tools, only ours; no settings; no transcripts on
    disk (D4); the gate denies anything else."""
    r = Running(mode="personal")
    try:
        svc: AgentService = r.gw.agent
        from loop.agent_service import Chat
        o = svc.options(Chat("w1"))
        assert o.tools == [] and o.strict_mcp_config
        assert not o.allowed_tools            # the gate decides every call
        assert o.setting_sources == []
        assert "no-session-persistence" in o.extra_args
        assert o.system_prompt == preamble() and "You have no other tools" in o.system_prompt
        deny = asyncio.run(o.can_use_tool("Bash", {}, None))
        allow = asyncio.run(o.can_use_tool("mcp__metis__repl", {}, None))
        assert type(deny).__name__ == "PermissionResultDeny"
        assert type(allow).__name__ == "PermissionResultAllow"
    finally:
        r.close()


def test_truncate_keeps_first_and_last():
    t = "\n".join(str(i) for i in range(1000))
    out = truncate(t).splitlines()
    assert out[0] == "0" and out[-1] == "999" and len(out) == 401


def test_shared_mode_has_no_agent():
    r = Running(mode="shared")
    try:
        assert r.gw.agent is None
    finally:
        r.close()


@pytest.mark.skipif(os.environ.get("METIS_AGENT_LIVE") != "1",
                    reason="real SDK turn on the operator's login: opt in "
                           "with METIS_AGENT_LIVE=1 (spends the subscription)")
def test_live_turn_on_the_operators_login():
    r = Running(mode="personal")
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            got = say(ws, sid, "Call the ctx tool once, then answer with "
                               "just the stage name.")
            done = got[-1]
            assert done["type"] == "done", done
            assert any(f.get("type") == "tool" for f in got) or \
                "go" in done["text"].lower()
            assert "go" in done["text"].lower()
    finally:
        r.close()
