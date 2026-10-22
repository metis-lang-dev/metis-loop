"""The console gateway (docs/CONSOLE-WS.md, step 1): the protocol over
a REAL socket — sessions, the queue, busy/stop, re-attach with the
in-memory log, run caps — and the shared-mode policy: token (D2), LLM
seats and chat refused, per-IP session cap, rate limit."""
import asyncio
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

websockets = pytest.importorskip("websockets")
from websockets.sync.client import connect  # noqa: E402

from loop.console_serve import ConsoleServer  # noqa: E402
from loop.gateway import DEFAULTS, Gateway, load_config  # noqa: E402


class Running:
    """A gateway on an ephemeral port in a background event loop."""

    def __init__(self, srv=None, **cfg):
        self.gw = Gateway(dict(DEFAULTS, port=0, **cfg), srv)
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        def run():
            asyncio.set_event_loop(self.loop)
            self.stop = asyncio.Event()
            r = asyncio.Event()

            async def go():
                t = asyncio.create_task(self.gw.serve(r, self.stop))
                await r.wait()
                ready.set()
                await t
            self.loop.run_until_complete(go())
        self.th = threading.Thread(target=run, daemon=True)
        self.th.start()
        assert ready.wait(10)
        self.url = f"127.0.0.1:{self.gw.port}"

    def ws(self, token=""):
        q = f"?token={token}" if token else ""
        return connect(f"ws://{self.url}/ws{q}", open_timeout=5)

    def close(self):
        self.loop.call_soon_threadsafe(self.stop.set)
        self.th.join(10)


def frames(ws, until, timeout=20):
    """Collect frames until `until(frame)` is true; returns them."""
    out, end = [], time.time() + timeout
    while time.time() < end:
        f = json.loads(ws.recv(timeout=max(0.1, end - time.time())))
        out.append(f)
        if until(f):
            return out
    raise AssertionError(f"timed out; got {out[-5:]}")


def open3(ws, llp="three_pigs"):
    frames(ws, lambda f: f.get("type") == "catalogs")
    ws.send(json.dumps({"ch": "repl", "type": "open", "llp": llp,
                        "req": "r1"}))
    f = frames(ws, lambda f: f.get("type") in ("session", "error"))[-1]
    if f.get("type") == "session":            # then the working copy (§4a)
        frames(ws, lambda g: g.get("type") == "source")
    return f


def send(ws, sid, cmd, iid):
    ws.send(json.dumps({"ch": "repl", "type": "intent", "session": sid,
                        "id": iid, "cmd": cmd, "actor": "viewer"}))
    return frames(ws, lambda f: f.get("type") == "posting"
                  and f.get("id") == iid)


@pytest.fixture
def personal():
    r = Running(mode="personal")
    yield r
    r.close()


def test_round_trip_queue_posting_and_reattach(personal):
    with personal.ws() as ws:
        man = json.loads(ws.recv(timeout=5))
        assert man["type"] == "manifest" and man["mode"] == "personal"
        # repl-tools step 4: the declared verbs carry the REPL API's lines
        from metis.lang.repl_api import REPL_API
        assert man["verbs"] == {t["name"]: t["description"] for t in REPL_API
                                if t["served_by"] in ("repl", "watch")}
        s = open3(ws)
        assert (s["type"], s["req"], s["status"]) == \
            ("session", "r1", "running")
        sid = s["session"]
        got = send(ws, sid, "run 3", "i1")
        kinds = [f["type"] for f in got]
        assert kinds[0] == "queued" and "session" in kinds
        assert any(f["type"] == "session" and f["busy"] for f in got)
        post = got[-1]
        assert post["status"] == "done" and post["epoch"] == 1
        assert [x["name"] for x in post["json"]["fired"]] == \
            ["build_stick", "build_straw", "blow_straw"]
        assert send(ws, sid, ":accept", "i2")[-1]["status"] == "refused"
    with personal.ws() as ws2:                      # reload / new window
        frames(ws2, lambda f: f.get("type") == "catalogs")
        ws2.send(json.dumps({"ch": "repl", "type": "open", "session": sid}))
        got = frames(ws2, lambda f: f.get("type") == "posting"
                     and f.get("id") == "i2")
        assert got[0]["type"] == "session" and got[0]["ctx"]["fired"] == 3
        assert [f["id"] for f in got if f["type"] == "posting"] == \
            ["i1", "i2"]                            # the in-memory log
        ws2.send(json.dumps({"ch": "repl", "type": "open",
                             "session": "wnope"}))
        assert frames(ws2, lambda f: f.get("type") == "error")[-1][
            "error"] == "gone"


