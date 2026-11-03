"""The backend's workspace channels (docs/WORKSPACE.md §3; loop-workspace s-5b4be5fa step 2) over a REAL socket, on a
scratch workspace: a REPL session's trace that metis.trace replays with no divergence, the trace channel's list, open,
tick and declared verbs, a surprise dropped from a session and from a trace, the bundle's STALE pushed when a member
changes after the build and the session's reload, the loop's journal tail and its child over a stub of pi's rpc."""
import asyncio
import json
import os
import shutil
import time

import pytest

websockets = pytest.importorskip("websockets")

from conftest import installed_catalog  # noqa: E402
from metis import trace as T  # noqa: E402
from metis.catalog import workspace as W  # noqa: E402
from test_gateway import Running, frames, send  # noqa: E402

from loop import workspace_ch  # noqa: E402
from loop.console_serve import ConsoleServer  # noqa: E402


def scratch(tmp_path):
    """A workspace with the catalog's three_pigs as its one domain."""
    src = installed_catalog() / "domains" / "ceptre" / "three_pigs"
    if not src.is_dir():
        src = next(installed_catalog().glob("domains/**/three_pigs/"))
    shutil.copytree(src, tmp_path / "domains" / "three_pigs",
                    ignore=shutil.ignore_patterns("records", "build", "__pycache__", "extensions"))
    return tmp_path


def opened(ws, trace=True):
    frames(ws, lambda f: f.get("type") == "catalogs")
    ws.send(json.dumps({"ch": "repl", "type": "open", "llp": "domains/three_pigs/three_pigs", "trace": trace,
                        "req": "r1"}))
    f = frames(ws, lambda f: f.get("type") in ("session", "error"))[-1]
    assert f["type"] == "session", f
    frames(ws, lambda g: g.get("type") == "source")
    return f


def ask(ws, ch, typ, **kw):
    req = "q" + str(time.monotonic_ns())
    ws.send(json.dumps({"ch": ch, "type": typ, "req": req, **kw}))
    return frames(ws, lambda f: f.get("req") == req)[-1]


@pytest.fixture
def gw(tmp_path):
    r = Running(ConsoleServer(scratch(tmp_path)), mode="personal")
    yield r
    r.close()


def test_a_session_trace_replays_with_no_divergence(gw, tmp_path):
    """open with trace: true writes .metis/traces/<session>/; inputs and rules as the commands made them, a cut at
    undo/reset; metis.trace replay on the session's program gives the record, through the declared verb too."""
    with gw.ws() as ws:
        f = opened(ws)
        sid = f["session"]
        assert f["trace"] == "traces/" + sid
        for k, cmd in enumerate(("run 3", "ctx", "step", "undo", "run 2", "reset", "run 4")):
            assert send(ws, sid, cmd, f"c{k}")[-1]["status"] in ("done", "ok"), cmd
        d = tmp_path / ".metis" / "traces" / sid
        segs = T.read(d)
        assert len(segs) == 3 and [s.header.get("cut") for s in segs] == [None, "cut", "cut"]   # undo, reset
        m = segs[0].header["members"]
        (member, info), = m.items()
        assert info["key"] == T.program_key(info["program"])
        r = T.replay(d, member, info["program"])
        assert r.divergence is None and r.rules >= 3, r.divergence
        tl = ask(ws, "trace", "list")
        assert [t["run"] for t in tl["traces"]] == [sid]
        op = ask(ws, "trace", "open", run=sid)["trace"]
        assert op["checkpoints"] == [s.k0 for s in segs]
        tick = ask(ws, "trace", "tick", run=sid, member=member, k=1)
        assert tick["exact"] is True and len(tick["fired"]) == 3
        v = ask(ws, "trace", "verb", name="trace_replay",
                args={"trace": "traces/" + sid, "member": member, "program": info["program"]})
        assert v["code"] == 0, v
        bad = ask(ws, "trace", "verb", name="trace_replay", args={"trace": "traces/" + sid, "rm": "-rf"})
        assert bad["type"] == "error" and "no parameter rm" in bad["error"]
        assert ask(ws, "trace", "verb", name="sh", args={})["type"] == "error"


