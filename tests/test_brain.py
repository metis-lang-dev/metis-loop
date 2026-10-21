"""The console's brain (brain-choice s-c59b7b51, loop/brain.py): the startup
choice claude | openrouter[:MODEL] | ollama, CLI > [console] > the default by
what is here; the seats it gives a session; the refusals naming the fix; the
OpenRouter command's per-session max_usd and its call log. No model call:
the OpenRouter face is replaced, and the gateway test's formalize endpoint
is a stand-in that only says which endpoint ran."""
import io
import json
import sys

import pytest

from loop import brain
from loop.gateway import DEFAULTS, agent_seat, formalize_seat, main, manifest, narrate_seat

KEY = "sk-or-test-not-a-key"


def cfg(**kw):
    return dict(DEFAULTS, **kw)


@pytest.fixture
def here(monkeypatch):
    """What is here: set(claude=…, key=…)."""
    def set_(claude=True, key=False):
        monkeypatch.setattr(brain, "claude_why", lambda: None if claude else "claude-agent-sdk is not installed")
        import loop.agent_service as a
        monkeypatch.setattr(a, "available", lambda: None if claude else "claude-agent-sdk is not installed")
        if key:
            monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
        else:
            monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return set_


def test_the_default_is_by_what_is_here(here):
    here(claude=True, key=True)
    assert brain.resolve(cfg())["name"] == "claude"
    here(claude=False, key=True)
    assert brain.resolve(cfg()) == {"name": "openrouter", "model": "deepseek/deepseek-v4-pro"}
    here(claude=False, key=False)
    assert brain.resolve(cfg()) == {"name": "ollama", "model": None}


def test_the_named_brain_wins_and_takes_its_model(here):
    here(claude=True, key=True)
    assert brain.resolve(cfg(brain="openrouter:qwen/qwen3-235b-a22b-2507"))["model"] == "qwen/qwen3-235b-a22b-2507"
    assert brain.resolve(cfg(brain="openrouter"))["model"] == DEFAULTS["openrouter_model"]
    assert brain.resolve(cfg(brain="ollama"))["name"] == "ollama"
    for bad, says in (("gpt", "claude | openrouter"), ("claude:opus", "only openrouter takes a model"),
                      ("ollama:x", "only openrouter takes a model")):
        with pytest.raises(brain.BrainError, match=says):
            brain.resolve(cfg(brain=bad))


def test_a_brain_asked_for_and_not_here_names_the_fix(here):
    here(claude=False, key=False)
    with pytest.raises(brain.BrainError) as e:
        brain.resolve(cfg(brain="claude"))
    assert "install Claude Code" in str(e.value) and "--brain openrouter" in str(e.value)
    with pytest.raises(brain.BrainError) as e:
        brain.resolve(cfg(brain="openrouter"))
    assert "export OPENROUTER_API_KEY" in str(e.value) and "--brain claude" in str(e.value)


def test_the_cli_refuses_at_startup(here, capsys, tmp_path, monkeypatch):
    here(claude=False, key=False)
    monkeypatch.setenv("METIS_CATALOG", str(tmp_path))
    assert main(["--brain", "openrouter", "--port", "0"]) == 2
    assert "export OPENROUTER_API_KEY" in capsys.readouterr().err
    assert main(["--brain", "claude", "--port", "0"]) == 2
    assert "install Claude Code" in capsys.readouterr().err


def test_claude_seats_are_the_specs_of_before(here):
    """No change on the claude path: both seats on the one Haiku spec the narrate
    seat set before (formalize read it as the session's endpoint)."""
    here(claude=True)
    before = (f"command:{sys.executable} -m metis_loop_sdk.models claude-command "
              "--model claude-haiku-4-5 --thinking 1024")
    assert narrate_seat(cfg()) == ("claude-haiku-4-5 (SDK)", before)
    assert formalize_seat(cfg()) == ("claude-haiku-4-5 (SDK)", before)
    # two keys, the same mechanism
    assert formalize_seat(cfg(formalize_model="claude-sonnet-5-5"))[1].endswith("--model claude-sonnet-5-5 --thinking 1024")
    assert narrate_seat(cfg(narrate="llm")) == ("llm (ollama)", None)
    assert formalize_seat(cfg(narrate="llm")) == ("llm", None)
    assert agent_seat(cfg()) == ("agent", None)


def test_openrouter_seats_go_through_the_capped_command(here):
    here(claude=True, key=True)
    c = cfg(brain="openrouter:deepseek/deepseek-v4-pro", max_usd=0.25)
    label, spec = formalize_seat(c, "w1", "/d/.metis/formalize-calls.jsonl")
    assert label == "deepseek/deepseek-v4-pro (OpenRouter)"
    assert spec == (f"command:{sys.executable} -m loop.brain openrouter-command --model deepseek/deepseek-v4-pro "
                    "--seat formalize --session w1 --log /d/.metis/formalize-calls.jsonl --max-usd 0.25")
    label, spec = narrate_seat(c, "w1", "/d/.metis/formalize-calls.jsonl")
    assert label == "deepseek/deepseek-v4-flash (OpenRouter)" and "--seat narrate" in spec
    assert spec.endswith("--max-usd 0.25 --reasoning low --max-tokens 4096")   # narrate reasons a little, with room
    assert "--reasoning" not in formalize_seat(c, "w1")[1] and "--max-tokens" not in formalize_seat(c, "w1")[1]
    assert "--reasoning medium --max-tokens" in narrate_seat(dict(c, narrate_reasoning="medium"), "w1")[1]
    assert KEY not in spec and "OPENROUTER_API_KEY" not in spec        # the key: the environment only
    seat, why = agent_seat(c)
    assert seat is None and why.startswith("needs claude")
    m = manifest(c)
    assert m["brain"] == {"name": "openrouter", "model": "deepseek/deepseek-v4-pro"}
    assert m["seats"]["formalize"] == "deepseek/deepseek-v4-pro (OpenRouter)"
    assert m["seats"]["chat"] is None and m["chat_unavailable"].startswith("needs claude")


