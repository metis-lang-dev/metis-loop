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
    assert "domains/ceptre/three_pigs/three_pigs" in names and names == sorted(names)
    assert srv.resolve("three_pigs").name == "three_pigs.llp"
    assert srv.resolve("domains/ceptre/three_pigs/three_pigs.llp") == srv.resolve("three_pigs")
    with pytest.raises(ValueError, match="no catalog"):
        srv.resolve("nope")
    with pytest.raises(ValueError):
        srv.resolve("../../etc/passwd")


def test_open_serve_and_epoch(srv):
    s = srv.open_session("w1", {"llp": "three_pigs"})
    assert s["status"] == "running" and s["epoch"] == 1
    assert s["name"] == "three-pigs" and s["llp"] == "domains/ceptre/three_pigs/three_pigs"
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
    srv.open_session("a", {"llp": "three_pigs"})
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
    w = srv.drain([{"id": "s1", "data": {"llp": "three_pigs", "status": "opening"}}],
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
    w2 = fresh.drain([("s1", {"llp": "domains/ceptre/three_pigs/three_pigs",
                              "status": "running", "epoch": 4})], [])
    s = w2[0]["data"]
    assert s["epoch"] == 5 and s["ctx"]["fired"] == 0 and "reopened" in s
    assert fresh.catalogs_doc()["path"] == "meta/catalogs"


def test_open_session_from_source_in_memory(srv, tmp_path, monkeypatch):
    """CONSOLE-WS §4a from day one: {source, name} compiles catalog TEXT
    in memory — the same kernel, no file written anywhere."""
    src = (srv.resolve("three_pigs")).read_text().replace(
        "#init pig 3", "#init pig 1")
    monkeypatch.chdir(tmp_path)
    before = set(srv.root.rglob("*"))
    s = srv.open_session("f1", {"source": src, "name": "domains/ceptre/three_pigs/three_pigs"})
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


def test_an_empty_cwd_is_an_empty_catalog(tmp_path, monkeypatch):
    """cwd-root s-ddac2cbf: `cd DIR && metis-loop` over an empty DIR — the
    console serves the cwd, lists nothing, `new` writes domains/<name>/, the
    list then shows it; the loop's own .metis/ is never a catalog nor a
    records file of the console, and an in-memory copy anchors under it."""
    monkeypatch.delenv("METIS_CATALOG", raising=False)
    monkeypatch.chdir(tmp_path)
    srv = ConsoleServer()
    assert srv.root == tmp_path.resolve()
    assert srv.catalogs() == [] and srv.domains() == [] and srv.records() == []
    assert srv.new_domain("lamp", "a lamp") == "domains/lamp/lamp"
    assert (tmp_path / "domains/lamp/domain.yaml").is_file()
    assert srv.catalogs() == ["domains/lamp/lamp"] and [e["name"] for e in srv.domains()] == ["lamp"]
    s = srv.open_session("e1", {"llp": "lamp"})
    assert s["status"] == "running", s
    (tmp_path / ".metis/records").mkdir(parents=True)
    (tmp_path / ".metis/records/formalize-calls.jsonl").write_text('{"ts": "x"}\n')
    (tmp_path / ".metis/scratch").mkdir()
    (tmp_path / ".metis/scratch/x.llp").write_text("catalog x 1.\n")
    assert srv.catalogs() == ["domains/lamp/lamp"] and srv.records() == []
    assert srv._source_path("a copy") == tmp_path.resolve() / ".metis/scratch/a_copy.llp"
    assert not (tmp_path / ".metis/scratch/a_copy.llp").exists()


def test_a_directory_of_packages_and_its_readme(tmp_path, monkeypatch):
    """cwd-root rules 9 and 10: `cd domains/ceptre && metis-loop` — the
    packages sit directly under DIR (no domains/), the list has them; DIR's
    README is the page's landing, its links to a package resolve to it, and
    every session's narrate seat reads the README after its doctrine."""
    import shutil
    from metis.loop.prompts import resolve
    for n in ("three_pigs", "gossip"):
        shutil.copytree(catalog_root() / "domains/ceptre" / n, tmp_path / n,
                        ignore=shutil.ignore_patterns("records", "build", "__pycache__"))
    (tmp_path / "README.md").write_text(
        "# the ports\n\n| package | from |\n| --- | --- |\n| [`three_pigs/`](three_pigs/) | 3lp |\n"
        "| [`gossip/`](gossip/gossip.llp) | gossip |\n\nThe [license](LICENSE) and [Ceptre](https://example.org/).\n")
    monkeypatch.delenv("METIS_CATALOG", raising=False)
    monkeypatch.chdir(tmp_path)
    srv = ConsoleServer()
    assert [e["name"] for e in srv.domains()] == ["gossip", "three_pigs"]
    rd = srv.readme()
    assert rd["path"] == "README.md" and rd["text"].startswith("# the ports")
    assert rd["links"] == {"three_pigs/": "three_pigs/three_pigs", "gossip/gossip.llp": "gossip/gossip"}
    s = srv.open_session("p1", {"llp": "three_pigs"})
    assert s["status"] == "running", s
    sysp = srv.shells["p1"].sys_prompts["narrate"]
    assert sysp.startswith(resolve("narrate", None)[0]) and "# the ports" in sysp and "README.md" in sysp
    (tmp_path / "README.md").unlink()
    assert srv.readme() is None
    srv.open_session("p2", {"llp": "three_pigs"})
    assert "narrate" not in srv.shells["p2"].sys_prompts           # no README: the doctrine alone
