"""The console's narrate seat on the Claude Agent SDK (CONSOLE-WS §4,
D3): `python -m loop.sdk_narrate [--model M]` — the kernel's narrate
prompt on stdin, one completion on stdout.

The gateway (personal mode) points a session's LLM endpoint at this
module through the kernel's EXISTING `command:` backend, so the kernel
is untouched: the certified material, the beat glosses and the system
doctrine are built exactly as for ollama, and only the completion moves
to Claude (default claude-haiku-4-5, the operator's login). The
terminal REPL never sees this endpoint — it narrates through ollama by
construction — and pages cannot set it (`command:` specs are refused
by the intent whitelist).

Containment, as the Agent Service's: no tools at all (one completion
over certified material), no MCP, no user/project settings, no session
persistence (nothing on disk, D4), one turn."""
import argparse
import asyncio
import sys

DEFAULT_MODEL = "claude-haiku-4-5"
# thinking budget (tokens): measured 2026-10-07 on 3lp with the console's
# narrate prompt — CLI default (unbounded) ~5k tokens / ~50 s and
# faithful; DISABLED ~4 s but it fused separate beats into one and once
# invented events (3/3 runs wrong); 1024 ~18 s and faithful. 0 = off.
DEFAULT_THINKING = 1024


def options(model: str, thinking: int = DEFAULT_THINKING):
    from claude_agent_sdk import ClaudeAgentOptions
    return ClaudeAgentOptions(
        tools=[],                         # no built-ins, and no MCP:
        strict_mcp_config=True,           # narration needs no tools
        setting_sources=[],
        max_turns=1,
        model=model,
        thinking=({"type": "enabled", "budget_tokens": int(thinking)}
                  if thinking else {"type": "disabled"}),
        extra_args={"no-session-persistence": None},
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
        raise RuntimeError(f"narrate via the SDK failed: {err}")
    return "".join(text).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m loop.sdk_narrate")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--thinking", type=int, default=DEFAULT_THINKING,
                    help="thinking budget in tokens (0 = off)")
    ns = ap.parse_args(argv)
    prompt = sys.stdin.read()
    try:
        sys.stdout.write(asyncio.run(complete(prompt, ns.model,
                                              ns.thinking)) + "\n")
    except Exception as e:                              # noqa: BLE001
        sys.stderr.write(f"{type(e).__name__}: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
