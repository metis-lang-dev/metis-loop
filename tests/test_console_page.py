"""Static guards on the published page (console/loop_console.html):
the artifact skeleton contract and capability discipline; the chat and
the narrator are retired with the brain (loop-workspace, WORKSPACE.md §7).
The behavior itself is driven through the gateway (loop/gateway.py; dev_serve.py went with the db mode, loop-ui 2.4)."""
import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1]
        / "console/loop_console.html").read_text()


def test_skeleton_free_title_style_first_one_script():
    assert PAGE.lstrip().startswith("<title>")
    assert PAGE.index("<style>") < PAGE.index("</style>") < PAGE.index("<header")
    # one inline script; the shell (console/lib/), the SDK's CATALOG widget
    # (sdk/catalog/) and its four workspace widgets with their wire (sdk/workspace/)
    # linked relative, before the page's own; after it the voice's module (console-voice); lib/embed.js the embed face
    # (loop-road-ui step 1)
    assert PAGE.count("<script") == 10 and PAGE.count("<script>") == 1
    assert PAGE.index('<script src="lib/embed.js"></script>') < PAGE.index("<script>")
    assert PAGE.count('<script type="module">') == 1 and PAGE.index("<script>") < PAGE.index('<script type="module">')
    for w in ("io", "bundle", "trace", "rulings", "loop"):
        assert PAGE.index(f'<script src="sdk/workspace/{w}.js"></script>') < PAGE.index("<script>")
    assert "sdk/workspace/surprises.js" not in PAGE        # console-voice step 1: the SURPRISES dock went
    assert PAGE.index('<link rel="stylesheet" href="sdk/workspace/workspace.css">') < PAGE.index("<style>")
    assert PAGE.index('<link rel="stylesheet" href="lib/shell.css">') < PAGE.index("<style>")
    assert PAGE.index('<link rel="stylesheet" href="sdk/catalog/catalog.css">') < PAGE.index("<style>")
    assert PAGE.index('<script src="lib/shell.js"></script>') < PAGE.index("<script>")
    assert PAGE.index('<script src="sdk/catalog/catalog.js"></script>') < PAGE.index("<script>")
    assert not re.search(r"<!doctype|<html\b|<head\b|<body\b", PAGE, re.I)


def test_the_shell_is_the_consoles_own():
    """shell-copy s-7c739dd7: the band, the docks, the strip and the colour
    tokens are console/lib/shell.css + shell.js, this repo's own copy (the
    metis-agent console keeps its own; no dependency for look and feel);
    the page links them and keeps no second copy inline."""
    lib = Path(__file__).resolve().parents[1] / "console" / "lib"
    css, js = (lib / "shell.css").read_text(), (lib / "shell.js").read_text()
    assert ":root{" in css and "#strip" in css and ".dock" in css
    assert "MetisShell" in js and "docks" in js and "splitter" in js
    assert ":root{" not in PAGE and "#strip{" not in PAGE and ".dock{" not in PAGE
    assert "MetisShell.docks({" in PAGE and "MetisShell.splitter()" in PAGE
    assert '<span class="brand">' in PAGE


def test_the_band_has_the_agents_field():
    """human-loop step 3: AGENT, hidden until the gateway sends meta/agent."""
    assert '<span id="b-agentw" hidden' in PAGE and 'id="b-agent"' in PAGE
    assert 'f.type==="agent"){agentM=f;renderAgent()' in PAGE
    assert "renderAgent();" in PAGE[PAGE.index("function renderBand(){"):]


def test_the_gateway_is_the_only_backend():
    """loop-ui 2.4 (the user, 2026-11-05: remove the artifact-era console mode): no claude.ai capability, no db
    transport (intents/sessions docs, their snapshots, the waiters a drain answered), no downloads capability."""
    assert "claude.use(" not in PAGE and "window.claude" not in PAGE
    for gone in ("db.doc(", "db.collection(", "awaitPosting", "waiters", "refreshIntent", "downloadsNs", "onSnapshot"):
        assert gone not in PAGE, gone
    assert "mockSample" not in PAGE and "/db" not in PAGE
    assert 'if(GW)wsConnect();' in PAGE and "the gateway serves this page (metis-loop console-serve)" in PAGE


def test_no_brain_on_the_page():
    """loop-workspace (WORKSPACE.md §3, §7): no CLAUDE dock, no chat, no dictation into it, no
    narrate chip, no narrator section; the formalize/narrate seats' words are gone too."""
    for gone in ('id="dock-claude"', 'data-strip="claude"', "chatq", "chatSend", "PREAMBLE",
                 'data-cmd="narrate"', "narratorHtml", "SpeechRecognition", '{ch:"chat"'):
        assert gone not in PAGE, gone


