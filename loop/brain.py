"""The console's brain (brain-choice s-c59b7b51): the model family its LLM
seats run on, a startup choice, so a person with a Claude subscription and a
person with an OpenRouter key both run the console locally.

    cd DIR && metis-loop                                   the default (below)
    cd DIR && metis-loop --brain claude                    the operator's Claude login (the Agent SDK)
    cd DIR && metis-loop --brain openrouter                OpenRouter, DEFAULTS' openrouter_model
    cd DIR && metis-loop --brain openrouter:deepseek/deepseek-v4-pro
    cd DIR && metis-loop --brain ollama                    the kernel's own [llm] endpoint

The choice: the CLI's --brain (run.sh: BRAIN=) > the dot file's `[console]
brain` > the default by what is here: claude when the Agent SDK is installed
(it carries its claude CLI; the login is the person's), else openrouter when
$OPENROUTER_API_KEY is set, else ollama. A brain that was asked for and
cannot run refuses at startup, naming the fix; the default never refuses.

The seats follow it per session, the dot file untouched (the gateway sets
the session's endpoint, as the narrate seat always did):

  claude      formalize on [console] formalize_model, narrate on narrate_model,
              both on the SDK's claude-command face (both Haiku, thinking 1024:
              the one spec both ran on before, when formalize read the
              narrate seat's endpoint); the agent seat on the Agent SDK
  openrouter  formalize on MODEL, narrate on openrouter_narrate_model, both
              through `python -m loop.brain openrouter-command` (below);
              the agent seat is off ("needs claude")
  ollama      formalize and narrate on the kernel's [llm] endpoint; the
              agent seat is off ("needs claude")

A person's `:llm X` in a session moves both seats to X, as it always did: the
brain's formalize endpoint is then not set for that session's formalize.
A shared instance has no brain: every LLM seat refuses there, as before.

    python -m loop.brain openrouter-command --model M --seat formalize|narrate
                         --session SID --log FILE --max-usd X

The kernel's `command:` backend for an OpenRouter seat: the prompt on stdin,
the completion on stdout, through the loop SDK's OpenAI-compatible face
(metis_loop_sdk.models.openai: the key from $OPENROUTER_API_KEY only, never an
argument; providers that keep no prompts). Formalize runs with 2048 tokens and
reasoning off (it wants the answer); narrate with [console] narrate_reasoning,
"low" by default, and 4096 tokens (its reasoning takes most of 2048): with
reasoning off both DeepSeek models narrated events a run never fired
(brain-choice step 1, the quiescent plant). Each call appends the face's own
log line, plus the session and the seat, to FILE
(DIR/.metis/formalize-calls.jsonl, the agentic loop's file and format). A
call starts only while the session's spend in FILE, by the cost the server
reports, is under X ([console] max_usd); past it the seat refuses with the
number."""
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

BRAINS = ("claude", "openrouter", "ollama")
LOG = "formalize-calls.jsonl"           # in the root's .metis/ (catalog.state())
STATE = ".metis"
REASONING = ("off", "low", "medium", "high")    # the SDK face's efforts (formalize: off)
FORMALIZE_TOKENS = 2048
NARRATE_TOKENS = 4096   # narrate's reasoning at low took 1827 of 2048 on the quiescent plant (the face's ceiling: 8192)


class BrainError(ValueError):
    """A brain that was asked for and cannot run here: the message names the fix."""


def claude_why() -> Optional[str]:
    """None when the claude brain can run here (the Agent SDK, with its claude
    CLI; the agent seat's own test), else why not."""
    from .agent_service import available
    return available()


def resolve(cfg: dict, env=None) -> dict:
    """{name, model}: the brain cfg names (`brain`: "" = the default by what
    is here), checked. Raises BrainError naming the fix."""
    env = os.environ if env is None else env
    spec = str(cfg.get("brain") or "").strip()
    name, _, model = spec.partition(":")
    if not name:
        name = ("claude" if claude_why() is None else
                "openrouter" if env.get("OPENROUTER_API_KEY") else "ollama")
    if name not in BRAINS:
        raise BrainError(f"brain {spec!r}: claude | openrouter[:MODEL] | ollama")
    if model and name != "openrouter":
        raise BrainError(f"brain {spec!r}: only openrouter takes a model "
                         f"(claude's is [console] narrate_model; ollama's the dot file's [llm] endpoint)")
    if name == "claude":
        why = claude_why()
        if why:
            raise BrainError(f"brain claude: {why} — install Claude Code (pip install "
                             f"'metis-loop[agent]', then log in with `claude`) or --brain openrouter")
        return {"name": "claude", "model": str(cfg.get("narrate_model") or "claude-haiku-4-5")}
    if name == "openrouter":
        if not env.get("OPENROUTER_API_KEY"):
            raise BrainError("brain openrouter: export OPENROUTER_API_KEY (read from the "
                             "environment only, never a file) or --brain claude")
        return {"name": "openrouter", "model": model or str(cfg["openrouter_model"])}
    return {"name": "ollama", "model": None}


def _command(argv) -> str:
    import shlex
    return "command:" + " ".join(shlex.quote(str(a)) for a in argv)


