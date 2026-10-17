"""The Ollama adapter (brief/repo-alignment.md §3b). Stdlib only.

The command face (`generate`; `python -m metis_loop_sdk.models
ollama-command --model M`): the prompt on stdin, the completion on stdout,
for the kernel's `command:` backend. Thinking off: metispy's own ollama
backend posts /api/generate without `think`, and Gemma 4 then thinks for
minutes per draft (agentic-loop s-3ddb3e87 step 1, finding 3); this asks for
the answer only, at temperature 0 (formalize's), capped. It was metis-agent's
tools/pi/ollama/generate.py.

    [llm]
    endpoint = "command:python -m metis_loop_sdk.models ollama-command --model metis-gemma4-e4b"

The probe (`probe`; `python -m metis_loop_sdk.models ollama-probe`): is the
server up, which models it holds, and is a model on the GPU (its /api/ps
size_vram). The case it exists for (agentic-loop step 1, finding 5): the
system service probes the GPU once, at start; started before the NVIDIA
driver was up it serves CPU only, silently, until restarted."""
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Callable, Optional

DEFAULT_URL = "http://127.0.0.1:11434"


def _post(url: str, path: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(url: str, path: str, timeout: float) -> dict:
    with urllib.request.urlopen(url.rstrip("/") + path, timeout=timeout) as r:
        return json.loads(r.read())


def generate(prompt: str, model: str, url: str = DEFAULT_URL, num_predict: int = 2048,
             timeout: float = 600, temperature: float = 0) -> str:
    """One completion, thinking off."""
    body = {"model": model, "prompt": prompt, "stream": False, "think": False,
            "options": {"temperature": temperature, "num_predict": num_predict}}
    return _post(url, "/api/generate", body, timeout)["response"]


def _gpu_present() -> Optional[str]:
    """The host's NVIDIA GPU, by nvidia-smi -L (None: none seen)."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out.splitlines()[0].split(" (UUID")[0] if out else None


def probe(url: str = DEFAULT_URL, model: Optional[str] = None, load: bool = False,
          timeout: float = 120, gpu_present: Optional[Callable] = None) -> dict:
    """{"url", "up", "version", "loaded": [{name, size, size_vram, gpu}],
    "model", "on_gpu": True (all of it in VRAM) | False (on the CPU, or
    split) | None (unknown), "why"}. load=True loads the model
    first (an empty generate, kept 5 min) — a GPU job: one at a time."""
    gpu_present = gpu_present or _gpu_present
    out = {"url": url, "up": False, "version": None, "loaded": [], "model": model, "on_gpu": None, "why": ""}
    try:
        out["version"] = _get(url, "/api/version", 10).get("version")
        out["up"] = True
    except (OSError, ValueError) as e:
        out["why"] = "the server does not answer at %s: %s" % (url, e)
        return out
    if model and load:
        try:
            _post(url, "/api/generate", {"model": model, "prompt": "", "stream": False, "keep_alive": "5m"}, timeout)
        except urllib.error.HTTPError as e:
            out["why"] = "loading %s failed: HTTP %d %s" % (model, e.code, e.read()[:200].decode(errors="replace"))
            return out
        except (OSError, ValueError) as e:
            out["why"] = "loading %s failed: %s" % (model, e)
            return out
    try:
        ps = _get(url, "/api/ps", 10).get("models") or []
    except (OSError, ValueError) as e:
        out["why"] = "the server's /api/ps does not answer: %s" % e
        return out
    for m in ps:
        size, vram = m.get("size") or 0, m.get("size_vram") or 0
        out["loaded"].append({"name": m.get("name"), "size": size, "size_vram": vram,
                              "gpu": round(vram / size, 3) if size else 0.0})
    if not model:
        out["why"] = "no model named: %d loaded" % len(out["loaded"])
        return out
    hit = [m for m in out["loaded"] if m["name"] in (model, model + ":latest") or m["name"].split(":")[0] == model]
    if not hit:
        out["why"] = "%s is not loaded (load=True / --load loads it)" % model
        return out
    m = hit[0]
    out["on_gpu"] = m["size_vram"] >= m["size"] > 0       # a partial offload is not on the GPU: it runs at CPU speed
    if out["on_gpu"]:
        out["why"] = "%s: %.0f%% of %d MiB in VRAM" % (m["name"], 100 * m["gpu"], m["size"] >> 20)
    elif m["size_vram"] > 0:
        out["why"] = ("%s is split: only %.0f%% of %d MiB in VRAM, the rest on the CPU (the GPU's memory is short: "
                      "another model or process holds it?)" % (m["name"], 100 * m["gpu"], m["size"] >> 20))
    else:
        gpu = gpu_present()
        out["why"] = ("%s runs on the CPU although the host has a GPU (%s): the server most likely probed for it "
                      "before the driver was up — restart it (sudo systemctl restart ollama)" % (m["name"], gpu)
                      if gpu else "%s runs on the CPU (no NVIDIA GPU seen on this host)" % m["name"])
    return out