def test_narrate_reasoning_is_checked():
    from loop.gateway import load_config
    with pytest.raises(ValueError, match="narrate_reasoning"):
        load_config(narrate_reasoning="lots")


def test_ollama_and_shared(here):
    here(claude=True, key=True)
    assert narrate_seat(cfg(brain="ollama")) == ("llm (ollama)", None)
    assert formalize_seat(cfg(brain="ollama")) == ("llm", None)
    here(claude=False, key=False)                    # shared: no brain, nothing resolved, nothing refused
    assert brain.seats(cfg(mode="shared", brain="claude")) == {
        "brain": None, "formalize": (None, None), "narrate": (None, None)}
    assert manifest(cfg(mode="shared"))["seats"]["formalize"] is None


def run_command(monkeypatch, capsys, log, prompt="P", session="w1", max_usd="0.05", reply=None):
    from metis_loop_sdk.models import openai
    calls = []

    def fake(p, model, base_url, max_tokens, reasoning, data_collection, log):
        calls.append({"model": model, "base_url": base_url, "max_tokens": max_tokens,
                      "reasoning": reasoning, "data_collection": data_collection})
        with open(log, "a") as f:
            f.write(json.dumps({"model": model, "cost": 0.004, "finish_reason": "stop"}) + "\n")
        return reply or "DRAFT"
    monkeypatch.setattr(openai, "complete", fake)
    monkeypatch.setattr(sys, "stdin", io.StringIO(prompt))
    rc = brain.openrouter_command(["--model", "m/x", "--seat", "formalize", "--session", session,
                                   "--log", str(log), "--max-usd", max_usd])
    return rc, capsys.readouterr(), calls


def test_the_command_logs_each_call_with_its_session_and_caps_the_session(monkeypatch, capsys, tmp_path):
    (tmp_path / ".git").mkdir()
    log = tmp_path / ".metis" / "formalize-calls.jsonl"
    rc, out, calls = run_command(monkeypatch, capsys, log)
    assert rc == 0 and out.out == "DRAFT"
    assert calls == [{"model": "m/x", "base_url": "https://openrouter.ai/api/v1", "max_tokens": 2048,
                      "reasoning": "off", "data_collection": "deny"}]
    line = json.loads(log.read_text())
    assert line == {"model": "m/x", "cost": 0.004, "finish_reason": "stop", "session": "w1", "seat": "formalize"}
    assert "/.metis/" in (tmp_path / ".gitignore").read_text()       # made through catalog.state()
    # 0.004 per call against 0.01: the third call is refused, with the number; another session goes on
    assert run_command(monkeypatch, capsys, log, max_usd="0.01")[0] == 0
    assert run_command(monkeypatch, capsys, log, max_usd="0.01")[0] == 0
    rc, out, calls = run_command(monkeypatch, capsys, log, max_usd="0.01")
    assert rc == 1 and calls == []
    assert "spent 0.0120 USD" in out.err and "max_usd is 0.01" in out.err
    assert run_command(monkeypatch, capsys, log, session="w2", max_usd="0.01")[0] == 0
    assert brain.spent(str(log), "w1") == pytest.approx(0.012)


def test_the_gateway_runs_formalize_on_its_own_endpoint(here, monkeypatch, tmp_path):
    """The kernel has one endpoint per session: the gateway sets the brain's
    formalize endpoint for a formalize command only, and puts narrate's back."""
    pytest.importorskip("websockets")
    from test_gateway import Running, open3, send
    here(claude=False, key=True)
    r = Running(mode="personal", brain="openrouter")
    try:
        assert r.gw.calls_log().endswith("/.metis/formalize-calls.jsonl")
        with r.ws() as ws:
            sid = open3(ws)["session"]
            narr = r.gw.srv.shells[sid].llm
            assert "--seat narrate" in narr and f"--session {sid}" in narr
            assert "--seat formalize" in r.gw.formalize_llm[sid]
            # a stand-in for the OpenRouter command: it says which endpoint ran, and no call leaves
            stand = f"command:{sys.executable} -c \"import sys; sys.stderr.write('FORMALIZE-SEAT'); sys.exit(1)\""
            r.gw.formalize_llm[sid] = stand
            send(ws, sid, ":text the lamp burns out after a while", "t1")
            p = send(ws, sid, ":formalize", "f1")[-1]
            assert "FORMALIZE-SEAT" in json.dumps(p)
            assert r.gw.srv.shells[sid].llm == narr
    finally:
        r.close()