def test_gateway_transport_is_flag_gated_and_manifest_driven():
    """CONSOLE-WS §5: the WS client only switches on under the gateway's
    flag (the only backend, loop-ui 2.4); stop is wired."""
    assert "const GW=window.LOOP_GATEWAY||null" in PAGE
    assert "if(GW)wsConnect();" in PAGE
    assert "new WebSocket(" in PAGE and "GW.ws" in PAGE
    assert "function applyManifest()" in PAGE
    assert 'type:"stop"' in PAGE and 'id="stopcmd"' in PAGE


def test_the_editor_over_the_files_and_panels():
    """CodeMirror only from the ONE vendor bundle (two CDN copies of @codemirror/state refuse to run) and only
    under the gateway; the EDITOR edits the session's files as they are on disk, save is the edit frame (diff +
    findings, then confirm), a visitor's view reads only (workspace-files s-9ea4cfa4: no copy, no IndexedDB);
    the right side is tool panels whose state is a per-viewer convenience."""
    assert 'import("/vendor/codemirror.js")' in PAGE
    assert not re.search(r"https?://[^\"']*codemirror", PAGE)
    assert "if(!GW){cmLib=null;return cmLib}" in PAGE
    for gone in ("indexedDB", "IndexedDB", "working " + "copy", "recompile", "certified", 'type:"work"', 'type:"save"',
                 "saveWork", "offeredCopy"):
        assert gone not in PAGE, gone
    assert 'if(f.type==="files"){if(f.session===sid)onFiles(f);return}' in PAGE
    assert 'wsSend({ch:"repl",type:"edit",session:sid,path,old:w.base,new:w.get()' in PAGE
    assert 'type:"edit",op:"confirm"' in PAGE and 'type:"edit",op:"refuse"' in PAGE
    assert 'w.reload=true;wsSend({ch:"repl",type:"files",session:sid})' in PAGE     # reload reads the disk now
    assert "${f.since_diff?" in PAGE                                                 # the SAVE dialog shows it
    assert 'id="newext"' in PAGE and "function newExtension(name)" in PAGE         # + extension: an edit of a new file
    assert 'const canWrite=()=>!!GW&&!!manifestM&&manifestM.mode==="personal";' in PAGE
    assert "lib.EditorView.editable.of(false)" in PAGE and "ta.readOnly=ro" in PAGE
    assert 'data-dock="catalog"' in PAGE and 'data-strip="catalog"' in PAGE
    assert 'key:"loopconsole.docks.v5"' in PAGE   # v5: CHAT (loop-chat step 1; v4: the five workspace docks)
    assert 'data-cmd="step ${esc(e.name)}"' in PAGE         # events step


def test_vendor_bundle_exports_what_the_page_uses():
    js = (Path(__file__).resolve().parents[1]
          / "console/vendor/codemirror.js").read_text()
    exports = js[js.rindex("export{"):]
    for name in ("EditorView", "basicSetup", "minimalSetup", "keymap",
                 "placeholder", "Prec", "StreamLanguage", "oneDark"):
        assert f" as {name}" in exports or f"{name}," in exports


def test_stream_tolerates_count_fired_and_links_follow_ups():
    """`state`/`list` return `fired` as a COUNT (run/step: a list) — the
    stream must not iterate it (it froze `state` at "queued"). Plain
    outputs carry follow-ups: atom → why, #K → why K, rule → step/edit."""
    assert "Array.isArray((i.json||{}).fired)" in PAGE
    assert 'h=`<pre class="out">${linkify(i.result)}</pre>`' in PAGE
    assert 'cmd="why "+t.slice(1)' in PAGE and '"step ":"edit "' in PAGE
    assert "e.shiftKey||e.altKey" in PAGE


def test_graph_renders_in_page_from_the_verbs_dot():
    """`graph` draws its own DOT with Graphviz-in-WASM (viz.js): the
    vendored copy under the gateway, the pinned CDN copy elsewhere,
    loaded lazily; nodes are follow-ups (why K); text + DOT kept."""
    assert 'import(GW?"/vendor/viz.js":"https://cdn.jsdelivr.net/npm/@viz-js/viz@3.31.0/dist/viz.js")' in PAGE
    assert "viz.renderSVGElement(i.json.dot)" in PAGE
    assert 'g.setAttribute("data-fu","why "+id.slice(1))' in PAGE
    assert "<summary>DOT source</summary>" in PAGE
    vz = Path(__file__).resolve().parents[1] / "console/vendor/viz.js"
    assert vz.stat().st_size > 500_000 and "renderSVGElement" in vz.read_text()


