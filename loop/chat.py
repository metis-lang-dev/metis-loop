"""The chat's /commands (loop-chat s-f6c32d0c step 2, docs/CHAT.md §2): a line the tester types that starts with "/"
is the backend's, deterministic and at 0 USD; anything else is the pi loop's (a model turn). Every command is one
declaration of `parser()`; loop/chat_tools.json is generated from it the way metispy's trace_tools.json is from the
trace verbs (tools/gen_chat_tools.py; a test checks the file equals the argparse), and /help is read from the table.

    /status                     the workspace: bundle, locks, child, spend, surprises
    /surprises [STATUS]         the records by status
    /take [ID]                  starts the pi loop if it is not running, says "take the next surprise" to it
    /replay [RUN] [K0..K1 | K]  the Tick table rows of the window (default: the last surprise's)
    /why ATOM [at K]            metis.trace blame: who last moved ATOM
    /diff [ID]                  the ruling's fired diff and goldens moved (default: the last ruling)
    /ruling [ID]                the ruling card (default: the last)
    /mark [RUN[:MEMBER]] [K | K0..K1] WORDS   a tick of the session's trace as a surprise (its REPL's mark), or RUN's
    /drop WORDS                 the session's last tick as a surprise with these words
    /apply [ID]                 an accepted ruling applied (the judge's merge of its pack onto its unit), at the gate
    /rebuild                    make (or metisc build .) of the bundle
    /reload                     the session re-opened from the rebuilt catalog
    /lint [MEMBER]              metis.lint with the member's manifest
    /budget USD                 the budget of the next pi start
    /stop                       stops the pi child
    /help [COMMAND]             this table

The answers are WorkspaceChannels' (loop/workspace_ch.py), over metispy's workspace face and metis.trace; nothing
here reaches a model. A reply is {command, text, …}: text the chat shows; ruling: an id the chat shows as its card;
child: the pi child's state."""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from metis import trace as T
from metis.catalog import workspace as W

TOOLS_FILE = Path(__file__).resolve().parent / "chat_tools.json"
SHOWN = {("replay", "window"): "[K0..K1 | K]", ("mark", "words"): "[RUN[:MEMBER]] [K | K0..K1] WORDS",
         ("narrate", "words"): "RUN[:MEMBER] K | K0..K1 CONTEXT"}   # /help's argument shapes
FREE = ("mark", "drop", "disagree", "narrate")   # commands whose words are the person's text: an apostrophe is a word's, not a quote
WINDOW = re.compile(r"^(-?\d+)(?:\.\.(-?\d+))?$")
ROWS = 60                     # a /replay's rows at most (the window's first; the rest are counted)
BUILD_SECS = 600
INTERVENTION = ("In the REPL (not the chat): `do +atom` / `do -atom` is the person's intervention; a bare `+atom` "
                "line is refused (`do` is the verb).")

# (name, one line for /help and the table, arguments)
COMMANDS = (
    ("status", "the workspace: bundle (name, image, BUILT/STALE), locks, the pi child, spend, open surprises", ()),
    ("surprises", "the surprise records by status", (("status", {"nargs": "?", "choices": W.STATUS,
                                                                 "help": "open | taken | ruled (default: all)"}),)),
    ("take", "starts the pi loop if it is not running and says \"take the next surprise\" to it (pi's words follow)",
     (("id", {"nargs": "?", "help": "a surprise id (default: the next open one)"}),)),
    ("replay", "the Tick table of a window: fired rules and made atoms per k (default: the last surprise's)",
     (("run", {"nargs": "?", "help": "a trace (default: the last surprise's)"}),
      ("window", {"nargs": "?", "help": "K0..K1 or K (default: the surprise's window)"}))),
    ("why", "metis.trace blame: who last moved ATOM at K (default: the last surprise's tick)",
     (("atom", {"help": "an atom (`atom 0`: it should not hold)"}),
      ("--at", {"type": int, "metavar": "K", "dest": "at", "help": "the tick (`at K` in the chat)"}))),
    ("diff", "the ruling's fired diff and the goldens it moved (default: the last ruling)",
     (("id", {"nargs": "?", "help": "a surprise id"}),)),
    ("ruling", "the ruling card (default: the last ruling)", (("id", {"nargs": "?", "help": "a surprise id"}),)),
    ("mark", "a tick (or K0..K1) of the open session's trace as a surprise, its REPL's mark; or RUN K's (RUN:MEMBER on a trace of several members): narrated first (the rules' own words), then /agree N or /disagree N WORDS",
     (("words", {"nargs": "+", "help": "[RUN[:MEMBER]] [K | K0..K1] WORDS"}),)),
    ("narrate", "a window of a trace told in its rules' own words for EVERY member (RUN:MEMBER for one), with its context (the event, what the tester saw): held as one mark, then /agree N or /disagree N WORDS (loop-road-ui: the road page's narrate)",
     (("words", {"nargs": "+", "help": "RUN[:MEMBER] K | K0..K1 CONTEXT"}),)),
    ("agree", "mark N as narrated: a pass, the mark closed (keep: kept as a closed mark with its narration)",
     (("n", {"type": int, "help": "the mark's number (/mark says it)"}),
      ("keep", {"nargs": "?", "choices": ["keep"], "help": "keep it as a closed mark"}))),
    ("disagree", "mark N not as narrated: a confusion record with your words, the narration you heard and its kind found on your words",
     (("n", {"type": int, "help": "the mark's number"}), ("words", {"nargs": "+", "help": "what you see that the narration does not say"}))),
    ("drop", "the open session's last tick as a surprise with these words", (("words", {"nargs": "+", "help": "the words"}),)),
    ("apply", "an accepted ruling applied: the judge's merge of its pack onto its unit, the diff shown, then confirm or refuse (default: the last ruling)",
     (("id", {"nargs": "?", "help": "a surprise id"}),)),
    ("rebuild", "make (or metisc build .) of the bundle, where its composition is", ()),
    ("reload", "the open session re-opened from the rebuilt catalog (epoch + 1)", ()),
    ("lint", "metis.lint of a member with its manifest (default: every member of the bundle)",
     (("member", {"nargs": "?", "help": "a member (a package of the catalog)"}),)),
    ("budget", "the budget of the next pi start, in USD", (("usd", {"type": float, "help": "USD, above 0"}),)),
    ("stop", "stops the pi child", ()),
    ("help", "this table", (("command", {"nargs": "?", "help": "one command"}),)),
)


