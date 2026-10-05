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
    assert PAGE.count("<script") == 1
    assert not re.search(r"<!doctype|<html\b|<head\b|<body\b", PAGE, re.I)


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