def test_the_catalog_list_is_the_sdks_widget():
    """catalog-sdk s-bc1718e3: the CATALOG panel's list is the loop SDK's
    widget (MetisCatalog.render, the same component the metis-agent console
    shows), served from the installed SDK; the page keeps only its own extras
    (the stale tag, the path, the new-domain form) and no row markup of its own."""
    from metis_loop_sdk import web
    assert "MetisCatalog.render(box,domainList," in PAGE
    assert 'class="dm' not in PAGE and "data-dom=" not in PAGE
    # its box is its own: the open box's datalist is #catlist (the widget once rendered into it)
    assert PAGE.count('id="catrows"') == 1 and '$("#catrows")' in PAGE and PAGE.count('id="catlist"') == 1
    js, css = web.widget_file("catalog.js"), web.widget_file("catalog.css")
    assert "window.MetisCatalog" in js[0] and js[1].startswith("text/javascript")
    assert ".tag.stale" in css[0] and css[1].startswith("text/css")
    assert web.widget_file("../catalog.py") is None and web.widget_file("x.js") is None


LIB = Path(__file__).resolve().parents[1] / "console" / "lib"


def test_no_voice_navigation_on_the_page():
    """voice-nav-removal s-90621b2c (the user, 2026-10-24: one voice paradigm, the dialog with the
    agent and the game; the web UI stays web): the console has no TALK dock, no navigation agent,
    no flip key and no widget tags. console/lib is the shell alone — the fsttm-web copies went with TALK; the
    voice of console-voice is fsttm-web served from its installed package (no copy, no import map). Beside the shell,
    the console's own embed face (embed.js, loop-road-ui step 1): no voice in it."""
    assert sorted(p.name for p in LIB.iterdir()) == ["embed.js", "shell.css", "shell.js"]
    for gone in ("dock-talk", 'data-strip="talk"', "nav.js", "ui-port", "importmap", "fsttm-web/",
                 "navHook", "consolePage", "flip_key", "data-w=", "data-role="):
        assert gone not in PAGE, gone
    assert '<dialog id="savewin"' in PAGE


def test_the_voice_in_the_band_and_the_dialog_dock():
    """console-voice s-dc1f184c (the user, 2026-11-05: "add fsttm-web widget into top bar and fsttm-web tool panel
    last after catalog and chat ... stt output goes to chat windows"): the voice widget fills #voice in the band,
    the dialog's own part (dialogIn) is the DIALOG dock, the last dock; the panel's own chat is not shown; a heard
    line is said in the CHAT as the person's (via heard); pi's words go to the dialog to be spoken."""
    assert '<span id="voice" hidden></span>' in PAGE[PAGE.index('<header id="band"'):PAGE.index("</header>")]
    docks = re.findall(r'data-dock="(\w+)"', PAGE)
    assert docks[-1] == "dialog" and docks.index("chat") < docks.index("dialog") and docks.index("catalog") < docks.index("dialog")
    assert 'const DOCKS=["catalog","chat","rulings","trace","bundle","dialog"];' in PAGE
    mod = PAGE[PAGE.index('<script type="module">'):]
    for imp in ("import('./lib/panel.js')", "import('./lib/switch.js')", "import('./lib/narrator.js')"):
        assert imp in mod, imp
    assert "dialogIn: $('#dialogpart')" in mod and "micButton: false" in mod and "#voicepanel{display:none}" in PAGE
    assert "c.say(text, 'heard')" in mod and "voiceWidget(panel" in mod
    assert "speak: text => panel.core.frame({ ev: 'chat', who: 'system', text })" in mod
    assert "onWords:t=>window.MetisVoice&&MetisVoice.speak(t)" in PAGE
    assert "onChange:st=>window.MetisVoice&&MetisVoice.showDialog(st)" in PAGE


def test_the_workspace_docks_mount_the_sdk_widgets():
    """loop-workspace step 4 (WORKSPACE.md §6), reduced by loop-chat step 1 (CHAT.md §1) and console-voice step 1:
    CHAT, RULINGS, TRACE, BUNDLE are docks whose bodies the SDK's widgets fill, mounted when the manifest serves the
    loop channel; their frames go to the widgets' wire; TRACE's mark puts the /mark line in the CHAT's input; a
    session opened here writes its trace."""
    for d in ("chat", "rulings", "trace", "bundle"):
        assert f'data-dock="{d}"' in PAGE and f'data-strip="{d}"' in PAGE and f'id="w-{d}"' in PAGE
    assert 'data-dock="loop"' not in PAGE and 'id="w-loop"' not in PAGE
    assert 'key:"loopconsole.docks.v5"' in PAGE and "docks.v4" not in PAGE
    assert '(m.channels||[]).includes("loop")&&!wsW)mountWorkspace()' in PAGE
    assert "if(wsIO&&WS_CH.includes(f.ch)){wsIO.feed(f);return}" in PAGE
    for g in ("MetisBundle", "MetisRulings", "MetisTrace", "MetisLoop"):
        assert f"{g}.mount(" in PAGE
    assert "MetisSurprises" not in PAGE and "W.surprises" not in PAGE
    assert 'W.chat.fill(`/mark ${d.run} ${d.window?d.window[0]+".."+d.window[1]:d.k} `)' in PAGE
    assert "...(wsW?{trace:true}:{})" in PAGE


