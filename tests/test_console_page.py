"""Static guards on the published page (console/loop_console.html):
the artifact skeleton contract, capability discipline, and the chat's
preamble/tool invariants (CONSOLE.md §3). The behavior itself is
driven in Chrome through console/dev_serve.py."""
import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1]
        / "console/loop_console.html").read_text()


def test_skeleton_free_title_style_first_one_script():
    assert PAGE.lstrip().startswith("<title>")
    assert PAGE.index("<style>") < PAGE.index("</style>") < PAGE.index("<header")
    # one inline script; the shell (console/lib/) and the SDK's CATALOG widget
    # (sdk/catalog/) linked relative, before the page's own
    assert PAGE.count("<script") == 3 and PAGE.count("<script>") == 1
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


def test_capabilities_only_through_use_and_no_dev_shim():
    assert not re.search(r"window\.claude\.", PAGE)
    for cap in ('"db"', '"user"', '"sample"'):
        assert f"claude.use({cap})" in PAGE
    assert "mockSample" not in PAGE and "/db" not in PAGE


def test_chat_preamble_and_tool_invariants():
    pre = PAGE[PAGE.index("const PREAMBLE="):PAGE.index("let sampleNs")]
    assert "prefix every line with \":\"" in pre
    assert ":accept is refused" in pre and "never approve" in pre
    assert "FROM THE DIAGNOSTICS" in pre
    assert 'name:"repl"' in PAGE and 'queue(line,"claude",true)' in PAGE
    assert "cache:false" in PAGE                 # chat never replays
    assert 'code==="not_granted"' in PAGE and 'code==="rate_limited"' in PAGE


def test_gateway_transport_is_flag_gated_and_manifest_driven():
    """CONSOLE-WS §5: the WS client only switches on under the gateway's
    flag; the artifact build keeps its capability shims; the chat pane
    and LLM affordances follow the manifest; stop is wired."""
    assert "const GW=window.LOOP_GATEWAY||null" in PAGE
    assert "if(GW){wsConnect();return}" in PAGE            # skips the db
    assert "new WebSocket(" in PAGE and "GW.ws" in PAGE
    assert "function applyManifest()" in PAGE
    assert '"chat is not served' not in PAGE                # gateway says it
    assert 'type:"stop"' in PAGE and 'id="stopcmd"' in PAGE


def test_working_copy_editor_panels_and_dictation():
    """§4a: CodeMirror only from the ONE vendor bundle (two CDN copies of
    @codemirror/state refuse to run) and only under the gateway; the
    copy lives in IndexedDB; the right side is tool panels whose state
    is a per-viewer convenience; dictation is feature-detected and says
    where Chrome sends the audio."""
    assert 'import("/vendor/codemirror.js")' in PAGE
    assert not re.search(r"https?://[^\"']*codemirror", PAGE)
    assert "if(!GW){cmLib=null;return cmLib}" in PAGE
    assert 'indexedDB.open("loopconsole"' in PAGE
    for d in ("claude", "catalog", "candidates", "records"):
        assert f'data-dock="{d}"' in PAGE and f'data-strip="{d}"' in PAGE
    assert 'key:"loopconsole.docks.v2"' in PAGE   # v2: the Records dock shows (e2e step 1)
    assert "#chatq{flex:1;background:var(--bg);color:var(--fg)" in PAGE
    assert "window.SpeechRecognition||window.webkitSpeechRecognition" in PAGE
    assert "Google's speech service" in PAGE
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
    from metis_loop_sdk import catalog
    assert "MetisCatalog.render(box,domainList," in PAGE
    assert 'class="dm' not in PAGE and "data-dom=" not in PAGE
    # its box is its own: the open box's datalist is #catlist (the widget once rendered into it)
    assert PAGE.count('id="catrows"') == 1 and '$("#catrows")' in PAGE and PAGE.count('id="catlist"') == 1
    js, css = catalog.widget_file("catalog.js"), catalog.widget_file("catalog.css")
    assert "window.MetisCatalog" in js[0] and js[1].startswith("text/javascript")
    assert ".tag.stale" in css[0] and css[1].startswith("text/css")
    assert catalog.widget_file("../catalog.py") is None and catalog.widget_file("x.js") is None
