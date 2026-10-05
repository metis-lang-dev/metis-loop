"""console_serve (CONSOLE §5a): sessions over the metis-catalog
checkout, one Repl each; intents through the run_intent whitelist;
epoch bumps on reset / key change."""
import pytest

from loop.console_serve import ConsoleServer, catalog_root


@pytest.fixture
def srv():
    return ConsoleServer(catalog_root())


def test_catalogs_and_resolution(srv):
    names = srv.catalogs()
    assert "domains/fiction/3lp" in names and names == sorted(names)
    assert srv.resolve("3lp").name == "3lp.llp"
    assert srv.resolve("domains/fiction/3lp.llp") == srv.resolve("3lp")
    with pytest.raises(ValueError, match="no catalog"):
        srv.resolve("nope")
    with pytest.raises(ValueError):
        srv.resolve("../../etc/passwd")


def test_open_serve_and_epoch(srv):
    s = srv.open_session("w1", {"llp": "3lp"})
    assert s["status"] == "running" and s["epoch"] == 1
    assert s["name"] == "three-pigs" and s["llp"] == "domains/fiction/3lp"
    assert s["ctx"]["fired"] == 0

    out = srv.serve_one("w1", "run 3")
    p, sess = out["posting"], out["session"]
    assert p["status"] == "done" and p["session"] == "w1"
    assert [f["name"] for f in p["json"]["fired"]] == \
        ["build_stick", "build_straw", "blow_straw"]
    assert [f["beat"] for f in p["json"]["fired"]] == [1, 2, 3]
    assert p["epoch"] == 1 and sess["ctx"]["fired"] == 3

    assert srv.serve_one("w1", ":accept")["posting"]["status"] == "refused"
    out = srv.serve_one("w1", "reset")
    assert out["posting"]["epoch"] == 2 and out["session"]["epoch"] == 2
    assert out["session"]["ctx"]["base"] == 3      # graph rebased


def test_sessions_are_independent(srv):
    srv.open_session("a", {"llp": "3lp"})
    srv.open_session("b", {"llp": "herstory"})
    srv.serve_one("a", "run 6")
    assert srv.shells["b"].ctx()["fired"] == 0
    assert srv.serve_one("b", "step")["session"]["name"] == "herstory"
    assert srv.close_session("a")["status"] == "closed"
    assert srv.serve_one("a", "ctx")["posting"]["status"] == "error"


def test_bad_llp_closes_the_session(srv):
    s = srv.open_session("x", {"llp": "nope"})
    assert s["status"] == "closed" and "no catalog" in s["error"]


def test_drain_is_a_pure_rows_to_writes_mapping(srv):
    """The serving session's whole job: rows in, update-writes out.
    Opening binds, queued intents serve oldest first, writes to one
    doc merge; a live session without an interpreter (server restart)
    re-binds with epoch + 1."""
    w = srv.drain([{"id": "s1", "data": {"llp": "3lp", "status": "opening"}}],
                  [{"id": "i2", "session": "s1", "cmd": ":step",
                    "status": "queued", "ts": "2"},
                   {"id": "i1", "session": "s1", "cmd": ":run 2",
                    "status": "queued", "ts": "1"},
                   {"id": "i0", "session": "s1", "cmd": ":ctx",
                    "status": "done", "ts": "0"}])
    by = {x["path"]: x["data"] for x in w}
    assert list(by) == ["sessions/s1", "intents/i1", "intents/i2"]
    assert by["intents/i1"]["json"]["fired"][0]["i"] == 1
    assert by["intents/i2"]["json"]["fired"][0]["i"] == 3   # after i1
    assert by["sessions/s1"]["ctx"]["fired"] == 3            # merged
    fresh = ConsoleServer(srv.root)                          # "restart"
    w2 = fresh.drain([("s1", {"llp": "domains/fiction/3lp",
                              "status": "running", "epoch": 4})], [])
    s = w2[0]["data"]
    assert s["epoch"] == 5 and s["ctx"]["fired"] == 0 and "reopened" in s
    assert fresh.catalogs_doc()["path"] == "meta/catalogs"


def test_open_session_from_source_in_memory(srv, tmp_path, monkeypatch):
    """CONSOLE-WS §4a from day one: {source, name} compiles catalog TEXT
    in memory — the same kernel, no file written anywhere."""
    src = (srv.resolve("3lp")).read_text().replace(
        "#init pig 3", "#init pig 1")
    monkeypatch.chdir(tmp_path)
    before = set(srv.root.rglob("*"))
    s = srv.open_session("f1", {"source": src, "name": "domains/fiction/3lp"})
    assert s["status"] == "running" and s["llp"].endswith("(in memory)")
    assert s["ctx"]["counts"]["pig"] == 1                 # the edited text
    out = srv.serve_one("f1", "run 6")["posting"]
    assert out["status"] == "done"
    assert set(srv.root.rglob("*")) == before and not any(tmp_path.iterdir())
    bad = srv.open_session("f2", {"source": "stage go {", "name": "x"})
    assert bad["status"] == "closed" and bad["error"]
    big = srv.open_session("f3", {"source": "%" * (300 * 1024)})
    assert "KiB" in big["error"]
    scratch = srv.open_session("f4", {"source": src, "name": "my fork!"})
    assert scratch["status"] == "running"