def test_chat_by_default_the_rest_behind_developer():
    """loop-chat step 1 (CHAT.md §1), console-voice step 1: on a workspace CHAT is open; TRACE, RULINGS, BUNDLE are
    hidden, their docks and strip buttons behind the band's developer switch (kept per viewer)."""
    i = PAGE.index('key:"loopconsole.docks.v5",')
    dflt = PAGE[i:PAGE.index("}}});", i) + 2]
    assert "chat:{shown:!!GW,open:true}" in dflt and "surprises:" not in dflt
    for d in ("rulings", "trace", "bundle"):
        assert f"{d}:{{shown:false,open:false}}" in dflt
        assert f'class="dock ws-dock dev-dock" id="dock-{d}"' in PAGE
        assert f'data-strip="{d}" class="ws-strip dev-strip"' in PAGE
    assert 'id="devbtn" hidden aria-pressed="false"' in PAGE
    assert 'DEV_DOCKS=["rulings","trace","bundle"]' in PAGE and 'store.get("loopconsole.dev",false)' in PAGE
    assert PAGE.index('id="dock-chat"') < PAGE.index('id="dock-rulings"')


def test_panels_query_mounts_only_those():
    """loop-chat step 1 (CHAT.md §1, the embedding): ?panels=chat mounts the named widgets only, with a
    layout key of its own, no band, REPL or strip, and no package opened."""
    assert 'new URLSearchParams(location.search).get("panels")' in PAGE
    assert 'if(PANELS)$("#root").classList.add("panels")' in PAGE
    assert "#root.panels #strip,#root.panels #band,#root.panels #left,#root.panels #split{display:none!important}" in PAGE
    assert 'key:"loopconsole.docks.v5.panels"' in PAGE
    for w in ("bundle", "rulings", "chat", "trace"):
        assert f'if(wsOn("{w}"))W.{w}=' in PAGE
    assert "&&!PANELS){pkgOpened=true;openCatalog" in PAGE


def test_the_chat_widget_carries_the_cards():
    """loop-chat step 1 (CHAT.md §1): the CHAT's header line (bundle, pi, spend of budget), the gate and a ruling as
    cards, STALE as a notice with rebuild and reload; the ruling card is RULINGS' own function, not a copy."""
    js = (Path(__file__).resolve().parents[1] / "web/workspace/loop.js").read_text()
    for part in ("function header()", "bundlePart()", "piPart()", "spendPart()", "function gateCard(", "function staleCard(",
                 "function builtCard(", "window.MetisRulings.card", "sendLine('/rebuild')", "sendLine('/reload')",
                 "io.ask('loop', 'start'", "'confirm'", "'refuse'"):
        assert part in js, part
    assert "row.kind === 'ruling'" in js                      # a ruling journalled opens its card
    assert "if (ev.empty) push('err', 'pi', ev.note" in js                  # step 3: an empty turn says so
    assert "of ${of} USD (pi's estimate)" in js
    assert "started the pi loop: ${c.model || msg.model" in js and "thinking ${msg.no_thinking ? 'off' : \"on (pi's default level)\"}" in js   # L4; reasoning on (loop-prompt)                              # the header's spend is pi's count, said so
    assert "disabled: !!held" not in js                                     # step 3: /commands answer under a TUI
    rjs = (Path(__file__).resolve().parents[1] / "web/workspace/rulings.js").read_text()
    assert "window.MetisRulings = { mount, card };" in rjs
    assert rjs.count("(r.inert ? ' (inert)' : '')") == 2                     # the card and the dock: accepted (inert)


def test_candidates_records_and_surprises_docks_are_gone():
    """console-voice step 1 (the user, 2026-11-05: "remove candidates, records, surprise panels ... we have
    /surprises for same info"): the three docks, their strips, scripts and renderers are out; the debugger, CATALOG,
    CHAT (and the developer's three, the DIALOG) stay. /surprises lists, /mark and /drop drop (the CHAT drops a /mark
    draft itself)."""
    for d in ("candidates", "records", "surprises"):
        assert f'data-dock="{d}"' not in PAGE and f'data-strip="{d}"' not in PAGE and f'id="dock-{d}"' not in PAGE
    for gone in ('id="cands"', 'id="records"', "w-surprises", "renderRight", "renderRecords", "pickRecord", "afterSink",
                 "fileRecs", "pendingRec", "canDecide", 'db.collection("candidates")', 'db.collection("surprise")',
                 "data-dec", '{ch:"repl",type:"records"}'):
        assert gone not in PAGE, gone
    assert re.findall(r'data-dock="(\w+)"', PAGE) == ["catalog", "chat", "rulings", "trace", "bundle", "dialog"]
