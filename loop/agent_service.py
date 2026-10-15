"""The console's Agent Service (docs/CONSOLE-WS.md §3, personal mode
only): the chat pane's Claude runs in the BACKEND on the operator's own
`claude login` (claude-agent-sdk) — no key or login ever reaches the
browser.

- System prompt = v1's PREAMBLE (read from the page, one source), in
  the real system slot — the CLI caches it across turns — plus a
  short addendum naming this backend's tools.
- Tools = ONE in-process MCP server pre-scoped to the window's session:
  `repl(line)` runs through the gateway's session queue (so it shows as
  a `claude>` line, obeys busy/stop and the same whitelist), `ctx()` and
  `transcript(n)` read the gateway's cached state without a REPL round.
  Results trimmed like v1's trimJson, text cut to its first/last 200
  lines; refusals come back as tool errors.
- Containment: NO built-in tools (`tools=[]`: no Bash/Read/Write on the
  operator's host), strict MCP config, a can_use_tool gate that denies
  anything but the three, no user/project settings loaded, and
  `--no-session-persistence` — nothing written to disk (D4).
- Caps: ≤ `agent_tool_calls` (10; the preamble states the configured value) tool calls per turn, a per-command
  timeout, `max_turns`; [stop] interrupts the SDK turn AND the running
  kernel command.
- History: in memory per session (D4) — a reload restores both panes
  while the backend lives; a restart starts clean.
"""
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Optional

TOOLS = ("repl", "ctx", "transcript", "source_read", "source_edit",
         "pack_create", "recompile", "apply", "intents_read", "intents_propose")
ALLOWED = tuple(f"mcp__metis__{t}" for t in TOOLS)
PAGE = Path(__file__).resolve().parent.parent / "console" / "loop_console.html"

ADDENDUM = """

== This console's backend (agent mode) ==
You run on the operator's host. Your tools, all scoped to the viewer's
session: `repl(line)` runs one REPL line (prefix ":"; it appears in the
transcript as claude>), `ctx()` returns the context at this stop without
a REPL round, `transcript(n)` returns the last n console lines (yours and
the viewer's). The WORKING COPY — the viewer's private, in-memory copy of
the catalog plus extension packs (each pack `extends` the copy and only
adds; the real catalog is touched only by apply()): `source_read(target)` shows it
with line numbers (target "copy" or "pack:N"), `source_edit(target,
old_str, new_str)` replaces one exact, unique piece of text,
`pack_create(name, source)` adds a pack, `recompile()` rebuilds the
session from copy + packs (until then the copy is UNCERTIFIED; a failed
recompile returns the findings and keeps the old world). `apply()` writes
a CERTIFIED copy (and its packs) into the catalog source — the operator's
checkout, the host side's verb: the person's "apply to catalog" — and
shows them the diff; metis-agent sees the change. Apply only when the
person asked for it or agreed, and say what you wrote. The viewer sees
every edit live in their editor. A domain's INTENTS (what the person may
ask it in the agent): `intents_read()` gives its intent.yaml or a draft
from the program, `intents_propose(text)` checks a whole new one and shows
the person the diff (they write it with `intents save`).

DIRECTIVES (spec §8): a line whose first non-blank character is `#` is
the interpreter's, not the compiler's (the program key does not change);
the body is one case-manifest line. The world's starting tokens are
`#init <atom> <count>` lines, one per atom, anywhere in the file (by
convention after the stages): `#init hand_free 1`, `#init pot_space 3`,
`#init at(door) 1`. A catalog with no #init lines opens EMPTY and
quiescent (its host or scene seeds it elsewhere) — to run it here, add
#init lines with source_edit (append after the last `}`) and recompile;
never invent declaration syntax for this. The other directives: `#steps
<n>`, `#seeds <n>`, `#query <atom>`, `#unknown <atom>`, `#lik <atom>=<v>`,
`#interactive <stage>`; `#plugin <spec>` and `#notch <file>` are the
served host's and stay as they are.

At most {cap} tool calls per answer — prefer ctx/transcript when they
answer the question. You have no other tools: no files, no shell, no web."""


