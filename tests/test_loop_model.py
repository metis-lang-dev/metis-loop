"""loop.sh's model from the dot file (llm-config s-07a070ad): MODEL unset → [llm] loop (metispy metis.loop.llm), an
Ollama model as pi's provider in DIR/.metis/pi-agent/ with no key and no budget, openrouter still needing its key and a
budget, MODEL given winning, no default; the kernel's formalize from [llm] formalize, default the loop's. A stand-in
pi records what loop.sh hands it (no model is called)."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LOOP_SH = HERE.parent / "pi" / "loop.sh"
SDK_PY = os.environ.get("TEST_SDK_PY", sys.executable)


def _has_seats():
    r = subprocess.run([SDK_PY, "-c", "import metis.loop.llm as m; m.pi_model"], capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(not _has_seats(), reason="metispy without metis.loop.llm.pi_model (llm-config)")

STUB = '''#!{py}
import json, os, sys
keep = ("MODEL", "PI_CODING_AGENT_DIR", "METIS_LOOP_BUDGET", "METIS_CONFIG")
out = {{"argv": sys.argv[1:], **{{k: os.environ.get(k) for k in keep}}}}
c = os.environ.get("METIS_CONFIG")
out["conf"] = open(c).read() if c and os.path.isfile(c) else None
out["key_set"] = bool(os.environ.get("OPENROUTER_API_KEY"))
json.dump(out, open(os.environ["STUB_OUT"], "w"))
'''


def run(tmp_path, dot=None, **env):
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    xdg = tmp_path / "xdg"
    (xdg / "metis").mkdir(parents=True, exist_ok=True)
    if dot is not None:
        (xdg / "metis" / "config.toml").write_text(dot)
    stub = tmp_path / "pi_stub.py"
    stub.write_text(STUB.format(py=sys.executable))
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    out = tmp_path / "stub.json"
    e = {k: v for k, v in os.environ.items() if k not in ("MODEL", "METIS_CONFIG", "OPENROUTER_API_KEY", "METIS_CATALOG",
                                                          "FORMALIZE_MODEL", "METIS_LOOP_BUDGET", "PI_CODING_AGENT_DIR")}
    e.update(METIS_LOOP_PI=str(stub), METIS_LOOP_SDK_PY=SDK_PY, XDG_CONFIG_HOME=str(xdg), METIS_OPENROUTER_ENV="",
             METIS_LOOP_TAKE_INTO="", METIS_LOOP_LLP="", STUB_OUT=str(out), **env)
    p = subprocess.run(["bash", str(LOOP_SH)], cwd=ws, env=e, capture_output=True, text=True, timeout=120,
                       stdin=subprocess.DEVNULL)
    return p, (json.loads(out.read_text()) if out.is_file() else None), ws


def test_an_ollama_loop_model_from_the_dot_file_needs_no_key_and_no_budget(tmp_path):
    p, got, ws = run(tmp_path, '[llm]\nendpoint = "ollama:gemma3:4b"\nloop = "ollama:phi4-mini@http://127.0.0.1:9"\n')
    assert p.returncode == 0, p.stderr
    assert "loop.sh: MODEL from [llm] loop (ollama:phi4-mini@http://127.0.0.1:9)" in p.stderr
    assert got["argv"][got["argv"].index("--model") + 1] == "ollama/phi4-mini"
    assert got["METIS_LOOP_BUDGET"] == "" and got["key_set"] is False
    agent = Path(got["PI_CODING_AGENT_DIR"])
    assert agent == ws / ".metis" / "pi-agent"
    prov = json.loads((agent / "models.json").read_text())["providers"]
    assert prov["ollama"]["baseUrl"] == "http://127.0.0.1:9/v1" and prov["ollama"]["api"] == "openai-completions"
    assert prov["ollama"]["models"][0]["id"] == "phi4-mini" and prov["ollama"]["models"][0]["cost"]["input"] == 0
    assert "openrouter" in prov                                       # pi/agent/models.json's entries kept
    assert got["conf"] == '[llm]\nendpoint = "ollama:phi4-mini@http://127.0.0.1:9"\n'   # formalize: the loop's


def test_an_openrouter_loop_model_still_needs_its_key_and_gets_a_budget(tmp_path):
    dot = '[llm]\nloop = "openrouter:deepseek/deepseek-v4.1-flash-1017"\n'
    p, got, _ = run(tmp_path, dot)
    assert p.returncode == 1 and "needs OPENROUTER_API_KEY" in p.stderr and got is None
    p, got, _ = run(tmp_path, dot, OPENROUTER_API_KEY="sk-test-never-printed")
    assert p.returncode == 0, p.stderr
    assert got["argv"][got["argv"].index("--model") + 1] == "openrouter/deepseek/deepseek-v4.1-flash-1017"
    assert got["METIS_LOOP_BUDGET"] == "1.00" and got["PI_CODING_AGENT_DIR"] is None or \
        not str(got["PI_CODING_AGENT_DIR"]).endswith("pi-agent")
    assert "openai-command --base-url https://openrouter.ai/api/v1 --model deepseek/deepseek-v4.1-flash-1017" in got["conf"]
    assert "sk-test-never-printed" not in p.stderr + p.stdout


def test_formalize_from_its_own_seat(tmp_path):
    dot = ('[llm]\nloop = "openrouter:deepseek/deepseek-v4.1-flash-1017"\nformalize = "ollama:phi4-mini@http://127.0.0.1:9"\n')
    p, got, _ = run(tmp_path, dot, OPENROUTER_API_KEY="sk-test")
    assert p.returncode == 0, p.stderr
    assert got["conf"] == '[llm]\nendpoint = "ollama:phi4-mini@http://127.0.0.1:9"\n'      # not the loop's face


def test_model_on_the_command_line_wins_and_there_is_no_default(tmp_path):
    p, got, _ = run(tmp_path, '[llm]\nloop = "ollama:phi4-mini@http://127.0.0.1:9"\n', MODEL="stub/script")
    assert p.returncode == 0, p.stderr
    assert got["argv"][got["argv"].index("--model") + 1] == "stub/script" and got["PI_CODING_AGENT_DIR"] is None
    p, got, _ = run(tmp_path / "none", "")
    assert p.returncode == 2 and got is None
    assert "no loop model" in p.stderr and "set [llm] loop" in p.stderr
    p, got, _ = run(tmp_path / "cmd", '[llm]\nloop = "command:cat"\n')
    assert p.returncode == 2 and "a command has no pi model" in p.stderr


def test_the_ollama_entry(tmp_path):
    from loop import pi_models
    info = {"capabilities": ["completion", "tools", "thinking"], "model_info": {"gemma4.context_length": 131072}}
    e = pi_models.entry("metis-gemma4-e4b", info)
    assert (e["reasoning"], e["contextWindow"], e["maxTokens"]) == (True, 131072, 8192)
    assert pi_models.entry("phi4-mini", {})["contextWindow"] == pi_models.CONTEXT
    d = pi_models.ollama_agent(tmp_path / ".metis", "phi4-mini", "http://box:11434/v1", info={})
    assert [p.name for p in d.iterdir()] == ["models.json"]           # never pi's auth.json into a workspace