def test_run_cap_and_chat_seat_precedence():
    """Precedence, pinned: with no agent seat the seat reason wins over
    "open a session first" (a session cannot fix a missing seat). The
    seat is disabled by config so this holds with or without the SDK;
    the session check itself is tested with the seat present
    (test_agent_service)."""
    r = Running(mode="personal", max_run_steps=2, agent=False)
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            post = send(ws, sid, "run 50", "i1")[-1]
            assert len(post["json"]["fired"]) == 2
            assert post["result"].startswith("(run capped at 2 steps)")
            ws.send(json.dumps({"ch": "chat", "type": "say", "text": "hi"}))
            err = frames(ws, lambda f: f.get("ch") == "chat")[-1]
            assert err["error"] == ("agent chat unavailable here: "
                                    "agent disabled in [console]")
    finally:
        r.close()


class SlowServer(ConsoleServer):
    """serve_one that spins in Python until interrupted (stop test)."""

    def serve_one(self, sid, cmd):
        if "slow" in cmd:
            end = time.time() + 30
            while time.time() < end:
                time.sleep(0.01)
        return super().serve_one(sid, cmd)


def test_stop_interrupts_the_running_command_and_drops_the_queue():
    r = Running(srv=SlowServer(), mode="personal")
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            for iid, cmd in (("a", ":ctx slow"), ("b", ":ctx")):
                ws.send(json.dumps({"ch": "repl", "type": "intent",
                                    "session": sid, "id": iid, "cmd": cmd}))
            frames(ws, lambda f: f.get("type") == "session" and f["busy"])
            t0 = time.time()
            ws.send(json.dumps({"ch": "repl", "type": "stop",
                                "session": sid}))
            got = frames(ws, lambda f: f.get("type") == "posting"
                         and f.get("id") == "a")
            assert time.time() - t0 < 5
            posts = {f["id"]: f for f in got if f["type"] == "posting"}
            assert posts["b"]["result"] == "cancelled (stop)"
            assert posts["a"]["json"]["error"] == "stopped"
            after = send(ws, sid, "run 1", "c")[-1]   # still serves
            assert after["status"] == "done"
    finally:
        r.close()


def test_shared_mode_token_llm_seats_chat_caps_and_rate():
    r = Running(mode="shared", token="s3cret", max_sessions_per_ip=1,
                rate_per_min=6, artifact_url="https://example.invalid/a")
    try:
        base = f"http://{r.url}/"
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base, timeout=5)
        assert e.value.code == 403
        page = urllib.request.urlopen(base + "?token=s3cret",
                                      timeout=5).read().decode()
        assert "window.LOOP_GATEWAY" in page and '"mode": "shared"' in page
        with pytest.raises(Exception):
            r.ws().close()                          # no token: refused
        with r.ws("s3cret") as ws:
            man = json.loads(ws.recv(timeout=5))
            assert man["seats"]["chat"] is None
            assert man["seats"]["narrate"] is None
            assert man["chat_pointer"] == "https://example.invalid/a"
            sid = open3(ws)["session"]
            for k, verb in enumerate(("narrate", "formalize x", "llm")):
                p = send(ws, sid, verb, f"n{k}")[-1]
                assert p["status"] == "refused" and "credentials" in \
                    p["result"]
            ws.send(json.dumps({"ch": "chat", "type": "say", "text": "x"}))
            assert "not served" in frames(
                ws, lambda f: f.get("ch") == "chat")[-1]["error"]
            ws.send(json.dumps({"ch": "repl", "type": "open", "llp": "three_pigs",
                                "req": "r2"}))
            err = frames(ws, lambda f: f.get("type") == "error")[-1]
            assert "session cap" in err["error"]
            # 6/min: open, 3 LLM-verb intents, the refused 2nd open = 5
            # counted; q0 is the 6th, q1 trips the limit
            for k in range(2):
                ws.send(json.dumps({"ch": "repl", "type": "intent",
                                    "session": sid, "id": f"q{k}",
                                    "cmd": ":ctx"}))
            err = frames(ws, lambda f: f.get("type") == "error"
                         and "rate" in f.get("error", ""))[-1]
            assert err["id"] == "q1"
    finally:
        r.close()


