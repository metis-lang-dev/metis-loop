"""The pi loop's model from the dot file (llm-config s-07a070ad): an Ollama model is pi's provider `ollama` over the
server's OpenAI-compatible URL/v1, written into an agent directory GENERATED for the start (DIR/.metis/pi-agent/:
pi/agent/models.json with the provider merged in). Why generated, not committed: the server's URL and
the model are the person's (their dot file's [llm] loop), and the committed pi/agent/models.json stays one file for
every host; why .metis/: the workspace's own state, git-ignored, rewritten at every start, so it never drifts.

    python -m loop.pi_models ollama-agent --state DIR/.metis --id phi4-mini --base-url http://127.0.0.1:11434/v1
        -> prints the agent directory (PI_CODING_AGENT_DIR for pi.sh)

The entry: api openai-completions, a dummy apiKey (Ollama ignores it; pi needs one to list the model), cost 0,
maxTokens 8192 (the loop's cap, as the openrouter entries), reasoning from Ollama's /api/show ("thinking" in its
capabilities), input text, compat supportsDeveloperRole false (the system prompt as role system: Ollama's
templates drop a `developer` message, which pi sends for a thinking model). contextWindow is what the server SERVES, not the model's trained length (qwen-loop
s-75ecbab5: qwen3:4b says 262144 and is served 32768; pi then never compacts before the server cuts the prompt):
the model's own num_ctx, else the server's OLLAMA_CONTEXT_LENGTH as this environment names it, else 32768 (the
setting WORKSPACE.md §10 asks for), never over the trained length.

Thinking: a thinking model's reasoning comes back in /v1's own `reasoning` field (pi's thinking blocks, never the
answer text), and pi's levels go as `reasoning_effort`; there is no off: pi sends no field for off, and Ollama
then thinks at its default (qwen3:4b is a thinking model; `reasoning_effort: none` makes it think in the answer
text instead), so the loop's local default is pi's own level and METIS_LOOP_THINKING=off changes nothing here."""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent / "pi" / "agent"
MAX_TOKENS = 8192
CONTEXT = 32768                    # when the server does not say


def show(base_url, model_id, timeout=3):
    """Ollama's /api/show for the model (the server root is BASE_URL without /v1): {} when it does not answer."""
    root = base_url[:-3] if base_url.endswith("/v1") else base_url
    req = urllib.request.Request(root.rstrip("/") + "/api/show", data=json.dumps({"model": model_id}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:  # noqa: BLE001 — the entry then takes the defaults; pi says what the server does
        return {}


def props(base_url, timeout=3):
    """llama.cpp's server under the same scheme (gpt-oss s-0f23f8cd: `ollama:MODEL@http://host:8081`, its /v1 is
    OpenAI-compatible as Ollama's): its /props read as /api/show's answer, {} when it does not answer. The served
    context is its n_ctx; thinking when its chat template takes a reasoning effort (gpt-oss's harmony)."""
    root = base_url[:-3] if base_url.endswith("/v1") else base_url
    try:
        with urllib.request.urlopen(root.rstrip("/") + "/props", timeout=timeout) as r:
            p = json.loads(r.read())
    except Exception:  # noqa: BLE001 — neither server answered: the defaults
        return {}
    n = (p.get("default_generation_settings") or {}).get("n_ctx")
    t = str(p.get("chat_template") or "")
    caps = ["completion", "tools"] + (["thinking"] if "reasoning_effort" in t or "<|channel|>" in t else [])
    return {"capabilities": caps, "parameters": f"num_ctx {n}" if n else "", "server": "llama.cpp"}


def served_context(info, env=None):
    """The context the server gives the model: its own num_ctx (it wins), else OLLAMA_CONTEXT_LENGTH as this
    environment names it; None when neither says (the caller's default)."""
    env = os.environ if env is None else env
    m = re.search(r"(?m)^\s*num_ctx\s+(\d+)", str((info or {}).get("parameters") or ""))
    if m:
        return int(m.group(1))
    v = str(env.get("OLLAMA_CONTEXT_LENGTH") or "")
    return int(v) if v.isdigit() and int(v) > 0 else None


def entry(model_id, info=None):
    """pi's models.json model entry for an Ollama model."""
    info = info or {}
    mi = info.get("model_info") or {}
    trained = next((v for k, v in mi.items() if k.endswith(".context_length") and isinstance(v, int)), None)
    ctx = served_context(info) or CONTEXT
    ctx = min(ctx, trained) if trained else ctx
    caps = info.get("capabilities") or []
    return {"id": model_id, "name": f"{model_id} ({'llama.cpp' if info.get('server') == 'llama.cpp' else 'Ollama'})", "reasoning": "thinking" in caps, "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": ctx, "maxTokens": MAX_TOKENS,
            # the instructions as role system (qwen-loop F4): pi sends a thinking model's system prompt as role
            # `developer`, and Ollama's chat templates (qwen3, gemma4) DROP that role: the model never saw
            # loop-system.md, its skills or its tools' rules (3925 prompt tokens with or without it)
            "compat": {"supportsDeveloperRole": False}}


def models_json(base, model_id, base_url, info=None):
    """BASE (pi/agent/models.json as data) with the provider `ollama` merged in: this model at BASE_URL."""
    out = json.loads(json.dumps(base))
    prov = out.setdefault("providers", {})
    prov["ollama"] = {"baseUrl": base_url, "api": "openai-completions", "apiKey": "ollama",
                      "models": [entry(model_id, info)]}
    return out


def ollama_agent(state, model_id, base_url, agent=AGENT, info=None):
    """DIR/.metis/pi-agent/: models.json, pi/agent/'s with the provider merged; nothing else is copied (auth.json is
    pi's login store: never into a workspace; pi makes its own state files here). → the directory."""
    d = Path(state) / "pi-agent"
    d.mkdir(parents=True, exist_ok=True)
    base = json.loads((Path(agent) / "models.json").read_text())
    if info is None:
        info = show(base_url, model_id) or props(base_url)
    tmp = d / "models.json.tmp"
    tmp.write_text(json.dumps(models_json(base, model_id, base_url, info), indent=1) + "\n")
    tmp.replace(d / "models.json")
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m loop.pi_models")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ollama-agent", help="the agent directory with an Ollama model as pi's provider")
    p.add_argument("--state", required=True, help="the workspace's .metis/")
    p.add_argument("--id", required=True, help="the Ollama model")
    p.add_argument("--base-url", required=True, help="the server's OpenAI-compatible URL (…/v1)")
    o = ap.parse_args(argv)
    print(ollama_agent(o.state, o.id, o.base_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