class _Parser(argparse.ArgumentParser):
    def error(self, message):                                    # never exit: the chat says it
        raise ValueError(f"{self.prog}: {message} (/help {self.prog.split()[-1].lstrip('/')})")


def parser():
    """The commands' argparse: the chat's grammar and, through tools/gen_chat_tools.py, loop/chat_tools.json."""
    ap = _Parser(prog="/", add_help=False, description="the chat's commands, answered by the backend at 0 USD")
    sub = ap.add_subparsers(dest="cmd", parser_class=_Parser)
    for name, help_, args in COMMANDS:
        p = sub.add_parser(name, help=help_, description=help_, add_help=False, prog="/" + name)
        for a, kw in args:
            p.add_argument(a, **kw)
    return ap


def declarations():
    """The table: {format, tools: [{name, verb, description, parameters}]}, each from its argparse (metispy's _tool,
    the trace table's own shape)."""
    ap = parser()
    sub = next(a for a in ap._actions if isinstance(a, argparse._SubParsersAction))
    tools = []
    for name, help_, _ in COMMANDS:
        t = W._tool(name, "chat", name, help_, sub.choices[name])
        t.pop("module", None)
        tools.append(t)
    return {"format": "metis-loop-chat/1", "note": INTERVENTION, "tools": tools}


def tools_json():
    return json.dumps(declarations(), indent=1, ensure_ascii=False) + "\n"


def tools():
    """The table as committed (loop/chat_tools.json): what the chat answers and /help says, nothing more."""
    return json.loads(TOOLS_FILE.read_text())


def parse(line):
    """A chat line starting with "/" → (command, argparse namespace). Refused (ValueError) in words: no such command,
    a bad argument. `/why ATOM at K` reads as `--at K`."""
    text = line.strip()
    if not text.startswith("/"):
        raise ValueError("a command starts with /")
    words = text[1:].split()
    if not words or words[0].lower() not in FREE:        # a person's words are not shell words: "it didn't stop"
        try:
            words = shlex.split(text[1:])
        except ValueError as e:
            raise ValueError(f"{text}: {e}") from None
    if not words:
        raise ValueError("/ alone: /help lists the commands")
    name = words[0].lower()
    if name not in {c[0] for c in COMMANDS}:
        raise ValueError(f"/{name}: no such command; /help")
    if name == "why" and len(words) >= 4 and words[-2] == "at" and re.match(r"^-?\d+$", words[-1]):
        words = words[:-2] + ["--at", words[-1]]                 # only the closing `at K`: an atom named at stays one
    return name, parser().parse_args([name] + words[1:])


def window(text):
    """K0..K1 or K → (k0, k1); None when TEXT is not one."""
    m = WINDOW.match(str(text or ""))
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) is not None else a
    if b < a:
        raise ValueError(f"window {text}: K0..K1 with K0 <= K1")
    return a, b


def first_sentence(words):
    """The reading a /drop carries (a record needs a reading or atoms; the architect: the words are enough): the words'
    first sentence, up to its stop (. ! ?), else the words, one line, at most 200 characters."""
    one = " ".join(str(words or "").split())
    m = re.match(r"^(.+?[.!?])(\s|$)", one)
    return (m.group(1) if m else one)[:200]


def help_text(command=None):
    """/help from the committed table."""
    rows = tools()["tools"]
    if command:
        t = next((x for x in rows if x["name"] == command.lstrip("/")), None)
        if t is None:
            raise ValueError(f"/{command}: no such command; /help")
        rows = [t]
    out = []
    for t in rows:
        props = t["parameters"]["properties"]
        args = []
        for k, p in props.items():
            shown = SHOWN.get((t["name"], k)) or ("at K" if k == "at" else k.upper())
            if (t["name"], k) in SHOWN:
                args.append(shown)
                continue
            args.append(shown if k in t["parameters"]["required"] else f"[{shown}]")
        out.append(f"/{t['name']}{(' ' + ' '.join(args)) if args else ''} — {t['description']}")
    if not command:
        out += ["", "Anything else goes to the pi loop (a model turn, within its budget).", tools()["note"]]
    return "\n".join(out)


# ── the answers ──────────────────────────────────────────────────────────────

def last_surprise(ws, ruled=False):
    """The surprise the chat means by default: the one ruled LAST (by its ruling's ts), else the one taken, else the
    newest record; None when RULED and none is (F7, loop-prompt step 5: /replay after a ruling showed the newest
    record's window, never the ruled one's)."""
    rows = ws.surprises()
    done = [ws.surprise(x["id"]) for x in rows if x.get("status") == "ruled"]
    if done:
        return max(done, key=lambda s: (str((s.get("ruling") or {}).get("ts") or ""), s["id"]))
    if ruled or not rows:
        return None
    taken = [x for x in rows if x.get("status") == "taken"]
    return taken[-1] if taken else rows[-1]


