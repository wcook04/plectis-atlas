"""The site's one door to Statement Map's export in backend/.

Statement Map, Will Cook's backend, joins the release's paper statements, Lean
challenges, outside readings, recorded re-runs and contributions into pinned
records with a receipt behind every count. scripts/vendor_backend.py copies the
slice the site reads into backend/ and pins it in backend/EXPORT.json.

load() checks every file against its recorded sha256, and the release, pin and
generation of each file against the export and upstream.json, so that a page
never mixes two generations or two pins. It returns None when backend/ is
absent; the site then builds from the atlas's own data alone. It raises
SystemExit when backend/ is present but inconsistent.

Ids are Statement Map's reader aliases: d:<discipline slug>, f:<family id>,
p:<manuscript slug>, r:<manuscript slug>:<TeX label or L-<file>-<line>> and
l:<Lean statement id>. They are opaque here and never rebuilt from TeX.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


class Backend:
    def __init__(self, export: dict, overview: dict, targets: dict):
        self.release_id = export["release_id"]
        self.pin = export["pin"]
        self.generation = export["generation_id"]
        self.commit = export.get("backend_commit")
        self.overview = overview
        self.families = {f["id"]: f for f in overview["families"]}
        self.lean = {l["id"]: l for l in overview["lean"]}
        self._targets = targets["targets"]

    def family(self, fid: str) -> dict | None:
        """The overview record of family `fid` ("159" or "f:159")."""
        return self.families.get(fid if fid.startswith("f:") else "f:" + fid)

    def lean_statement(self, sid: str) -> dict | None:
        return self.lean.get(sid if sid.startswith("l:") else "l:" + sid)

    def target(self, alias: str) -> dict | None:
        """The contribution target of an object: {"id", "fingerprint", "grain"}."""
        t = self._targets.get(alias)
        return {"id": t[0], "fingerprint": t[1], "grain": t[2]} if t else None


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


_LOADED: dict = {}


def load(release: str = "openai-math") -> Backend | None:
    if release in _LOADED:
        return _LOADED[release]
    exp_path = BACKEND / "EXPORT.json"
    if not exp_path.exists():
        _LOADED[release] = None
        return None
    export = json.loads(exp_path.read_text(encoding="utf-8"))
    for rel, meta in export["files"].items():
        p = BACKEND / rel
        if not p.is_file() or _sha(p) != meta["sha256"]:
            raise SystemExit(f"backend/{rel} differs from backend/EXPORT.json; re-run scripts/vendor_backend.py")
    pin = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))["commit"]
    if export["release_id"] != release or export["pin"] != pin:
        raise SystemExit(f"backend/ holds {export['release_id']} at {export['pin'][:12]}, "
                         f"but the atlas reads {release} at {pin[:12]}")
    overview = json.loads((BACKEND / release / "overview.json").read_text(encoding="utf-8"))
    targets = json.loads((BACKEND / release / "targets.json").read_text(encoding="utf-8"))
    for name, doc in (("overview", overview), ("targets", targets)):
        if (doc.get("generation_id"), doc.get("pin"), doc.get("release_id")) != (export["generation_id"], pin, release):
            raise SystemExit(f"backend/{release}/{name}.json is from another generation, pin or release")
    _LOADED[release] = Backend(export, overview, targets)
    return _LOADED[release]
