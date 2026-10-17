"""The `claude -p` adapter (brief/repo-alignment.md §3b): no API key — the
operator's own `claude` login — and contained: no built-in tools, no MCP,
no user/project settings, no session left on disk where it is not needed.

The command face (`complete`; `python -m metis_loop_sdk.models
claude-command`): the prompt on stdin, one completion on stdout, through
the Agent SDK (extra `claude`). It plugs into the kernel's existing
`command:` backend, so the kernel builds its prompts exactly as for
ollama and only the completion moves to Claude. It was metis-loop's
loop/sdk_narrate.py (the console's narrate seat, CONSOLE-WS §4 D3); its
model and thinking defaults are kept here.

The seat face (`Seat`): a conversation turn by turn with the tool calls
emulated as text (route A). `claude -p --tools ""` has no native tool; the
system prompt carries the declarations as text and the protocol, the model
writes the call on a line of its own, the caller runs it and sends the
result as the next message. One claude session per question: the first
turn `--session-id U`, every later one `--resume U`, so the transcript is
real assistant/user turns and the system prompt is the cached prefix. Each
process runs with --safe-mode (no hooks, CLAUDE.md, plugins, MCP, skills)
in an empty directory, so the model sees only what the seat sends. It was
metis-agent's claude_seat.py (SPECIALIST.md §4), which now subclasses it
for the specialist's cont protocol. Two call protocols:
  REPL  `REPL: <verb> <arg>` — one string argument (the REPL's lines)
  JSON  `CALL: <tool> {json}` — named arguments (the chat endpoint's tools)

The chat face is chat.py, over the seat."""
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

# -- containment, shared by every Agent SDK use ---------------------------

def containment() -> dict:
    """The ClaudeAgentOptions keywords every contained use shares: no
    built-in tools, no MCP but what the caller passes, no user/project
    settings, nothing persisted. A caller adds its own (system prompt,
    MCP server, permission gate, turns, model)."""
    return {
        "tools": [],                      # no built-ins at all
        "strict_mcp_config": True,        # only the MCP the caller passes
        "setting_sources": [],            # no user/project settings
        "extra_args": {"no-session-persistence": None},   # nothing on disk
    }


# -- the command face -----------------------------------------------------

DEFAULT_MODEL = "claude-haiku-4-5"
# thinking budget (tokens): measured 2026-10-07 on 3lp with the console's
# narrate prompt — CLI default (unbounded) ~5k tokens / ~50 s and
# faithful; DISABLED ~4 s but it fused separate beats into one and once
# invented events (3/3 runs wrong); 1024 ~18 s and faithful. 0 = off.
DEFAULT_THINKING = 1024


def options(model: str = DEFAULT_MODEL, thinking: int = DEFAULT_THINKING):
    """The command face's options: one completion, no tools at all."""
    from claude_agent_sdk import ClaudeAgentOptions
    return ClaudeAgentOptions(
        **containment(),
        max_turns=1,
        model=model,
        thinking=({"type": "enabled", "budget_tokens": int(thinking)}
                  if thinking else {"type": "disabled"}),
    )


async def complete(prompt: str, model: str = DEFAULT_MODEL,
                   thinking: int = DEFAULT_THINKING) -> str:
    """One completion; raises on an SDK error result."""
    from claude_agent_sdk import query
    text, err = [], None
    async for msg in query(prompt=prompt, options=options(model, thinking)):
        kind = type(msg).__name__
        if kind == "AssistantMessage":
            text += [getattr(b, "text", "") for b in msg.content
                     if type(b).__name__ == "TextBlock"]
        elif kind == "ResultMessage" and msg.is_error:
            err = str(getattr(msg, "result", "") or msg.subtype)
    if err and not text:
        raise RuntimeError(f"claude via the SDK failed: {err}")
    return "".join(text).strip()


def available() -> Optional[str]:
    """None when the command face can run here, else why not."""
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return "claude-agent-sdk not installed (pip install 'metis-loop-sdk[claude]')"
    return None


# -- the seat face: the call protocols ------------------------------------

class ReplLines:
    """`REPL: <verb> <arg>`: tools of one string argument `arg` (the
    REPL's lines); a tool of named fields takes one JSON object."""
    text = """

How to call a tool: write the REPL line on a line of its own, starting with `REPL: `, then the tool name, then its argument exactly as you would type it, for example

REPL: state
REPL: step carry[A=near,X=goat,B=far]

and end your reply there. The next message is what the REPL printed. One REPL: line per reply. A reply with no REPL: line is your answer.

The tools:
"""
    LINE = re.compile(r"^\s*`?REPL:\s*([A-Za-z_]\w*)[ \t]*(.*?)`?\s*$", re.M)

    @staticmethod
    def declarations(tools) -> str:
        """The declarations as text: name, its help, its argument's shape."""
        out = []
        for t in tools:
            props = t["parameters"]["properties"]
            if "arg" in props:
                out.append("- %s: %s\n  argument: %s" % (t["name"], t["description"], props["arg"]["description"]))
            else:   # a tool of named fields (the consultant's answer): one JSON object on the line
                fields = "; ".join("%s%s: %s" % (k, " (one of %s)" % "/".join(v["enum"]) if v.get("enum") else "",
                                                 v.get("description", "")) for k, v in props.items())
                out.append("- %s: %s\n  argument: one JSON object on the line, e.g. REPL: %s {\"kind\": …}; fields: %s"
                           % (t["name"], t["description"], t["name"], fields))
        return "\n".join(out)

    @classmethod
    def parse(cls, text):
        """The first REPL: line → (verb, {"arg": arg}, said before it); None if none."""
        m = cls.LINE.search(text)
        if not m:
            return None
        return m.group(1), {"arg": m.group(2).strip()}, text[:m.start()].strip()