def _trace_dir(ws, run):
    run = str(run or "").removeprefix("traces/").rstrip("/")
    return ws.path("trace", run=W._check_run(run)), run


def target(ws, run=None, win=None):
    """(the trace's dir, its run, members, (k0, k1)) of a /replay or /why: RUN and WIN as given, else the last surprise's
    trace, member and window (k, k0..k1), else the newest trace whole."""
    s = last_surprise(ws) if run is None else None
    if run is None and s and s.get("trace"):
        run = s["trace"]
        members = [s["member"]]
        if win is None:
            w = s.get("window")
            win = tuple(w) if w else ((s["k"], s["k"]) if s.get("k") is not None else None)
    else:
        members = None
    if run is None:
        traces = ws.traces()
        if not traces:
            raise ValueError("no trace in this workspace (.metis/traces/): name one, /replay RUN")
        run = traces[-1]["run"]
    d, run = _trace_dir(ws, run)
    head = T.read(d)[0].header
    if members is None or any(m not in head["members"] for m in members):
        members = sorted(head["members"])
    return d, run, members, win


def _stood_in(d, member):
    """metispy's line for a member opened with its weight ports stood in (metis.trace trace_note), or none on a metispy
    before it."""
    note = getattr(T, "trace_note", None)
    return note(d, member) if note else []


def replay(ws, run=None, win=None):
    d, run, members, win = target(ws, run, win)
    lines, n, notes = [], 0, []
    for m in members:
        notes += [f"{m}: {x}" for x in _stood_in(d, m)]
        ticks, exact = T.timeline(d, m)
        sel = [t for t in ticks if win is None or win[0] <= t.k <= win[1]]
        if not sel and win is not None:
            ks = [t.k for t in ticks]
            raise ValueError(f"no tick {win[0]}..{win[1]} in {run} ({ks[0]}..{ks[-1]})" if ks else f"{run}: no tick")
        for t in sel:
            n += 1
            if len(lines) < ROWS:
                lines.append(f"k {t.k:>5}  {m}: fired {', '.join(t.fired) or '—'}"
                             + (f"; made {', '.join(sorted(t.made))}" if t.made else ""))
    span = f"{win[0]}..{win[1]}" if win else "whole"
    head = f"{run} · {span} · {', '.join(members)} · {n} row(s)" + (f" (the first {ROWS} shown)" if n > ROWS else "")
    return {"text": "\n".join([head, *notes, *lines, "(fired as the trace has them; made: the takes' and beats' atoms)"]),
            "run": run, "rows": n}


def why(ws, atom, at=None):
    d, run, members, win = target(ws)
    k = at if at is not None else (win[1] if win else None)
    if k is None:
        ks = [t["k"] for s in T.read(d) for t in s.ticks]
        k = ks[-1] if ks else 0
    out = []
    for m in members:
        try:
            r = T.blame(d, m, k, [atom])
        except T.TraceError as e:
            out.append(f"{m}: {e}")
            continue
        for row in r["atoms"]:
            last = row.get("last") or {}
            mover = f"last moved at k {last.get('k')} by {last.get('by')} ({last.get('what')})" if last else "never moved"
            out.append(f"{m}: {row['atom']} want {row['want']} have {row['have']} at k {k}: {mover}; "
                       f"{row.get('whose') or 'holds as it should'}")
        out.append(f"{m}: {r['verdict']}")
        if r.get("note"):
            out.append(f"{m}: {r['note']}")
    return {"text": f"why {atom} at k {k} on {run}\n" + "\n".join(out), "run": run, "k": k}


def ruling_of(ws, sid=None):
    """(the surprise, its ruling) of SID, else of the newest ruled surprise."""
    if sid:
        s = ws.surprise(sid)
    else:
        s = last_surprise(ws, ruled=True)
        if s is None:
            raise ValueError("no ruling yet in this workspace (.metis/rulings/)")
        s = ws.surprise(s["id"])
    if s["status"] != "ruled":
        raise ValueError(f"{s['id']}: {s['status']}, not ruled")
    return s, s["ruling"]


def ruling_line(s, r):
    e, f = r.get("first_enabled") or {}, r.get("firings") or {}
    w = r.get("identified")                    # what the record identifies of the pack (s-5e34eb35 step 3); absent on old rulings
    if w and w != "nothing identified":
        parts = [(r.get("verdict") or "?") + (", " + w if r.get("verdict") == "accepted" and w != "identified" else "")]
    else:
        parts = [(r.get("verdict") or "?") + (" (inert)" if r.get("inert") else "")]   # accepted with nothing enabled says so
    if e:
        parts.append(f"first enabled k {e.get('k')} {e.get('rule')}")
    if f:
        parts.append(f"{f.get('count', 0)} firing(s) in {f.get('rows', 0)} row(s)")
    parts.append("goldens held" if not r.get("moved") else f"goldens moved: {', '.join(map(str, r['moved']))}")
    parts.append(f"{float(r.get('spent') or 0):.4f} USD")
    return f"{s['id']} on {s.get('member')}: " + " · ".join(parts)


def diff(ws, sid=None):
    s, r = ruling_of(ws, sid)
    lines = [ruling_line(s, r)]
    md = ws.root / ".metis" / r["md"] if r.get("md") and not str(r["md"]).startswith(".metis") else ws.root / str(r.get("md") or "")
    if md.is_file():
        text = md.read_text().splitlines()
        at = next((i for i, l in enumerate(text) if l.startswith("#") and "fired" in l.lower()), None)
        if at is not None:
            end = next((i for i in range(at + 1, len(text)) if text[i].startswith("#")), len(text))
            lines += text[at:min(end, at + 40)]
        else:
            lines.append("(the ruling's document has no fired-diff section)")
    for k in ("lint", "reads_absent"):
        if r.get(k):
            lines.append(f"{k}: " + "; ".join(map(str, r[k]))[:600])
    return {"text": "\n".join(lines), "ruling": s["id"]}