def test_a_surprise_dropped_from_a_session_and_from_a_trace(gw, tmp_path):
    with gw.ws() as ws:
        sid = opened(ws)["session"]
        send(ws, sid, "run 2", "a")
        assert ask(ws, "surprise", "drop", session=sid)["type"] == "error"          # no reading, no atoms
        got = ask(ws, "surprise", "drop", session=sid, reading={"saw": "the wolf waits"}, words="it should blow")
        a = got["id"]
        b = ask(ws, "surprise", "drop", run=sid, member="three_pigs", window=[1, 2], atoms=["+houses_down"])["id"]
        ws_ = W.workspace(tmp_path)
        recs = {r["id"]: r for r in ws_.surprises()}
        assert recs[a]["trace"] == "traces/" + sid and recs[a]["k"] == 1 and recs[a]["status"] == "open"
        assert recs[a]["member"] == "three_pigs" and recs[a]["words"] == "it should blow"
        assert recs[b]["window"] == [1, 2] and recs[b]["who"] == "backend"
        assert [r["id"] for r in ask(ws, "surprise", "list")["surprises"]] == [a, b]
        ws_.rule(a, "# ruling\n\naccepted", "accepted", pack="stage main { }")
        g = ask(ws, "surprise", "get", id=a)
        assert g["surprise"]["status"] == "ruled" and g["md"].startswith("# ruling")
        assert ask(ws, "surprise", "drop", run="nope", member="x", atoms=["a"])["type"] == "error"
        kinds = [r["kind"] for r in ws_.events()]
        assert kinds.count("surprise") == 2 and "ruling" in kinds


def test_the_bundle_goes_stale_and_the_session_reloads(gw, tmp_path):
    root = tmp_path / "domains"
    (root / "composition.yaml").write_text("name: pigs\ndirect: three_pigs\n")
    (root / "build").mkdir()
    (root / "build" / "pigs.build").write_text("image build/pigs.image.v-abc123\n")
    old = time.time() - 100
    for f in [root / "composition.yaml", *(root / "three_pigs").rglob("*")]:
        os.utime(f, (old, old))
    with gw.ws() as ws:
        sid = opened(ws, trace=False)["session"]
        b = ask(ws, "bundle", "state")["bundle"]
        assert b["name"] == "pigs" and b["image"] == "abc123" and b["stale"] is False
        asyncio.run_coroutine_threadsafe(gw.gw.wsc.poll(), gw.loop).result(10)       # the watch's first look
        (root / "three_pigs" / "three_pigs.llp").write_text((root / "three_pigs" / "three_pigs.llp").read_text())
        asyncio.run_coroutine_threadsafe(gw.gw.wsc.poll(), gw.loop).result(10)
        st = frames(ws, lambda f: f.get("ch") == "bundle" and f.get("type") == "stale")[-1]
        assert st["bundle"]["stale"] is True and "three_pigs.llp" in st["bundle"]["why"]
        ws.send(json.dumps({"ch": "bundle", "type": "reload", "session": sid, "req": "rl"}))
        got = frames(ws, lambda f: f.get("req") == "rl")            # the reply follows the session's frame
        assert [f["epoch"] for f in got if f.get("type") == "session" and f.get("reload")] == [2]
        assert got[-1] == {"ch": "bundle", "type": "reload", "req": "rl", "session": sid}
        assert "reload" in [r["kind"] for r in W.workspace(tmp_path).events()]