def test_config_layers_and_mode_validation():
    cfg = load_config(port=9999, mode=None)
    assert cfg["port"] == 9999 and cfg["mode"] in ("personal", "shared")
    with pytest.raises(ValueError):
        load_config(mode="public")


def test_open_from_source_over_the_socket(personal):
    """§4a's open frame: catalog TEXT compiled in memory."""
    from loop.console_serve import catalog_root
    src = (catalog_root() / "domains/ceptre/three_pigs/three_pigs.llp").read_text()
    with personal.ws() as ws:
        frames(ws, lambda f: f.get("type") == "catalogs")
        ws.send(json.dumps({"ch": "repl", "type": "open", "req": "s1",
                            "source": src.replace("#init pig 3",
                                                  "#init pig 2"),
                            "name": "domains/ceptre/three_pigs/three_pigs"}))
        f = frames(ws, lambda f: f.get("type") in ("session", "error"))[-1]
        assert f["type"] == "session" and f["llp"].endswith("(in memory)")
        assert f["ctx"]["counts"]["pig"] == 2


def test_vendor_bundles_served_and_nothing_else():
    r = Running()
    try:
        for name in ("codemirror.js", "viz.js"):
            with urllib.request.urlopen(f"http://{r.url}/vendor/{name}") as f:
                assert f.status == 200 and "javascript" in f.headers["Content-Type"]
        for bad in ("VERSIONS.txt", "nope.js", "..%2Fgateway.py", "x/../viz.js"):
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://{r.url}/vendor/{bad}")
    finally:
        r.close()


def test_the_shell_served_without_the_token():
    """/lib/: the page's shell (console/lib/shell.css, shell.js) — public
    code, served before the token check; flat names of the library only."""
    r = Running(mode="shared", token="t0k")
    try:
        for name, ctype in (("shell.css", "text/css"), ("shell.js", "javascript")):
            with urllib.request.urlopen(f"http://{r.url}/lib/{name}") as f:
                assert f.status == 200 and ctype in f.headers["Content-Type"]
                assert b"MetisShell" in f.read() or name == "shell.css"
        for bad in ("nope.css", "..%2F..%2Fpackage.json", "fixtures/x.json", ".hidden.js"):
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://{r.url}/lib/{bad}")
        with pytest.raises(urllib.error.HTTPError):          # the page itself still needs it
            urllib.request.urlopen(f"http://{r.url}/")
    finally:
        r.close()


def test_the_catalog_widget_served_from_the_sdk():
    """/sdk/catalog/: the loop SDK's CATALOG widget (catalog-sdk s-bc1718e3),
    the installed package's bytes — public code, before the token check; its
    two files only."""
    from metis_loop_sdk import web
    r = Running(mode="shared", token="t0k")
    try:
        for name, ctype in (("catalog.js", "javascript"), ("catalog.css", "text/css")):
            with urllib.request.urlopen(f"http://{r.url}/sdk/catalog/{name}") as f:
                assert f.status == 200 and ctype in f.headers["Content-Type"]
                assert f.read().decode() == (web.WIDGET_DIR / name).read_text()
        for bad in ("catalog.py", "..%2Fcatalog.py", "nope.js", ""):
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://{r.url}/sdk/catalog/{bad}")
    finally:
        r.close()


def test_shared_mode_never_shows_the_operators_paths():
    """Web output names catalogs relative to the checkout
    ("domains/ceptre/three_pigs/three_pigs.llp"), never the operator's filesystem — every
    frame of a shared-mode round trip, file-bearing verbs included."""
    from pathlib import Path
    r = Running(mode="shared", token="t0k")
    roots = {str(r.gw.srv.root), str(r.gw.srv.root.resolve()),
             str(Path.home())}
    try:
        with r.ws("t0k") as ws:
            got = frames(ws, lambda f: f.get("type") == "catalogs")
            ws.send(json.dumps({"ch": "repl", "type": "open", "llp": "three_pigs"}))
            got += frames(ws, lambda f: f.get("type") == "source")
            sid = [f for f in got if f.get("type") == "session"][-1]["session"]
            for k, cmd in enumerate(["run 2", "list", "ctx", "state", "why",
                                     "graph", "show llp", "findings",
                                     "edit build_stick", "nope"]):
                got += send(ws, sid, cmd, f"p{k}")
        text = json.dumps(got)
        assert "domains/ceptre/three_pigs/three_pigs.llp" in text
        assert "/home/" not in text
        for root in roots:
            assert root not in text, root
    finally:
        r.close()


