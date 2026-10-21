"""domains/repl served by metis-agent's domain agent (py), METIS_CATALOG = this checkout, against
the stub gateway (console-nav s-b923ebfe): typed intents in (no model), the frames the host
sends, the rules' words back. Needs metis-agent's py venv (METIS_AGENT_PY, its python; with
METIS_AGENT_DIR, a checkout's py/ put first on its PYTHONPATH) whose AgentHost hands the
payload to the host (take_payload)."""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("websockets")
from stub_gateway import StubGateway  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PY = os.environ.get("METIS_AGENT_PY", "")
DIR = os.environ.get("METIS_AGENT_DIR", "")


def _agent_ok():
    if not PY or not Path(PY).exists():
        return False
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (DIR, os.environ.get("PYTHONPATH", "")) if p))
    r = subprocess.run([PY, "-c", "from metis_agent.agent_host import AgentHost; import inspect; "
                        "assert 'take_payload' in inspect.getsource(AgentHost.on_event)"], env=env, capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(not _agent_ok(), reason="no metis-agent py venv whose AgentHost hands the payload over "
                                                        "(METIS_AGENT_PY, METIS_AGENT_DIR)")


def test_the_repl_served_by_the_domain_agent():
    gw = StubGateway(domains=[{"name": "plant", "path": "domains/plant/plant", "host": "plant_host.py:make"}]).start()
    env = dict(os.environ, METIS_CATALOG=str(ROOT), METIS_LOOP_WS=gw.url,
               PYTHONPATH=os.pathsep.join(p for p in (DIR, str(ROOT / "sdk"), os.environ.get("PYTHONPATH", "")) if p))
    p = subprocess.Popen([PY, "-m", "metis_agent.domain_agent", "--domain", "repl", "--case", "replay"],
                         cwd=DIR or None, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, env=env)

    def line(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()
        out = []
        while True:
            r = json.loads(p.stdout.readline())
            out.append(r)
            if "ack" in r or "clock" in r:
                return out

    def say(i, verb, **args):
        out = line({"domain": "repl", "id": i, "verb": verb, "args": args})
        for _ in range(40):                               # beats until the program settles on an outcome
            out += line({"clock": "beat"})
            if any(r.get("status") in ("done", "refused") for r in out):
                break
            time.sleep(0.05)
        return [(r["status"], r.get("text", "")) for r in out if r.get("status") in ("done", "refused")]

    try:
        assert json.loads(p.stdout.readline())["clock"] == "ready"
        line({"clock": "beat"})                            # the start (the embedded case's token, if any, settles)
        assert say(1, "LOAD", package="the plant") == [("done", "The package is loaded.")]
        assert say(2, "RUN", n=3)[0][0] == "done"
        assert say(3, "NARRATE")[0] == ("done", "The narration is in the log.")
        assert say(4, "APPLY") == [("refused", "There is nothing to apply: the working copy is the catalog's.")]
        assert say(5, "TELL", text="the lamp should dim before it goes dark")[0][0] == "done"
        assert say(6, "UNDO") == [("done", "I undo the last step.")]
        sent = [(m["type"], m.get("cmd") or m.get("llp") or m.get("text")) for m in gw.received]
        assert sent == [("open", "domains/plant/plant"), ("intent", ":run 3"), ("intent", ":narrate"),
                        ("say", "the lamp should dim before it goes dark"), ("intent", ":undo")]
        assert gw.written == []
    finally:
        p.stdin.close()
        p.wait(20)
        gw.stop()
