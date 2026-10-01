"""Loop-core gates, on the stage-45 benchmark fixtures from the
metis-lang corpus: the admit seam reproduces the harness verdicts,
and the repair loop converges when the backend's first candidate is
broken — the untrusted-formalizer contract, exercised end to end
with a scripted backend (no model needed)."""
import os
import stat
import sys
from pathlib import Path

from loop import admit, formalize_loop

ROOT = Path(__file__).resolve().parents[1]
LANG = Path(os.environ.get(
    "METIS_LANG", ROOT.parent / "metis-lang")).resolve()
TEXT = "%% market coin: a mark trades on the coin flip outcome."


def _fixture(name):
    return (LANG / "corpus" / name).read_text()


def test_admit_pack_ok():
    rep = admit(TEXT, _fixture("packmark.llp"),
                base_path=LANG / "corpus/packbase.llp",
                scenarios=[{"coin": 1, "mkt": 1}], steps=4)
    assert rep.ok, rep.findings
    assert rep.scenarios and rep.scenarios[0].key


def test_admit_vocabulary_drift_caught():
    bad = _fixture("packmark.llp").replace("mkt", "unlock", 1)
    rep = admit(TEXT, bad, base_path=LANG / "corpus/packbase.llp")
    assert not rep.ok and rep.findings


def test_repair_loop_converges(tmp_path):
    """Round 1 emits vocabulary drift; the findings feed back; round
    2 emits the correct pack. The loop must report rounds=2, ok."""
    good = LANG / "corpus/packmark.llp"
    bad = tmp_path / "bad.llp"
    bad.write_text(_fixture("packmark.llp").replace("mkt", "unlock", 1))
    marker = tmp_path / "called"
    backend = tmp_path / "backend.sh"
    backend.write_text(
        "#!/bin/sh\n"
        f"if [ -e {marker} ]; then cat {good}; else touch {marker}; "
        f"cat {bad}; fi\n")
    backend.chmod(backend.stat().st_mode | stat.S_IEXEC)

    res = formalize_loop(TEXT, "coin, heads, tails, mkt", [str(backend)],
                         base_path=LANG / "corpus/packbase.llp",
                         scenarios=[{"coin": 1, "mkt": 1}], steps=4)
    assert res.ok and res.rounds == 2, (res.rounds, res.history)
    assert not res.history[0][1] == []          # round 1 had findings
    assert res.report and res.report.scenarios


def test_cli_admit(tmp_path, capsys):
    from loop.cli import main
    t = tmp_path / "t.md"
    t.write_text(TEXT)
    rc = main(["admit", str(t), str(LANG / "corpus/packmark.llp"),
               "--base", str(LANG / "corpus/packbase.llp"),
               "--scenario", "coin=1,mkt=1", "--steps", "4"])
    out = capsys.readouterr().out
    assert rc == 0 and "ok=True" in out and "diff" in out


MEADOW = """catalog meadow 1.
provenance text "repl gate: wolf and flock" "2026-09-27".
layers (dyn pack).
stages (hunt rest).
namespace md produce (dyn).
pred wolf : md.
pred sheep : md.
pred night : md.
pred fed : md.
pred hungry : md.
weight pk reads {}.
stage hunt {
  %% catch.
  catch [dyn] : wolf * sheep * night -o wolf * fed  @w pk.
  %% evade.
  evade [dyn] : wolf * night -o wolf * hungry  @w ~pk.
}
%% settle.
qui hr [dyn] : hunt -o rest.
"""
SHEPHERD = """catalog shepherd 1.
extends meadow.
provenance text "repl gate: the tally pack" "2026-09-27".
namespace sh produce (pack).
pred tally : sh.
pred loss : sh.
pred safe : sh.
stage rest {
  %% loss.
  n1 [pack] : tally * $fed -o loss.
  %% safe.
  n2 [pack] : tally * $hungry -o safe.
}
"""


def test_repl_tabula_rasa_cycle():
    """text -> llp -> gate -> accept -> trace/map/marginals ->
    repeat with a pack over the accepted world."""
    from loop.repl import Session
    s = Session()
    assert s.dispatch("init", "wolf=1,sheep=3,night=2,tally=2")["ok"]
    assert s.dispatch("steps", "6")["ok"]
    s.dispatch("text", "%% meadow world")
    s.dispatch("llp", MEADOW)
    g1 = s.dispatch("gate", "")
    assert g1["ok"] and g1["rules"], g1
    assert s.dispatch("accept", "")["ok"]
    tr = s.dispatch("trace", "7")
    assert tr["ok"] and tr["events"][0].startswith("hunt/"), tr
    mp = s.dispatch("map", "")
    assert mp["ok"] and mp["events"][0] == "hunt/catch"
    mg = s.dispatch("marginals", "fed hungry")
    assert abs(mg["marginals"]["hungry"] - 0.5) < 1e-12
    # repeat: the pack extends the accepted world; the measure diff
    # is the instrument.
    s.dispatch("text", "%% shepherd tally")
    s.dispatch("llp", SHEPHERD)
    g2 = s.dispatch("gate", "")
    assert g2["ok"], g2
    diffs = dict((d[0], (d[1], d[2])) for d in g2["scenarios"][0]["diffs"])
    assert diffs["loss"][0] == 0.0 and diffs["loss"][1] > 0.8
    assert s.dispatch("accept", "")["ok"]
    tr2 = s.dispatch("trace", "7")
    assert any(e.startswith("rest/") for e in tr2["events"]), tr2
    # the REPL kernel refuses nonsense instead of guessing
    assert not s.dispatch("nosuch", "")["ok"]


