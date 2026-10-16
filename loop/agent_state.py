"""The agent's state of each domain, for the band (human-loop s-4b71aabf
step 3): live, stale or reloaded, read from metis-agent's own console wire.

The loop gateway subscribes to the agent's /ws as a page does (hello, then
the `catalog` frames it pushes on hello and on every change; metis-agent
docs/WIRE.md) and keeps, per served domain:

  stale     the agent's row says `changed`: the files on disk differ from
            what the domain was loaded with (an apply not yet reloaded)
  reloaded  the mark cleared after it was stale: the agent runs the change
  live      served, and nothing changed since the agent started or the
            loop console began watching

Opt-in (`[console] metis_agent = "ws://127.0.0.1:8395/ws"` or
--metis-agent), personal mode only; down or absent, the band says so and
nothing else in the loop console depends on it.
"""
import asyncio
import json


class AgentState:
    def __init__(self, url: str):
        self.url = url
        self.up = False
        self.rows = {}              # domain -> {"state", "changed"}

    def update(self, domains) -> bool:
        """One `catalog` frame's rows -> True when the band would change."""
        rows = {}
        for d in domains or []:
            if not d.get("served"):
                continue
            prev = (self.rows.get(d["name"]) or {}).get("state")
            if d.get("changed"):
                st = "stale"
            elif prev in ("stale", "reloaded"):
                st = "reloaded"
            else:
                st = "live"
            rows[d["name"]] = {"state": st, "changed": d.get("changed")}
        changed = rows != self.rows or not self.up
        self.rows, self.up = rows, True
        return changed

    def frame(self) -> dict:
        return {"ch": "meta", "type": "agent", "url": self.url,
                "up": self.up, "domains": self.rows}

    async def run(self, on_change, retry=5.0):
        """Follow the agent's catalog for as long as the gateway runs;
        on_change(frame) after every change, reconnecting when it drops."""
        from websockets.asyncio.client import connect
        while True:
            try:
                async with connect(self.url, open_timeout=5,
                                   max_size=2 ** 24) as ws:
                    await ws.send(json.dumps({"ev": "hello", "since": 10 ** 12}))
                    async for raw in ws:
                        try:
                            m = json.loads(raw)
                        except ValueError:
                            continue
                        if m.get("ev") == "catalog" and self.update(m.get("domains")):
                            await on_change(self.frame())
            except asyncio.CancelledError:
                raise
            except Exception:                           # noqa: BLE001
                pass
            if self.up or self.rows:
                self.up, self.rows = False, {}
                await on_change(self.frame())
            await asyncio.sleep(retry)
