"""The console's embed face (loop-road-ui s-0314a8ee step 1, CHAT.md §1): ?panels=chat&embed=ORIGIN, postMessage both
ways, origin-checked. console/lib/embed.js is run under node with a fake window and parent (node: $NODE, else `node` on
PATH; none, the behaviour test skips — METIS_LOOP_REQUIRE_NODE=1, as CI sets it, fails instead); the wiring is read
from the page and the CHAT widget."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EMBED = ROOT / "console/lib/embed.js"
PAGE = (ROOT / "console/loop_console.html").read_text()
LOOP_JS = (ROOT / "web/workspace/loop.js").read_text()

HOST = "http://127.0.0.1:8400"

# the harness: embed.js in a vm context; a fake window whose parent records postMessage; a fake chat recording say /
# answerGate; the scenario's deliveries as {origin, from_parent, data}; prints the record as JSON
HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const [src, search, plan] = [process.argv[2], process.argv[3], JSON.parse(process.argv[4])];
const posted = [], said = [], gates = [], listeners = [];
const parent = { postMessage: (m, o) => posted.push({ m, o }) };
const win = { parent, addEventListener: (t, f) => { if (t === 'message') listeners.push(f); } };
const ctx = { window: win, URL, URLSearchParams };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(src, 'utf8'), ctx);
const face = ctx.window.MetisEmbed.face(win, search);
const out = { face: !!face, listeners: listeners.length };
if (face) {
  face.attach({ say: (t, via) => said.push([t, via || null]), answerGate: (id, how) => gates.push([id, how]) });
  for (const d of plan.deliver || [])
    for (const f of listeners) f({ origin: d.origin, source: d.from_parent === false ? {} : parent, data: d.data });
  for (const r of plan.rows || []) face.row(r);
  for (const g of plan.gates || []) face.gate(g);
}
Object.assign(out, { posted, said, gates });
process.stdout.write(JSON.stringify(out));
"""


def node():
    n = os.environ.get("NODE") or shutil.which("node")
    if not n:
        if os.environ.get("METIS_LOOP_REQUIRE_NODE") == "1":
            pytest.fail("no node for the embed face's test (NODE or PATH)")
        pytest.skip("no node for the embed face's test")
    return n


def run(tmp_path, search, plan):
    h = tmp_path / "harness.js"
    h.write_text(HARNESS)
    p = subprocess.run([node(), str(h), str(EMBED), search, json.dumps(plan)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_without_embed_nothing_listens_or_posts(tmp_path):
    for search in ("?panels=chat", "?panels=chat&embed=", "?panels=chat&embed=javascript:alert(1)",
                   "?panels=chat&embed=http://127.0.0.1:8400/world.html", "?panels=chat&embed=*"):
        r = run(tmp_path, search, {"deliver": [{"origin": HOST, "data": {"metis": "chat", "text": "/status"}}]})
        assert r == {"face": False, "listeners": 0, "posted": [], "said": [], "gates": []}, search


def test_the_origin_check(tmp_path):
    """Only the named origin AND the framing page: another origin, or another window at the same origin, is ignored."""
    r = run(tmp_path, f"?panels=chat&embed={HOST}", {"deliver": [
        {"origin": "http://127.0.0.1:9999", "data": {"metis": "chat", "text": "/status"}},
        {"origin": "http://evil.example", "data": {"metis": "chat", "text": "/apply"}},
        {"origin": HOST, "from_parent": False, "data": {"metis": "chat", "text": "/take"}},
        {"origin": HOST, "data": {"metis": "chat", "text": "  /status  "}},
        {"origin": HOST, "data": {"metis": "chat", "text": "why did it brake", "via": "heard"}},
        {"origin": HOST, "data": {"metis": "chat", "text": "   "}},
        {"origin": HOST, "data": {"metis": "chat", "text": 42}},
        {"origin": HOST, "data": "not an object"},
    ]})
    assert r["face"] and r["listeners"] == 1
    assert r["said"] == [["/status", None], ["why did it brake", "heard"]]
    assert r["posted"] == [{"m": {"metis": "ready"}, "o": HOST}]          # every post at the named origin, never "*"


def test_a_status_row_and_the_gate_posted(tmp_path):
    rows = [{"who": "you", "text": "/status", "kind": "me"},
            {"who": "/status", "text": "road · v-(not built) STALE", "kind": "cmd"},
            {"who": "loop", "text": "mark 1, as the rules tell it:\nk 2201: I speed up.", "kind": "mark", "mark": 1}]
    r = run(tmp_path, f"?panels=chat&embed={HOST}/", {
        "deliver": [{"origin": HOST, "data": {"metis": "gate", "answer": "confirm", "id": "t1"}},
                    {"origin": HOST, "data": {"metis": "gate", "answer": "delete", "id": "t1"}},
                    {"origin": HOST, "data": {"metis": "gate", "answer": "refuse"}}],
        "rows": rows,
        "gates": [{"open": True, "token": "t1", "title": "apply ruling s-1"}, {"answered": "confirm", "token": "t1"}]})
    assert r["gates"] == [["t1", "confirm"]]
    assert [p["o"] for p in r["posted"]] == [HOST] * 6
    ms = [p["m"] for p in r["posted"]]
    assert ms[0] == {"metis": "ready"}
    assert ms[2] == {"metis": "row", "who": "/status", "text": "road · v-(not built) STALE", "kind": "cmd"}
    assert ms[3]["kind"] == "mark" and ms[3]["mark"] == 1
    assert ms[4:] == [{"metis": "gate", "open": True, "id": "t1", "title": "apply ruling s-1"},
                      {"metis": "gate", "answered": "confirm", "id": "t1"}]


def test_ready_is_the_first_post_even_before_attach(tmp_path):
    """The CHAT's opening rows come during its mount, before the page attaches it: "ready" still goes first, once."""
    h = tmp_path / "harness.js"
    h.write_text(HARNESS.replace("face.attach({", "face.row({who: 'loop', text: 'opening', kind: 'note'}); face.attach({"))
    p = subprocess.run([node(), str(h), str(EMBED), f"?embed={HOST}", "{}"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    ms = [x["m"] for x in json.loads(p.stdout)["posted"]]
    assert ms == [{"metis": "ready"}, {"metis": "row", "who": "loop", "text": "opening", "kind": "note"}]


def test_the_page_attaches_the_face_to_the_chat():
    assert '<script src="lib/embed.js"></script>' in PAGE
    assert "const EMBED=window.MetisEmbed?MetisEmbed.face(window,location.search):null;" in PAGE
    assert "EMBED?{session:()=>sid,onRow:EMBED.row,onGate:EMBED.gate}" in PAGE      # embedded: the host speaks, no onWords
    assert "if(EMBED&&W.chat)EMBED.attach(W.chat);" in PAGE


def test_the_chat_widget_emits_its_rows_and_gate():
    for part in ("function emit(row)", "if (o.onRow) try { o.onRow(row); }", "emit({ who, text: String(text == null ? '' : text)",
                 "if (m.row) emit(m.row);", "o.onGate({ open: true, token: m.token", "o.onGate({ answered: how, token: m.token })",
                 "function answerGate(token, how)", "return { refresh, tail, ruling, say: sendLine, fill, answerGate };",
                 "row: { who: 'loop', kind: 'mark', mark: r.mark"):
        assert part in LOOP_JS, part