def test_interventions_served_in_shared_mode_and_whatif_run_capped():
    """Spec 10 P5: do/fork/back/whatif/necessity/sufficiency are
    session-local REPL verbs — a shared nook serves them like run/step
    (no LLM, no paths); `whatif … run N` obeys the run cap."""
    r = Running(mode="shared", token="t0k", max_run_steps=3)
    try:
        with r.ws("t0k") as ws:
            sid = open3(ws)["session"]
            send(ws, sid, "run 3", "a")
            p = send(ws, sid, "whatif 1 do(~blow_stick) run 50", "b")[-1]
            assert p["status"] == "done"
            assert p["result"].startswith("(whatif run capped at 3 steps)")
            assert "WHATIF at #1  do(~blow_stick)  ·  run 3 " in p["result"]
            p = send(ws, sid, "necessity 1", "c")[-1]
            assert p["status"] == "done"
            assert p["result"].startswith(("NECESSITY of #1 ",
                                           "necessity 1 needs an ATOM"))
            for k, cmd in enumerate(["do ~blow_stick", "fork 1", "back",
                                     "sufficiency 1 stickhouse"]):
                p = send(ws, sid, cmd, f"d{k}")[-1]
                assert p["status"] == "done", (cmd, p)
    finally:
        r.close()


def test_the_copy_of_a_domain_carries_its_extensions(tmp_path):
    """human-loop step 1: the one-click open's working copy is the program
    AND its extensions (the served program), certified as the catalog's."""
    from loop.console_serve import ConsoleServer
    from test_workflow_files import SOIL, VISITOR
    srv = ConsoleServer(tmp_path)
    llp = srv.new_domain("plant", "a plant")
    d = tmp_path / "domains/plant"
    (d / "plant.llp").write_text(SOIL)
    (d / "extensions").mkdir()
    (d / "extensions/visitor.llp").write_text(VISITOR)
    r = Running(srv, mode="personal")
    try:
        with r.ws() as ws:
            frames(ws, lambda f: f.get("type") == "catalogs")
            ws.send(json.dumps({"ch": "repl", "type": "open", "llp": llp, "req": "r1"}))
            src = frames(ws, lambda f: f.get("type") == "source")[-1]
            assert src["extensions"] == [{"name": "visitor", "source": VISITOR}] and src["certified"] == "checkout"
    finally:
        r.close()


def test_a_gateway_started_in_an_empty_dir_serves_it(tmp_path, monkeypatch):
    """cwd-root s-ddac2cbf through the wire: started in an empty directory
    (no METIS_CATALOG), the greeting lists no domain and no catalog; `new`
    writes domains/<name>/ there, the panel's list then shows it, and it opens."""
    monkeypatch.delenv("METIS_CATALOG", raising=False)
    monkeypatch.chdir(tmp_path)
    r = Running(mode="personal")
    try:
        assert r.gw.srv.root == tmp_path.resolve()
        with r.ws() as ws:
            hello = frames(ws, lambda f: f.get("type") == "catalogs")
            assert [f["domains"] for f in hello if f.get("type") == "domains"] == [[]]
            assert [f["readme"] for f in hello if f.get("type") == "readme"] == [None]     # no README.md
            assert hello[-1]["names"] == []
            ws.send(json.dumps({"ch": "repl", "type": "new", "name": "lamp", "line": "a lamp", "req": "n1"}))
            got = frames(ws, lambda f: f.get("type") == "source")
            doms = [f["domains"] for f in got if f.get("type") == "domains"]
            assert [e["name"] for e in doms[-1]] == ["lamp"]
            assert (tmp_path / "domains/lamp/lamp.llp").is_file()
    finally:
        r.close()
