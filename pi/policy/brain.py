"""The brain: the formalization model the driver asks for rules (POLICY.md: OpenRouter or the
operator's `claude`), behind one call, with the run's cost log and the caps.

    b = Brain("openrouter/qwen/qwen3-235b-a22b-2507", run_dir, spend=0.50)
    text = b.ask(prompt, purpose="explore")   # the completion; one JSON line in RUN/cost.jsonl

Backends:
  openrouter/<model>   metis_loop_sdk.models.openai (reasoning off, temperature 0, providers that keep
                       no prompts); the key from $OPENROUTER_API_KEY only, never printed
  claude[/<model>]     the operator's `claude` login (metis_loop_sdk.models' claude-command under the
                       workspace's .venv; default claude-opus-5-5, thinking off), no spend
  script:<file>        the answers in a JSON-lines file ({"text", "when"?: a regex on the prompt, "keep"?}):
                       the first whose `when` matches, used once unless `keep` — the tests' and a
                       dry run's brain, no model

The caps (the pi-release lesson: a run's cost is guarded where it is spent, and pi's own count ran
~4x under the bill): every request is bounded (max_tokens, and the prompt's characters); with a
spend budget the KEY'S OWN USAGE (OpenRouter's /key, read before each call) is the meter — the
run stops (a Budget) before a call that would start past it. The cost log keeps what each call
reported beside the key's usage before it."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

SDK = Path(__file__).resolve().parents[2] / "sdk"          # metis-loop/sdk: metis_loop_sdk (stdlib adapters)
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))

OPENROUTER = "https://openrouter.ai/api/v1"


def sdk_python():
    """The python whose site has claude_agent_sdk: $METIS_LOOP_SDK_PY, else the workspace's .venv
    (the first parent with one)."""
    p = os.environ.get("METIS_LOOP_SDK_PY")
    if p:
        return p
    d = Path(__file__).resolve()
    for _ in range(8):
        d = d.parent
        c = d / ".venv" / "bin" / "python"
        if c.exists():
            return str(c)
    return sys.executable


class Budget(RuntimeError):
    """The run's spend is exhausted: the driver disengages (reason budget)."""


