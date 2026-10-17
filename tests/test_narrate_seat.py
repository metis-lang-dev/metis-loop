"""The narrate seat on the SDK (CONSOLE-WS §4, D3): the gateway points a
personal session's LLM endpoint at the loop SDK's claude command face
(`python -m metis_loop_sdk.models claude-command`; its options, the
completion and their tests: sdk/tests/test_models.py) through the
kernel's own `command:` backend — kernel untouched, no tools, nothing
persisted; shared mode never gets it; `narrate = "llm"` keeps ollama.
A real Haiku narration is opt-in (METIS_AGENT_LIVE=1)."""
import json
import os

import pytest

pytest.importorskip("websockets")
pytest.importorskip("claude_agent_sdk")

from loop.gateway import DEFAULTS, narrate_seat  # noqa: E402
from test_gateway import Running, frames, open3, send  # noqa: E402


def test_seat_is_personal_only_and_configurable():
    label, spec = narrate_seat(dict(DEFAULTS))
    assert label == "claude-haiku-4-5 (SDK)"
    assert spec.startswith("command:") and "-m metis_loop_sdk.models claude-command" in spec
    assert spec.endswith("--thinking 1024")
    assert narrate_seat(dict(DEFAULTS, mode="shared")) == (None, None)
    assert narrate_seat(dict(DEFAULTS, narrate="llm")) == ("llm (ollama)", None)


def test_gateway_sets_the_seat_on_personal_sessions_only():
    r = Running(mode="personal")
    try:
        with r.ws() as ws:
            man = json.loads(ws.recv(timeout=5))
            assert man["seats"]["narrate"] == "claude-haiku-4-5 (SDK)"
            sid = open3(ws)["session"]
            assert "metis_loop_sdk.models claude-command" in r.gw.srv.shells[sid].llm
            # the page cannot move the seat to an arbitrary command
            p = send(ws, sid, ":llm command:sh -c id", "x1")[-1]
            assert p["status"] == "refused"
    finally:
        r.close()
    r = Running(mode="shared")
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            assert "metis_loop_sdk" not in (r.gw.srv.shells[sid].llm or "")
    finally:
        r.close()


@pytest.mark.skipif(os.environ.get("METIS_AGENT_LIVE") != "1",
                    reason="real Haiku narration on the operator's login: "
                           "opt in with METIS_AGENT_LIVE=1")
def test_live_narration_on_haiku():
    r = Running(mode="personal")
    try:
        with r.ws() as ws:
            sid = open3(ws)["session"]
            send(ws, sid, ":run 3", "r1")
            post = frames(ws, lambda f: f.get("type") == "posting"
                          and f.get("id") == "n1", timeout=120) \
                if ws.send(json.dumps({"ch": "repl", "type": "intent",
                                       "session": sid, "id": "n1",
                                       "cmd": ":narrate"})) is None else []
            p = post[-1]
            assert p["status"] == "done", p["result"]
            assert p["json"]["source"] == "session"
            assert "claude-command" in p["json"]["llm"]
            assert len(p["json"]["narration"]) > 80
            print("\n--- Haiku narration ---\n" + p["json"]["narration"])
    finally:
        r.close()
