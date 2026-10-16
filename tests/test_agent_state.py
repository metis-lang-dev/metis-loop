"""The band's AGENT field (human-loop s-4b71aabf step 3): the gateway
follows metis-agent's console wire (its `catalog` frames) and tells its
pages the agent's state of each served domain — live, stale, reloaded —
or that the agent is down. Opt-in, personal mode only."""
import asyncio
import json
import threading

import pytest

websockets = pytest.importorskip("websockets")
from websockets.asyncio.server import serve  # noqa: E402

from loop.agent_state import AgentState  # noqa: E402
from test_gateway import Running, frames  # noqa: E402


def row(name, changed=None, served=True):
    return {"name": name, "served": served, "loaded": served, "state": "idle",
            "changed": changed}


def test_live_stale_reloaded():
    a = AgentState("ws://x")
    assert a.update([row("dog"), row("plant"), row("wildfire", served=False)])
    assert a.rows == {"dog": {"state": "live", "changed": None},
                      "plant": {"state": "live", "changed": None}}
    assert a.update([row("dog", "dog.llp: %% I sit down, nice and slow."), row("plant")])
    assert a.rows["dog"]["state"] == "stale" and a.rows["plant"]["state"] == "live"
    assert a.update([row("dog"), row("plant")])                  # the mark cleared: reloaded
    assert a.rows["dog"] == {"state": "reloaded", "changed": None}
    assert not a.update([row("dog"), row("plant")])              # nothing new: no frame
    assert a.rows["dog"]["state"] == "reloaded"
    a.update([row("dog", "dog.llp: x"), row("plant")])           # changed again: stale
    assert a.rows["dog"]["state"] == "stale"


class FakeAgent:
    """metis-agent's /ws as far as the band reads it: hello -> catalog,
    then a catalog on every push()."""

    def __init__(self):
        self.socks, self.domains = set(), [row("dog"), row("plant")]
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        async def handler(ws):
            self.socks.add(ws)
            try:
                async for raw in ws:
                    if json.loads(raw).get("ev") == "hello":
                        await ws.send(json.dumps({"ev": "catalog", "domains": self.domains}))
            finally:
                self.socks.discard(ws)

        def run():
            asyncio.set_event_loop(self.loop)

            async def go():
                self.stop = asyncio.Event()
                async with serve(handler, "127.0.0.1", 0) as srv:
                    self.port = srv.sockets[0].getsockname()[1]
                    ready.set()
                    await self.stop.wait()
            self.loop.run_until_complete(go())
        self.th = threading.Thread(target=run, daemon=True)
        self.th.start()
        assert ready.wait(10)
        self.url = f"ws://127.0.0.1:{self.port}/ws"

    def push(self, domains):
        self.domains = domains

        async def go():
            for ws in list(self.socks):
                await ws.send(json.dumps({"ev": "catalog", "domains": domains}))
        asyncio.run_coroutine_threadsafe(go(), self.loop).result(5)

    def close(self):
        self.loop.call_soon_threadsafe(self.stop.set)
        self.th.join(10)


def agent_frame(ws, pred):
    return frames(ws, lambda f: f.get("type") == "agent" and pred(f))[-1]


def test_the_page_follows_the_agent():
    fa = FakeAgent()
    r = Running(mode="personal", metis_agent=fa.url)
    try:
        with r.ws() as ws:
            f = agent_frame(ws, lambda f: f["up"])
            assert f["domains"]["dog"]["state"] == "live" and f["url"] == fa.url
            fa.push([row("dog", "dog.llp: %% I sit down, nice and slow."), row("plant")])
            f = agent_frame(ws, lambda f: f["domains"]["dog"]["state"] == "stale")
            assert f["domains"]["dog"]["changed"].endswith("nice and slow.")
            fa.push([row("dog"), row("plant")])
            agent_frame(ws, lambda f: f["domains"]["dog"]["state"] == "reloaded")
        fa.close()                                   # the agent goes away: down
        with r.ws() as ws:
            agent_frame(ws, lambda f: not f["up"] and f["domains"] == {})
    finally:
        r.close()


def test_off_by_default_and_never_shared():
    for cfg in ({"mode": "personal"}, {"mode": "shared", "metis_agent": "ws://127.0.0.1:9/ws"}):
        r = Running(**cfg)
        try:
            assert r.gw.agent_state is None
            with r.ws() as ws:
                fs = frames(ws, lambda f: f.get("type") == "catalogs")
                assert not any(f.get("type") == "agent" for f in fs)
        finally:
            r.close()
