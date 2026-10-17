"""The OpenAI-compatible adapter (agentic-loop s-3ddb3e87 step 2). Stdlib only.

The command face (`complete`; `python -m metis_loop_sdk.models openai-command
--base-url U --model M`): the prompt on stdin, the completion on stdout, for
the kernel's `command:` backend — one user message to U/chat/completions, not
streamed. The servers it is for:

  OpenRouter   https://openrouter.ai/api/v1, the key in $OPENROUTER_API_KEY
  Ollama       http://127.0.0.1:11434/v1, no key
  any other    OpenAI-compatible server, the key in the variable --key-env names

    [llm]
    endpoint = "command:python -m metis_loop_sdk.models openai-command --base-url https://openrouter.ai/api/v1 --model deepseek/deepseek-v4-pro"

Reasoning off where the API allows (formalize wants the answer, not minutes
of thought): OpenRouter's `reasoning: {"effort": "none"}`, elsewhere
OpenAI's `reasoning_effort: "none"` (Ollama maps it to think off). Only the
message's content is the completion; reasoning the server returns anyway is
dropped. Temperature 0 (formalize's), max_tokens bounded (2048, at most
MAX_TOKENS). On OpenRouter the request also asks for providers that keep no
prompts (`provider: {"data_collection": "deny"}`).

The key is read from the environment only (an argument would show in ps and
in the kernel's config), sent only as the Authorization header to the base
URL, and never printed: errors quote the server with anything key-shaped
masked. A key is sent to OpenRouter over https (openrouter.ai or a
subdomain, by the exact host), or wherever --key-env names one; nowhere
else (an OPENAI_API_KEY in the environment does not reach Ollama).

`log`, when given, gets one JSON line per call: the model, the tokens, the
cost the server reports (OpenRouter's usage.cost, USD), finish_reason, seconds."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

OPENROUTER = "https://openrouter.ai/api/v1"
MAX_TOKENS = 8192                     # the ceiling: a formalize draft is a page of LLP
RETRY = (429, 500, 502, 503, 504)     # the server's or a provider's hiccup: tried again
_KEYISH = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")


def is_openrouter(base_url: str) -> bool:
    """OpenRouter's host itself or one of its subdomains — not any host
    whose name merely ends in the letters (evilopenrouter.ai)."""
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


def key_env(base_url: str, name: Optional[str] = None) -> Optional[str]:
    """The variable the key is read from: the one named (the caller's
    choice), else OpenRouter's for OpenRouter over https only (never over
    plain http), else none (no Authorization header)."""
    if name:
        return name
    https = urllib.parse.urlparse(base_url).scheme == "https"
    return "OPENROUTER_API_KEY" if https and is_openrouter(base_url) else None


def body(prompt: str, model: str, base_url: str, max_tokens: int = 2048, temperature: float = 0,
         reasoning: str = "off", data_collection: str = "deny") -> dict:
    """The request: one user message; reasoning in the server's dialect
    ("default" sends none); OpenRouter's provider routing."""
    if not 0 < max_tokens <= MAX_TOKENS:
        raise ValueError("max_tokens %d: 1..%d" % (max_tokens, MAX_TOKENS))
    b = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False,
         "max_tokens": max_tokens, "temperature": temperature}
    effort = "none" if reasoning == "off" else reasoning
    if is_openrouter(base_url):
        if reasoning != "default":
            b["reasoning"] = {"effort": effort}
        b["provider"] = {"data_collection": data_collection}
    elif reasoning != "default":
        b["reasoning_effort"] = effort
    return b


def mask(text: str, key: Optional[str] = None) -> str:
    if key:
        text = text.replace(key, "sk-…")
    return _KEYISH.sub("sk-…", text)


_THINK = re.compile(r"^\s*<think>.*?</think>\s*", re.S)


def complete(prompt: str, model: str, base_url: str, key_var: Optional[str] = None,
             max_tokens: int = 2048, temperature: float = 0, reasoning: str = "off",
             data_collection: str = "deny", timeout: float = 600, retries: int = 2,
             log: Optional[str] = None, env=None) -> str:
    """One completion. Raises RuntimeError with the server's reason (key
    masked) on an HTTP error, an error body, or an answer with no content."""
    env = os.environ if env is None else env
    var = key_env(base_url, key_var)
    key = env.get(var) if var else None
    if var and not key:
        raise RuntimeError("%s is not set (the key is read from the environment only)" % var)
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = "Bearer " + key
    data = json.dumps(body(prompt, model, base_url, max_tokens, temperature, reasoning, data_collection)).encode()
    url = base_url.rstrip("/") + "/chat/completions"
    t0 = time.time()
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers),
                                        timeout=timeout) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            why = "HTTP %d: %s" % (e.code, e.read()[:400].decode(errors="replace"))
            if e.code not in RETRY or attempt == retries:
                raise RuntimeError(mask("%s %s" % (url, why), key)) from None
        except (urllib.error.URLError, OSError) as e:
            if attempt == retries:
                raise RuntimeError(mask("%s: %s" % (url, e), key)) from None
        time.sleep(2 * (attempt + 1))
    if out.get("error"):
        raise RuntimeError(mask("%s: %s" % (url, json.dumps(out["error"])[:400]), key))
    choice = (out.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    text = _THINK.sub("", text)
    usage = out.get("usage") or {}
    if log:
        os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps({"model": out.get("model") or model, "provider": out.get("provider"),
                                "prompt_chars": len(prompt), "prompt_tokens": usage.get("prompt_tokens"),
                                "completion_tokens": usage.get("completion_tokens"),
                                "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                                "cost": usage.get("cost"), "finish_reason": choice.get("finish_reason"),
                                "seconds": round(time.time() - t0, 1)}) + "\n")
    if not text.strip():
        raise RuntimeError("%s: no content in the answer (finish_reason %s)" % (model, choice.get("finish_reason")))
    return text
