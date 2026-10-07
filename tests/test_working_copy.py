"""The working copy (docs/CONSOLE-WS.md §4a, simplified): on open the
catalog text is the session's copy; edits and extension packs mirror to
the gateway's memory and uncertify it; `recompile` rebuilds the session
from copy + packs (each pack gated as a pack, merged in memory, never
committed) — on failure the old world is kept and the error shown."""
import json

import pytest

from loop.console_serve import ConsoleServer, catalog_root

PACK = """% the pigs tire: a pack on top of the copy
catalog three-pigs-ext1 1.
extends three-pigs.
provenance hand "web console" "2026-10-07".
namespace ext1 produce (story).
pred example1 : ext1.
stage go {
  %% an example rule the pack adds
  example1 [story] : example1 -o example1.
}
"""
# undocumented rule: the pack gate rejects it (a genuine finding, not
# the namespace-rights question)
BAD = """% broken on purpose
catalog bad 1.
extends three-pigs.
provenance hand "test" "2026-10-07".
stage go {
  ghost_rule [story] : nosuchpred -o nosuchpred2.
}
"""


@pytest.fixture
def srv():
    return ConsoleServer(catalog_root())


def test_build_from_source_with_a_pack(srv):
    src = srv.resolve("3lp").read_text()
    r, label, reps = srv.build({"source": src, "name": "three-pigs",
                                "packs": [{"name": "tired", "source": PACK}]})
    assert label == "three-pigs (in memory + 1 pack)"
    assert reps[0]["name"] == "tired" and reps[0]["ok"]
    out = srv.open_session("w2", {"source": src, "name": "three-pigs",
                                  "packs": [{"name": "tired", "source": PACK}]})
    assert out["status"] == "running"
    listed = srv.serve_one("w2", "list")["posting"]["result"]
    assert "example1" in listed and "blow_brick" in listed
    # the checkout file is untouched
    assert "example1" not in srv.resolve("3lp").read_text()


def test_build_rejects_a_bad_pack_and_open_keeps_the_old_world(srv):
    src = srv.resolve("3lp").read_text()
    with pytest.raises(ValueError, match="pack 'bad' not admitted: .*%% doc"):
        srv.build({"source": src, "packs": [{"name": "bad", "source": BAD}]})
    assert srv.open_session("w1", {"llp": "3lp"})["status"] == "running"
    key = srv.shells["w1"].key
    out = srv.open_session("w1", {"source": src, "packs": [
        {"name": "bad", "source": BAD}]})
    assert out["status"] == "closed" and "not admitted" in out["error"]
    assert srv.shells["w1"].key == key            # old interpreter kept


websockets = pytest.importorskip("websockets")
from test_gateway import Running, frames, open3  # noqa: E402


@pytest.fixture
def gw():
    r = Running(mode="personal", agent=False)
    yield r
    r.close()


def _open(ws):
    frames(ws, lambda f: f.get("type") == "catalogs")
    ws.send(json.dumps({"ch": "repl", "type": "open", "llp": "3lp"}))
    got = frames(ws, lambda f: f.get("type") == "source")
    return [f for f in got if f.get("type") == "session"][-1], got[-1]


def test_source_frame_work_mirror_and_recompile(gw):
    with gw.ws() as a, gw.ws() as b:
        sess, src = _open(a)
        sid = sess["session"]
        assert src["certified"] == "checkout" and src["packs"] == []
        assert "catalog three-pigs" in src["copy"] and src["key"]
        frames(b, lambda f: f.get("type") == "catalogs")
        b.send(json.dumps({"ch": "repl", "type": "open", "session": sid}))
        frames(b, lambda f: f.get("type") == "source")

        a.send(json.dumps({"ch": "repl", "type": "work", "session": sid,
                           "copy": src["copy"] + "\n% an edit\n",
                           "packs": [{"name": "tired", "source": PACK}]}))
        m = frames(b, lambda f: f.get("type") == "source")[-1]
        assert m["certified"] is None and m["packs"][0]["name"] == "tired"
        assert m["copy"].endswith("% an edit\n")

        a.send(json.dumps({"ch": "repl", "type": "recompile",
                           "session": sid}))
        got = frames(a, lambda f: f.get("type") == "source")
        s2 = [f for f in got if f.get("type") == "session"][-1]
        assert s2.get("recompiled") and s2["epoch"] == sess["epoch"] + 1
        assert got[-1]["certified"] == "local" and got[-1]["error"] is None
        assert got[-1]["key"] != src["key"]
        a.send(json.dumps({"ch": "repl", "type": "intent", "session": sid,
                           "id": "i1", "cmd": "list", "actor": "viewer"}))
        p = frames(a, lambda f: f.get("type") == "posting"
                   and f.get("id") == "i1")[-1]
        assert p["status"] == "done" and "example1" in p["result"]


def test_recompile_failure_keeps_the_session(gw):
    with gw.ws() as a:
        sess, src = _open(a)
        sid = sess["session"]
        a.send(json.dumps({"ch": "repl", "type": "work", "session": sid,
                           "packs": [{"name": "bad", "source": BAD}]}))
        a.send(json.dumps({"ch": "repl", "type": "recompile",
                           "session": sid}))
        m = frames(a, lambda f: f.get("type") == "source")[-1]
        assert "not admitted" in m["error"] and m["certified"] is None
        assert m["key"] == src["key"]                 # old world kept
        a.send(json.dumps({"ch": "repl", "type": "intent", "session": sid,
                           "id": "i1", "cmd": "run 1", "actor": "viewer"}))
        p = frames(a, lambda f: f.get("type") == "posting"
                   and f.get("id") == "i1")[-1]
        assert p["status"] == "done" and p["epoch"] == sess["epoch"]


def test_open3_helper_still_sees_checkout_copy(gw):
    with gw.ws() as a:
        assert open3(a)["status"] == "running"
