"""domains/repl's host against the stub gateway (console-nav s-b923ebfe): the frame each
event sends, the report each answer becomes at a later tick, the pairs it keeps, the
sensor face. No kernel, no model (the program's side: test_console_domains.py)."""
import contextlib
import importlib.util
import json
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


def host(url, own=True):
    h = repl_host.ReplHost(url=url, own_sessions=own)
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
    assert h.effects == []                                        # own sessions: nothing for a page
    assert h.observe({}) == {"loaded": 1, "unloaded": 0}
    event(h, "load_switch", gw=gw, package="Love Triangle")
    assert gw.received[-1]["llp"] == "domains/ceptre/love_triangle/love_triangle"


def test_a_name_twice_loads_the_domain():
    """The console lists a domain and a golden case of one name (domains/plant/plant and
    goldens/cases/plant): "load the plant" means the domain, with its host, whichever comes last."""
    h = repl_host.ReplHost(url="ws://127.0.0.1:9/ws")
    rows = [{"name": "plant", "path": "domains/plant/plant", "host": "plant_host.py:make"},
            {"name": "plant", "path": "goldens/cases/plant", "host": None}]
    for order in (rows, rows[::-1]):
        h._frame_in({"ch": "meta", "type": "domains", "domains": order})
        assert h.domains["plant"]["path"] == "domains/plant/plant"


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
    h = repl_host.ReplHost(url="ws://127.0.0.1:9/ws", own_sessions=True)   # nothing listens there
    event(h, "load", package="plant")
    assert h.reports == ["+absent"] and "did not answer" in h.error
    event(h, "tell", text="x")
    assert h.reports[-1] == "+tell_refused"
    event(h, "load_switch_ran", package="plant")
    assert h.reports[-1] == "+absent"
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


# -- the person's session (the live mode): the page opens, says and shows; the host attaches --

def attached(h, gw, sid):
    """h attaches to the page's session, and the stub has the attach frame."""
    n = len(gw.received)
    h.attach(sid)
    end = time.time() + 5
    while len(gw.received) == n and time.time() < end:
        time.sleep(0.01)


@contextlib.contextmanager
def page_open(gw, llp):
    """A page: its own socket opens the package (the page's session)."""
    from websockets.sync.client import connect
    with connect(gw.url) as ws:
        while json.loads(ws.recv(timeout=5)).get("type") != "catalogs":
            pass
        ws.send(json.dumps({"ch": "repl", "type": "open", "llp": llp, "req": "page-1"}))
        while True:
            f = json.loads(ws.recv(timeout=5))
            if f.get("type") == "session":
                yield ws, f["session"]
                return




def test_a_load_is_the_pages_open_then_its_session_attached(gw):
    h = host(gw.url, own=False)
    h.connect()
    n = len(gw.received)
    event(h, "load", package="the plant")
    assert len(gw.received) == n                                   # nothing opened by the host
    assert h.effects == [{"repl": "open", "llp": "domains/plant/plant", "host": True, "req": h.effects[0]["req"]}]
    assert h.observe({}) == {}                                    # in flight
    with page_open(gw, h.effects[0]["llp"]) as (ws, sid):                   # the page carries it out
        attached(h, gw, sid)
        assert h.tick({}) == ["+opened"] and h.sid == sid
        assert h.observe({}) == {"loaded": 1, "unloaded": 0}
        event(h, "run", gw=gw, n=3)                                    # the person's session, driven
        assert gw.received[-1]["session"] == sid
        tick_until(h, want="+stopped")


def test_the_activate_bindings_name_the_socket_and_the_session(gw):
    """step 2: the page's activate bindings (metis-agent's take_bindings): the gateway's socket
    and token as the page reaches it, then its session attached; a load the page could not
    carry out is +absent through them too."""
    h = host(gw.url, own=False)                                  # the socket the agent started with, no token
    h.connect()
    event(h, "load", package="the plant")
    with page_open(gw, h.effects[0]["llp"]) as (ws, sid):
        n = len(gw.received)
        h.take_bindings({"ws": gw.url, "token": "tk", "session": sid})
        end = time.time() + 5
        while len(gw.received) == n and time.time() < end:
            time.sleep(0.01)
        assert h.url == gw.url + "?token=tk" and h.sid == sid
        assert gw.received[-1] == {"ch": "repl", "type": "open", "session": sid}
        assert h.tick({}) == ["+opened"]
        n = len(gw.received)
        h.take_bindings({"token": "tk", "session": sid})            # the same again: no second attach
        assert h.url == gw.url + "?token=tk" and len(gw.received) == n
    g = host(gw.url, own=False)
    event(g, "load", package="plant")
    g.take_bindings({"open_failed": "no such catalog file"})
    assert g.tick({}) == ["+absent"] and g.error == "no such catalog file"


def test_a_load_over_an_open_session_is_the_pages_open_too(gw):
    """repl.llp v3's switch rules (load_switch_fresh, load_switch_ran) open the package as load
    does: the page's open, then its new session attached (+opened); found live in step 2."""
    for rule in ("load_switch_fresh", "load_switch_ran"):
        h = host(gw.url, own=False)
        h.connect()
        event(h, rule, package="the plant")
        assert h.effects == [{"repl": "open", "llp": "domains/plant/plant", "host": True, "req": h.effects[0]["req"]}], rule
        with page_open(gw, h.effects[0]["llp"]) as (ws, sid):
            attached(h, gw, sid)
            assert "+opened" in h.tick({}), rule


def test_a_load_the_page_could_not_open_is_absent(gw):
    h = host(gw.url, own=False)
    event(h, "load", package="plant")
    h.open_failed("no such catalog file")
    assert h.tick({}) == ["+absent"] and h.error == "no such catalog file"


def test_tell_is_the_pages_and_told_when_the_chat_has_it(gw):
    h = host(gw.url, own=False)
    with page_open(gw, "domains/plant/plant") as (ws, sid):
        h.connect()
        attached(h, gw, sid)
        h.tick({})
        event(h, "tell", text="the lamp dims first")
        eff = h.effects[-1]
        assert eff == {"repl": "tell", "id": eff["id"], "text": "the lamp dims first"}
        ws.send(json.dumps({"ch": "chat", "type": "say", "session": sid, "text": "the lamp should dim before it goes dark"}))
        tick_until(h, want="+told")                                    # the chat's user frame, broadcast to the session
        event(h, "tell", text="again")
        seen = []
        for _ in range(repl_host.TELL_WAIT + 1):                       # the page never posts: refused after the wait
            seen += h.tick({})
        assert "+tell_refused" in seen


def test_apply_asks_for_the_plan_and_the_page_opens_its_dialog(gw):
    h = host(gw.url, own=False)
    with page_open(gw, "domains/plant/plant") as (ws, sid):
        h.connect()
        attached(h, gw, sid)
        h.tick({})
        event(h, "apply", gw=gw)
        assert gw.received[-1] == {"ch": "repl", "type": "save", "session": sid}
        assert h.effects[-1] == {"repl": "apply", "session": sid}
        tick_until(h, want="+plan_shown")
        assert gw.written == []
