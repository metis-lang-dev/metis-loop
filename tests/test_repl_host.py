"""domains/repl's host against the stub gateway (console-nav s-b923ebfe): the frame each
event sends, the report each answer becomes at a later tick, the pairs it keeps, the
sensor face. No kernel, no model (the program's side: test_console_domains.py)."""
import importlib.util
import time
from pathlib import Path

import pytest

pytest.importorskip("websockets")       # the stub gateway's server; the host itself is stdlib
from stub_gateway import StubGateway  # noqa: E402

HOST = Path(__file__).resolve().parents[1] / "domains" / "repl" / "repl_host.py"
spec = importlib.util.spec_from_file_location("repl_host", HOST)
repl_host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repl_host)


def tick_until(h, counts=None, want=None, secs=5):
    """Tick until a do-line in `want` comes (the answer is asynchronous); the do-lines seen."""
    seen, end = [], time.time() + secs
    while time.time() < end:
        seen += h.tick(dict(counts or {}))
        if want is None or want in seen:
            return seen
        time.sleep(0.02)
    raise AssertionError(f"no {want} in {seen}")


HOSTS = []


def host(url):
    h = repl_host.ReplHost(url=url)
    HOSTS.append(h)
    return h


def event(h, name, gw=None, **payload):
    """The event, the payload riding with it; with gw, until the stub has the frame."""
    n = len(gw.received) if gw else 0
    h.take_payload(payload)
    h.on_event(name, [])
    end = time.time() + 5
    while gw and len(gw.received) == n and time.time() < end:
        time.sleep(0.01)


@pytest.fixture
def gw():
    g = StubGateway(domains=[{"name": "plant", "path": "domains/plant/plant", "host": "plant_host.py:make", "line": "a plant"},
                             {"name": "love_triangle", "path": "domains/ceptre/love_triangle/love_triangle", "host": None}],
                    script=lambda cmd, sid: ("refused", "busy") if cmd == ":run 999" else None).start()
    yield g
    while HOSTS:
        HOSTS.pop().close()
    g.stop()


def loaded(gw):
    h = host(gw.url)
    event(h, "load", gw=gw, package="the plant")
    assert tick_until(h, want="+opened")
    return h


def test_load_opens_the_package_the_payload_names(gw):
    h = host(gw.url)
    assert h.connect() and set(h.domains) == {"plant", "love_triangle"} and h.chat_ok is True
    assert h.observe({}) == {"loaded": 0, "unloaded": 1}
    event(h, "load", gw=gw, package="the plant")
    assert h.observe({}) == {}                                    # in flight: no reading
    assert gw.received[-1] == {"ch": "repl", "type": "open", "llp": "domains/plant/plant", "host": True,
                               "req": gw.received[-1]["req"]}
    assert "+opened" in tick_until(h, want="+opened")
    assert h.effects == [{"repl": "attach", "session": h.sid}]    # the page shows it once it attaches
    assert h.observe({}) == {"loaded": 1, "unloaded": 0}
    event(h, "load_switch", gw=gw, package="Love Triangle")
    assert gw.received[-1]["llp"] == "domains/ceptre/love_triangle/love_triangle"


def test_an_unknown_package_is_absent_without_a_frame(gw):
    h = host(gw.url)
    h.connect()
    n = len(gw.received)
    event(h, "load", package="the toaster")
    assert len(gw.received) == n and h.tick({}) == ["+absent"]


def test_run_step_narrate_undo_reset_and_their_reports(gw):
    h = loaded(gw)
    event(h, "run", gw=gw, n=3)
    assert gw.received[-1]["cmd"] == ":run 3" and gw.received[-1]["session"] == h.sid
    tick_until(h, want="+stopped")
    event(h, "run", gw=gw)
    assert gw.received[-1]["cmd"] == f":run {repl_host.RUN_N}"
    tick_until(h, want="+stopped")
    event(h, "run", gw=gw, n=999)
    tick_until(h, want="+run_refused")                            # the console refused the line
    event(h, "step", gw=gw)
    assert gw.received[-1]["cmd"] == ":step"
    tick_until(h, want="+stopped")
    event(h, "narrate", gw=gw)
    tick_until(h, want="+narrated")
    for ev, cmd in (("undo", ":undo"), ("reset", ":reset")):
        event(h, ev, gw=gw)
        assert gw.received[-1]["cmd"] == cmd
    assert not any(d.startswith("+") for d in tick_until(h))     # undo and reset owe no report