def preamble(cfg: Optional[dict] = None) -> str:
    """v1's PREAMBLE, extracted from the page (the single source), plus the
    backend's addendum with the [console] cap the gate enforces."""
    cap = int((cfg or {}).get("agent_tool_calls", 10))
    src = PAGE.read_text()
    ver = re.search(r'const PREAMBLE_VERSION="([^"]*)"', src)
    m = re.search(r"const PREAMBLE=`(.*?)`;\n", src, re.S)
    if not m:
        raise RuntimeError("PREAMBLE not found in the console page")
    text = m.group(1).replace("${PREAMBLE_VERSION}",
                              ver.group(1) if ver else "?")
    return text.replace("\\`", "`") + ADDENDUM.replace("{cap}", str(cap))


def available() -> Optional[str]:
    """None when the agent seat can run here, else the reason."""
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return "claude-agent-sdk is not installed (pip install " \
               "'metis-loop[agent]')"
    return None


def trim_json(j, cap=30):
    """v1's trimJson: small and plain (each tool round costs)."""
    if not isinstance(j, dict):
        return j
    o = {}
    for k, v in j.items():
        if k in ("text", "src", "dot", "narration"):
            continue
        if k == "fired" and isinstance(v, list):
            o["fired"] = [{x: f.get(x) for x in ("i", "name", "beat", "kind",
                                                 "consume", "produce")}
                          for f in v[:cap]]
        elif k == "rules" and isinstance(v, list):
            o["rules"] = [{x: r.get(x) for x in ("name", "state", "detail")}
                          for r in v]
        elif k in ("nodes", "edges"):
            o[k + "_count"] = len(v) if isinstance(v, list) else 0
        elif isinstance(v, list):
            o[k] = v[:cap]
        else:
            o[k] = v
    return o


def truncate(text: str, keep=200) -> str:
    """First/last `keep` lines of a long result (§3 caps)."""
    lines = str(text or "").splitlines()
    if len(lines) <= 2 * keep:
        return "\n".join(lines)
    return "\n".join(lines[:keep] + [f"… [{len(lines) - 2 * keep} lines "
                                     "cut] …"] + lines[-keep:])


def _ok(obj):
    return {"content": [{"type": "text", "text": json.dumps(obj,
                                                            default=str)}]}


def _err(msg):
    return {"content": [{"type": "text", "text": msg}], "is_error": True}


class Chat:
    """One session's chat: the SDK client (memory only), the turns."""

    def __init__(self, sid: str):
        self.sid = sid
        self.client = None
        self.turns = []                 # [{role, content, tools}]
        self.task: Optional[asyncio.Task] = None
        self.reply: Optional[dict] = None
        self.calls = 0


