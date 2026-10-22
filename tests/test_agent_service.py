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


def say_answering(ws, sid, text, answer, timeout=30):
    """A chat turn whose agent writes wait for the person: each save plan by the agent
    is answered as the person would (answer: "confirm" — the apply with its token —
    or "refuse"). Returns every frame up to the chat's end."""
    import time as _t
    ws.send(json.dumps({"ch": "chat", "type": "say", "session": sid, "text": text}))
    out, end = [], _t.time() + timeout
    while _t.time() < end:
        f = json.loads(ws.recv(timeout=max(0.1, end - _t.time())))
        out.append(f)
        if f.get("type") == "save" and f.get("by") == "agent":
            ws.send(json.dumps({"ch": "repl", "type": "save" if answer == "confirm" else "refuse",
                                "session": sid, "token": f["token"]}))
        if f.get("ch") == "chat" and f.get("type") in ("done", "error"):
            return out
    raise AssertionError(f"timed out; got {out[-5:]}")


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
        assert o.system_prompt == preamble(svc.cfg) and "no shell, no web" in o.system_prompt
        assert f"At most {svc.cfg.get('agent_tool_calls', 10)} tool calls" in o.system_prompt
        assert "#init <atom> <count>" in o.system_prompt       # the directives are taught
        assert "At most 25 tool calls" in preamble({"agent_tool_calls": 25})
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


def test_source_tools_edit_extension_and_recompile(agent):
    """§4a: Claude reads/edits the working copy and adds an extension (memory
    only), every window sees the source frames, recompile certifies it
    locally; ambiguous edits, extension without extends, bad targets fail."""
    from test_working_copy import PACK
    FakeClient.hang = False
    FakeClient.script = [
        ("source_read", {"target": "copy", "start": 1, "end": 2}),
        ("source_edit", {"target": "copy", "old_str": "stage",
                         "new_str": "x"}),                    # not unique
        ("source_edit", {"target": "copy",
                         "old_str": "% Port of interactive-lp",
                         "new_str": "% Ported from interactive-lp"}),
        ("extension_create", {"name": "nope", "source": "catalog x 1."}),
        ("extension_create", {"name": "tired", "source": PACK}),
        ("source_read", {"target": "extension:9"}),
        ("recompile", {}),
    ]
    with agent.ws() as ws:
        sid = open3(ws)["session"]
        got = say(ws, sid, "extend it")
        parts = got[-1]["text"].split(" | ")
        assert [p[:3] for p in parts] == \
            ["Don", "ERR", "ok ", "ERR", "ok ", "ERR", "ok "]
        assert "\"target\": \"copy\"" in parts[0] and "exactly once" in parts[1]
        srcs = [f for f in got if f.get("type") == "source"]
        assert srcs[0]["certified"] is None           # after the edit
        assert srcs[-1]["certified"] == "local"       # after recompile
        assert srcs[-1]["copy"].startswith("% Ported from interactive-lp")
        assert [p["name"] for p in srcs[-1]["extensions"]] == ["tired"]
        assert any(f.get("type") == "session" and f.get("recompiled")
                   for f in got)
    # the checkout itself is untouched
    assert "% Port of interactive-lp" in agent.gw.srv.resolve(
        "three_pigs").read_text()


def test_chat_needs_a_session_when_the_seat_exists(agent):
    with agent.ws() as ws:
        frames(ws, lambda f: f.get("type") == "catalogs")
        ws.send(json.dumps({"ch": "chat", "type": "say", "text": "hi"}))
        err = frames(ws, lambda f: f.get("ch") == "chat")[-1]
        assert err["type"] == "error" and err["error"] == "open a session first"


def test_apply_writes_only_a_certified_copy_and_shows_the_diff(tmp_path):
    """human-loop step 1: `apply()` is the chat's "apply to catalog" — the
    copy written into the catalog source only after a recompile certified
    it and the person confirmed the plan (loop-parity step 2: the agent's
    write waits for the person, as pi's does); the diff posted to the
    console; nothing to apply on an unchanged copy. On a scratch checkout."""
    from loop.console_serve import ConsoleServer
    srv = ConsoleServer(tmp_path)
    llp = srv.new_domain("plant", "a plant")
    path = tmp_path / "domains/plant/plant.llp"
    r = Running(srv, mode="personal")
    r.gw.agent.client_factory = FakeClient
    FakeClient.hang = False
    FakeClient.script = [
        ("apply", {}),                                                       # unchanged: nothing to apply
        ("source_edit", {"target": "copy", "old_str": "%% I wake up.", "new_str": "%% I wake up slowly."}),
        ("apply", {}),                                                       # uncertified: refused
        ("recompile", {}),
        ("apply", {}),                                                       # written
    ]
    try:
        with r.ws() as ws:
            sid = open3(ws, llp)["session"]
            got = say_answering(ws, sid, "make it wake up slowly and apply it", "confirm")
            parts = got[-1]["text"].split(" | ")
            assert [p[:3] for p in parts] == ["Don", "ok ", "ERR", "ok ", "ok "]
            asked = [f for f in got if f.get("type") == "save" and f.get("by") == "agent"]
            assert len(asked) == 1 and "+  %% I wake up slowly." in asked[0]["files"][0]["diff"]   # the person saw the plan
            assert '"written": []' in parts[0]                              # the notes are cut at 40 chars
            post = [f for f in got if f.get("type") == "posting" and f.get("cmd") == ":apply"]
            assert len(post) == 1 and "+  %% I wake up slowly." in post[0]["result"] and post[0]["actor"] == "claude"
            assert [f for f in got if f.get("type") == "source"][-1]["certified"] == "checkout"
        assert "%% I wake up slowly." in path.read_text()
    finally:
        r.close()


def test_the_agents_apply_refused_by_the_person_writes_nothing(tmp_path):
    """loop-parity step 2: the person refuses the agent's plan — nothing written, the
    agent told so in words; the refusal is remembered (the next plan's since_diff)."""
    from loop.console_serve import ConsoleServer
    srv = ConsoleServer(tmp_path)
    llp = srv.new_domain("plant", "a plant")
    path = tmp_path / "domains/plant/plant.llp"
    before = path.read_text()
    r = Running(srv, mode="personal")
    r.gw.agent.client_factory = FakeClient
    FakeClient.hang = False
    FakeClient.script = [
        ("source_edit", {"target": "copy", "old_str": "%% I wake up.", "new_str": "%% I wake up slowly."}),
        ("recompile", {}),
        ("apply", {}),                                                       # refused by the person
    ]
    try:
        with r.ws() as ws:
            sid = open3(ws, llp)["session"]
            got = say_answering(ws, sid, "make it wake up slowly and apply it", "refuse")
            parts = got[-1]["text"].split(" | ")
            assert [p[:3] for p in parts] == ["Don", "ok ", "ERR"] and "refused" in parts[2]
            assert [f for f in got if f.get("type") == "refused"]
        assert path.read_text() == before
        w = next(iter(r.gw.sessions.values())).work
        again = srv.save_plan(w)
        assert again["files"][0].get("since_diff") is not None                # remembered: what changed since
    finally:
        r.close()


def test_apply_is_one_of_the_seats_tools():
    assert "mcp__metis__apply" in ALLOWED
