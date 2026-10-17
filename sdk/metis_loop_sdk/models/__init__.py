"""metis_loop_sdk.models — the model adapters (loop-sdk s-9aabd5a0;
brief/repo-alignment.md §3b). No API keys anywhere: Claude is the
operator's own `claude` login, Ollama a local server.

  claude   `claude -p`, three faces:
           command  prompt on stdin, completion on stdout — the kernel's
                    `command:` backend (narrate, formalize)
           seat     turn by turn with tool calls emulated as text lines
                    (--tools "", --resume per turn) — the specialist's seat
           chat     (chat.py) a local OpenAI-compatible /v1/chat/completions
                    over the seat — pi reaches Claude as an ordinary provider
  ollama   the think-off command face, and the probe: is the server up,
           and is the model on the GPU

The CLI: python -m metis_loop_sdk.models claude-command | claude-chat |
ollama-command | ollama-probe (--help on each)."""
