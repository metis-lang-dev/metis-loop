"""python -m metis_loop_sdk.models <face> … — the model adapters for
non-Python consumers (the kernel's `command:` backend, pi, scripts).

  claude-command  [--model M] [--thinking N]     prompt on stdin → completion on stdout
  ollama-command  --model M [--url U] [--num-predict N] [--timeout S]
                                                 prompt on stdin → completion (thinking off)
  ollama-probe    [--url U] [--model M] [--load] the server, its models, the GPU: one JSON
                                                 object; exit 0 on the GPU, 3 on the CPU,
                                                 2 down/unknown"""
import argparse
import asyncio
import json
import sys

from . import claude, ollama


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
    r = ollama.probe(a.url, a.model, a.load)
    print(json.dumps(r, indent=1))
    return 0 if r["on_gpu"] else 3 if r["on_gpu"] is False else 2


if __name__ == "__main__":
    sys.exit(main())
