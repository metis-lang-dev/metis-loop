"""e2e-workflow s-143c3088 step 2 (d): `intents` in the loop console — a
domain's intent.yaml drafted from its program, proposed (it must generate
and every example map to a command atom, checked by metis-agent's generic
domain agent), shown as a diff, written with its generated files. On a
scratch checkout with a small plant."""
import shutil
from pathlib import Path

import pytest

from loop import intents as it
from loop.console_serve import ConsoleServer

SIB = Path(__file__).resolve().parents[2]
GEN = SIB / "metis-catalog/tools/intents.py"
AGENT_PY = SIB / "metis-agent/py/.venv/bin/python"

pytestmark = pytest.mark.skipif(not (GEN.exists() and AGENT_PY.exists()),
                                reason="needs the metis-catalog and metis-agent checkouts beside this one")

PLANT = """catalog plant 1.
provenance text "a potted plant that dries out; the person waters it or asks how it is" "2026-10-14".
layers (dyn).
stages (serve).

pred dry : plant.
pred wet : plant.
pred cmd_water : plant.
pred cmd_check : plant.
pred done(act) : plant.
pred refused(act) : plant.
type act {water check}.

namespace plant produce (dyn).

stage serve {
  %% I water the plant.
  water [dyn] : cmd_water * dry -o wet * done(water).
  %% The plant does not need water: it is wet.
  water_wet [dyn] : cmd_water * $wet -o refused(water).
  %% I tell you how the plant is.
  check [dyn] : cmd_check -o done(check).
}

#init dry 1
"""


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("METIS_AGENT_PY", str(AGENT_PY))     # the venv is not beside a scratch checkout
    (tmp_path / "tools").mkdir()
    shutil.copy(GEN, tmp_path / "tools/intents.py")
    s = ConsoleServer(tmp_path)
    s.new_domain("plant", "a potted plant that dries out")
    (tmp_path / "domains/plant/plant.llp").write_text(PLANT)
    return s


def test_draft_propose_save(srv, tmp_path):
    name = "domains/plant/plant"
    r = it.read(srv, name)
    assert r["draft"] and "verb: WATER" in r["text"] and "I water the plant." in r["text"]
    p = it.propose(srv, name, r["text"])
    assert p["ok"], p["misses"]
    assert p["new"] and p["path"] == "domains/plant/intent.yaml" and "+verbs:" in p["diff"]
    assert not (tmp_path / "domains/plant/intent.yaml").exists()          # shown, not written
    bad = it.propose(srv, name, r["text"].replace("atom: cmd_water", "atom: cmd_nope"))
    assert not bad["ok"] and bad["misses"]                                  # an example that maps to no atom
    assert "asks:\n- CHECK" in r["text"]                                    # the draft's candidate: check only reads
    ask = it.propose(srv, name, r["text"] + "asks: [WATER]\n")             # an ask that changes the state
    assert not ask["ok"] and any(m.startswith("ASKS asks WATER: rule water consumes dry") for m in ask["misses"])
    with pytest.raises(ValueError, match="does not generate"):
        it.propose(srv, name, "verbs: [}")
    with pytest.raises(ValueError, match="no such proposal"):
        it.save(srv, p, "wrong")
    out = it.save(srv, p, p["token"])
    assert out["written"] == ["domains/plant/intent.yaml", "domains/plant/intent/plant.gbnf",
                              "domains/plant/intent/plant-prompt.txt", "domains/plant/intent/plant-spoken.txt",
                              "domains/plant/domain.yaml"]
    # the manifest names the spec only (the generated files at their fixed names), its own text kept,
    # and the loader derives them (catalog-entry step 2)
    import yaml
    from metis_loop_sdk import catalog
    mtext = (tmp_path / "domains/plant/domain.yaml").read_text()
    m = yaml.safe_load(mtext)
    assert m["intent"] == {"spec": "intent.yaml"} and m["display"] == "the plant"
    got = catalog.get("plant", tmp_path).intent
    assert (got["grammar"].name, got["prompt"].name, got["examples"]["gemma4"].name) == \
        ("plant.gbnf", "plant-prompt.txt", "plant-spoken.txt")
    out2 = it.save(srv, p, p["token"])                                     # again: the operator's block stands
    assert "domains/plant/domain.yaml" not in out2["written"] and "manifest_lacks" not in out2
    assert (tmp_path / "domains/plant/domain.yaml").read_text() == mtext
    g = (tmp_path / "domains/plant/intent/plant.gbnf").read_text()
    assert '"\\"WATER\\""' in g and '"\\"CHECK\\""' in g
    assert not it.read(srv, name)["draft"]


def test_intents_need_a_domain_directory(srv):
    with pytest.raises(ValueError, match="in memory only"):
        it.read(srv, "scratch thing")
    with pytest.raises(ValueError, match="no intent.yaml yet"):
        it.check(srv, "domains/plant/plant")
