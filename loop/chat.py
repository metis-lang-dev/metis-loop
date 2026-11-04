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
    /mark [RUN] [K | K0..K1] WORDS   a surprise draft (the SURPRISES dialog, filled in)
    /drop WORDS                 the session's last tick as a surprise with these words
    /rebuild                    make (or metisc build .) of the bundle
    /reload                     the session re-opened from the rebuilt catalog
    /lint [MEMBER]              metis.lint with the member's manifest
    /budget USD                 the budget of the next pi start
    /stop                       stops the pi child
    /help [COMMAND]             this table

The answers are WorkspaceChannels' (loop/workspace_ch.py), over metispy's workspace face and metis.trace; nothing
here reaches a model. A reply is {command, text, …}: text the chat shows; ruling: an id the chat shows as its card;
draft: the SURPRISES dialog's fields; child: the pi child's state."""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from metis import trace as T
from metis.catalog import workspace as W

TOOLS_FILE = Path(__file__).resolve().parent / "chat_tools.json"
SHOWN = {("replay", "window"): "[K0..K1 | K]", ("mark", "words"): "[RUN] [K | K0..K1] WORDS"}   # /help's argument shapes
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
    ("mark", "a surprise draft from the open session's trace (or RUN's): the SURPRISES dialog, filled in",
     (("words", {"nargs": "+", "help": "[RUN] [K | K0..K1] WORDS"}),)),
    ("drop", "the open session's last tick as a surprise with these words", (("words", {"nargs": "+", "help": "the words"}),)),
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
    """The newest surprise (with a ruling when RULED), or None."""
    rows = ws.surprises("ruled" if ruled else None)
    return rows[-1] if rows else None


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


def status_text(ws, child, budget_next=None):
    b = ws.bundle()
    bl = "no bundle" if b is None else f"{b['name']} · v-{(b['image'] or '')[:12] or '(not built)'} " + (
        f"STALE ({b['why']})" if b["stale"] else "BUILT")
    loops = ws.loops()
    pi = loops.get("pi")
    if child and child.get("state") == "running":
        pl = f"pi: running pid {child.get('pid')} ({child.get('model') or 'loop.sh default'})"
    elif pi and pi.get("alive"):
        pl = f"pi: held elsewhere, pid {pi.get('pid')} ({pi.get('mode') or '?'})"
    else:
        pl = "pi: none"
    c = ws.cost()
    n = {k: len(ws.surprises(k)) for k in W.STATUS}
    nxt = f" · next start {budget_next} USD" if budget_next is not None else ""
    return (f"{bl} · {pl} · {c['total']:.4f} USD spent by pi's estimate ({c['calls']} calls; the key's bill runs higher){nxt}\n"
            f"surprises: {n['open']} open, {n['taken']} taken, {n['ruled']} ruled")


def mark(ws, words, session=None):
    """/mark [RUN] [K | K0..K1] WORDS → the SURPRISES dialog's draft: {run, member, k | window, words} for a trace
    named, else {session, k | window, words} for the page's open session (SESSION {session, k}: the dialog drops from
    it, its member and trace the session's); the tick as given, else the session's last."""
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
        d, run = _trace_dir(ws, run)
        ms = sorted(T.read(d)[0].header["members"])
        draft = {"run": run, "member": ms[0] if len(ms) == 1 else None, "words": text}
    if win is not None:
        if win[0] == win[1]:
            draft["k"] = win[0]
        else:
            draft["window"] = [win[0], win[1]]
    return draft


def rebuild(ws, scope=()):
    """make where the bundle's composition is (its Makefile), else metisc build . there."""
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
    ws.journal("backend", "built", bundle=b["name"], before=b["image"], image=after["image"] if after else None,
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


def main(argv=None):
    """python -m loop.chat [--root DIR] "/replay 412..430" — a READ command answered on the workspace at DIR (the
    pi loop's chat_<name> tools); without --root, the line parsed only. Prints the text; exit 1 with the refusal."""
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
            out = answer(W.workspace(o.root), name, a)
        except (ValueError, KeyError, T.TraceError, OSError) as e:
            print(str(e).strip("'\""), file=sys.stderr)
            return 1
        print(out.get("text", ""))
        if out.get("ruling"):
            print(f"(ruling {out['ruling']}: the chat shows it as its card)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