def test_repl_revise_replaces_world_with_diff():
    """A base edit goes through :revise — the world is REPLACED,
    packs drop, and the before/after exact diff is the instrument."""
    from loop.repl import Session
    s = Session()
    s.dispatch("init", "wolf=1,sheep=1,night=1,tally=1")
    s.dispatch("steps", "4")
    s.dispatch("text", "%% base"); s.dispatch("llp", MEADOW)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]
    s.dispatch("text", "%% tally"); s.dispatch("llp", SHEPHERD)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]
    # revision: a catch now yields DOUBLE fed
    rev = MEADOW.replace("-o wolf * fed ", "-o wolf * fed * fed ")
    s.dispatch("text", "%% revised: a catch gorges the wolf")
    s.dispatch("llp", rev)
    g = s.dispatch("revise", "")
    assert g["ok"] and g["revision"], g
    a = s.dispatch("accept", "")
    assert a["ok"] and a["dropped_packs"] == 1, a
    # the diff surfaces the dropped pack: its vocabulary vanishes
    # from the measure and its consumed trigger comes back.
    d = {x[0]: (x[1], x[2]) for x in a["diffs"]}
    assert d["loss"][1] == 0.0 and d["tally"] == (0.0, 1.0), a
    # the shepherd pack must be RE-proposed against the new base
    s.dispatch("text", "%% tally again"); s.dispatch("llp", SHEPHERD)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]


def test_short_name_collision_warned():
    """A pack reusing a base rule's SHORT name admits (entry names
    stay layer-qualified) but must WARN — traces and the debug
    sidecar read short names."""
    collide = """catalog p 1.
extends meadow.
provenance text "t" "2026-09-27".
namespace px produce (pack).
pred mark : px.
stage rest {
  %% shadow name.
  catch [pack] : mark * $fed -o mark.
}
"""
    from loop.repl import Session
    s = Session()
    s.dispatch("init", "wolf=1,sheep=1,night=1,mark=1")
    s.dispatch("steps", "4")
    s.dispatch("text", "%% base"); s.dispatch("llp", MEADOW)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]
    s.dispatch("text", "%% name collision"); s.dispatch("llp", collide)
    g = s.dispatch("gate", "")
    assert g["ok"] and any("catch" in w and "short" in w
                           for w in g["warnings"]), g


def test_repl_scene_verbs_and_directive_adoption():
    """:seed sets the scene's third coordinate; :load adopts a file's
    embedded '#'-directives where the scene is unset (explicit verbs
    win); :help answers on the wire."""
    from loop.repl import Session
    fiction = (ROOT.parent
               / "metis-catalog/domains/fiction/love_triangle.llp")
    s = Session()
    assert s.dispatch("seed", "5")["ok"] and s.seed == 5
    r = s.dispatch("load", str(fiction))
    assert r["ok"] and "init" in r["adopted_directives"]
    assert s.init["eros(helena,hermia)"] == 1 and s.steps == 6
    assert r["adopted_text_chars"] and s.text.startswith("%")
    assert s.dispatch("gate", "")["ok"]    # the adopted text suffices
    tr = s.dispatch("trace", "")           # starts from :seed
    assert tr["ok"] and tr["seed"] == 5
    assert ":sink" in s.dispatch("help", "")["help"]
    # explicit scene wins over the file's directives
    s2 = Session()
    s2.dispatch("init", "eros(helena,hermia)=1")
    r2 = s2.dispatch("load", str(fiction))
    assert "adopted_directives" not in r2 or \
        "init" not in r2.get("adopted_directives", {})
    assert s2.init == {"eros(helena,hermia)": 1}


