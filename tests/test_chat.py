"""The chat's /commands (loop-chat s-f6c32d0c step 2, docs/CHAT.md §2): one declaration table generated from the
argparse, the say frame routed by its first character (a "/" line is the backend's, never pi's), /help from the
table, and every command answered at 0 USD on a committed road trace (tests/fixtures/road-town01-2: metis-worlds'
sort-town01-2, its first segment), the loop channel driven directly (no socket, a stub pi)."""
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from metis.catalog import workspace as W

from loop import chat, workspace_ch

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "road-town01-2"
RUN = "road-town01-2"
LAMP = """% lamp — a lamp
catalog lamp 1.
layers (dyn).
stages (main).
namespace lamp produce (dyn).
pred off : lamp.
pred on : lamp.
stage main {
  %% I switch on.
  on [dyn] : off -o on.
}
#init off 1
"""


class GW:
    """The gateway as the channels use it: its mode, its server's root, its sessions, its sends."""

    def __init__(self, root):
        self.cfg = {"mode": "personal"}
        self.srv = SimpleNamespace(root=root)
        self.sessions = {}
        self.sent, self.reopened = [], []

    async def _send(self, page, f):
        self.sent.append(f)

    async def _send_all(self, f):
        self.sent.append(f)

    async def reopen(self, s, why):
        self.reopened.append((s.sid, why))

    def member_of(self, s):
        return s.trace.member


class StubPi:
    made = []

    def __init__(self, argv, cwd, env):
        self.argv, self.cwd, self.env, self.said, self.pid = argv, cwd, env, [], 4242
        self.q = asyncio.Queue()
        StubPi.made.append(self)

    async def start(self):
        pass

    async def say(self, text):
        self.said.append(text)

    async def answer(self, token, ok):
        pass

    async def stop(self):
        await self.q.put({"kind": "exit", "code": 0})

    async def events(self):
        while True:
            ev = await self.q.get()
            yield ev
            if ev["kind"] == "exit":
                return


@pytest.fixture
def root(tmp_path):
    """A workspace: the road trace's first segment in .metis/traces/, the lamp as a package."""
    shutil.copytree(FIXTURE, tmp_path / ".metis" / "traces" / RUN, ignore=shutil.ignore_patterns("README.md"))
    (tmp_path / "domains" / "lamp").mkdir(parents=True)
    (tmp_path / "domains" / "lamp" / "lamp.llp").write_text(LAMP)
    (tmp_path / "domains" / "lamp" / "domain.yaml").write_text("program: lamp.llp\n")
    return tmp_path


def say(ch, text, **kw):
    """One say frame through the loop channel: the frame sent back to the page."""
    ch.gw.sent.clear()
    asyncio.run(ch.handle("page", {"ch": "loop", "type": "say", "text": text, "req": "r", **kw}))
    (f,) = [x for x in ch.gw.sent if x.get("req") == "r"]
    return f


def channels(root, pi=None):
    return workspace_ch.WorkspaceChannels(GW(root), root, pi_factory=pi)


def surprise(root, **kw):
    rec = {"member": "planner", "trace": "traces/" + RUN, "window": [0, 5], "reading": "it accelerated",
           "words": "it should have waited", **kw}
    return W.workspace(root).drop_surprise(rec)


# ── the table ───────────────────────────────────────────────────────────────