class Brain:
    def __init__(self, model, run_dir, spend=None, max_tokens=2048, prompt_chars=40000, env=None):
        self.model, self.run_dir = model, Path(run_dir)
        self.spend, self.max_tokens, self.prompt_chars = spend, max_tokens, prompt_chars
        self.env = os.environ if env is None else env
        self.log = self.run_dir / "cost.jsonl"
        self.calls, self.script, self.start_usage = 0, None, None
        if model.startswith("script:"):
            p = Path(model[len("script:"):])
            self.script = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        elif model.startswith("openrouter/") and spend is not None:
            self.start_usage = self.usage()

    @property
    def paid(self):
        return self.model.startswith("openrouter/")

    def usage(self):
        """The key's usage so far (USD), from OpenRouter's /key; the key is sent only there."""
        key = self.env.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (the key is read from the environment only)")
        req = urllib.request.Request(OPENROUTER + "/key", headers={"authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read()).get("data") or {}
        return float(d.get("usage") or 0.0)

    def reported(self):
        """The calls' reported costs (USD), summed over the run's cost log (every resume's calls too)."""
        return sum(float(json.loads(l).get("cost") or 0) for l in self.log.read_text().splitlines()) if self.log.exists() else 0.0

    def spent(self):
        """USD spent by this run: the larger of the key's usage since the run's first start (a paid
        brain with a budget; OpenRouter's /key can lag the calls) and the calls' reported costs."""
        if self.start_usage is not None:
            return max(self.usage() - self.start_usage, self.reported())
        return self.reported()

    def keep(self, state):
        """The meter across resumes (nina's R1): the run's first start_usage and its cap live in
        the run's state; a resumed brain takes them, it never starts the meter again."""
        if not (self.paid and self.spend is not None):
            return
        if state.get("spend_start") is None:
            state["spend_start"], state["spend_cap"] = self.start_usage, self.spend
        else:
            self.start_usage, self.spend = state["spend_start"], state["spend_cap"]

    def ask(self, prompt, purpose=""):
        if len(prompt) > self.prompt_chars:
            raise ValueError("the prompt is %d characters, past the per-request cap %d" % (len(prompt), self.prompt_chars))
        before = None
        if self.paid and self.spend is not None:
            before = self.spent()
            if before >= self.spend:
                raise Budget("spent %.4f of %.4f USD" % (before, self.spend))
        self.calls += 1
        t0 = time.time()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.script is not None:
            import re
            k = next((i for i, e in enumerate(self.script) if not e.get("when") or re.search(e["when"], prompt, re.S)), None)
            if k is None:
                raise Budget("the script has no answer for this prompt")
            text = (self.script[k] if self.script[k].get("keep") else self.script.pop(k))["text"]
            self._log({"model": self.model, "purpose": purpose, "cost": 0, "prompt_chars": len(prompt)})
        elif self.paid:
            from metis_loop_sdk.models import openai
            calls = self.run_dir / "calls.jsonl"
            text = openai.complete(prompt, self.model[len("openrouter/"):], OPENROUTER, max_tokens=self.max_tokens,
                                   log=str(calls), env=self.env)
            last = json.loads(calls.read_text().splitlines()[-1])
            self._log(dict(last, purpose=purpose, usage_before=before))
        elif self.model.split("/")[0] == "claude":
            # the SDK's command face under the python that has claude_agent_sdk (the workspace's .venv:
            # $METIS_LOOP_SDK_PY), the prompt on stdin: the operator's login, no spend
            import subprocess
            m = self.model.split("/", 1)[1] if "/" in self.model else "claude-opus-5-5"
            r = subprocess.run([sdk_python(), "-m", "metis_loop_sdk.models", "claude-command", "--model", m, "--thinking", "0"],
                               input=prompt, text=True, capture_output=True, timeout=900,
                               env=dict(self.env, PYTHONPATH=str(SDK)))
            if r.returncode != 0:
                raise RuntimeError("claude-command: %s" % r.stderr.strip()[-400:])
            text = r.stdout
            self._log({"model": self.model, "purpose": purpose, "cost": 0, "prompt_chars": len(prompt)})
        else:
            raise ValueError("brain %r: openrouter/<model> | claude[/<model>] | script:<file>" % self.model)
        with open(self.run_dir / "prompts.jsonl", "a") as f:                 # what the brain was given and said
            f.write(json.dumps({"call": self.calls, "purpose": purpose, "prompt": prompt, "answer": text,
                                "seconds": round(time.time() - t0, 1)}) + "\n")
        return text

    def _log(self, rec):
        with open(self.log, "a") as f:
            f.write(json.dumps(dict(rec, call=self.calls, t=time.strftime("%Y-%m-%dT%H:%M:%S"))) + "\n")


# ── the answer: lines to splice into the base ──
def block_of(text):
    """The answer's ```llp block (else the whole answer): its lines."""
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            body = parts[i]
            if body.startswith(("llp", "metis", "ll")):
                body = body.split("\n", 1)[1] if "\n" in body else ""
            return [l.rstrip() for l in body.splitlines()]
    return [l.rstrip() for l in text.splitlines()]


def splice(base, lines):
    """The base with the answer's lines in it: `pred …` declarations before the first stage (a
    name already declared is left), each rule (with the `%%` lines above it) into the stage
    block — replacing the rule of the same name, else added at its end; `drop NAME` removes a
    rule. → (text, {added, replaced, dropped, declared})."""
    out = base.splitlines()
    declared = {l.split()[1].split("(")[0].rstrip(":").strip() for l in out if l.strip().startswith(("pred ", "bwd "))}
    preds, rules, drops, doc = [], [], [], []
    for l in lines:
        s = l.strip()
        if not s or (s.startswith("%") and not s.startswith("%%")):
            continue
        if s.startswith("%%"):
            doc.append("  " + s)
        elif s.startswith(("pred ", "bwd ")):
            if s.split()[1].split("(")[0].rstrip(":").strip() not in declared:
                preds.append(s)
        elif s.startswith("drop "):
            drops.append(s.split()[1])
        elif ":" in s and "-o" in s:
            rules.append((s.split()[0], doc + ["  " + s]))
            doc = []
    st = next(i for i, l in enumerate(out) if l.strip().startswith("stage ") and l.strip().endswith("{"))
    end = next(i for i in range(st, len(out)) if out[i].strip() == "}")
    body = out[st + 1:end]
    info = {"added": [], "replaced": [], "dropped": [], "declared": [p.split()[1].split("(")[0] for p in preds]}

    def without(body, name):
        keep, i = [], 0
        while i < len(body):
            s = body[i].strip()
            if s.startswith("%%"):
                j = i
                while j < len(body) and body[j].strip().startswith("%%"):
                    j += 1
                if j < len(body) and body[j].strip().split()[:1] == [name]:
                    i = j + 1
                    continue
            if s.split()[:1] == [name] and ":" in s:
                i += 1
                continue
            keep.append(body[i])
            i += 1
        return keep
    for name in drops:
        b2 = without(body, name)
        if len(b2) != len(body):
            info["dropped"].append(name)
        body = b2
    for name, text in rules:
        b2 = without(body, name)
        (info["replaced"] if len(b2) != len(body) else info["added"]).append(name)
        body = b2 + text
    new = out[:st] + preds + out[st:st + 1] + body + out[end:]
    return "\n".join(new) + "\n", info
