"""The console-nav stub gateway (tests/stub_gateway.py) speaks the frames the hosts'
tests rely on: the greeting, open, intent, save without a token, records, chat."""
import json

import pytest

pytest.importorskip("websockets")
from websockets.sync.client import connect  # noqa: E402

from stub_gateway import StubGateway  # noqa: E402


def recv_until(ws, typ, timeout=5):
    out = []
    while True:
        f = json.loads(ws.recv(timeout=timeout))
        out.append(f)
        if f.get("type") == typ:
            return out


@pytest.fixture
def gw():
    g = StubGateway(domains=["plant", "dog"], records=[{"file": "records/x.jsonl"}],
                    script=lambda cmd, sid: ("refused", "busy") if cmd == ":run 99" else None).start()
    yield g
    g.stop()


def test_greeting_open_intent_save_records(gw):
    with connect(gw.url) as ws:
        greet = recv_until(ws, "catalogs")
        assert [f["type"] for f in greet] == ["manifest", "domains", "readme", "catalogs"]
        assert greet[-1]["names"] == ["plant", "dog"]
        ws.send(json.dumps({"ch": "repl", "type": "open", "llp": "domains/plant/plant.llp", "req": "r1"}))
        s = recv_until(ws, "source")[0]
        assert s["type"] == "session" and s["name"] == "plant" and s["req"] == "r1"
        sid = s["session"]
        ws.send(json.dumps({"ch": "repl", "type": "intent", "session": sid, "id": "i1", "cmd": ":run 3"}))
        p = recv_until(ws, "posting")[-1]
        assert (p["status"], p["cmd"]) == ("done", ":run 3")
        ws.send(json.dumps({"ch": "repl", "type": "intent", "session": sid, "id": "i2", "cmd": ":run 99"}))
        assert recv_until(ws, "posting")[-1]["status"] == "refused"
        ws.send(json.dumps({"ch": "repl", "type": "save", "session": sid}))
        plan = recv_until(ws, "save")[-1]
        assert plan["token"] and plan["files"] and gw.written == []
        ws.send(json.dumps({"ch": "repl", "type": "records"}))
        assert recv_until(ws, "records")[-1]["records"] == [{"file": "records/x.jsonl"}]
        ws.send(json.dumps({"ch": "chat", "type": "say", "session": sid, "text": "the lamp dims"}))
        assert recv_until(ws, "done")[0]["text"] == "the lamp dims"
        ws.send(json.dumps({"ch": "repl", "type": "open", "llp": "nope", "req": "r2"}))
        assert recv_until(ws, "error")[-1]["req"] == "r2"
    assert [m["type"] for m in gw.received] == ["open", "intent", "intent", "save", "records", "say", "open"]


def test_a_brain_without_the_chat_seat():
    g = StubGateway(chat=False).start()
    try:
        with connect(g.url) as ws:
            man = recv_until(ws, "catalogs")[0]
            assert man["seats"]["chat"] is None and "needs claude" in man["chat_unavailable"]
            ws.send(json.dumps({"ch": "chat", "type": "say", "session": "w1", "text": "x"}))
            assert "needs claude" in recv_until(ws, "error")[-1]["error"]
    finally:
        g.stop()


def test_push_reaches_the_clients():
    g = StubGateway().start()
    try:
        with connect(g.url) as ws:
            recv_until(ws, "catalogs")
            g.push({"ch": "repl", "type": "session", "session": "w9", "busy": True})
            assert recv_until(ws, "session")[-1]["busy"] is True
    finally:
        g.stop()