class AgentService:
    def __init__(self, gw, cfg: dict, client_factory=None):
        self.gw, self.cfg = gw, cfg
        self.chats: Dict[str, Chat] = {}
        self.client_factory = client_factory       # tests inject a fake
        self.system = preamble(cfg)

    # -- tools (pre-scoped to one session) -------------------------------

    def tool_fns(self, chat: Chat):
        """The three tools as plain async callables (args dict -> MCP
        result dict) — wrapped for the SDK in `_server`, called directly
        by tests."""
        gw, cfg = self.gw, self.cfg
        cap = int(cfg.get("agent_tool_calls", 10))
        timeout = float(cfg.get("agent_cmd_timeout", 60))

        def counted():
            if chat.calls >= cap:
                return _err(f"tool-call cap reached ({cap} per answer) — "
                            "answer with what you have")
            chat.calls += 1
            return None

        async def repl(args):
            over = counted()
            if over:
                return over
            s = gw.sessions.get(chat.sid)
            if not s:
                return _err("the session is gone")
            line = str(args.get("line", "")).strip()
            rec = {"line": line, "status": "queued"}
            if chat.reply is not None:
                chat.reply["tools"].append(rec)
            await self._emit(chat, {"type": "tool", **rec,
                                    "n": len(chat.reply["tools"])
                                    if chat.reply else 0})
            try:
                post = await asyncio.wait_for(
                    gw.submit(s, line, "claude"), timeout)
            except asyncio.TimeoutError:
                rec["status"] = f"timed out ({timeout:g}s)"
                await self._emit(chat, {"type": "tool", **rec,
                                        "n": len(chat.reply["tools"])})
                return _err(f"no result within {timeout:g}s — the command "
                            "may still be running")
            rec["status"] = post.get("status")
            await self._emit(chat, {"type": "tool", **rec,
                                    "n": len(chat.reply["tools"])})
            out = {"status": post.get("status"),
                   "result": truncate(post.get("result")),
                   "json": trim_json(post.get("json"))}
            if post.get("status") == "refused":
                return _err("refused by the console whitelist: " +
                            str(post.get("result"))[:400])
            return _ok(out)

        async def ctx(args):
            over = counted()
            if over:
                return over
            s = gw.sessions.get(chat.sid)
            if not s:
                return _err("the session is gone")
            c = gw._session_frame(s).get("ctx") or {}
            return _ok(trim_json({k: v for k, v in c.items()
                                  if k != "file"}))

        async def transcript(args):
            over = counted()
            if over:
                return over
            s = gw.sessions.get(chat.sid)
            if not s:
                return _err("the session is gone")
            n = max(1, min(int(args.get("n") or 10), 50))
            posts = [f for f in s.log if f.get("type") == "posting"][-n:]
            return _ok([{"actor": f.get("actor"), "cmd": f.get("cmd"),
                         "status": f.get("status"),
                         "result": truncate(f.get("result"), 20)}
                        for f in posts])
        def work_of(target):
            s = gw.sessions.get(chat.sid)
            if not s or not getattr(s, "work", None):
                return None, None, "the session has no working copy"
            t = str(target or "copy")
            if t == "copy":
                return s, ("copy", None), None
            if t.startswith("pack:") and t[5:].isdigit() and \
                    1 <= int(t[5:]) <= len(s.work["packs"]):
                return s, ("pack", int(t[5:]) - 1), None
            return None, None, (f"no target {t!r} — use 'copy' or "
                                f"'pack:1'..'pack:{len(s.work['packs'])}'")

        def text_of(s, where):
            return s.work["copy"] if where[0] == "copy" else \
                s.work["packs"][where[1]]["source"]

        async def source_read(args):
            over = counted()
            if over:
                return over
            s, where, err = work_of(args.get("target"))
            if err:
                return _err(err)
            lines = text_of(s, where).splitlines()
            a = max(1, int(args.get("start") or 1))
            b = min(len(lines), int(args.get("end") or len(lines)))
            body = "\n".join(f"{k:4} {lines[k - 1]}" for k in range(a, b + 1))
            return _ok({"target": args.get("target") or "copy",
                        "certified": s.work["certified"],
                        "lines": f"{a}-{b} of {len(lines)}",
                        "text": truncate(body)})

        async def source_edit(args):
            over = counted()
            if over:
                return over
            s, where, err = work_of(args.get("target"))
            if err:
                return _err(err)
            old, new = str(args.get("old_str", "")), str(args.get("new_str", ""))
            text = text_of(s, where)
            n = text.count(old) if old else 0
            if n != 1:
                return _err(f"old_str must occur exactly once (found {n}) "
                            "— read the source and quote a unique piece")
            text = text.replace(old, new, 1)
            if where[0] == "copy":
                s.work["copy"] = text
            else:
                s.work["packs"][where[1]]["source"] = text
            s.work["certified"] = None
            await gw._broadcast(s, gw._source_frame(s))
            return _ok({"edited": args.get("target") or "copy",
                        "certified": None,
                        "note": "uncertified until recompile()"})

        async def pack_create(args):
            over = counted()
            if over:
                return over
            s, _, err = work_of("copy")
            if err:
                return _err(err)
            src = str(args.get("source") or "")
            if "extends" not in src:
                return _err("a pack must declare `extends <the copy's "
                            "catalog name>.`")
            s.work["packs"].append({"name": str(args.get("name") or
                                                f"pack {len(s.work['packs']) + 1}"),
                                    "source": src})
            s.work["certified"] = None
            await gw._broadcast(s, gw._source_frame(s))
            return _ok({"created": f"pack:{len(s.work['packs'])}",
                        "note": "uncertified until recompile()"})

        async def recompile(args):
            over = counted()
            if over:
                return over
            s, _, err = work_of("copy")
            if err:
                return _err(err)
            if s.running:
                return _err("a command is running — try again after it ends")
            out = await gw.recompile(s)
            return _ok(out) if out.get("ok") else _err(
                "recompile failed (old world kept): " + str(out.get("error")))

        async def apply(args):
            """The copy and its packs written into the catalog source (the
            save the person's "apply to catalog" does), only after a
            recompile certified THIS copy; the diff is posted to the console
            so the person sees what was written. Personal mode only."""
            over = counted()
            if over:
                return over
            s, _, err = work_of("copy")
            if err:
                return _err(err)
            if gw.cfg.get("mode") == "shared":
                return _err("apply writes the operator's checkout: personal mode only")
            w = s.work
            if w.get("certified") not in ("local", "checkout"):
                return _err("the copy is uncertified: recompile() first — apply writes only a copy that compiled")
            loop = asyncio.get_running_loop()
            try:
                plan = await loop.run_in_executor(None, gw.srv.save_plan, w)
                if not plan["files"]:
                    return _ok({"written": [], "note": "nothing to apply: the copy and its packs equal the checkout"})
                out = await loop.run_in_executor(None, gw.srv.save_apply, w, plan["token"])
            except ValueError as e:
                return _err(str(e))
            w["certified"] = "checkout"
            await gw._broadcast(s, gw._source_frame(s))
            diff = "".join(f["diff"] for f in plan["files"])
            await gw._broadcast(s, {"ch": "repl", "type": "posting", "session": s.sid, "id": "a" + plan["token"][:8],
                                    "cmd": ":apply", "actor": "claude", "status": "done",
                                    "result": "applied " + ", ".join(out["written"]) + " (not committed)\n" + diff,
                                    "json": {"ok": True, "written": out["written"]}}, log=True)
            return _ok({"written": out["written"], "diff_lines": len(diff.splitlines()),
                        "note": "written to the catalog source and shown to the person; say what you wrote"})

        async def intents_read(args):
            over = counted()
            if over:
                return over
            s, _, err = work_of("copy")
            if err:
                return _err(err)
            from . import intents as it
            try:
                out = await asyncio.get_running_loop().run_in_executor(None, it.read, gw.srv, s.work.get("name"))
            except ValueError as e:
                return _err(str(e))
            return _ok({"domain": out["domain"], "draft": out["draft"], "text": truncate(out["text"])})

        async def intents_propose(args):
            over = counted()
            if over:
                return over
            s, _, err = work_of("copy")
            if err:
                return _err(err)
            from . import intents as it
            try:
                p = await asyncio.get_running_loop().run_in_executor(
                    None, it.propose, gw.srv, s.work.get("name"), str(args.get("text") or ""))
            except ValueError as e:
                return _err(str(e))
            s.intents_pending = p
            # the person sees the diff in the console log, as `intents show` prints it
            await gw._broadcast(s, {"ch": "repl", "type": "posting", "session": s.sid, "id": "i" + p["token"][:8],
                                    "cmd": ":intents show", "actor": "claude", "status": "done",
                                    "result": gw.intents_text(p), "json": {"ok": p["ok"]}}, log=True)
            return _ok({"ok": p["ok"], "mapped": p["mapped"], "misses": p["misses"],
                        "diff_lines": len(p["diff"].splitlines()),
                        "note": "shown to the person; `intents save` writes it, `intents check` runs the check"})

        return {"repl": repl, "ctx": ctx, "transcript": transcript,
                "source_read": source_read, "source_edit": source_edit,
                "pack_create": pack_create, "recompile": recompile, "apply": apply,
                "intents_read": intents_read, "intents_propose": intents_propose}

    def _server(self, chat: Chat):
        from claude_agent_sdk import create_sdk_mcp_server, tool
        fns = self.tool_fns(chat)
        tools = [
            tool("repl", "Run ONE line in the viewer's console REPL session "
                 "(prefix ':', e.g. ':run 6', ':why', ':ctx rules'). Same "
                 "whitelist as the viewer: :accept, paths and command: "
                 "specs are refused. Returns {status, result, json}.",
                 {"line": str})(fns["repl"]),
            tool("ctx", "The context at this stop — catalog, stage, beat, "
                 "episode, status, tokens, enabled, rule states — without "
                 "a REPL round.", {})(fns["ctx"]),
            tool("transcript", "The last n console lines (commands + "
                 "results, viewer's and yours).", {"n": int})(
                     fns["transcript"]),
            tool("source_read", "The working copy with line numbers: "
                 "target 'copy' or 'pack:N'; optional start/end lines.",
                 {"target": str, "start": int, "end": int})(
                     fns["source_read"]),
            tool("source_edit", "Replace ONE exact, unique piece of the "
                 "working copy (target 'copy' or 'pack:N'). The copy is "
                 "uncertified until recompile().",
                 {"target": str, "old_str": str, "new_str": str})(
                     fns["source_edit"]),
            tool("pack_create", "Add an extension pack on top of the copy: "
                 "full LLP text starting with `catalog <name> 1.` and "
                 "`extends <the copy's catalog name>.`; it may only ADD.",
                 {"name": str, "source": str})(fns["pack_create"]),
            tool("recompile", "Rebuild the session from the working copy + "
                 "packs (in memory). Returns the new key, or the findings "
                 "and keeps the old world.", {})(fns["recompile"]),
            tool("apply", "Write the working copy and its packs into the catalog source (the "
                 "operator's checkout: the program over its file, packs under <domain>/packs/) — "
                 "only after recompile() certified this copy. The diff is shown to the person; "
                 "metis-agent sees the change. Never a git commit. Say what you wrote.",
                 {})(fns["apply"]),
            tool("intents_read", "The open domain's intent.yaml (metis-catalog CATALOG.md "
                 "\"intent.yaml\": what the person may ask it, the mapper's and the replier's "
                 "tables), or — when it has none — a draft made from the program's cmd_* atoms "
                 "and %% lines (draft: true).", {})(fns["intents_read"]),
            tool("intents_propose", "Propose the WHOLE intent.yaml (text). It is checked: it must "
                 "generate the grammar and prompts, and every example must map to a command atom "
                 "of the program. Returns ok and the misses; the person sees the diff and writes it "
                 "with `intents save` — you never write the checkout.",
                 {"text": str})(fns["intents_propose"]),
        ]
        return create_sdk_mcp_server("metis", tools=tools)

    def options(self, chat: Chat):
        from claude_agent_sdk import (ClaudeAgentOptions, PermissionResultAllow,
                                      PermissionResultDeny)

        async def gate(name, _input, _ctx):
            if name in ALLOWED:
                return PermissionResultAllow()
            return PermissionResultDeny(message=f"{name} is not available "
                                        "in the console", interrupt=False)
        return ClaudeAgentOptions(
            system_prompt=self.system,
            mcp_servers={"metis": self._server(chat)},
            strict_mcp_config=True,
            tools=[],                       # no built-ins at all
            # no allowed_tools: an allow-list entry auto-approves before
            # the callback; the gate is the ONE authority for every call
            can_use_tool=gate,
            setting_sources=[],             # no user/project settings
            include_partial_messages=True,
            max_turns=int(self.cfg.get("agent_max_turns", 12)),
            model=self.cfg.get("agent_model") or None,
            cwd=str(self.gw.srv.root),
            extra_args={"no-session-persistence": None},   # D4
        )

    # -- turns -----------------------------------------------------------

    async def _emit(self, chat: Chat, frame: dict):
        s = self.gw.sessions.get(chat.sid)
        if s:
            await self.gw._broadcast(s, {"ch": "chat", "session": chat.sid,
                                         **frame})

    def history(self, sid: str):
        chat = self.chats.get(sid)
        return {"ch": "chat", "type": "history", "session": sid,
                "turns": chat.turns if chat else [],
                "busy": bool(chat and chat.task and not chat.task.done())}

    async def say(self, sid: str, text: str):
        s = self.gw.sessions.get(sid)
        if not s:
            return {"error": "no such session"}
        chat = self.chats.setdefault(sid, Chat(sid))
        if chat.task and not chat.task.done():
            return {"error": "Claude is still answering — stop it or wait"}
        text = str(text or "").strip()[:8000]
        if not text:
            return {"error": "empty message"}
        chat.turns.append({"role": "user", "content": text})
        chat.reply = {"role": "assistant", "content": "", "tools": [],
                      "pending": True}
        chat.turns.append(chat.reply)
        chat.turns[:] = chat.turns[-60:]
        await self._emit(chat, {"type": "user", "text": text})
        chat.task = asyncio.create_task(self._turn(s, chat, text))
        return None

    def _ctx_line(self, s) -> str:
        c = self.gw._session_frame(s).get("ctx") or {}
        if not c:
            return "[console now: the session is not bound]"
        return (f"[console now: catalog {c.get('catalog')}, stage "
                f"{c.get('stage')}, beat {c.get('beat')}, episode "
                f"{c.get('episode')}, {c.get('status')}, "
                f"{c.get('fired', 0) - c.get('base', 0)} fired since base, "
                f"last {c.get('last_event') or '—'}]")

    async def _client(self, chat: Chat):
        if chat.client is None:
            if self.client_factory:
                chat.client = self.client_factory(self, chat)
            else:
                from claude_agent_sdk import ClaudeSDKClient
                chat.client = ClaudeSDKClient(options=self.options(chat))
            await chat.client.connect()
        return chat.client

    async def _turn(self, s, chat: Chat, text: str):
        reply = chat.reply
        chat.calls = 0
        try:
            client = await self._client(chat)
            await client.query(f"{text}\n\n{self._ctx_line(s)}")
            async for msg in client.receive_response():
                kind = type(msg).__name__
                if kind == "StreamEvent":
                    ev = msg.event or {}
                    if ev.get("type") == "content_block_start" and \
                            (ev.get("content_block") or {}).get("type") == \
                            "text" and reply["content"]:
                        reply["content"] += "\n\n"
                    d = ev.get("delta") or {}
                    if ev.get("type") == "content_block_delta" and \
                            d.get("type") == "text_delta":
                        reply["content"] += d.get("text", "")
                        reply["pending"] = False
                        await self._emit(chat, {"type": "token",
                                                "text": reply["content"]})
                elif kind == "AssistantMessage" and not reply["content"]:
                    txt = "".join(getattr(b, "text", "") for b in msg.content
                                  if type(b).__name__ == "TextBlock")
                    if txt:
                        reply["content"] = txt
                        await self._emit(chat, {"type": "token",
                                                "text": txt})
                elif kind == "ResultMessage" and msg.is_error:
                    reply["error"] = str(getattr(msg, "result", "") or
                                         msg.subtype)
            reply["pending"] = False
            await self._emit(chat, {"type": "done",
                                    "text": reply["content"],
                                    "error": reply.get("error")})
        except asyncio.CancelledError:
            reply["pending"] = False
            reply["content"] = (reply["content"] or "") + " [stopped]"
            await self._emit(chat, {"type": "done",
                                    "text": reply["content"]})
        except Exception as e:                          # noqa: BLE001
            reply["pending"] = False
            reply["error"] = f"{type(e).__name__}: {e}"[:400]
            await self._emit(chat, {"type": "error",
                                    "error": reply["error"],
                                    "text": reply["content"]})
            await self._drop_client(chat)

    async def stop(self, sid: str):
        """[stop]: interrupt the SDK turn (and the gateway stops the
        running kernel command)."""
        chat = self.chats.get(sid)
        if not chat or not chat.task or chat.task.done():
            return
        try:
            if chat.client is not None:
                await asyncio.wait_for(chat.client.interrupt(), 5)
        except Exception:                               # noqa: BLE001
            pass
        await asyncio.sleep(0.5)
        if not chat.task.done():
            chat.task.cancel()

    async def _drop_client(self, chat: Chat):
        c, chat.client = chat.client, None
        if c is not None:
            try:
                await asyncio.wait_for(c.disconnect(), 5)
            except Exception:                           # noqa: BLE001
                pass

    async def close(self, sid: str):
        chat = self.chats.pop(sid, None)
        if chat:
            if chat.task and not chat.task.done():
                chat.task.cancel()
            await self._drop_client(chat)