def surprises_text(ws, status=None):
    rows = ws.surprises(status)
    if not rows:
        return "no surprises" + (f" {status}" if status else "") + " (.metis/surprises/)"
    out = []
    for r in rows:
        where = r.get("trace") or ""
        w = r.get("window")
        span = f" {w[0]}..{w[1]}" if w else (f" k {r['k']}" if r.get("k") is not None else "")
        out.append(f"{r['status']:6} {r['id']}  {r.get('member')}  {where}{span}  {str(r.get('words') or r.get('reading') or '')[:80]}")
    return "\n".join(out)


def spend(ws):
    """The one spend count (loop-ui I8): metispy's Workspace.spend (the REPL's status says the same); a metispy before
    loop-ui: cost.jsonl alone, as before."""
    if hasattr(ws, "spend"):
        return ws.spend()
    c = ws.cost()
    return {"usd": c["total"], "calls": c["calls"], "local": False,
            "line": f"{c['total']:.4f} USD spent by pi's estimate ({c['calls']} calls; the key's bill runs higher)"}


def status_text(ws, child, budget_next=None):
    b = ws.bundle()
    bl = "no bundle" if b is None else f"{b['name']} · v-{(b['image'] or '')[:12] or '(not built)'} " + (
        f"STALE ({b['why']})" if b["stale"] else "BUILT")
    loops = ws.loops()
    pi = loops.get("pi")
    if child and child.get("state") == "running":
        pl = f"pi: running pid {child.get('pid')} ({child.get('model') or 'loop.sh default'})"
    elif pi and pi.get("alive") and str(pi.get("pid")) == os.environ.get("METIS_LOOP_PI_SELF"):
        pl = f"pi: this session, pid {pi.get('pid')} ({pi.get('mode') or '?'}, {pi.get('model') or 'loop.sh default'})"
    elif pi and pi.get("alive"):
        pl = f"pi: held elsewhere, pid {pi.get('pid')} ({pi.get('mode') or '?'})"
    else:
        pl = "pi: none"
    n = {k: len(ws.surprises(k)) for k in W.STATUS}
    nxt = f" · next start {budget_next} USD" if budget_next is not None else ""
    return (f"{bl} · {pl} · {spend(ws)['line']}{nxt}\n"
            f"surprises: {n['open']} open, {n['taken']} taken, {n['ruled']} ruled")


def mark(ws, words, session=None):
    """/mark [RUN[:MEMBER]] [K | K0..K1] WORDS → the surprise's draft (drop_draft drops it): {run, member, k | window, words}
    for a trace named, else {session, k | window, words} for SESSION {session, k} (its member and trace the
    session's); the tick as given, else the session's last. The console's /mark K on its own session is the REPL's
    mark (loop-ui 2.2); the SURPRISES dialog this once filled went with its dock."""
    ws_words = list(words)
    run = None
    if len(ws_words) >= 2 and window(ws_words[0]) is None and window(ws_words[1]) is not None:
        run = ws_words.pop(0)
    win = window(ws_words[0]) if ws_words else None
    if win is not None:
        ws_words.pop(0)
    text = " ".join(ws_words).strip()
    if not text:
        raise ValueError("/mark [RUN] [K | K0..K1] WORDS: the words are what the record carries")
    if run is None:
        if session is None:
            raise ValueError("/mark: no open session writes a trace on this page: name the trace, /mark RUN K WORDS")
        draft = {"session": session["session"], "words": text}
        if win is None and session.get("k") is not None:
            win = (session["k"], session["k"])
    else:
        # RUN:MEMBER names the member of a trace of several (loop-ui I9: the alfworld demo's run has six)
        run, _, member = run.partition(":")
        d, run = _trace_dir(ws, run)
        ms = sorted(T.read(d)[0].header["members"])
        if member and member not in ms:
            raise ValueError(f"/mark: {run} has no member {member} (its members: {', '.join(ms)})")
        draft = {"run": run, "member": member or (ms[0] if len(ms) == 1 else None), "members": ms, "words": text}
    if win is not None:
        if win[0] == win[1]:
            draft["k"] = win[0]
        else:
            draft["window"] = [win[0], win[1]]
    return draft


def rebuild(ws, scope=(), who="backend"):
    """make where the bundle's composition is (its Makefile), else metisc build . there. The one rebuild: the chat's
    /rebuild in every face and pi's bundle_build tool (loop-ui I4); WHO journals it ("pi" from pi's session)."""
    b = ws.bundle()
    if b is None:
        raise ValueError("no bundle here (no domains/composition.yaml): nothing to rebuild")
    cdir = (ws.root / b["composition"]).parent
    import os
    argv = ["make"] if (cdir / "Makefile").is_file() else [os.environ.get("METISC") or "metisc", "build", "."]
    try:
        p = subprocess.run(list(scope) + argv, cwd=str(cdir), capture_output=True, text=True, timeout=BUILD_SECS)
    except FileNotFoundError as e:
        raise ValueError(f"/rebuild: {e}") from None
    except subprocess.TimeoutExpired:
        raise ValueError(f"/rebuild: stopped after {BUILD_SECS} s") from None
    after = ws.bundle()
    ws.journal(who, "built", bundle=b["name"], before=b["image"], image=after["image"] if after else None,
               code=p.returncode)
    tail = (p.stdout + p.stderr).strip().splitlines()[-12:]
    head = (f"image {b['image'] or '(none)'} -> {(after or {}).get('image') or '(none)'}"
            + (f" (still STALE: {after['why']})" if after and after["stale"] else "")) if p.returncode == 0 else \
        f"{' '.join(argv)} failed (exit {p.returncode})"
    return {"text": "\n".join([f"{' '.join(argv)} in {cdir.relative_to(ws.root)}", head, *tail]), "code": p.returncode}


