"""The pi loop's model from the dot file (llm-config s-07a070ad): an Ollama model is pi's provider `ollama` over the
server's OpenAI-compatible URL/v1, written into an agent directory GENERATED for the start (DIR/.metis/pi-agent/:
pi/agent/models.json with the provider merged in). Why generated, not committed: the server's URL and
the model are the person's (their dot file's [llm] loop), and the committed pi/agent/models.json stays one file for
every host; why .metis/: the workspace's own state, git-ignored, rewritten at every start, so it never drifts.

    python -m loop.pi_models ollama-agent --state DIR/.metis --id phi4-mini --base-url http://127.0.0.1:11434/v1
        -> prints the agent directory (PI_CODING_AGENT_DIR for pi.sh)

The entry: api openai-completions, a dummy apiKey (Ollama ignores it; pi needs one to list the model), cost 0,
maxTokens 8192 (the loop's cap, as the openrouter entries), contextWindow and reasoning from Ollama's /api/show (its
context length; "thinking" in its capabilities), input text."""
import argparse
import json
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


def entry(model_id, info=None):
    """pi's models.json model entry for an Ollama model."""
    info = info or {}
    mi = info.get("model_info") or {}
    ctx = next((v for k, v in mi.items() if k.endswith(".context_length") and isinstance(v, int)), None) or CONTEXT
    caps = info.get("capabilities") or []
    return {"id": model_id, "name": f"{model_id} (Ollama)", "reasoning": "thinking" in caps, "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": ctx, "maxTokens": MAX_TOKENS}


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
        info = show(base_url, model_id)
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