class JsonLines:
    """`CALL: <tool> {json}`: tools of named arguments (JSON schemas, as an
    OpenAI-style client declares them). A call whose JSON does not parse
    comes back with args None, so the caller can ask again."""
    text = """

How to call a tool: write one line starting with `CALL: `, then the tool's name, then its arguments as one JSON object, for example

CALL: domain_clock {"n": 3}
CALL: repl_state {}

and end your reply there. The next message is the tool's result. One CALL: line per reply: call one tool, read its result, then decide. A reply with no CALL: line is your answer to the person. Never write a tool's result yourself.

The tools:
"""
    HEAD = re.compile(r"^[ \t]*`?CALL:[ \t]*([A-Za-z_][\w.-]*)[ \t]*", re.M)

    @staticmethod
    def declarations(tools) -> str:
        out = []
        for t in tools:
            params = json.dumps(t.get("parameters") or {"type": "object", "properties": {}},
                                separators=(",", ":"), ensure_ascii=False)
            out.append("- %s: %s\n  arguments (JSON schema): %s" % (t["name"], (t.get("description") or "").strip(), params))
        return "\n".join(out)

    @classmethod
    def parse(cls, text):
        """The first CALL: line → (tool, args dict | None, said before it); None if none."""
        m = cls.HEAD.search(text)
        if not m:
            return None
        rest = text[m.end():].lstrip()
        said = text[:m.start()].strip()
        if not rest or rest[0] != "{":
            return m.group(1), ({} if not rest.strip(" `\n") else None), said
        try:
            args, _ = json.JSONDecoder().raw_decode(rest)
        except ValueError:
            return m.group(1), None, said
        return m.group(1), (args if isinstance(args, dict) else None), said


REPL = ReplLines
JSON = JsonLines


# -- the seat face --------------------------------------------------------

@dataclass
class Reply:
    text: str                       # the reply as received
    call: Optional[tuple]           # (tool, args, said) — None: the reply is the answer
    stop: str = "end_turn"
    ms: float = 0.0


@dataclass
class Seat:
    """`claude -p` turn by turn, the tool calls emulated (the module's
    docstring). `ask` runs one turn; `open` starts a new session."""
    model: str = "opus"
    effort: str = ""            # "" = the CLI's default
    timeout: float = 300.0
    cwd: str = ""
    session: str = ""
    protocol: type = ReplLines
    _turns: int = 0
    usage: dict = field(default_factory=dict)   # the last call's usage
    model_id: str = ""
    cost_usd: float = 0.0
    log: list = field(default_factory=list)     # one record per claude -p call

    def __post_init__(self):
        if not self.cwd:
            self.cwd = tempfile.mkdtemp(prefix="claude-seat-")

    def tokens(self):
        """Context tokens at the last call: its input (cached or not) + its output."""
        u = self.usage
        return (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0))

    def system(self, system, tools):
        return system.strip() + self.protocol.text + self.protocol.declarations(tools)

    def argv(self, sys_text, first):
        cmd = ["claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config",
               "--output-format", "json", "--model", self.model, "--system-prompt", sys_text]
        if self.effort:
            cmd += ["--effort", self.effort]
        return cmd + (["--session-id", self.session] if first else ["--resume", self.session])

    def open(self):
        """A new session: the next ask is its first turn."""
        self.session, self._turns, self.log = str(uuid.uuid4()), 0, []

    def _call(self, sys_text, prompt, first):
        env = dict(os.environ, METIS_CONFIG="")
        t0 = time.perf_counter()
        p = subprocess.run(self.argv(sys_text, first), input=prompt, capture_output=True, text=True,
                           cwd=self.cwd, env=env, timeout=self.timeout)
        ms = (time.perf_counter() - t0) * 1e3
        if p.returncode != 0:
            raise RuntimeError("claude -p exited %d: %s" % (p.returncode, (p.stderr or p.stdout)[-500:]))
        d = json.loads(p.stdout)
        self.usage = d.get("usage", {})
        self.model_id = next(iter(d.get("modelUsage", {})), self.model_id)
        self.cost_usd += d.get("total_cost_usd", 0.0)
        self.log.append({"turn": self._turns, "first": first, "prompt": prompt, "reply": d.get("result", ""),
                         "stop": d.get("stop_reason"), "ms": round(ms), "ms_api": d.get("duration_api_ms"),
                         "usage": {k: self.usage.get(k) for k in ("input_tokens", "cache_read_input_tokens",
                                                                  "cache_creation_input_tokens", "output_tokens")},
                         "thinking_tokens": self.usage.get("output_tokens_details", {}).get("thinking_tokens")})
        return d.get("result", ""), d.get("stop_reason") or "end_turn", ms

    def ask(self, system, tools, prompt, first=None) -> Reply:
        """One turn: the first of a new session when first (default: when
        no turn was taken since open), else a resume. The reply parsed by
        the seat's protocol."""
        if first is None:
            first = self._turns == 0
        if first:
            self.open()
        reply, stop, ms = self._call(self.system(system, tools), prompt, first)
        self._turns += 1
        return Reply(reply, self.protocol.parse(reply), stop, ms)