def lint_targets(ws, member=None):
    """[(member, program, manifest)] of /lint: MEMBER, else every member of the bundle."""
    from metis import catalog
    names = [member] if member else ((ws.bundle() or {}).get("members") or [])
    if not names:
        raise ValueError("/lint MEMBER: no bundle to take the members from")
    out = []
    for n in names:
        d = catalog.get(n, ws.root)
        if not d.program:
            raise ValueError(f"{n}: no program to lint")
        mf = Path(d.dir) / "domain.yaml"
        out.append((n, str(d.program), str(mf) if mf.is_file() else None))
    return out


# the commands that read the workspace only (no page, no session, no child to start or stop): the pi loop's tools too
# (loop-chat step 3: pi/extensions/metis-workspace.ts registers chat_<name> from the table and runs the CLI below)
READ = ("status", "surprises", "replay", "why", "diff", "ruling")


def answer(ws, name, a, child=None, budget_next=None):
    """The answer of a READ command (its argparse namespace A): {text, ruling?} — the chat's and the pi loop's alike."""
    if name == "status":
        return {"text": status_text(ws, child, budget_next)}
    if name == "surprises":
        return {"text": surprises_text(ws, a.status)}
    if name == "replay":
        run, win = a.run, window(a.window) if a.window else None
        if run is not None and win is None and window(run) is not None and a.window is None:
            run, win = None, window(run)             # /replay 412..430: the window of the last surprise's trace
        return replay(ws, run, win)
    if name == "why":
        return why(ws, a.atom, a.at)
    if name == "diff":
        return diff(ws, a.id)
    if name == "ruling":
        sr, r = ruling_of(ws, a.id)
        return {"text": ruling_line(sr, r), "ruling": sr["id"]}
    raise ValueError(f"/{name}: not a command the workspace answers alone (the chat's: /help)")


# the commands the pi loop's TUI answers itself through this CLI (two-terminals s-065d46d5: pi.registerCommand in
# pi/extensions/metis-workspace.ts): READ, and these, with no page and no REPL session in this process — the REPL
# is the other terminal. take, budget and stop are the pi session's own (the extension answers them).
TERMINAL = ("help", "mark", "narrate", "agree", "disagree", "drop", "apply", "rebuild", "reload", "lint")


def drop_draft(ws, draft):
    """A /mark draft dropped as it is (no dialog in a terminal): a trace's window kept as its own trace first (as the
    console's drop does), the run's config.yaml carried, the reading the words' first sentence. → the surprise id."""
    run = draft.get("run")
    if not run:
        raise ValueError("/mark here names a trace: /mark RUN K WORDS (the REPL's own `mark K WORDS` marks its session)")
    if not draft.get("member"):
        ms = draft.get("members") or []
        raise ValueError(f"/mark: {run} has several members" + (f" ({', '.join(ms)})" if ms else "")
                         + f": name one, /mark {run}:MEMBER K WORDS")
    rec = {"member": draft["member"], "trace": "traces/" + run, "words": draft["words"],
           "reading": first_sentence(draft["words"])}
    for f in ("kind", "verdict", "narration", "mark"):          # a mark's ending (spec 20 §8's confusion fields)
        if draft.get(f) is not None:
            rec[f] = draft[f]
    if draft.get("window"):
        k0, k1 = draft["window"]
        name = "w%d-%d" % (k0, k1)
        got = ws.path("trace", run=W._check_run("%s-%s" % (run, name)))
        rec["trace"] = "traces/" + got.name if got.is_dir() else ws.keep_window(run, k0, k1, name)
        rec["window"] = [k0, k1]
    elif draft.get("k") is not None:
        rec["k"] = draft["k"]
    cfg = ws.state / rec["trace"] / "config.yaml"
    if cfg.is_file():
        rec["config"] = str(cfg.relative_to(ws.root))
    return ws.drop_surprise(rec)


# ── a mark's two endings (spec 20 §10 item 7, surprise-kinds s-7a02c2ac): narrated first, then the person agrees or not ──
def _rule_docs(ws, member):
    """{rule: its %% doc} of MEMBER's program and the units it includes (the rules' own words, the narrator's vocabulary)."""
    import os
    import re
    from metis import catalog
    try:
        prog = Path(catalog.get(member, ws.root).program)
    except Exception:  # noqa: BLE001 — no program: the Tick table alone
        return {}
    docs, todo, seen = {}, [prog], set()
    home = os.environ.get("METIS_HOME")
    while todo:
        f = todo.pop()
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        text = f.read_text()
        for doc, rule in re.findall(r"^\s*%%\s*(.+?)\s*\n\s*([a-z_][a-z0-9_]*)\s*\[", text, re.M):
            docs.setdefault(rule, doc)
        for inc in re.findall(r'^include "([^"]+)"', text, re.M):
            todo += [d / inc for d in [f.parent] + ([Path(home)] if home else [])]
    return docs


