"""The console dev harness (console/dev_serve.py): its in-memory store
answers the page's queries, and one drain pass does what the serving
session does — bind the opening session, serve the queued intent."""
import importlib.util
from pathlib import Path

from loop.console_serve import ConsoleServer

spec = importlib.util.spec_from_file_location(
    "dev_serve", Path(__file__).resolve().parents[1] / "console/dev_serve.py")
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


def test_store_query_where_order_limit():
    st = dev.Store()
    for k, (sid, ts) in enumerate([("a", "1"), ("b", "2"), ("a", "3")]):
        st.op({"op": "set", "path": f"intents/i{k}",
               "data": {"session": sid, "ts": ts}})
    st.op({"op": "set", "path": "intents/i9/sub/x", "data": {"ts": "9"}})
    got = st.op({"op": "query", "path": "intents",
                 "q": {"where": [["session", "==", "a"]],
                       "orderBy": ["ts", "desc"], "limit": 5}})["docs"]
    assert [d["id"] for d in got] == ["i2", "i0"]
    assert st.op({"op": "get", "path": "intents/nope"}) == \
        {"exists": False, "data": None}
    assert "error" in st.op({"op": "update", "path": "intents/nope",
                             "data": {}})


def test_drain_once_opens_and_serves():
    st, srv = dev.Store(), ConsoleServer()
    st.docs["sessions/s1"] = {"llp": "3lp", "status": "opening", "ts": "0"}
    st.docs["intents/i1"] = {"session": "s1", "cmd": ":run 3",
                             "status": "queued", "ts": "1"}
    dev.drain_once(st, srv)
    s = st.docs["sessions/s1"]
    i = st.docs["intents/i1"]
    assert s["status"] == "running" and s["ctx"]["fired"] == 3
    assert i["status"] == "done" and i["epoch"] == 1
    assert [f["beat"] for f in i["json"]["fired"]] == [1, 2, 3]
