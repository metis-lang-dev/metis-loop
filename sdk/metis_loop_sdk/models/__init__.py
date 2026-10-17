"""metis_loop_sdk.models — the model adapters (loop-sdk s-9aabd5a0;
brief/repo-alignment.md §3b). No API keys anywhere: Claude is the
operator's own `claude` login, Ollama a local server.

  claude   `claude -p`, two faces:
           command  prompt on stdin, completion on stdout — the kernel's
                    `command:` backend (narrate, formalize)
           seat     turn by turn with tool calls emulated as text lines
                    (--tools "", --resume per turn) — the specialist's seat
           (a third, an OpenAI-compatible chat endpoint over the seat for pi,
           is postponed with pi as the principal loop — brief v2; it was
           built and tested in 0a5e3d3, models/chat.py)
  ollama   the think-off command face, and the probe: is the server up,
           and is the model on the GPU

The CLI: python -m metis_loop_sdk.models claude-command |
ollama-command | ollama-probe (--help on each)."""