class MockClient:
    """`console-serve --mock-agent` (DEV ONLY, never a model): runs the
    REPL lines found in the viewer's message through the real tools,
    then streams a canned summary word by word — drives the chat pane,
    the claude> transcript, busy/stop without spending anyone's
    subscription. The CONSOLE-WS twin of the page's ?mocksample."""
    LINE = re.compile(r":?\b(run \d+|step|why|ctx(?: \w+)?|events|graph|"
                      r"accept|reset|map \d+|list)\b")

    def __init__(self, svc, chat):
        self.fns, self.stopped = svc.tool_fns(chat), asyncio.Event()

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def interrupt(self):
        self.stopped.set()

    async def query(self, prompt):
        self.text = prompt.split("\n\n[console now")[0]

    async def receive_response(self):
        lines = [":" + m.group(1) for m in self.LINE.finditer(self.text)]
        notes = []
        for line in lines:
            r = await self.fns["repl"]({"line": line})
            notes.append(f"{line} -> " + ("refused/error" if r.get(
                "is_error") else "done"))
        text = ("[mock agent] I ran " + ", ".join(notes) + "."
                if notes else "[mock agent] no REPL line in your message.") + \
            " (canned reply — the real agent answers with --mock-agent off)"
        shown = ""

        class StreamEvent:
            def __init__(self, t):
                self.event = {"type": "content_block_delta",
                              "delta": {"type": "text_delta", "text": t}}
        for w in re.split(r"(\s+)", text):
            if self.stopped.is_set():
                raise asyncio.CancelledError
            await asyncio.sleep(0.03)
            shown += w
            yield StreamEvent(w)

