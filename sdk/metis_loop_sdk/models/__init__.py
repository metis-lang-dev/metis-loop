"""metis_loop_sdk.models — the model adapters (loop-sdk s-9aabd5a0;
brief/repo-alignment.md §3b). Claude is the operator's own `claude` login;
the one key, a hosted model's (openai), is read from the environment and
never written anywhere.

  claude   `claude -p`, two faces:
           command  prompt on stdin, completion on stdout — the kernel's
                    `command:` backend (narrate, formalize)
           seat     turn by turn with tool calls emulated as text lines
                    (--tools "", --resume per turn) — the specialist's seat
           (a third, an OpenAI-compatible chat endpoint over the seat for pi,
           is postponed with pi as the principal loop — brief v2; it was
           built and tested in 0a5e3d3, models/chat.py)
  openai   an OpenAI-compatible server's command face (OpenRouter, a
           local server's /v1): reasoning off, max_tokens bounded, the key from the
           environment only — the kernel's `command:` backend on a hosted
           model (agentic-loop s-3ddb3e87 step 2: formalize on DeepSeek)

The CLI: python -m metis_loop_sdk.models claude-command | openai-command
(--help on each). The Ollama faces went with loop-workspace (Ollama out of
the loop; WORKSPACE.md §5.3)."""
