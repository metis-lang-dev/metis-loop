"""A stub of the loop console page for domains/ui's host (console-nav s-b923ebfe): the
widget tree and roles read from the instance (domains/ui/ui.llp's child/2 and role/2 facts),
the page's real focus, docks and dialog, and the input port of README.md. It carries out the
host's effects as the page would and reports back; the person's own acts (a click, the
dialog rising) are its methods.

    page = StubPage(lists={"catin": ["plant", "dog", "dog_two"]})
    page.carry(host)          # every effect the host has queued, then the reports into host.port
    page.click("records")     # the person's focusin: reported
    page.open_dialog()        # the APPLY dialog rises: reported, the focus to its entry

Faithful to the port's rules: a focus the page makes for an effect is reported as focusin
(as the browser does: it does not know who moved it); a dock the page shows or hides for an
effect is NOT reported (only one it shows or hides itself is); while the dialog is up the
rest of the page is inert — a click there is refused unless breach=True (the case the
standards leave silent, which observe() must catch)."""
import re
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "domains" / "ui" / "ui.llp"


class StubPage:
    def __init__(self, lists=None, path=UI):
        text = Path(path).read_text()
        self.parent = {c: p for p, c in re.findall(r"^child\((\w+),\s*(\w+)\)\.", text, re.M)}
        self.role = dict(re.findall(r"^role\((\w+),\s*(\w+)\)\.", text, re.M))
        self.shown = {w for w in re.findall(r"^#init shown\((\w+)\)", text, re.M)}
        self.hidden = {w for w in re.findall(r"^#init hidden\((\w+)\)", text, re.M)}
        self.focus, self.modal, self.mode, self.numbered = "root", None, "command", None
        self.lists = {w: list(v) for w, v in (lists or {}).items()}
        self.reports, self.done = [], []          # pending reports; effects carried out (the journal)

    def _report(self, r):
        self.reports.append(r)

    def inert(self, w):
        return self.modal is not None and w != self.modal and not self._inside(w, self.modal)

    def _inside(self, w, d):
        while w in self.parent:
            w = self.parent[w]
            if w == d:
                return True
        return False

    # -- the host's effects ---------------------------------------------------

    def effect(self, e):
        self.done.append(e)
        kind, w = e["ui"], e.get("widget")
        if kind == "focus":
            if w in self.shown and not self.inert(w) and w in self.role:
                if w != self.focus:
                    self.focus = w
                    self._report({"focus": w})            # focusin: the browser does not know who moved it
        elif kind == "show" and w in self.hidden:
            self.hidden.discard(w)
            self.shown.add(w)                             # for an effect: not reported
        elif kind == "hide" and w in self.shown:
            self.shown.discard(w)
            self.hidden.add(w)
        elif kind == "numbers":
            self.numbered = w
        elif kind == "unnumber":
            self.numbered = None
        elif kind == "pick":
            entries = self.lists.get(w, [])
            if "number" in e:
                hit = entries[e["number"] - 1:e["number"]] if 0 < e["number"] <= len(entries) else []
            else:
                hit = [x for x in entries if e.get("name", "").lower() in x.lower()] if e.get("name") else []
            self._report({"picked": True} if len(hit) == 1 else {"ambiguous": True} if hit else {"nothing_picked": True})
        elif kind == "mode":
            self.mode = e["mode"]

    def carry(self, host):
        """Every effect the host queued, carried out; the page's reports into its port."""
        while host.effects:
            self.effect(host.effects.pop(0))
        self.flush(host)

    def flush(self, host):
        while self.reports:
            host.port(self.reports.pop(0))

    # -- the person's own acts --------------------------------------------------

    def click(self, w, breach=False):
        """A focusin the person makes (mouse or keyboard); inert widgets take none, unless breach."""
        if w not in self.role or w not in self.shown or (self.inert(w) and not breach):
            return False
        if w != self.focus:
            self.focus = w
            self._report({"focus": w})
        return True

    def open_dialog(self, d="apply"):
        """The dialog rises and takes the focus (its entry: the instance's entry/2, the dialog
        itself here); the page folds that focusin into the opened report."""
        self.modal = d
        self.hidden.discard(d)
        self.shown.add(d)
        self._report({"opened": d})
        self.focus = d                                    # the dialog's entry (ui.llp: entry(apply, apply))

    def close_dialog(self, d="apply", back="root"):
        """The dialog falls; the browser restores the focus to its invoker (a focusin: reported)."""
        self.modal = None
        self.shown.discard(d)
        self.hidden.add(d)
        self._report({"closed": d})
        self.focus = back
        self._report({"focus": back})

    def lose_focus_silently(self, to="root"):
        """The focused element goes away (removed, re-rendered): the browser moves the focus with no
        focusin. The port says nothing; the page samples its real focus (?blur / ?focus(W))."""
        self.focus = to
        self._report({"sample": None if to == "root" else to})

    def hide_itself(self, w):
        """The page hides a dock by itself (not for an effect): reported."""
        self.shown.discard(w)
        self.hidden.add(w)
        self._report({"hidden": w})
