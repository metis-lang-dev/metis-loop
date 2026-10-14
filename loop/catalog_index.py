"""The CATALOG panel's index (domain-catalog s-2a2bc758 step 1): every
catalog in the metis-catalog checkout, the domains first, each with its
display line and what it has (a host, a notch, a README), so the page lists
them and opens one by one click — program + host + notch.

Until the domain manifests land (step 2: domains/<name>/domain.yaml and the
metis_catalog loader replace this module's inference), what a catalog has
is read off the checkout:

  host    the file's `#plugin SPEC`; else a `<stem>_host.py` beside it with
          a `make` (the dog's dog_host.py); else HOSTS (a host that lives
          outside the catalog today: the kitchen's, in metispy)
  notch   the file's `#notch FILE`; else `<stem>.notch.json` beside it
  readme  README.md in the catalog's own directory (domains/dog/), or in
          the directory named after it (domains/rddl/wildfire/)
  line    the README's title; else the catalog README's table row for the
          directory when the file is its only catalog; else the file's
          first `%` line; else the row

A catalog with a host, a notch or its own README is a DOMAIN (listed
first); every other .llp is listed as a plain catalog. The host spec is
the server's, read from the operator's checkout — the page names a
catalog, never a spec (metispy D4: no code is imported by the wire).
"""
import re
from pathlib import Path

# hosts that live outside the catalog today (step 2 moves them in)
HOSTS = {"domains/kitchen/kitchen": "metis.domains.kitchen.host:make"}

_PLUGIN = re.compile(r"^#plugin\s+(\S+)", re.M)
_NOTCH = re.compile(r"^#notch\s+(\S+)", re.M)
_DRAFT = re.compile(r"(^|/)(iter\d+-world|step\d|.*_born$|.*-candidate|.*LOSSY)")


def _title(readme: Path) -> str:
    for line in readme.read_text(errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _table(root: Path) -> dict:
    """The catalog README's `| `domains/x/` | what |` rows: dir -> line."""
    rows = {}
    readme = root / "README.md"
    if readme.is_file():
        for m in re.finditer(r"^\|\s*`([^`]+)/`\s*\|\s*(.+?)\s*\|\s*$", readme.read_text(errors="replace"), re.M):
            rows[m.group(1).strip("/")] = re.sub(r"\s+", " ", m.group(2))
    return rows


def _first_comment(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("%"):
            s = line.lstrip("% ").strip()
            if s and not s.startswith(("SOURCE:", "//", "/")):
                return s
        elif line.strip():
            break
    return ""


def _short(s: str, n: int = 140) -> str:
    s = re.sub(r"\*\*|`", "", s)
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def entry(root: Path, path: Path, table: dict) -> dict:
    rel = path.relative_to(root).with_suffix("").as_posix()
    text = path.read_text(errors="replace")
    host = (m.group(1) if (m := _PLUGIN.search(text)) else
            f"{path.stem}_host.py:make" if (path.parent / f"{path.stem}_host.py").is_file() else
            HOSTS.get(rel))
    notch = (m.group(1) if (m := _NOTCH.search(text)) else
             f"{path.stem}.notch.json" if (path.parent / f"{path.stem}.notch.json").is_file() else None)
    readme = next((r for r in (path.parent / path.stem / "README.md", path.parent / "README.md")
                   if r.is_file() and (r.parent.name == path.stem or len(list(r.parent.glob("*.llp"))) == 1)), None)
    row = table.get(path.parent.relative_to(root).as_posix(), "")
    alone = len(list(path.parent.glob("*.llp"))) == 1     # the dir's table row is about this file
    line = (_title(readme) if readme else "") or (row if alone else "") or _first_comment(text) or row
    domain = bool(host or notch or readme) and not _DRAFT.search(rel)
    return {"name": path.stem, "path": rel, "line": _short(line), "kind": "domain" if domain else "catalog",
            "host": host, "notch": notch, "readme": readme.relative_to(root).as_posix() if readme else None,
            "has": {"host": bool(host), "notch": bool(notch), "readme": bool(readme)}}


def index(root: Path) -> list:
    """Every .llp under the checkout: the domains first (by name), then the
    plain catalogs (by path)."""
    root = Path(root).resolve()
    table = _table(root)
    out = [entry(root, p, table) for p in sorted(root.rglob("*.llp")) if ".git" not in p.parts]
    return sorted(out, key=lambda e: (e["kind"] != "domain", e["name"] if e["kind"] == "domain" else e["path"]))


def readme_head(root: Path, rel: str, limit: int = 1600) -> str:
    """The README's opening (its title and first paragraphs, up to limit
    characters, cut at a paragraph) for the panel."""
    p = Path(root) / rel
    if not p.is_file():
        return ""
    out, n = [], 0
    for para in p.read_text(errors="replace").split("\n\n"):
        if n + len(para) > limit and out:
            break
        out.append(para)
        n += len(para) + 2
    return "\n\n".join(out)
