"""domains/ui's host, the page (console-nav s-b923ebfe): the effect each fired rule sends the
page, the input port (focusin coalesced, the dialog, the docks, a pick's answer), the card's
activation, observe() and its catch-up; then through metis-agent's domain agent (the kernel,
typed intents, no model) with the stub page carrying the effects."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from stub_page import StubPage

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ui_host", ROOT / "domains" / "ui" / "ui_host.py")
ui_host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui_host)


def fired(h, event, **payload):
    h.take_payload(payload)
    h.on_event(event, [])
    out, h.effects = list(h.effects), []
    return out


def test_each_rule_sends_the_page_its_effect():
    h = ui_host.UiHost()
    assert fired(h, "go_child[W=catalog,F=root,Q=root]") == [{"ui": "focus", "widget": "catalog"}]
    assert fired(h, "go_hidden[W=editor,F=catalog,Q=root]") == [{"ui": "show", "widget": "editor"},
                                                                {"ui": "focus", "widget": "editor"}]
    assert fired(h, "close[W=editor,P=root]") == [{"ui": "hide", "widget": "editor"}, {"ui": "focus", "widget": "root"}]
    assert fired(h, "exit[F=copy,Q=catalog,P=catalog]") == [{"ui": "focus", "widget": "catalog"}]
    assert fired(h, "exit_to_dialog[F=ok,Q=root,D=apply]") == [{"ui": "focus", "widget": "apply"}]   # nina's H2
    assert fired(h, "home[F=catalog,Q=copy,P=root]") == [{"ui": "focus", "widget": "root"}]
    assert fired(h, "back[F=root,P=catalog]") == [{"ui": "focus", "widget": "catalog"}]
    assert fired(h, "numbers[W=copy]") == [{"ui": "numbers", "widget": "copy"}]
    assert fired(h, "clear_numbers[N=stream]") == [{"ui": "unnumber"}]
    assert fired(h, "pick[W=catin]", name="the plant") == [{"ui": "pick", "widget": "catin", "name": "the plant"}]
    assert fired(h, "pick_n[N=n3,W=copy]") == [{"ui": "pick", "widget": "copy", "number": 3}]
    assert fired(h, "dictate[W=prompt]")[0] == {"ui": "mode", "mode": "dictation"}
    assert fired(h, "mode_back[N=root,R=container]") == [{"ui": "mode", "mode": "command"}]
    assert fired(h, "move[N=records,O=prompt]") == []                  # the person's own: nothing to do
    assert fired(h, "show[W=records]") == [{"ui": "show", "widget": "records"}]
    assert fired(h, "go_numbers[W=chat]") == [{"ui": "unnumber"}]      # a voice move drops the numbers
    assert fired(h, "jump") == [{"ui": "jump"}]
    assert fired(h, "jump_to[L=c]") == [{"ui": "jump", "letter": "c"}]
    assert fired(h, "jump_pick[N=n2]") == [{"ui": "jump_pick", "number": 2}]
    assert fired(h, "jump_ok_hidden[W=editor,F=root,Q=root]") == [{"ui": "show", "widget": "editor"},
                                                                  {"ui": "focus", "widget": "editor"}]
    for r in ("clear_jump[N=chat]", "go_jump[W=chat]", "cancel_jump"):
        assert fired(h, r) == [{"ui": "unjump"}]
    # a pending choice dropped unresolved: the candidates' numbers go (nina's H3)
    for r in ("cancel_choice", "clear_choice[N=chat]", "blur_choice", "open_choice[D=apply]", "go_choice[W=chat]",
              "exit_choice", "home_choice", "back_choice", "jump_choice", "jump_to_choice[L=c]"):
        assert fired(h, r) == [{"ui": "unnumber"}], r
    assert fired(h, "pick_replace[W=catin]", name="dog") == [{"ui": "unnumber"},
                                                             {"ui": "pick", "widget": "catin", "name": "dog"}]
    assert fired(h, "pick_choice[N=n2]")[0]["ui"] == "pick"                # resolved: the page clears them itself
    assert fired(h, "hold_command") == [{"ui": "mode", "mode": "held"}]   # push-to-talk
    assert fired(h, "release[M=command]") == [{"ui": "mode", "mode": "command"}]


def test_the_repl_card_follows_the_focus_into_the_repls_widgets():
    h = ui_host.UiHost()
    assert fired(h, "go_named[W=prompt,F=root,Q=root,P=debugger]")[-1] == {"ui": "activate", "domain": "repl"}
    assert fired(h, "go_child[W=stream,F=debugger,Q=prompt]") == [{"ui": "focus", "widget": "stream"}]   # still in
    assert fired(h, "move[N=records,O=stream]") == [{"ui": "deactivate", "domain": "repl"}]           # a click out


def test_the_port_coalesces_focusin_and_reports_the_rest():
    h = ui_host.UiHost()
    for w in ("catalog", "copy", "readme"):                 # three focusins in one tick
        h.port({"focus": w})
    h.port({"picked": True})
    assert h.tick({"done(go)": 1}) == ["-done(go) 1", "+enter(readme)", "+picked"]
    h.port({"page_refused": True})
    h.world(["+page_refused"])
    assert h.tick({}) == ["+page_refused", "+page_refused"]
    h.port({"blur": True})
    assert h.tick({}) == ["+blur"]
    h.port({"opened": "apply"})
    h.port({"focus": "apply"})                              # the dialog's entry: +opened's, not a move
    assert h.tick({}) == ["+opened(apply)"]
    h.port({"hidden": "records"})
    assert h.tick({}) == ["-shown(records)", "+hidden(records)"]
    h.world(["+enter(chat)", "+closed(apply)"])
    assert h.tick({}) == ["+enter(chat)", "+closed(apply)"]
    with pytest.raises(ValueError):
        h.world(["+click(chat)"])
    h.world(["?focus(records)"])                            # a sample asserts nothing
    assert h.tick({}) == [] and h.page["focus"] == "records"
    h.world(["?blur"])
    assert h.page["focus"] == "root"


def test_observe_reads_the_page_once_it_caught_up():
    h = ui_host.UiHost()
    page = StubPage()
    counts = {"focused(root)": 1, "free": 1}
    assert h.observe(counts) == {}                          # the page has said nothing yet
    page.click("chat")
    page.flush(h)
    h.tick(counts)
    counts = {"focused(chat)": 1, "free": 1}
    assert h.observe(counts)["focused(chat)"] == 1
    fired_effects = fired(h, "go_child[W=catalog,F=root,Q=chat]")
    assert h.observe(counts) == {}                          # our effect is in flight
    for e in fired_effects:
        page.effect(e)
    page.flush(h)
    h.tick(counts)
    assert h.observe({"focused(catalog)": 1})["focused(catalog)"] == 1
    fired(h, "go_child[W=readme,F=catalog,Q=root]")         # the page never carries this one out
    for _ in range(ui_host.CATCH_UP + 1):
        h.tick({})
    r = h.observe({"focused(readme)": 1})
    assert r["focused(readme)"] == 0 and r["focused(catalog)"] == 1      # the difference the watch prices


def test_snapshot_is_json_and_restores():
    import json
    h = ui_host.UiHost()
    h.port({"focus": "chat"})
    h.on_event("go_child[W=catalog,F=root,Q=root]", [])
    s = json.loads(json.dumps(h.snapshot()))
    g = ui_host.UiHost()
    g.restore(s)
    assert g.snapshot() == h.snapshot()


# -- through the domain agent: the kernel serves ui, the stub page carries it out ------------

def _agent():
    d = os.environ.get("METIS_AGENT_DIR")
    if d and d not in sys.path:
        sys.path.insert(0, d)
    try:
        from metis_agent.domain_agent import Process, serve
        return Process, serve
    except Exception:                       # noqa: BLE001 — no metis-agent here
        return None


def _served(monkeypatch, page):
    Process, serve = _agent()
    monkeypatch.setenv("METIS_CATALOG", str(ROOT))
    proc = Process(["ui"])
    agent = proc.build(1, "replay")
    host = agent.host.inner

    def line(msg):
        """One line; the page carries out the effects its replies bring (the trace's `effects`,
        metis-agent's drain), else what the host still queues (an agent before the drain)."""
        out = serve(agent, msg, proc.build, proc.reload, proc.add_line)[1]
        for r in out:
            for e in (r.get("effects") or []) if r.get("kind") == "trace" else []:
                page.effect(e)
        page.carry(host)
        return out

    def run(msg=None, beats=4):
        out = line(msg) if msg else []
        for _ in range(beats):
            out += line({"clock": "beat"})
        return out
    return agent, run



@pytest.mark.skipif(_agent() is None, reason="no metis-agent (METIS_AGENT_DIR: its py/)")
def test_ui_served_by_the_domain_agent_with_the_page(monkeypatch):
    page = StubPage(lists={"catin": ["plant", "dog", "dog_shared"]})
    agent, run = _served(monkeypatch, page)
    n = [0]

    def say(verb, **args):
        n[0] += 1
        out = run({"domain": "ui", "id": n[0], "verb": verb, "args": args})
        return [(r.get("status"), r.get("text", "")) for r in out if r.get("status") in ("done", "refused")]

    assert say("GO", widget="CATALOG")[0][0] == "done" and page.focus == "catalog"
    assert say("GO", widget="PROMPT")[0][0] == "done" and page.focus == "prompt"
    assert {"ui": "activate", "domain": "repl"} in page.done
    page.click("records")                                   # the person's own focus: tracked
    run(beats=3)
    assert agent.repl.counts.get("focused(records)") == 1
    assert say("EXIT")[0][0] == "done" and page.focus == "root"
    page.open_dialog()                                      # the APPLY dialog rises (the REPL's apply)
    run(beats=3)
    assert agent.repl.counts.get("modal(apply)") == 1 and agent.repl.counts.get("focused(apply)") == 1
    refusal = say("GO", widget="CATALOG")
    assert refusal and refusal[0][0] == "refused"           # the dialog holds the focus, with the reason
    assert [r for r in run(beats=3) if r.get("kind") == "surprise"] == []      # the page and the program agree

@pytest.mark.skipif(_agent() is None, reason="no metis-agent (METIS_AGENT_DIR: its py/)")
def test_a_go_the_page_cannot_carry_out_is_a_surprise(monkeypatch):
    """The program moved the focus to the README; the page has none (it does not take the
    focus): after the catch-up, observe() reads the page's real focus — a surprise record."""
    page = StubPage()
    page.shown.discard("readme")                        # this page lacks the widget
    agent, run = _served(monkeypatch, page)
    run({"domain": "ui", "id": 1, "verb": "GO", "args": {"widget": "CATALOG"}})
    out = run({"domain": "ui", "id": 2, "verb": "GO", "args": {"widget": "README"}}, beats=ui_host.CATCH_UP + 4)
    s = [r for r in out if r.get("kind") == "surprise"]
    assert s and "focused(readme)" in json.dumps(s[0])


@pytest.mark.skipif(_agent() is None, reason="no metis-agent (METIS_AGENT_DIR: its py/)")
def test_a_focus_breach_during_the_dialog_is_a_surprise(monkeypatch):
    """A focusin outside the modal dialog (the page let a click through its inert background):
    the rules do not follow it (p_enter_modal consumes the port line), so observe() reads the
    page's focus elsewhere — a surprise record."""
    page = StubPage()
    agent, run = _served(monkeypatch, page)
    page.open_dialog()
    assert [r for r in run() if r.get("kind") == "surprise"] == []          # the dialog's rise: agreed
    assert agent.repl.counts.get("focused(apply)") == 1
    page.click("records", breach=True)                  # the inert page let a click through
    out = run(beats=ui_host.CATCH_UP + 2)
    s = [r for r in out if r.get("kind") == "surprise"]
    assert s and "focused(records)" in json.dumps(s[0])
    assert agent.repl.counts.get("focused(apply)") == 1                     # the rules did not follow it


@pytest.mark.skipif(_agent() is None, reason="no metis-agent (METIS_AGENT_DIR: its py/)")
def test_a_focus_change_the_port_never_reported_is_a_surprise(monkeypatch):
    """H1: the focused widget goes away (no focusin); the page samples its real focus; the rules
    did not see it, observe() does — a surprise record."""
    page = StubPage()
    agent, run = _served(monkeypatch, page)
    run({"domain": "ui", "id": 1, "verb": "GO", "args": {"widget": "CATALOG"}})
    assert [r for r in run() if r.get("kind") == "surprise"] == []
    page.lose_focus_silently()
    s = [r for r in run(beats=ui_host.CATCH_UP + 2) if r.get("kind") == "surprise"]
    assert s and agent.repl.counts.get("focused(catalog)") == 1


@pytest.mark.skipif(_agent() is None, reason="no metis-agent (METIS_AGENT_DIR: its py/)")
def test_a_voice_jump_labels_the_page_and_lands_on_the_label(monkeypatch):
    """Jump mode: JUMP labels the reachable widgets, a number resolves a label, the page answers
    +jumped(W), and the focus lands there; a label that names nothing is refused."""
    page = StubPage()
    agent, run = _served(monkeypatch, page)
    run({"domain": "ui", "id": 1, "verb": "JUMP", "args": {}})
    assert page.labels and agent.repl.counts.get("jumping") == 1
    target = page.labels[2]
    out = run({"domain": "ui", "id": 2, "verb": "PICK", "args": {"number": 3}})
    assert [r.get("status") for r in out if r.get("status") in ("done", "refused")] == ["done"]
    assert agent.repl.counts.get(f"focused({target})") == 1 and page.focus == target
    assert [r for r in run() if r.get("kind") == "surprise"] == []
    run({"domain": "ui", "id": 3, "verb": "JUMP", "args": {}})
    out = run({"domain": "ui", "id": 4, "verb": "PICK", "args": {"number": 9 if len(page.labels) < 9 else 1}})
    st = [r.get("status") for r in out if r.get("status") in ("done", "refused")]
    assert st and st[-1] in ("done", "refused") and agent.repl.counts.get("idle_jump") == 1