def narration(ws, draft, why=True):
    """The window of DRAFT told in the rules' own words, deterministic and at 0 USD: per tick, each fired rule's %% doc with its
    binding's values in the doc's {X} (the Tick table's vocabulary); a rule with no doc is named; why: the explain half after it
    (the rules one fact short). → [lines]."""
    import re
    run, member = draft.get("run"), draft.get("member")
    if not run or not member:
        raise ValueError("/mark here names a trace and its member: /mark RUN[:MEMBER] K WORDS")
    d, run = _trace_dir(ws, run)
    k0, k1 = draft.get("window") or [draft.get("k"), draft.get("k")]
    docs = _rule_docs(ws, member)
    ticks, _ = T.timeline(d, member)
    out = []
    for t in ticks:
        if (k0 is not None and t.k < k0) or (k1 is not None and t.k > k1):
            continue
        for name in t.fired:
            base, _, bind = name.partition("[")
            vals = dict(x.split("=", 1) for x in bind.rstrip("]").split(",") if "=" in x)
            doc = docs.get(base.rsplit("-", 1)[0] if base not in docs else base)
            said = re.sub(r"\{(\w+)\}", lambda m: vals.get(m.group(1), m.group(0)), doc) if doc else f"({base}: a rule with no words)"
            if not out or out[-1] != f"k {t.k}: {said}":
                out.append(f"k {t.k}: {said}")
    out = out or [f"no rule of {member} fired in {k0}..{k1}"]
    return out + (explain(ws, d, member, k0, k1) if why else [])


EXPLAIN_ROWS = 8


def explain(ws, d, member, k0, k1):
    """The explain half (spec 20 §3, §10.7: narrate, then explain): per rule that did NOT fire in the window and was one fact
    short of firing, a line "k A–B: RULE was one fact short: ATOM" (metispy metis.surprise_kind.one_guard_away on the member's
    program), the member's own state and protocol tokens left out (a bare atom, tick__…); nothing when the program or the
    instrument is not at hand. → [lines] (at most EXPLAIN_ROWS, the rest counted)."""
    try:
        from metis import catalog
        from metis.surprise_kind import one_guard_away
        prog = catalog.get(member, ws.root).program
        if not prog or k0 is None:
            return []
        rows = one_guard_away(d, member, k0, k1 if k1 is not None else k0, str(prog))
    except Exception:  # noqa: BLE001 — an explanation is an aside: a trace the instrument cannot replay says nothing
        return []
    from metis import trace as T
    try:                                    # the predicates the member's own rules make (its state, not the world's)
        made = {T.pred_of(a) for _, _, ev in T.open_session(str(prog)).events_tbl for a in getattr(ev, "produce", {})}
    except Exception:  # noqa: BLE001 — a program the session cannot open: nothing more left out
        made = set()
    # the member's own state left out: a bare atom, a protocol token, and any fact its own rules make (road_director's held/queued/
    # age_of… were 113 of its 121 rows: the user, 2026-11-07, "the rest is gibberish"); what stays is a fact the world gives
    keep = [r for r in rows if not r.get("fired_at") and "(" in r["missing"] and not r["missing"].startswith("tick__")
            and T.pred_of(r["missing"]) not in made]
    lines = []
    for r in keep[:EXPLAIN_ROWS]:
        ts = r.get("ticks") or []
        when = (f"k {ts[0]}–{ts[-1]}" if ts and ts[0] != ts[-1] else f"k {ts[0]}") if ts else f"k {k0}–{k1}"
        lines.append(f"{when}: {r.get('ground') or r['rule']} was one fact short: {r['missing']}")
    if len(keep) > EXPLAIN_ROWS:
        lines.append(f"(and {len(keep) - EXPLAIN_ROWS} rule(s) more one fact short)")
    return lines


def _marks(ws):
    d = ws.state / "marks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def open_mark(ws, draft):
    """A /mark held open, narrated: .metis/marks/N.json {n, draft, narration}. → (N, the narration's lines)."""
    if not draft.get("run"):
        raise ValueError("/mark here names a trace: /mark RUN K WORDS (the REPL's own `mark K WORDS` marks its session)")
    if not draft.get("member"):
        ms = draft.get("members") or []
        raise ValueError(f"/mark: {draft['run']} has several members" + (f" ({', '.join(ms)})" if ms else "")
                         + f": name one, /mark {draft['run']}:MEMBER K WORDS")
    return _hold(ws, draft, narration(ws, draft))


SILENT = "no rule of "