class StubPi:
    """pi's rpc client as loop/pi_rpc.PiRpc will be: start, say, events, answer, stop, pid."""
    made = []

    def __init__(self, argv, cwd, env):
        self.argv, self.cwd, self.env = argv, cwd, env
        self.q, self.said, self.answers, self.pid = asyncio.Queue(), [], [], 4242
        StubPi.made.append(self)

    async def start(self):
        pass

    async def say(self, text):
        self.said.append(text)
        await self.q.put({"kind": "text", "text": "I take the surprise"})
        await self.q.put({"kind": "tool_call", "name": "surprise_next", "id": "t1", "args": {}})
        await self.q.put({"kind": "gate", "token": "g1", "plan": {"files": [{"path": "domains/x.llp"}]}})

    async def answer(self, token, ok):
        self.answers.append((token, ok))
        await self.q.put({"kind": "exit", "code": 0})

    async def stop(self):
        await self.q.put({"kind": "exit", "code": 0})

    async def events(self):
        while True:
            ev = await self.q.get()
            yield ev
            if ev["kind"] == "exit":
                return


def test_the_loop_channel_bridges_a_pi_child_and_tails_the_journal(gw, tmp_path):
    gw.gw.wsc.pi_factory = StubPi
    ws_ = W.workspace(tmp_path)
    with gw.ws() as ws:
        frames(ws, lambda f: f.get("type") == "catalogs")
        ev = ask(ws, "loop", "events", since=0)
        assert ev["rows"] == []
        ws_.lock("pi", pid=os.getpid(), mode="tui")                      # a TUI holds the workspace
        err = ask(ws, "loop", "start", mode="rpc", model="openrouter/x")
        assert err["type"] == "error" and "holds this workspace" in err["error"]
        ws_.unlock("pi", pid=os.getpid())
        assert ask(ws, "loop", "say", text="hi")["type"] == "error"        # no child yet
        st = ask(ws, "loop", "start", mode="rpc", model="openrouter/x", budget=0.5)
        assert st["child"]["pid"] == 4242 and st["child"]["state"] == "running"
        pi = StubPi.made[-1]
        assert pi.argv[-3:] == [str(workspace_ch.LOOP_SH), "--mode", "rpc"] and pi.env["MODEL"] == "openrouter/x"
        assert pi.env["METIS_CATALOG"] == str(tmp_path) and pi.env["METIS_LOOP_BUDGET"] == "0.5"
        assert ask(ws, "loop", "start", mode="rpc")["type"] == "error"      # one child
        ask(ws, "loop", "say", text="take the next surprise")
        gate = frames(ws, lambda f: f.get("ch") == "loop" and f.get("type") == "gate")[-1]
        assert gate["token"] == "g1" and gate["plan"]["files"][0]["path"] == "domains/x.llp"
        assert ask(ws, "loop", "confirm", token="nope")["type"] == "error"
        ask(ws, "loop", "confirm", token="g1")
        frames(ws, lambda f: f.get("ch") == "loop" and f.get("type") == "child")
        assert pi.said == ["take the next surprise"] and pi.answers == [("g1", True)]
        asyncio.run_coroutine_threadsafe(gw.gw.wsc.poll(), gw.loop).result(10)
        pushed = frames(ws, lambda f: f.get("ch") == "loop" and f.get("type") == "event"
                        and f["row"]["kind"] == "rpc_exit")
        kinds = [f["row"]["kind"] for f in pushed if f.get("type") == "event"]
        assert {"rpc_text", "rpc_tool_call", "rpc_gate"} <= set(kinds)
        state = ask(ws, "loop", "state")
        assert state["child"]["state"] == "exited" and state["loops"]["pi"] is None


def test_a_shared_instance_refuses_the_workspace(tmp_path):
    r = Running(ConsoleServer(scratch(tmp_path)), mode="shared")
    try:
        with r.ws() as ws:
            frames(ws, lambda f: f.get("type") == "catalogs")
            for ch, typ in (("trace", "list"), ("surprise", "list"), ("bundle", "state"), ("loop", "state")):
                f = ask(ws, ch, typ)
                assert f["type"] == "error" and "personal mode only" in f["error"], (ch, f)
        assert not (tmp_path / ".metis").exists()
    finally:
        r.close()
