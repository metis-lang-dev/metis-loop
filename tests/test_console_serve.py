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
