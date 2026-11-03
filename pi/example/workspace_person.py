#!/usr/bin/env python3
"""The workspace's flow with the MODEL driving and a scripted person over pi's RPC mode (docs/WORKSPACE.md §4-5;
loop-workspace s-5b4be5fa step 3): what the console does through the backend's `loop` channel, with loop/pi_rpc.py
as the client. The person drops nothing: a surprise waits in DIR/.metis/surprises/ (the backend's, or ws drop). The
person says the task once, approves (or, with --deny-first, refuses the first of) the gates, nudges when the model
stops before the surprise is ruled, and stops the session at --minutes. The spend cap is loop.sh's --budget (the
workspace extension refuses past it); the cost is pi's, as each assistant message reports it.

    example/workspace_person.py DIR [--budget USD] [--minutes 30] [--nudges 4] [--deny-first]
                                    [--model openrouter/deepseek/deepseek-v4-pro]

The key comes from the environment only (OPENROUTER_API_KEY): never an argument, never printed. Writes
DIR/.metis/workspace-person.md (the run as read) and .json (the events, the spend, how it ended)."""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))          # metis-loop: loop.pi_rpc
from loop.pi_rpc import PiRpc  # noqa: E402

TASK = ("A surprise waits in this workspace. Take it (surprise_next), read the trace around its tick with the trace tools, "
        "and write the smallest pack that makes the person's words true. Judge it with pack_propose, with no brain: the "
        "evidence alone. If the verdict is accepted, apply the pack to the member's own file with catalog_edit (one exact "
        "edit: the pack after its last include line), then rebuild the bundle with bundle_build. Note your progress with "
        "journal. Say in a few lines what the ruling found and what you applied.")
NUDGE = "Go on: the surprise is not ruled and applied yet. Take the next step with your tools."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path)
    ap.add_argument("--model", default="openrouter/deepseek/deepseek-v4-pro")
    ap.add_argument("--budget", default="1.00")
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--nudges", type=int, default=4)
    ap.add_argument("--deny-first", action="store_true")
    a = ap.parse_args()
    d = a.dir.resolve()
    if a.model.startswith("openrouter/") and not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("workspace_person: OPENROUTER_API_KEY from the environment (a paid model)")
    st = d / ".metis"
    md, js = st / "workspace-person.md", st / "workspace-person.json"
    lines = [f"# the workspace's flow, the model driving over RPC ({time.strftime('%Y-%m-%dT%H:%M:%S')}; {a.model}; budget {a.budget} USD)\n"]

    def say(s):
        lines.append(s)
        print(s, flush=True)
        md.write_text("\n".join(lines) + "\n")

    env = dict(os.environ, MODEL=a.model, METIS_CATALOG=str(d))
    argv = [str(HERE.parent / "loop.sh"), "--budget", a.budget, "--mode", "rpc"]   # loop.sh's own options first, then pi's
    rec = {"model": a.model, "budget": float(a.budget), "events": [], "usd": 0.0, "requests": 0, "gates": [], "ended": None, "verdict": None}

    async def go():
        rpc = PiRpc(argv, cwd=str(d), env=env)
        await rpc.start()
        say(f"pi ready (pid {rpc.pid})\n\n**the person:** {TASK}\n")
        await rpc.say(TASK)
        t0, nudges, denied, ruled = time.time(), 0, False, False
        evs = rpc.events()
        while True:
            left = a.minutes * 60 - (time.time() - t0)
            if left <= 0:
                rec["ended"] = f"{a.minutes} minutes"
                break
            try:
                ev = await asyncio.wait_for(evs.__anext__(), left)
            except (asyncio.TimeoutError, StopAsyncIteration):
                rec["ended"] = rec["ended"] or f"{a.minutes} minutes"
                break
            rec["events"].append(ev)
            k = ev["kind"]
            if k == "text":
                say(f"**the model:** {ev['text'].strip()}\n")
            elif k == "tool_call":
                say(f"→ `{ev['name']}` {json.dumps(ev['args'])[:600]}")
            elif k == "tool_result":
                say(f"  ← {'ok' if ev['ok'] else 'ERROR'}: {ev['text'][:1500]}".replace("\n", "\n    "))
                if ev["name"] == "pack_propose" and ev["ok"]:
                    ruled = True
                    verdict = ev["text"].split(":", 1)[0].strip()
                    rec["verdict"] = verdict
                    if verdict != "accepted":           # ruled: nothing to apply; the person ends the session here
                        say(f"\n**the person:** the surprise is ruled {verdict}: that is the session's end.")
                        rec["ended"] = f"the ruling ({verdict})"
                        break
            elif k == "usage":
                rec["usd"] += ev["cost"] or 0
                rec["requests"] += 1
            elif k == "gate":
                ok = not (a.deny_first and not denied)
                denied = denied or not ok
                rec["gates"].append({"title": ev["plan"]["title"], "approved": ok})
                say(f"  **gate:** {ev['plan']['title']} — the person {'approves' if ok else 'refuses'}")
                await rpc.answer(ev["token"], ok)
            elif k == "notify":
                say(f"  _notify ({ev['level']}): {ev['text']}_")
                if "budget is spent" in ev["text"]:
                    rec["ended"] = "the budget"
            elif k == "error":
                say(f"  _error ({ev['where']}): {ev['error']}_")
            elif k == "turn_end":
                if rec["ended"] == "the budget":
                    break
                built = any(e["kind"] == "tool_result" and e["name"] == "bundle_build" and e["ok"] for e in rec["events"])
                if built or nudges >= a.nudges or (ruled and rec.get("verdict") != "accepted"):
                    rec["ended"] = "the work done" if built else f"{nudges} nudges"
                    break
                nudges += 1
                say(f"\n**the person:** {NUDGE}\n")
                await rpc.say(NUDGE)
            elif k == "exit":
                rec["ended"] = rec["ended"] or f"pi exited ({ev['code']})"
                break
        await rpc.stop()
        rec["ruled"] = ruled

    try:
        asyncio.run(go())
    finally:
        say(f"\nended: {rec['ended']}; {rec['requests']} requests, {rec['usd']:.4f} USD by pi's usage")
        js.write_text(json.dumps(rec, indent=1, default=str))


if __name__ == "__main__":
    main()