def narrate(ws, words):
    """/narrate RUN[:MEMBER] K0..K1 CONTEXT (loop-road-ui, the user 2026-11-07: the road page's narrate goes to the loop's chat with its
    context): the window told for every member of the trace (or the one named), a member where nothing fired left out unless none fired;
    held as ONE mark (its member the first that fired: /disagree's record names it), so /agree N or /disagree N WORDS ends it.
    → (N, the narration's lines, the context)."""
    w = list(words)
    if w and w[0].lower() in ("event", "it", "this", "the"):         # "/narrate event 4": a host page's event, not a trace
        raise ValueError("/narrate names a trace and its window: /narrate RUN[:MEMBER] K0..K1 CONTEXT; an event of the road page: "
                         "its ¶, or \"narrate event N\" said or typed on the page")
    if not marks_a_run(w):
        raise ValueError("/narrate names a trace and its window: /narrate RUN[:MEMBER] K0..K1 CONTEXT")
    one = ":" in w[0]
    draft = mark(ws, w, None)
    if draft.get("k") is None and not draft.get("window"):
        raise ValueError("/narrate: the window, K or K0..K1, after the trace")
    members = [draft["member"]] if one else (draft.get("members") or [draft["member"]])
    # a tester's narration (the user, 2026-11-07): what each member did, in its rules' words, numbered; the explain half (the rules
    # one fact short, in the rules' own syntax) and the protocol's unworded rules are not a tester's: /why and pi's explain have them
    raw = [(m, narration(ws, dict(draft, member=m), why=False)) for m in members]
    told = [(m, _numbered(_said(ls))) for m, ls in raw]
    if not any(ls for _, ls in told):                    # no member's rules have words (a catalog without %% docs): their names, as fired
        told = [(m, _numbered([x for x in ls if _K.match(x)])) for m, ls in raw]
    fired = [(m, ls) for m, ls in told if ls]
    keep = fired or [(members[0], [f"no rule with words fired in {draft['window'][0] if draft.get('window') else draft.get('k')}"
                                    f"..{draft['window'][1] if draft.get('window') else draft.get('k')}"])]
    lines = []
    for m, ls in keep:
        lines += [f"{m}:"] + [f"  {x}" for x in ls] if len(keep) > 1 else ls
    if fired and len(fired) < len(told):
        lines.append("(nothing to tell for " + ", ".join(m for m, _ in told if m not in dict(fired)) + ")")
    n, lines = _hold(ws, dict(draft, member=keep[0][0], narrated=[m for m, _ in keep]), lines)
    return n, lines, draft["words"]


_STEP = re.compile(r"^(?:k \d+(?:[–-]\d+)?: |\d+\. )(.*)$")
_K = re.compile(r"^k \d+(?:[–-]\d+)?: (.*)$")


def _numbered(lines):
    """A tester's narration (the user, 2026-11-07): the trace's ticks ("k 12814:") left out, the steps a list numbered from 1 in their
    order, the same words said again at once one step (×N)."""
    out, n, last = [], 0, None
    for x in lines:
        m = _K.match(x)
        if not m:
            out.append(x); last = None
            continue
        text = m.group(1)
        if last is not None and last[0] == text:
            last[1] += 1
            out[last[2]] = f"{n}. {text} (×{last[1]})"
            continue
        n += 1
        out.append(f"{n}. {text}")
        last = [text, 1, len(out) - 1]
    return out


def _said(lines):
    """The fired rules that have words: the steps "k N: …" whose rule has a doc (no "(X: a rule with no words)", no silence line)."""
    return [x for x in lines if _K.match(x) and not x.endswith(": a rule with no words)") and " was one fact short: " not in x]


def _worded(lines):
    """A tester's narration: the protocol's rules with no words (decide, back: "(X: a rule with no words)") left out and counted."""
    keep = [x for x in lines if not x.endswith(": a rule with no words)")]
    n = len(lines) - len(keep)
    return keep + ([f"({n} line(s) of the protocol's own rules, with no words, left out)"] if n else []) if keep else lines


def _hold(ws, draft, lines):
    d = _marks(ws)
    last = d / "last"                                   # the marks' numbers never come again, a closed one's neither
    held = [int(f.stem) for f in d.glob("*.json") if f.stem.isdigit()]
    n = 1 + max(held + ([int(last.read_text())] if last.is_file() else []), default=0)
    last.write_text(str(n))
    (d / f"{n}.json").write_text(json.dumps({"n": n, "draft": draft, "narration": lines}, indent=1))
    ws.journal("backend", "mark", n=n, run=draft["run"], member=draft["member"])
    return n, lines


def _held(ws, n):
    f = _marks(ws) / f"{int(n)}.json"
    if not f.is_file():
        raise ValueError(f"no open mark {n} (/mark opens one)")
    return f, json.loads(f.read_text())


def _confusion(m, verdict, said=None):
    draft = m["draft"]
    k0, k1 = draft.get("window") or [draft.get("k"), draft.get("k")]
    rec = dict(draft, kind="confusion", verdict=verdict, narration=m["narration"],
               mark={"n": m["n"], "k0": k0, "k1": k1, "said": said if said is not None else draft["words"]})
    if said is not None:
        rec["words"] = said
    return rec


def agree(ws, n, keep=False):
    """/agree N: the narration accepted, the mark closed as a pass; KEEP: kept as a closed mark (a confusion record, verdict agreed,
    status closed), else nothing recorded. → {text}."""
    f, m = _held(ws, n)
    sid = drop_draft(ws, _confusion(m, "agreed")) if keep else None
    f.unlink()
    ws.journal("backend", "mark agreed", n=int(n), surprise=sid)
    return {"text": f"mark {n} closed: agreed" + (f", kept as {sid}" if sid else ""), "surprise": sid}


def disagree(ws, n, words):
    """/disagree N WORDS: the mark kept with the person's words and the narration they heard, as a confusion record (verdict
    disagreed), then spec 20 §4 run on the words (metispy metis.surprise_kind.triage): its THEN is the kind found. → {text}."""
    if not words.strip():
        raise ValueError(f"/disagree {n} WORDS: the words are what the record carries")
    f, m = _held(ws, n)
    sid = drop_draft(ws, _confusion(m, "disagreed", said=words.strip()))
    f.unlink()
    found, why = None, None
    try:
        from metis import surprise_kind as K
        rec = ws.surprise(sid)
        r = K.triage(rec, ws.state / rec["trace"])
        ws.set_kind(sid, r["kind"], r["evidence"], r["response"], then=r.get("then"), also=r.get("also") or ())
        found = r.get("then")
        if found == "evidential":              # not a finding: the columns it lacks (today mostly the truth column)
            why = "it waits for %s" % ", ".join((r.get("evidence") or {}).get("missing") or ["a column the trace lacks"])
    except ImportError:                        # a metispy before the triage: the record waits for `metis.trace kind`
        why = "this metispy has no triage"
    except (ValueError, LookupError) as x:     # the trace not readable, a window gone (TraceError is a ValueError)
        why = str(x)[:200]
    ws.journal("backend", "mark disagreed", n=int(n), surprise=sid, then=found)
    said = (f", its kind on your words: {found}" if found and found != "evidential" else "") + \
        (f"; kind not decided: {why} (metis.trace kind --write decides it later)" if why else "")
    return {"text": f"mark {n} kept as {sid}: confusion" + said, "surprise": sid, "then": found}


