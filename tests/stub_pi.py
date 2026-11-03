#!/usr/bin/env python3
"""A stand-in for `pi --mode rpc` (loop/pi_rpc.py's tests, and the gateway's loop channel): the protocol's records
as pi 1.3.0 writes them (docs/rpc.md, rpc-commands.md, rpc-extension-ui.md, json.md), no model, no cost.

  prompt "...apply..."  an assistant message, a catalog_edit tool call, the gate's confirm request; on the
                        answer, the tool's result (applied | refused by the person); a select it expects
                        cancelled; a notify; then agent_settled
  prompt "...abandon..." a confirm request, then the turn ends without waiting for its answer
  prompt (any other)    an assistant message ("heard: <msg>", with U+2028 inside: one record, not two), agent_settled
  get_state / abort     their responses
  stdin closed          exit 0 (pi's orderly shutdown)
STUB_PI_DIE=1: exit 3 at once with "boom" on stderr. STUB_PI_MUTE=1: never answer (a pi that hangs).
STUB_PI_ARGS: a file the argv and the cwd are written to (JSON)."""
import json
import os
import sys

if os.environ.get("STUB_PI_ARGS"):
    with open(os.environ["STUB_PI_ARGS"], "w") as f:
        json.dump({"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin_devnull": os.path.realpath("/proc/self/fd/0") == "/dev/null"}, f)
if os.environ.get("STUB_PI_DIE"):
    sys.stderr.write("boom: the stand-in died\n")
    sys.exit(3)
sys.stderr.write("stub pi: ready\n")
sys.stderr.flush()


def out(rec):
    sys.stdout.write(json.dumps(rec) + "\n")
    sys.stdout.flush()


def read():
    line = sys.stdin.readline()
    return json.loads(line) if line.strip() else (None if not line else read())


def assistant(text, cost=0.0):
    out({"type": "message_end", "message": {"role": "assistant", "model": "stub/model", "content": [{"type": "text", "text": text}],
                                            "usage": {"cost": {"total": cost}}}})


while True:
    rec = read()
    if rec is None:
        sys.exit(0)
    if os.environ.get("STUB_PI_MUTE"):
        continue
    t, cid = rec.get("type"), rec.get("id")
    if t == "get_state":
        out({"id": cid, "type": "response", "command": "get_state", "success": True, "data": {"model": {"id": "stub/model"}, "isStreaming": False}})
    elif t == "abort":
        out({"id": cid, "type": "response", "command": "abort", "success": True})
    elif t == "prompt":
        msg = rec.get("message", "")
        out({"id": cid, "type": "response", "command": "prompt", "success": True, "data": {"disposition": "started"}})
        out({"type": "agent_start"})
        out({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "he"}})
        if "abandon" in msg:                       # a gate pi gives up on: the turn ends with it unanswered
            out({"type": "extension_ui_request", "id": "g3", "method": "confirm", "title": "Apply?", "message": "a diff"})
        elif "apply" in msg:
            assistant("I apply the pack.", 0.002)
            out({"type": "tool_execution_start", "toolCallId": "t1", "toolName": "catalog_edit", "args": {"domain": "planner"}})
            out({"type": "extension_ui_request", "id": "g1", "method": "select", "title": "which?", "options": ["a", "b"]})
            sel = read()
            assert sel == {"type": "extension_ui_response", "id": "g1", "cancelled": True}, sel
            out({"type": "extension_ui_request", "id": "g2", "method": "confirm", "title": "Edit in the catalog: domains/planner/planner.llp?",
                 "message": "--- a/planner.llp\n+++ b/planner.llp"})
            ans = read()
            ok = ans.get("type") == "extension_ui_response" and ans.get("id") == "g2" and ans.get("confirmed") is True
            out({"type": "extension_ui_request", "id": "n1", "method": "notify", "message": "applied" if ok else "refused", "notifyType": "info"})
            out({"type": "tool_execution_end", "toolCallId": "t1", "toolName": "catalog_edit",
                 "result": {"content": [{"type": "text", "text": "applied: domains/planner/planner.llp" if ok else "refused by the person"}]}, "isError": not ok})
        else:
            assistant("heard: " + msg)
        out({"type": "agent_end", "messages": [], "willRetry": False})
        out({"type": "agent_settled", "aborted": False})
    else:
        out({"id": cid, "type": "response", "command": t, "success": False, "error": f"unknown command: {t}"})
