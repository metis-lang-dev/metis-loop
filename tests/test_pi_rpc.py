"""loop/pi_rpc.py (docs/WORKSPACE.md §5.2; loop-workspace step 3 part C) against tests/stub_pi.py, a stand-in that
writes pi 1.3.0's records: the person's turn and pi's words, a tool call and its result, the gate's confirm as a token
answered both ways, a select answered cancelled, framing on LF only, a child that dies before it is ready, one that
never answers, stop idempotent; and loop.sh --mode rpc keeps the client's stdin (no /dev/null redirect)."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from loop import pi_rpc
from loop.pi_rpc import PiRpc, PiRpcError

HERE = Path(__file__).resolve().parent
STUB = [sys.executable, str(HERE / "stub_pi.py")]


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 60))


async def until(rpc, kind):
    got = []
    async for ev in rpc.events():
        got.append(ev)
        if ev["kind"] == kind:
            return got
    return got


def test_a_turn_its_words_and_turn_end():
    async def go():
        rpc = PiRpc(STUB, env=dict(os.environ))
        st = await rpc.start()
        assert st["model"]["id"] == "stub/model" and rpc.pid
        assert await rpc.say("hello there") == "started"
        evs = await until(rpc, "turn_end")
        texts = [e["text"] for e in evs if e["kind"] == "text"]
        assert texts == ["heard: hello there"]                  # one record: LF framing only
        assert {"kind": "usage", "cost": 0.0, "model": "stub/model"} in evs
        assert evs[-1] == {"kind": "turn_end", "aborted": False}
        await rpc.stop()
        await rpc.stop()                                                  # idempotent
        rest = [e async for e in rpc.events()]
        assert rest[-1]["kind"] == "exit" and rest[-1]["code"] == 0
        assert "stub pi: ready" in rest[-1]["stderr_tail"]
    run(go())


@pytest.mark.parametrize("ok", [True, False])
def test_the_gate_is_a_token_answered_by_the_person(ok):
    async def go():
        rpc = PiRpc(STUB, env=dict(os.environ))
        await rpc.start()
        await rpc.say("please apply the ruling")
        evs = await until(rpc, "gate")
        assert {"kind": "usage", "cost": 0.002, "model": "stub/model"} in evs
        call = [e for e in evs if e["kind"] == "tool_call"]
        assert call == [{"kind": "tool_call", "id": "t1", "name": "catalog_edit", "args": {"domain": "planner"}}]
        assert any(e["kind"] == "notify" and "select" in e["text"] and "cancelled" in e["text"] for e in evs)
        g = evs[-1]
        assert g["token"] == "g2" and g["plan"]["title"].startswith("Edit in the catalog") and "+++ b/planner.llp" in g["plan"]["message"]
        with pytest.raises(PiRpcError):
            await rpc.answer("nope", True)
        await rpc.answer(g["token"], ok)
        with pytest.raises(PiRpcError):
            await rpc.answer(g["token"], ok)                              # answered once
        evs = await until(rpc, "turn_end")
        res = [e for e in evs if e["kind"] == "tool_result"]
        assert res == [{"kind": "tool_result", "id": "t1", "name": "catalog_edit", "ok": ok,
                        "text": "applied: domains/planner/planner.llp" if ok else "refused by the person"}]
        await rpc.stop()
    run(go())


def test_a_child_that_dies_before_it_is_ready_says_why():
    async def go():
        rpc = PiRpc(STUB, env=dict(os.environ, STUB_PI_DIE="1"))
        with pytest.raises(PiRpcError, match=r"exit 3.*boom: the stand-in died"):
            await rpc.start()
        evs = [e async for e in rpc.events()]
        assert evs[-1]["kind"] == "exit" and evs[-1]["code"] == 3
    run(go())


def test_a_child_that_never_answers_is_stopped(monkeypatch):
    monkeypatch.setattr(pi_rpc, "READY_TIMEOUT", 1.0)
    monkeypatch.setattr(pi_rpc, "STOP_GRACE", 1.0)

    async def go():
        rpc = PiRpc(STUB, env=dict(os.environ, STUB_PI_MUTE="1"))
        with pytest.raises(PiRpcError, match="no answer in 1.0s"):
            await rpc.start()
        assert rpc.proc.returncode is not None                            # not left running
    run(go())


def test_a_refused_command_and_a_turn_after_exit():
    async def go():
        rpc = PiRpc(STUB, env=dict(os.environ))
        await rpc.start()
        r = await rpc._command({"type": "frobnicate"})
        assert r["success"] is False and "unknown command" in r["error"]
        await rpc.stop()
        with pytest.raises(PiRpcError, match="not running"):
            await rpc.say("anyone?")
    run(go())


def test_loop_sh_in_rpc_mode_keeps_the_clients_stdin(tmp_path):
    """loop.sh redirects a non-terminal stdin to /dev/null so a TUI-less pi ends (test_propose's case); in rpc mode
    stdin IS the protocol, so the redirect must not happen: the backend's child talks through loop.sh."""
    args = tmp_path / "args.json"
    sdk_py = os.environ.get("TEST_SDK_PY", sys.executable)
    env = dict(os.environ, METIS_LOOP_PI=f"{HERE / 'stub_pi.py'}", METIS_LOOP_SDK_PY=sdk_py, METIS_CONFIG="", MODEL="stub/script",
               METIS_LOOP_TAKE_INTO="", METIS_LOOP_LLP="", STUB_PI_ARGS=str(args))
    env.pop("METIS_CATALOG", None)
    loop_sh = HERE.parent / "pi" / "loop.sh"

    async def go():
        rpc = PiRpc([str(loop_sh), "--mode", "rpc"], cwd=str(tmp_path), env=env)
        await rpc.start()
        await rpc.say("through loop.sh")
        evs = await until(rpc, "turn_end")
        assert [e["text"] for e in evs if e["kind"] == "text"] == ["heard: through loop.sh"]
        await rpc.stop()
    run(go())
    a = json.loads(args.read_text())
    assert a["stdin_devnull"] is False and "--mode" in a["argv"] and a["argv"][a["argv"].index("--mode") + 1] == "rpc"
    assert a["cwd"] == str(tmp_path)