def marks_a_run(words):
    """/mark RUN K WORDS (a trace named): the terminal's form; /mark K WORDS marks the page's own session (the REPL's)."""
    w = list(words)
    return len(w) >= 2 and window(w[0]) is None and window(w[1]) is not None


def apply_plan(ws, sid=None):
    """/apply [ID]: the plan of the accepted ruling ID (default: the last ruling): metispy's Workspace.apply_plan, the
    judge's merge of its pack onto its unit (loop-ui 2.3, the user: the apply writes exactly what was judged), with
    the gate card's title and its message (the unified diff). Written only through a face's gate (pi's TUI, the
    console's CHAT): here, nothing is."""
    import difflib
    if not sid:
        s = last_surprise(ws, ruled=True)
        if s is None:
            raise ValueError("no ruling yet in this workspace (.metis/rulings/): nothing to apply")
        sid = s["id"]
    pl = ws.apply_plan(sid)
    diff = "".join(difflib.unified_diff(pl["old"].splitlines(keepends=True), pl["new"].splitlines(keepends=True),
                                        fromfile=pl["unit"], tofile=pl["unit"], n=2))
    what = ", ".join(([f"drop {x}" for x in pl["dropped"]] + [f"+ {x}" for x in pl["added"]])) or "the pack"
    return pl, {"title": f"apply ruling {sid} to {pl['unit']} ({what}): the judge's merge, as judged", "message": diff}


def terminal(ws, name, a):
    """The answer of a TERMINAL command: {text}."""
    if name == "help":
        return {"text": help_text(a.command)}
    if name == "mark":
        w = list(a.words)
        if not marks_a_run(w):
            raise ValueError("/mark here names a trace: /mark RUN K WORDS (the REPL's own `mark K WORDS` marks its "
                             "session)")
        n, lines = open_mark(ws, mark(ws, w, None))
        return {"text": "\n".join([f"mark {n}, as the rules tell it:", *lines,
                                   f"agree: /agree {n}   ·   disagree: /disagree {n} WHAT YOU SEE"]), "mark": n, "narration": lines}
    if name == "narrate":
        n, lines, ctx = narrate(ws, a.words)
        return {"text": "\n".join([f"mark {n}, as the rules tell it: {ctx}", *lines,
                                   f"agree: /agree {n}   ·   disagree: /disagree {n} WHAT YOU SEE"]), "mark": n, "narration": lines, "context": ctx}
    if name == "agree":
        return agree(ws, a.n, keep=bool(a.keep))
    if name == "disagree":
        return disagree(ws, a.n, " ".join(a.words))
    if name == "drop":
        raise ValueError("/drop is the REPL's: `drop WORDS` in its terminal drops its last tick (here: /mark RUN K WORDS)")
    if name == "reload":
        raise ValueError("/reload is the REPL's: `reload` in its terminal re-reads the files (after /rebuild)")
    if name == "apply":                   # the CLI shows the plan; a face's gate writes it (pi's /apply, the CHAT's)
        pl, card = apply_plan(ws, a.id)
        return {"text": f"{card['title']}\n{card['message']}(nothing written here: /apply in pi's TUI or the console's "
                        "CHAT asks you to confirm it)"}
    if name == "rebuild":
        from .workspace_ch import _scope
        return rebuild(ws, _scope(), who="pi" if os.environ.get("METIS_LOOP_PI_SELF") else "backend")
    if name == "lint":
        rows = []
        for m, prog, mf in lint_targets(ws, a.member):
            argv = W.tool_argv("lint", {"file": prog, **({"manifest": mf} if mf else {})})
            p = subprocess.run(argv, cwd=str(ws.root), capture_output=True, text=True, timeout=BUILD_SECS)
            rows.append(f"{m}: " + ((p.stdout + p.stderr).strip() or f"exit {p.returncode}"))
        return {"text": "\n".join(rows)}
    raise ValueError(f"/{name}: the pi session's own (/take, /budget, /stop), not this CLI's")


def main(argv=None):
    """python -m loop.chat [--root DIR] "/replay 412..430" — a READ or TERMINAL command answered on the workspace at
    DIR (the pi loop's chat_<name> tools and its TUI's /commands); without --root, the line parsed only. Prints the
    text; exit 1 with the refusal."""
    ap = argparse.ArgumentParser(prog="python -m loop.chat", description="the chat's read-only commands, on a workspace")
    ap.add_argument("--root", help="the workspace (default: the line is parsed only)")
    ap.add_argument("lines", nargs="+")
    o = ap.parse_args(argv)
    for line in o.lines:
        try:
            name, a = parse(line)
            if o.root is None:
                print(name, vars(a))
                continue
            ws = W.workspace(o.root)
            out = answer(ws, name, a) if name in READ else terminal(ws, name, a)
        except (ValueError, KeyError, T.TraceError, OSError) as e:
            print(str(e).strip("'\""), file=sys.stderr)
            return 1
        print(out.get("text", ""))
        if out.get("ruling"):
            print(f"(ruling {out['ruling']}: the chat shows it as its card)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
