"""The site's one door to Statement Map's reader packets in backend/.

Statement Map, Will Cook's backend, decides what a reader of the release sees:
which theorem a family's catalogue headline points to, which paper statement a
Lean file is paired with and by what evidence, what each outside reader found,
which re-runs are accepted at the current pin, what is left to check, and every
number the site states, each with a receipt. scripts/vendor_backend.py copies
the packets the site reads into backend/<release>/web/. The atlas renders
those decisions and never makes them again.

load() checks backend/EXPORT.json's files against their hashes, and the
manifest's schema, release, pin and generation against the export and
upstream.json. packet() then checks each packet's bytes against its manifest
entry and its own schema, release, pin and generation before returning it, so
a page can never be assembled from two generations. Any mismatch stops the
build with a message (ReaderError is a SystemExit).

Ids are Statement Map's reader aliases: d:<discipline slug>, f:<family id>,
p:<manuscript slug>, r:<manuscript slug>:<TeX label or L-<file>-<line>> and
l:<Lean statement id>. They are opaque here and never rebuilt from TeX. Routes
are {path, pointer} pairs relative to the release's web/ directory; a route
into ../rows/ names a canonical row the site does not vendor.

Standard library only.
"""
from __future__ import annotations

import hashlib
import json
from functools import cached_property
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SCHEMA = "statement-map-web/2"
EXPORT_SCHEMA = "plectis-atlas-backend-export/2"
IDENTITY = ("schema", "release_id", "pin", "generation_id")