def test_the_table_is_the_argparse_and_help_reads_it():
    assert chat.TOOLS_FILE.read_text() == chat.tools_json()
    r = subprocess.run([sys.executable, str(HERE.parent / "tools" / "gen_chat_tools.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    names = [t["name"] for t in chat.tools()["tools"]]
    assert names == ["status", "surprises", "take", "replay", "why", "diff", "ruling", "mark", "drop", "rebuild",
                     "reload", "lint", "budget", "stop", "help"]
    h = chat.help_text()
    for n in names:
        assert f"/{n}" in h, n
    assert "/why ATOM [at K]" in h and "/replay [RUN] [K0..K1 | K]" in h and "/mark [RUN] [K | K0..K1] WORDS" in h
    assert "`do +atom`" in h and "a bare `+atom` line is refused" in h                 # the drive's F6
    assert chat.help_text("why").startswith("/why ATOM [at K] — ")


def test_a_slash_line_is_the_backends_and_never_reaches_pi(root):
    StubPi.made.clear()
    ch = channels(root, StubPi)
    f = say(ch, "/help")
    assert f["type"] == "say" and f["command"] == "help" and "/status" in f["text"]
    assert StubPi.made == []                                                         # no pi was started
    assert say(ch, "/nope")["error"] == "/nope: no such command; /help"
    assert "budget" in say(ch, "/budget lots")["error"]
    f = say(ch, "take the next surprise")                                            # anything else is pi's
    assert f["type"] == "error" and "no pi loop runs" in f["error"]
    rows = W.workspace(root).events()
    assert [r["command"] for r in rows if r["kind"] == "command"] == ["help"]


def test_completion_is_the_table(root):
    ch = channels(root)
    ch.gw.sent.clear()
    asyncio.run(ch.handle("page", {"ch": "loop", "type": "commands", "req": "c"}))
    (f,) = ch.gw.sent
    assert [c["name"] for c in f["commands"]] == [t["name"] for t in chat.tools()["tools"]]


# ── each command, on the road trace ─────────────────────────────────────────

def test_status(root):
    ch = channels(root)
    surprise(root)
    t = say(ch, "/status")["text"]
    assert t.startswith("no bundle · pi: none · 0.0000 USD spent by pi's estimate (0 calls; the key's bill runs higher)")
    assert "surprises: 1 open, 0 taken, 0 ruled" in t


def test_surprises(root):
    ch = channels(root)
    assert say(ch, "/surprises")["text"].startswith("no surprises")
    sid = surprise(root)
    t = say(ch, "/surprises open")["text"]
    assert sid in t and "planner" in t and "traces/road-town01-2 0..5" in t and "it should have waited" in t
    assert say(ch, "/surprises ruled")["text"] == "no surprises ruled (.metis/surprises/)"


def test_replay_the_last_surprises_window_and_a_named_one(root):
    ch = channels(root)
    surprise(root)
    f = say(ch, "/replay")
    assert f["text"].startswith("road-town01-2 · 0..5 · planner · 6 row(s)")
    assert "k     2  planner: fired decide, accel, back" in f["text"]
    t = say(ch, "/replay 2")["text"]                                                  # the window alone: the last surprise's trace
    assert t.startswith("road-town01-2 · 2..2 · planner · 1 row(s)")
    t = say(ch, f"/replay {RUN} 1..2")["text"]                                       # a trace named: every member
    assert "responder, planner, road_director" not in t and "planner, responder, road_director · 6 row(s)" in t
    assert "road_director: fired status_reset[D=responder,A=a0], path_push[D=planner]" in t
    assert "no tick 900..901" in say(ch, f"/replay {RUN} 900..901")["error"]


def test_why(root):
    ch = channels(root)
    surprise(root, window=[40, 50])
    t = say(ch, "/why now at 50")["text"]
    assert t.startswith("why now at k 50 on road-town01-2")
    assert "planner: now want 1 have 5 at k 50: last moved at k 41 by world (+now); the world's reading" in t
    assert "planner: not this package's" in t
    assert say(ch, "/why now")["k"] == 50                                            # the surprise's window end
    assert chat.parse("/why at at 3")[1].atom == "at" and chat.parse("/why at at 3")[1].at == 3   # an atom named at
    assert chat.parse("/why at")[1].atom == "at" and chat.parse("/why at")[1].at is None


def rule(root, sid):
    md = ("# the ruling\n\naccepted.\n\n## the fired diff\n\n| k | record | candidate |\n|---|---|---|\n"
          "| 3 | accel | brake_late |\n\n## goldens\n\nheld\n")
    W.workspace(root).rule(sid, md, "accepted", pack="brake_late [dyn] : now -o ().\n", moved=[], lint=[],
                           first_enabled={"k": 3, "rule": "brake_late"}, firings={"count": 3, "rows": 3, "of_rows": 3,
                                                                                  "first": 3, "last": 5}, spent=0.02)


def test_ruling_and_diff(root):
    ch = channels(root)
    assert "no ruling yet" in say(ch, "/ruling")["error"]
    sid = surprise(root)
    assert "open, not ruled" in say(ch, f"/diff {sid}")["error"]
    rule(root, sid)
    f = say(ch, "/ruling")
    assert f["ruling"] == sid
    assert f["text"] == (f"{sid} on planner: accepted · first enabled k 3 brake_late · 3 firing(s) in 3 row(s) · "
                         "goldens held · 0.0200 USD")
    t = say(ch, "/diff")["text"]
    assert "## the fired diff" in t and "| 3 | accel | brake_late |" in t and "## goldens" not in t


def test_mark_from_a_trace_and_the_refusals(root):
    ch = channels(root)
    f = say(ch, f"/mark {RUN} 10..20 it braked late behind the lead car")
    assert f["draft"] == {"run": RUN, "member": None, "window": [10, 20],
                          "words": "it braked late behind the lead car"}
    assert say(ch, f"/mark {RUN} 12 late")["draft"]["k"] == 12
    assert "no open session writes a trace" in say(ch, "/mark 10 late")["error"]
    assert "the words are what the record carries" in say(ch, f"/mark {RUN} 10")["error"]


def test_mark_and_drop_from_the_pages_session(root):
    ch = channels(root)
    trace = SimpleNamespace(path=root / ".metis" / "traces" / "s1", member="lamp", last_k=lambda: 7, extensions=())
    ch.gw.sessions["s1"] = SimpleNamespace(sid="s1", subs={"page"}, trace=trace, running=False)
    f = say(ch, "/mark it should be on", session="s1")
    assert f["draft"] == {"session": "s1", "k": 7, "words": "it should be on"}        # the dialog drops from the session
    assert "no open session" in say(ch, "/drop it should be on")["error"]            # no session named: refused
    assert "no open session" in say(ch, "/drop x", session="other")["error"]         # not this page's
    f = say(ch, "/drop it should be on. The switch was pressed at 5.", session="s1")   # opus's review: the drop writes
    rec = W.workspace(root).surprise(f["id"])
    assert f["text"] == f"dropped {f['id']}: the pi loop takes it from .metis/surprises/"
    assert (rec["session"], rec["member"], rec["trace"], rec["k"], rec["words"], rec["reading"], rec["status"]) == \
        ("s1", "lamp", "traces/s1", 7, "it should be on. The switch was pressed at 5.", "it should be on.", "open")
    assert chat.first_sentence("  no stop here  ") == "no stop here" and chat.first_sentence("a? b.") == "a?"


def test_rebuild(root):
    ch = channels(root)
    assert "no bundle here" in say(ch, "/rebuild")["error"]
    d = root / "domains" / "hier"
    d.mkdir()
    (d / "composition.yaml").write_text("name: road\nspecialists: [lamp]\n")
    (d / "Makefile").write_text("all:\n\t@echo built the image\n")
    f = say(ch, "/rebuild")
    assert f["code"] == 0 and f["text"].startswith("make in domains/hier\nimage (none) -> (none) (still STALE: no build yet")
    assert "built the image" in f["text"]
    assert any(r["kind"] == "built" and r["who"] == "backend" for r in W.workspace(root).events())


def test_reload_needs_the_pages_session(root):
    ch = channels(root)
    assert "/reload: no open session" in say(ch, "/reload")["error"]
    ch.gw.sessions["s1"] = SimpleNamespace(sid="s1", subs={"page"}, trace=None, running=False)
    assert say(ch, "/reload", session="s1")["text"].startswith("reloaded s1")
    assert ch.gw.reopened == [("s1", "reload")]


def test_lint(root):
    ch = channels(root)
    t = say(ch, "/lint lamp")["text"]
    assert t.startswith("lamp: ") and "lamp.llp" in t
    assert "no bundle to take the members from" in say(ch, "/lint")["error"]


def test_budget_take_and_stop(root):
    StubPi.made.clear()
    ch = channels(root, StubPi)
    assert "the next pi start has a budget of 0.3 USD" in say(ch, "/budget 0.3")["text"]
    assert "above 0" in say(ch, "/budget 0")["error"]
    assert "no pi loop runs" in say(ch, "/stop")["error"]

    async def take_then_stop():
        await ch.handle("page", {"ch": "loop", "type": "say", "text": "/take", "req": "t"})
        await ch.handle("page", {"ch": "loop", "type": "say", "text": "/take 20261103T000000-abcdef", "req": "u"})
        await ch.handle("page", {"ch": "loop", "type": "say", "text": "/stop", "req": "s"})
        await asyncio.sleep(0.05)
    asyncio.run(take_then_stop())
    (pi,) = StubPi.made
    assert pi.env["METIS_LOOP_BUDGET"] == "0.3" and pi.said == ["take the next surprise", "take surprise 20261103T000000-abcdef"]
    t, u = (next(x for x in ch.gw.sent if x.get("req") == r) for r in ("t", "u"))
    assert t["text"] == "started the pi loop (budget 0.3); said to pi: take the next surprise"
    assert u["text"] == "said to pi: take surprise 20261103T000000-abcdef"            # running: no second start
    assert ch.child["state"] == "exited"
    ch.child = {"state": "starting", "rpc": None, "gates": {}, "model": None, "budget": None, "started": ""}
    assert "the pi loop is starting" in say(ch, "/take")["error"]                       # opus's review (5)


def test_the_page_routes_a_slash_line_to_the_backend_and_completes_it():
    """The chat widget (web/workspace/loop.js): a "/" line asks the backend and never starts pi; the input's
    completion is the table; a /mark draft opens the host's SURPRISES dialog (the console wires onMark)."""
    js = (HERE.parent / "web" / "workspace" / "loop.js").read_text()
    assert "if (text.startsWith('/')) return command(text);" in js
    assert js.index("if (text.startsWith('/')) return command(text);") < js.index("if (!running()) {\n        if (elsewhere())")
    assert "list: listId" in js and "el('datalist', { id: listId }" in js and "io.ask('loop', 'commands')" in js
    assert "o.onMark(r.draft)" in js
    page = (HERE.parent / "console" / "loop_console.html").read_text()
    assert 'W.chat=MetisLoop.mount($("#w-chat"),wsIO,{session:()=>sid,\n    onMark:' in page
    assert "d.words || ''" in (HERE.parent / "web" / "workspace" / "surprises.js").read_text()   # the draft's words filled in


def test_an_inert_acceptance_says_so():
    """patterns open item 6 (opus): 'accepted' with no candidate rule enabled reads as more than it is: the chat's
    /ruling line says 'accepted (inert)', as the ruling's title does."""
    from loop import chat
    line = chat.ruling_line({"id": "x", "member": "m"}, {"verdict": "accepted", "inert": True})
    assert line.startswith("x on m: accepted (inert) · ")
    assert "(inert)" not in chat.ruling_line({"id": "x", "member": "m"}, {"verdict": "accepted", "first_enabled": {"k": 3, "rule": "r"}})



PICKY = """
catalog picky 1.
provenance text "a weight port for the chat's stand-in line" "2026-11-04".
layers (dyn).
stages (main).
type place {door sofa}.
namespace g produce (dyn).
pred want(place) : g.
pred at(place) : g.
pred ready : g.
weight pick(P) reads {want(P)}.
stage main {
  %% I go to {P}, or I stay.
  go [dyn] : want(P) -o (at(P) @w pick(P) | ready @w ~pick(P)).
}
#steps 20
#seeds 1
"""


def test_replay_and_why_say_a_weight_port_was_stood_in(root):
    """alfworld's task (weight look): metispy opens the member with the port stood in, and /replay and /why carry its
    one line, so the loop reads on every tool that the member's choices are the record's, not evidence."""
    from metis import trace as T
    if not hasattr(T, "trace_note"):
        pytest.skip("metispy before the trace verbs' stand-in (trace-stand-in)")
    from metis.fw.registry import Registry
    from metis.lang.repl import Repl as Shell
    p = root / "domains" / "picky" / "picky.llp"
    p.parent.mkdir(parents=True)
    p.write_text(PICKY)
    sh = Shell(str(p), seed=1, registry=Registry().weight("pick", T.STAND_IN))
    chose = sorted(e.name for _, _, e in sh.events_tbl if "door" in e.name)[-1]
    d = root / ".metis" / "traces" / "wpicky"
    w = T.Segments(d, every=0)
    w.open_segment(0, {"members": {"picky": {"key": T.program_key(p), "program": str(p), "seed": 1, "weights": ["pick"], "out": []}},
                       "commands": [], "live": "metis-loop-console", "clock": "command"},
                   {"sessions": {"picky": T.session_state(sh)}, "copies": {"picky": {}}})
    w.line({"k": 1, "members": {"picky": {"why": "command", "seq": [{"take": ["+want(door)"], "by": "person"}]}}})
    w.line({"k": 2, "members": {"picky": {"why": "command", "seq": [{"step": [chose], "by": "tool"}]}}})
    w.close()
    W.workspace(root).drop_surprise({"member": "picky", "trace": "traces/wpicky", "k": 2, "reading": "it stayed"})
    ch = channels(root)
    line = "picky: pick stood in at 0.5: this member's choices are the record's, not evidence"
    t = say(ch, "/replay wpicky 2")["text"]
    assert line in t and "fired " + chose in t, t
    t = say(ch, "/why ready at 2")["text"]
    assert line in t and "last moved at k 2 by rule" in t, t


def test_replay_defaults_to_the_surprise_ruled_last_not_the_newest_record(root):
    """F7 (loop-prompt step 5): after a ruling, /replay with no argument is the ruled surprise's window."""
    ch = channels(root)
    first = surprise(root)                                                            # window 0..5
    surprise(root, window=[2, 4])                                                     # the newest record
    assert say(ch, "/replay")["text"].startswith("road-town01-2 · 2..4 · planner")  # nothing ruled: the newest
    rule(root, first)
    assert say(ch, "/replay")["text"].startswith("road-town01-2 · 0..5 · planner")  # the one ruled, not the newest
    assert say(ch, "/ruling")["ruling"] == first


def test_the_terminal_cli_answers_the_tuis_commands(root, capsys):
    """two-terminals: the pi TUI's /commands run `python -m loop.chat --root DIR "/…"` (no page, no session here: the
    REPL is the other terminal). /mark RUN K WORDS drops at once (no dialog), the window kept as its own trace;
    /drop and /reload point at the REPL; /help is the table."""
    import io
    from metis.lang.repl import Repl
    from metis.session_trace import SessionTrace
    r = Repl(root / "domains" / "lamp" / "lamp.llp", seed=1, stdout=io.StringIO())
    tr = SessionTrace(W.workspace(root).path("trace", run="repl-1"), r, "lamp", program=r.path)
    for cmd in ("run 1", "run 1"):
        tr.before(r)
        r.onecmd(cmd)
        tr.after(r, cmd)
    tr.close()
    assert chat.main(["--root", str(root), "/mark repl-1 1 the lamp lit. It should not have."]) == 0
    sid = capsys.readouterr().out.split()[1].rstrip(":")
    rec = W.workspace(root).surprise(sid)
    assert (rec["member"], rec["trace"], rec["k"], rec["reading"]) == ("lamp", "traces/repl-1", 1, "the lamp lit.")
    assert chat.main(["--root", str(root), "/mark repl-1 1..2 both ticks"]) == 0
    sid = capsys.readouterr().out.split()[1].rstrip(":")
    rec = W.workspace(root).surprise(sid)
    assert rec["window"] == [1, 2] and rec["trace"] == "traces/repl-1-w1-2" and (root / ".metis" / rec["trace"]).is_dir()
    assert chat.main(["--root", str(root), f"/mark {RUN} 10 late"]) == 1          # the road's: several members
    assert "several members" in capsys.readouterr().err
    assert chat.main(["--root", str(root), "/mark 3 no trace named"]) == 1
    assert "/mark here names a trace" in capsys.readouterr().err
    for line, words in (("/drop x", "`drop WORDS` in its terminal"), ("/reload", "`reload` in its terminal"),
                        ("/take", "the pi session's own")):
        assert chat.main(["--root", str(root), line]) == 1 and words in capsys.readouterr().err, line
    assert chat.main(["--root", str(root), "/help"]) == 0 and "/replay" in capsys.readouterr().out
