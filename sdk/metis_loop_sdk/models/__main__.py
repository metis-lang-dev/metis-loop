"""python -m metis_loop_sdk.models <face> … — the model adapters for
non-Python consumers (the kernel's `command:` backend, pi, scripts).

  claude-command  [--model M] [--thinking N]     prompt on stdin → completion on stdout
  ollama-command  --model M [--url U] [--num-predict N] [--timeout S]
                                                 prompt on stdin → completion (thinking off)
  openai-command  --base-url U --model M [--key-env NAME] [--max-tokens N]
                  [--reasoning off|low|medium|high|default] [--data-collection deny|allow]
                  [--temperature T] [--timeout S] [--log FILE]
                                                 an OpenAI-compatible server (OpenRouter, Ollama's
                                                 /v1): prompt on stdin → completion, reasoning off;
                                                 the key from the environment only
  ollama-probe    [--url U] [--model M] [--load] the server, its models, the GPU: one JSON
                                                 object; exit 0 on the GPU, 3 on the CPU,
                                                 2 down/unknown"""
import argparse
import asyncio
import json
import os
import sys

from . import claude, ollama, openai


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m metis_loop_sdk.models",
                                 description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="face", required=True)
    c = sub.add_parser("claude-command", help="claude: prompt on stdin, completion on stdout")
    c.add_argument("--model", default=claude.DEFAULT_MODEL)
    c.add_argument("--thinking", type=int, default=claude.DEFAULT_THINKING, help="thinking budget in tokens (0 = off)")
    o = sub.add_parser("ollama-command", help="ollama: prompt on stdin, completion on stdout, thinking off")
    o.add_argument("--model", required=True)
    o.add_argument("--url", default=ollama.DEFAULT_URL)
    o.add_argument("--num-predict", type=int, default=2048)
    o.add_argument("--timeout", type=int, default=600)
    w = sub.add_parser("openai-command", help="an OpenAI-compatible server: prompt on stdin, completion on stdout")
    w.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                   help="e.g. %s or http://127.0.0.1:11434/v1 (default $OPENAI_BASE_URL)" % openai.OPENROUTER)
    w.add_argument("--model", default=os.environ.get("OPENAI_MODEL"), help="default $OPENAI_MODEL")
    w.add_argument("--key-env", help="the variable holding the key (default: OPENROUTER_API_KEY on OpenRouter, "
                                     "else none is sent)")
    w.add_argument("--max-tokens", type=int, default=2048, help="at most %d" % openai.MAX_TOKENS)
    w.add_argument("--reasoning", default="off", choices=("off", "low", "medium", "high", "default"))
    w.add_argument("--data-collection", default="deny", choices=("deny", "allow"), help="OpenRouter's provider routing")
    w.add_argument("--temperature", type=float, default=0)
    w.add_argument("--timeout", type=int, default=600)
    w.add_argument("--log", help="append one JSON line per call: tokens, cost, finish_reason, seconds")
    p = sub.add_parser("ollama-probe", help="ollama: up? which models? on the GPU?")
    p.add_argument("--url", default=ollama.DEFAULT_URL)
    p.add_argument("--model")
    p.add_argument("--load", action="store_true", help="load the model first (a GPU job)")
    a = ap.parse_args(argv)

    if a.face == "claude-command":
        try:
            sys.stdout.write(asyncio.run(claude.complete(sys.stdin.read(), a.model, a.thinking)) + "\n")
        except Exception as e:                              # noqa: BLE001
            sys.stderr.write(f"{type(e).__name__}: {e}\n")
            return 1
        return 0
    if a.face == "ollama-command":
        try:
            sys.stdout.write(ollama.generate(sys.stdin.read(), a.model, a.url, a.num_predict, a.timeout))
        except Exception as e:                              # noqa: BLE001
            sys.stderr.write(f"{type(e).__name__}: {e}\n")
            return 1
        return 0
    if a.face == "openai-command":
        if not a.base_url or not a.model:
            sys.stderr.write("openai-command needs --base-url and --model (or $OPENAI_BASE_URL, $OPENAI_MODEL)\n")
            return 2
        try:
            sys.stdout.write(openai.complete(sys.stdin.read(), a.model, a.base_url, a.key_env, a.max_tokens,
                                             a.temperature, a.reasoning, a.data_collection, a.timeout, log=a.log))
        except Exception as e:                              # noqa: BLE001
            sys.stderr.write(f"{type(e).__name__}: {openai.mask(str(e))}\n")
            return 1
        return 0
    r = ollama.probe(a.url, a.model, a.load)
    print(json.dumps(r, indent=1))
    return 0 if r["on_gpu"] else 3 if r["on_gpu"] is False else 2


if __name__ == "__main__":
    sys.exit(main())