def seats(cfg: dict, sid: str = "", log: Optional[str] = None) -> dict:
    """The session's seats: {brain, formalize: (label, spec), narrate:
    (label, spec)}. A None spec leaves the kernel's endpoint; a shared
    instance has no seats at all (labels None)."""
    if cfg["mode"] == "shared":
        return {"brain": None, "formalize": (None, None), "narrate": (None, None)}
    b = resolve(cfg)
    kernel = cfg.get("narrate") != "sdk"            # [console] narrate = "llm": the kernel's endpoint
    if b["name"] == "claude":
        if kernel:                                  # as before: the session keeps the kernel's endpoint
            return {"brain": b, "formalize": ("llm", None), "narrate": ("llm (ollama)", None)}

        def face(model, thinking):
            return _command([sys.executable, "-m", "metis_loop_sdk.models", "claude-command",
                             "--model", model, "--thinking", int(thinking)])
        # two keys, one mechanism; the defaults are the one Haiku spec both seats ran on before
        # (formalize read the session's endpoint, the narrate seat's)
        fm = str(cfg.get("formalize_model") or "claude-haiku-4-5")
        return {"brain": b,
                "formalize": (f"{fm} (SDK)", face(fm, cfg.get("formalize_thinking", 1024))),
                "narrate": (f"{b['model']} (SDK)", face(b["model"], cfg.get("narrate_thinking", 1024)))}
    if b["name"] == "openrouter":
        def face(seat, model, *more):
            return _command([sys.executable, "-m", "loop.brain", "openrouter-command", "--model", model,
                             "--seat", seat, "--session", sid or "-", "--log", log or LOG,
                             "--max-usd", float(cfg["max_usd"]), *more])
        narr = str(cfg["openrouter_narrate_model"])
        return {"brain": b,
                "formalize": (f"{b['model']} (OpenRouter)", face("formalize", b["model"])),
                "narrate": (("llm (ollama)", None) if kernel else
                            (f"{narr} (OpenRouter)",
                             face("narrate", narr, "--reasoning", str(cfg["narrate_reasoning"]),
                                  "--max-tokens", NARRATE_TOKENS)))}
    return {"brain": b, "formalize": ("llm", None), "narrate": ("llm (ollama)", None)}


def describe(cfg: dict, log: Optional[str] = None) -> str:
    """The start line's words for the brain."""
    s = seats(cfg, log=log)
    b = s["brain"]
    if b is None:
        return "brain: none (shared instance: no LLM seat)"
    if b["name"] == "claude":
        return (f"brain: claude — formalize {s['formalize'][0]}, narrate {s['narrate'][0]}, the agent seat "
                f"{cfg.get('agent_model') or 'the CLI default'} (your Claude login)")
    if b["name"] == "openrouter":
        return (f"brain: openrouter — formalize {s['formalize'][0]}, narrate {s['narrate'][0]}; "
                f"at most {float(cfg['max_usd']):g} USD per session; each call and its cost in "
                f"{log or LOG}; the agent seat needs claude")
    return "brain: ollama — formalize and narrate on the dot file's [llm] endpoint"


def spent(log: str, session: str) -> float:
    """The session's spend in the log: the costs the server reported."""
    total = 0.0
    try:
        with open(log) as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("session") == session and isinstance(o.get("cost"), (int, float)):
                    total += o["cost"]
    except FileNotFoundError:
        pass
    return total


def openrouter_command(argv=None) -> int:
    import argparse

    from metis_loop_sdk.models import openai
    ap = argparse.ArgumentParser(prog="python -m loop.brain openrouter-command")
    ap.add_argument("--model", required=True)
    ap.add_argument("--seat", required=True, choices=("formalize", "narrate"))
    ap.add_argument("--session", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--reasoning", default="off", choices=REASONING)
    ap.add_argument("--max-tokens", type=int, default=FORMALIZE_TOKENS)
    a = ap.parse_args(argv)
    used = spent(a.log, a.session)
    if used >= a.max_usd:
        sys.stderr.write(f"this session has spent {used:.4f} USD on OpenRouter, its max_usd is "
                         f"{a.max_usd:g}: open a new session, or raise [console] max_usd\n")
        return 1
    prompt = sys.stdin.read()
    with tempfile.TemporaryDirectory() as t:
        one = os.path.join(t, "call.jsonl")
        try:
            text = openai.complete(prompt, a.model, openai.OPENROUTER, max_tokens=a.max_tokens,
                                   reasoning=a.reasoning, data_collection="deny", log=one)
        except Exception as e:                              # noqa: BLE001
            sys.stderr.write(f"{type(e).__name__}: {openai.mask(str(e))}\n")
            return 1
        finally:
            if os.path.exists(one):                     # the face's line, the session and seat added
                log = Path(a.log)
                if log.parent.name == STATE and not log.parent.is_dir():
                    from metis_loop_sdk import catalog
                    catalog.state(log.parent.parent)    # DIR/.metis/, git-ignored in a checkout
                log.parent.mkdir(parents=True, exist_ok=True)
                with open(one) as f, open(a.log, "a") as out:
                    for line in f:
                        out.write(json.dumps({**json.loads(line), "session": a.session, "seat": a.seat}) + "\n")
    sys.stdout.write(text)
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["openrouter-command"]:
        return openrouter_command(args[1:])
    sys.stderr.write("usage: python -m loop.brain openrouter-command --model M --seat S "
                     "--session SID --log FILE --max-usd X\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
