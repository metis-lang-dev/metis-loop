"""The console's serving half (CONSOLE §5a): one kernel REPL per open
console window, over the metis-catalog checkout.

The artifact db is reachable only by the page's capability or by a
Claude session's ArtifactData tool, so the drain is a Claude session
(skills/metis-loop "Serving the console"); this module is the python
it calls — no db access of its own, no threads, import-light:

  - `catalogs()`           names for meta/catalogs (load chips);
  - `open_session(sid, doc)` binds an interpreter to a sessions doc
                            and returns the fields to write back;
  - `serve_one(sid, cmd)`  runs ONE queued intent line through the
                            run_intent whitelist (`intent_posting`) and
                            returns {posting, session}: the intent
                            doc's update and the session doc's update;
  - `close_session(sid)`.

v1 keeps the interpreters in-process (`Repl` instances); the fifo bus
of N `metis --json` processes (SPEC §6) is a v2 swap behind the same
four calls. The epoch (start 1) bumps when the world under a window
changes — a reset, or a new program key — and the page clears its
stream on a bump."""
import io
import os
import time
from pathlib import Path
from typing import Dict, Optional


def catalog_root() -> Path:
    """$METIS_CATALOG, else the metis-catalog checkout beside this
    package (perotheia-packages/metis-catalog)."""
    env = os.environ.get("METIS_CATALOG")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "metis-catalog"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ConsoleServer:
    """{sid: Repl} plus the per-session epoch."""

    def __init__(self, root: Optional[Path] = None, seed: int = 1):
        self.root = Path(root) if root else catalog_root()
        self.seed = seed
        self.shells: Dict[str, object] = {}
        self.epochs: Dict[str, int] = {}

    # -- catalogs --------------------------------------------------------

    def catalogs(self):
        """Every .llp under the checkout, as names relative to it
        without the suffix (`domains/fiction/3lp`), sorted."""
        return sorted(str(p.relative_to(self.root).with_suffix(""))
                      for p in self.root.rglob("*.llp")
                      if ".git" not in p.parts)

    def resolve(self, llp: str) -> Path:
        """A catalog name -> its file in the checkout: the full
        relative name (with or without .llp), or a unique basename
        (`3lp`). Never outside the checkout."""
        name = (llp or "").strip()
        if not name:
            raise ValueError("no catalog named")
        name = name[:-4] if name.endswith(".llp") else name
        names = self.catalogs()
        hits = [n for n in names if n == name] or \
               [n for n in names if n.split("/")[-1] == name] or \
               [n for n in names if n.endswith("/" + name)]
        if not hits:
            raise ValueError(f"no catalog '{llp}' in {self.root}")
        if len(hits) > 1:
            raise ValueError(f"'{llp}' is ambiguous: {', '.join(hits)}")
        path = (self.root / (hits[0] + ".llp")).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"'{llp}' resolves outside the checkout")
        return path

    # -- sessions --------------------------------------------------------

    def _fields(self, sid: str) -> dict:
        """The session doc's backend-owned fields, ctx included (the
        band renders from it)."""
        r = self.shells[sid]
        c = r.ctx()
        return {"name": c["catalog"], "key": c["key"],
                "stage": c["stage"], "status": c["status"],
                "epoch": self.epochs[sid], "ctx": c,
                "last_ts": _now()}

    def open_session(self, sid: str, doc: dict) -> dict:
        """Bind an interpreter to sessions/{sid} ({llp, …}); returns
        the fields to write back. A bad llp comes back as
        {status: "closed", error}."""
        from metis.lang.repl import Repl
        try:
            path = self.resolve(doc.get("llp", ""))
            self.shells[sid] = Repl(path, seed=self.seed,
                                    stdout=io.StringIO())
        except Exception as e:                      # noqa: BLE001
            return {"status": "closed", "error": str(e),
                    "last_ts": _now()}
        self.epochs[sid] = 1
        out = self._fields(sid)
        out["llp"] = str(path.relative_to(self.root.resolve())
                         .with_suffix(""))
        return out

    def serve_one(self, sid: str, cmd: str) -> dict:
        """One queued intent: {posting: the intent doc's update
        (intent_posting + epoch + done_ts), session: the session doc's
        update (epoch bumped on reset / key change)}."""
        from metis.loop.wire import intent_posting
        if sid not in self.shells:
            return {"posting": {"status": "error",
                                "result": f"no open session '{sid}'",
                                "json": {"ok": False}, "done_ts": _now()},
                    "session": None}
        r = self.shells[sid]
        line = cmd.strip()
        line = line if line.startswith(":") else ":" + line
        key = r.key
        posting = intent_posting(r, line, session=sid)
        verb = line[1:].split(" ", 1)[0]
        if posting["status"] == "done" and (verb == "reset"
                                            or r.key != key):
            self.epochs[sid] += 1
        session = self._fields(sid)
        posting.update({"epoch": self.epochs[sid], "done_ts": _now()})
        return {"posting": posting, "session": session}

    def close_session(self, sid: str) -> dict:
        self.shells.pop(sid, None)
        self.epochs.pop(sid, None)
        return {"status": "closed", "last_ts": _now()}
