"""e2e-workflow s-143c3088 step 2 (d): `intents` in the loop console — a
domain's intent.yaml drafted from its program, proposed (it must generate
and every example map to a command atom, checked by metis-agent's generic
domain agent), shown as a diff, written with its generated files. On a
scratch checkout with a small plant."""
import os
from pathlib import Path

import pytest

from loop import intents as it
from loop.console_serve import ConsoleServer
from metis import catalog

AGENT_PY = Path(os.environ.get("METIS_AGENT_PY") or "/nonexistent")

pytestmark = pytest.mark.skipif(not AGENT_PY.exists(), reason="needs metis-agent's py venv (METIS_AGENT_PY)")

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
    s = ConsoleServer(tmp_path)
    s.new_domain("plant", "a potted plant that dries out")
    (tmp_path / "domains/plant/plant.llp").write_text(PLANT)
    return s


def test_intents_need_a_domain_directory(srv):
    with pytest.raises(ValueError, match="in memory only"):
        it.domain_of(srv, "scratch thing")
    with pytest.raises(ValueError, match="no intent.yaml yet"):
        it.check(srv, "domains/plant/plant")