def test_repl_surprise_refinement_loop(tmp_path):
    """The loop, entirely in the REPL: sink -> record (scene adopted)
    -> replay (likelihood 0, the explanation gap) -> mine -> candidate
    -> gate -> accept -> replay again (likelihood moved positive =
    fixed, with the MAP explanation naming the new rule)."""
    import json
    from loop.repl import Session
    rec = {"format": "metis-surprise", "version": 1,
           "program_key": "(demo)", "steps": 6,
           "init": {"wolf": 1, "sheep": 3, "night": 2, "tally": 2},
           "observed": {"safe": 1}, "likelihood": 0.0,
           "kind": "unmodeled", "meta": {"source": "test:meadow"}}
    sink = tmp_path / "sink.jsonl"
    sink.write_text(json.dumps(rec) + "\n")
    s = Session()
    r = s.dispatch("sink", str(sink))
    assert r["ok"] and r["records"][0]["kind"] == "unmodeled"
    r = s.dispatch("record", "")
    assert r["ok"] and s.init["wolf"] == 1 and s.steps == 6
    s.dispatch("text", "%% meadow world")
    s.dispatch("llp", MEADOW)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]
    r = s.dispatch("replay", "")
    assert r["ok"] and r["likelihood"] == 0.0 and not r["fixed"]
    assert "hint" in s.dispatch("mine", "")
    s.dispatch("mine", "%% the shepherd tallies the flock at rest: "
                       "a fed wolf means a loss, a hungry one safety.")
    assert s.records[0]["mined_text"].startswith("%% the shepherd")
    assert s.text.startswith("%% the shepherd")
    s.dispatch("llp", SHEPHERD)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]
    r = s.dispatch("replay", "")
    assert r["ok"] and r["likelihood"] > 0 and r["fixed"] and r["explains"]
    assert any("n2" in e for e in r["explanation_events"])


def test_ollama_adapter_is_the_formalizer_seam():
    """generate() speaks the Ollama wire (temperature 0, no stream),
    strips the fences models add anyway, and backend() satisfies
    run_backend's callable shape."""
    import http.server
    import json
    import threading
    from loop import ollama
    from loop.core import run_backend
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers["Content-Length"])
            seen.update(json.loads(self.rfile.read(n)))
            body = json.dumps(
                {"response": "```llp\ncatalog x 1.\n```"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        host = f"http://127.0.0.1:{srv.server_port}"
        assert ollama.generate("p", model="m", host=host) \
            == "catalog x 1.\n"
        assert seen["model"] == "m" and seen["stream"] is False
        assert seen["options"] == {"temperature": 0}
        assert run_backend(ollama.backend("m", host), "p") \
            == "catalog x 1.\n"
    finally:
        srv.shutdown()


def test_intent_policy_is_the_single_gate():
    """Chat-suggested REPL lines execute only through run_intent's
    whitelist: drafting and instrument verbs pass, approval, file
    paths and arbitrary backend commands are refused."""
    from loop.repl import Session, parse_intent
    assert parse_intent(":marginals fed hungry") == ("marginals",
                                                    "fed hungry")
    assert parse_intent(":formalize ollama:llama3.1") is not None
    for bad in (":accept", ":save /tmp/x", ":load /etc/passwd",
                ":sink /etc/passwd", ":formalize rm -rf /",
                ":quit", "marginals fed", ""):
        assert parse_intent(bad) is None, bad
    s = Session()
    s.dispatch("init", "wolf=1,sheep=3,night=2,tally=2")
    s.dispatch("steps", "6")
    s.dispatch("text", "%% meadow world")
    s.dispatch("llp", MEADOW)
    assert s.dispatch("gate", "")["ok"] and s.dispatch("accept", "")["ok"]
    r = s.run_intent(":marginals hungry")
    assert r["ok"] and abs(r["marginals"]["hungry"] - 0.5) < 1e-12
    r = s.run_intent(":accept")
    assert not r["ok"] and "refused" in r["error"]


def test_llm_endpoint_resolve_and_intent_policy():
    from loop.llm import resolve
    from loop.repl import parse_intent
    assert resolve("ollama").backend == "ollama"
    assert resolve("anthropic:claude-opus-5-5").arg == "claude-opus-5-5"
    assert resolve("ollama:qwen2.5-coder:7b").arg == "qwen2.5-coder:7b"
    try:
        resolve("sorcery")
        assert False
    except ValueError:
        pass
    # page intents may pick models, never commands
    assert parse_intent(":llm anthropic:claude-opus-5-5") is not None
    assert parse_intent(":llm command:rm -rf /") is None
    assert parse_intent(":narrate 2") is not None


def test_narrate_via_command_backend():
    """The narrate-out boundary with `cat` in the LLM seat: the
    'narration' is the prompt itself, so the certified material —
    beats, state, rules — is verifiably all the model ever sees."""
    from loop.repl import Session
    s = Session()
    assert s.dispatch("load", str(LANG / "corpus/love_triangle.llp"))["ok"]
    assert s.dispatch("gate", "")["ok"]
    assert s.dispatch("llm", "command:cat")["ok"]
    r = s.dispatch("narrate", "1")
    assert r["ok"] and r["events"] > 0
    txt = r["narration"]
    assert "beats" in txt and "== the final state ==" in txt
    assert "== the rules" in txt and "jealousy" in txt
    # within-beat independence is stated to the narrator
    assert "INDEPENDENT" in txt