def test_apply_asks_for_the_plan_only(gw):
    h = loaded(gw)
    event(h, "apply", gw=gw)
    assert gw.received[-1] == {"ch": "repl", "type": "save", "session": h.sid}    # no token
    tick_until(h, want="+plan_shown")
    assert gw.written == []                                       # applying is the person's click


def test_tell_hands_the_text_to_the_chat(gw):
    h = loaded(gw)
    event(h, "tell", gw=gw, text="the lamp should dim before it goes dark")
    assert gw.received[-1] == {"ch": "chat", "type": "say", "session": h.sid,
                               "text": "the lamp should dim before it goes dark"}
    tick_until(h, want="+told")
    event(h, "tell", text="")
    assert h.tick({}) == ["+tell_refused"]


def test_a_brain_without_the_chat_seat():
    g = StubGateway(chat=False).start()
    try:
        h = host(g.url)
        assert h.tick({"chat_seat": 1}) == ["-chat_seat", "+no_chat_seat"]
        event(h, "load", gw=g, package="plant")
        tick_until(h, want="+opened")
        event(h, "tell", gw=g, text="the lamp dims")
        tick_until(h, want="+tell_refused")
    finally:
        h.close()
        g.stop()


def test_the_working_copy_and_the_outcomes_retracted(gw):
    h = loaded(gw)
    assert h.tick({"clean": 1, "done(load)": 1}) == ["-done(load) 1"]
    gw.push({"ch": "repl", "type": "source", "session": h.sid, "certified": None})      # the person edited
    d = tick_until(h, {"clean": 1}, want="+dirty")
    assert d[-2:] == ["-clean", "+dirty"]
    gw.push({"ch": "repl", "type": "source", "session": h.sid, "certified": "local"})   # recompiled, not saved
    assert "+dirty" in tick_until(h, {"clean": 1}, want="+dirty")
    gw.push({"ch": "repl", "type": "source", "session": h.sid, "certified": "checkout"})
    assert tick_until(h, {"dirty": 1}, want="+clean")[-2:] == ["-dirty", "+clean"]


def test_stop_and_records(gw):
    h = loaded(gw)
    event(h, "records", gw=gw)
    assert gw.received[-1] == {"ch": "repl", "type": "records"}
    event(h, "run", gw=gw, n=5)
    event(h, "stop_run", gw=gw)
    assert gw.received[-1] == {"ch": "repl", "type": "stop", "session": h.sid}
    assert h.observe({}) != {} or h.pending == {}                # the stopped run owes no report


def test_no_console_refuses_the_tasks():
    h = repl_host.ReplHost(url="ws://127.0.0.1:9/ws")             # nothing listens there
    event(h, "load", package="plant")
    assert h.reports == ["+absent"] and "did not answer" in h.error
    event(h, "tell", text="x")
    assert h.reports[-1] == "+tell_refused"
    assert h.observe({}) == {}


def test_attach_adopts_the_pages_session(gw):
    page = host(gw.url)                         # the page opened a session itself
    event(page, "load", gw=gw, package="plant")
    tick_until(page, want="+opened")
    h = host(gw.url)
    h.connect()
    n = len(gw.received)
    h.attach(page.sid)
    end = time.time() + 5
    while len(gw.received) == n and time.time() < end:
        time.sleep(0.01)
    assert gw.received[-1] == {"ch": "repl", "type": "open", "session": page.sid}
    assert h.tick({}) == ["-unloaded", "+loaded", "+fresh", "+clean"]
    assert h.observe({}) == {"loaded": 1, "unloaded": 0}


def test_snapshot_is_json_and_restores():
    import json
    h = repl_host.ReplHost(url="ws://127.0.0.1:9/ws")
    h.sid, h.pending, h.reports, h.acted = "w1", {"nav-run-1": "run"}, ["+stopped"], ((1, "run", "intent"),)
    s = json.loads(json.dumps(h.snapshot()))
    g = repl_host.ReplHost(url="ws://127.0.0.1:9/ws")
    g.restore(s)
    assert (g.sid, g.pending, g.reports, g.acted) == (h.sid, h.pending, h.reports, h.acted)