class ReaderError(SystemExit):
    """A vendored packet is missing, altered, or from another generation."""


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical_sha(doc) -> str:
    """Statement Map's logical digest: sorted keys, UTF-8, no ASCII escaping, compact."""
    return _sha(json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def pointer(doc, ptr: str | None):
    """Follow an RFC 6901 JSON Pointer ("" is the whole document)."""
    if not ptr:
        return doc
    if not ptr.startswith("/"):
        raise ReaderError(f"not a JSON Pointer: {ptr!r}")
    for part in ptr[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            doc = doc[int(part)] if isinstance(doc, list) else doc[part]
        except (KeyError, IndexError, ValueError) as e:
            raise ReaderError(f"JSON Pointer {ptr!r} does not resolve") from e
    return doc


class Reader:
    def __init__(self, root: Path = BACKEND, release: str = "openai-math", upstream_pin: str | None = None):
        self.root = Path(root)
        exp_path = self.root / "EXPORT.json"
        if not exp_path.is_file():
            raise ReaderError(f"{exp_path} is missing; run scripts/vendor_backend.py")
        export = json.loads(exp_path.read_text(encoding="utf-8"))
        if export.get("schema") != EXPORT_SCHEMA:
            raise ReaderError(f"backend/EXPORT.json is {export.get('schema')}; the site reads {EXPORT_SCHEMA}")
        for rel, meta in export["files"].items():
            p = self.root / rel
            if not p.is_file() or _sha(p.read_bytes()) != meta["sha256"]:
                raise ReaderError(f"backend/{rel} differs from backend/EXPORT.json; re-run scripts/vendor_backend.py")
        pin = upstream_pin or json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))["commit"]
        if export["release_id"] != release or export["pin"] != pin:
            raise ReaderError(f"backend/ holds {export['release_id']} at {export['pin'][:12]}, "
                              f"but the atlas reads {release} at {pin[:12]}")
        if export.get("reader_schema") != SCHEMA:
            raise ReaderError(f"backend/ holds {export.get('reader_schema')}; the site reads {SCHEMA}")
        self.export = export
        self.release_id = release
        self.pin = pin
        self.generation = export["generation_id"]
        self.commit = export.get("backend_commit")
        receipt = export.get("acceptance_receipt") or {}
        self.runtime = receipt.get("tested_commit")
        self.exporter = receipt.get("exporter")
        self.identity = (SCHEMA, release, pin, self.generation)
        self.web = self.root / release / "web"
        manifest = json.loads((self.web / "manifest.json").read_text(encoding="utf-8"))
        if tuple(manifest.get(k) for k in IDENTITY) != self.identity:
            raise ReaderError("backend manifest is from another schema, release, pin or generation")
        self.assets = manifest["assets"]
        targets = json.loads((self.root / release / "targets.json").read_text(encoding="utf-8"))
        if (targets.get("generation_id"), targets.get("pin"), targets.get("release_id")) != (self.generation, pin, release):
            raise ReaderError(f"backend/{release}/targets.json is from another generation, pin or release")
        self._targets = targets["targets"]
        self._cache: dict[str, dict] = {}

    # -- packets and routes -------------------------------------------------

    def packet(self, logical: str) -> dict:
        """One vendored packet, checked against its manifest entry and its own identity."""
        doc = self._cache.get(logical)
        if doc is not None:
            return doc
        entry = self.assets.get(logical)
        if entry is None:
            raise ReaderError(f"{logical} is not among the packets vendored in backend/")
        path = self.web / logical
        if not path.is_file():
            raise ReaderError(f"backend/{self.release_id}/web/{logical} is missing; re-run scripts/vendor_backend.py")
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or _sha(raw) != entry["sha256"]:
            raise ReaderError(f"backend/{self.release_id}/web/{logical} differs from the manifest")
        doc = json.loads(raw)
        got = tuple(doc.get(k) for k in IDENTITY)
        if got != self.identity:
            raise ReaderError(f"{logical} is from generation {str(got[3])[:19]} at pin {str(got[2])[:12]}; "
                              f"the export is generation {self.generation[:19]} at {self.pin[:12]}")
        self._cache[logical] = doc
        return doc

    def resolve(self, route):
        """Follow a route ({path, pointer} or a bare logical path) relative to web/."""
        if route is None:
            raise ReaderError("a null route has no target")
        path, ptr = (route, "") if isinstance(route, str) else (route["path"], route.get("pointer") or "")
        if path.startswith("../"):
            raise ReaderError(f"{path} is a canonical row; the site does not vendor rows")
        return pointer(self.packet(path), ptr)

    def verify_all(self) -> int:
        """Read and check every vendored packet; return how many."""
        for logical in self.assets:
            self.packet(logical)
        self._cache.clear()
        return len(self.assets)

    def browser_files(self, kinds) -> list[tuple[str, Path]]:
        """(logical path, file) for every vendored packet of these kinds, for copying into the site."""
        kinds = set(kinds)
        return [(lg, self.web / lg) for lg, a in sorted(self.assets.items()) if a.get("kind") in kinds]

    # -- the release --------------------------------------------------------

    @cached_property
    def overview(self) -> dict:
        return self.packet("overview.json")

    @cached_property
    def universe(self) -> dict:
        return self.packet("universe.json")

    @cached_property
    def numbers_index(self) -> dict:
        return self.packet("numbers-index.json")

    @cached_property
    def search_index(self) -> dict:
        return self.packet("search-index.json")

    @cached_property
    def _families(self) -> dict:
        return {f["id"]: f for f in self.overview["families"]}

    @cached_property
    def _lean(self) -> dict:
        return {l["id"]: l for l in self.overview["lean"]}

    @staticmethod
    def fid(family_id: str) -> str:
        return family_id if family_id.startswith("f:") else "f:" + family_id

    def overview_family(self, family_id: str) -> dict | None:
        """The compact overview record of a family ("159" or "f:159")."""
        return self._families.get(self.fid(family_id))

    def family_ids(self) -> list[str]:
        """Every family id, in the release's source order."""
        return [f["id"] for f in self.overview["families"]]

    def family(self, family_id: str) -> dict:
        """A family's reader packet: the backend's claim, selection, pairing, readings,
        re-runs, checks and what is left, for one family."""
        fam = self.overview_family(family_id)
        if fam is None:
            raise ReaderError(f"no family {family_id} in the overview")
        doc = self.resolve(fam["reader"])
        if doc.get("id") != fam["id"]:
            raise ReaderError(f"the reader route of {fam['id']} leads to {doc.get('id')}")
        return doc

    def lean_summary(self, lean_id: str) -> dict | None:
        """The overview's compact record of a Lean statement ("SiegelZeros" or "l:SiegelZeros")."""
        return self._lean.get(lean_id if lean_id.startswith("l:") else "l:" + lean_id)

    lean_statement = lean_summary

    def target(self, alias: str) -> dict | None:
        """An object's contribution target: {"id", "fingerprint", "grain"}."""
        t = self._targets.get(alias)
        return {"id": t[0], "fingerprint": t[1], "grain": t[2]} if t else None

    # -- numbers ------------------------------------------------------------

    def number(self, sentence_key: str) -> dict:
        """The summary behind a number the site states in a sentence: value, unit, rule,
        state and a route to its receipt. Use .get("value") with .get("state"): a value
        is None when the state is incomplete or unavailable, never zero."""
        key = self.numbers_index["sentence_keys"].get(sentence_key)
        if key is None:
            raise ReaderError(f"the numbers index has no sentence key {sentence_key!r}")
        return self.numbers_index["number_summaries"][key]

    def number_receipt(self, sentence_key: str) -> dict:
        """The complete receipt for a number: its record with every named collection
        restored from its pages, checked against the record's own digest."""
        summary = self.number(sentence_key)
        header = self.packet(summary["receipt"]["path"])
        number = dict(pointer(header, summary["receipt"].get("pointer") or "/number"))
        for name, coll in (header.get("collections") or {}).items():
            items, expect = [], 0
            for page_path in coll.get("pages") or []:
                page = self.packet(page_path)
                if page.get("start") != expect:
                    raise ReaderError(f"{page_path} starts at {page.get('start')}, expected {expect}")
                items.extend(page["items"])
                expect += len(page["items"])
            if expect != coll.get("count"):
                raise ReaderError(f"{sentence_key}: {name} has {expect} items, the header says {coll.get('count')}")
            number[name] = items
        recorded = number.pop("sha256", None)
        if recorded and canonical_sha(number) != recorded:
            raise ReaderError(f"{sentence_key}: the reconstructed receipt does not match its digest")
        number["sha256"] = recorded
        return number


_LOADED: dict = {}


def load(release: str = "openai-math") -> Reader:
    """The checked reader for a release (cached)."""
    if release not in _LOADED:
        _LOADED[release] = Reader(release=release)
    return _LOADED[release]


if __name__ == "__main__":
    r = load()
    n = r.verify_all()
    print(f"backend/: {n} packets checked; {r.release_id} at {r.pin[:12]}, generation {r.generation[:19]}, "
          f"runtime {(r.runtime or '?')[:12]} ({r.exporter})")
