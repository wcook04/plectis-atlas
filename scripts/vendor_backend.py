#!/usr/bin/env python3
"""Copy the slice of Statement Map's output that the site reads into backend/.

Statement Map is Will Cook's backend: it joins a release's paper statements,
Lean challenges, outside readings, recorded re-runs and contributions into
pinned records with a receipt behind every count. The site reads three things
from it:

    backend/catalog.json                       the backend's catalogue, as written
    backend/<release>/overview.json            every family's and Lean statement's
                                               evidence, with receipts, as written
    backend/<release>/targets.json             each object's contribution target and
                                               fingerprint, taken from objects.json
    backend/EXPORT.json                        what was exported, from which commit
                                               and generation, with every file's sha256

Run it against a Statement Map checkout whose release pin matches upstream.json:

    python3 scripts/vendor_backend.py --from ../statement-map

It refuses a release whose pin differs from the atlas's, or whose files carry
different generations. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="src", required=True, help="a Statement Map checkout")
    ap.add_argument("--release", default="openai-math")
    args = ap.parse_args()
    src = Path(args.src).resolve()
    data = src / "data"
    pin = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))["commit"]

    catalog = json.loads((data / "catalog.json").read_text(encoding="utf-8"))
    rel = next((r for r in catalog["releases"] if r["id"] == args.release), None)
    if rel is None:
        raise SystemExit(f"release {args.release} is not in the catalogue")
    if rel["pin"] != pin:
        raise SystemExit(f"release pin {rel['pin']} differs from upstream.json {pin}")
    web = rel["web"]
    generation = web["generation_id"]
    overview_path = data / web["overview"]
    objects_path = overview_path.parent / "objects.json"
    overview = json.loads(overview_path.read_text(encoding="utf-8"))
    objects = json.loads(objects_path.read_text(encoding="utf-8"))
    for name, doc in (("overview", overview), ("objects", objects)):
        if doc.get("generation_id") != generation or doc.get("pin") != pin or doc.get("release_id") != args.release:
            raise SystemExit(f"{name}.json does not match the catalogue's generation, pin or release")

    targets = {}
    for o in objects["objects"]:
        t = o.get("contribution_target") or {}
        if t.get("id"):
            targets[o["id"]] = [t["id"], t.get("fingerprint"), t.get("grain")]

    rel_dir = OUT / args.release
    rel_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(data / "catalog.json", OUT / "catalog.json")
    shutil.copyfile(overview_path, rel_dir / "overview.json")
    tdoc = {"_note": ("Each object's contribution target and fingerprint, copied from Statement Map's "
                      "objects.json by scripts/vendor_backend.py. A target names the exact content a "
                      "contribution concerns; the fingerprint changes when that content changes."),
            "schema": "plectis-atlas-backend-targets/1", "release_id": args.release, "pin": pin,
            "generation_id": generation, "fields": ["target_id", "fingerprint", "grain"],
            "targets": dict(sorted(targets.items()))}
    (rel_dir / "targets.json").write_text(json.dumps(tdoc, ensure_ascii=False, separators=(",", ":")) + "\n",
                                          encoding="utf-8")
    notice = src / "NOTICE.md"
    if notice.exists():
        shutil.copyfile(notice, OUT / "NOTICE.md")

    def git(*a):
        try:
            return subprocess.run(["git", "-C", str(src), *a], capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    receipt = src / "receipts" / "acceptance.json"
    rdoc = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {}
    files = {}
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "EXPORT.json":
            files[str(p.relative_to(OUT))] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    export = {
        "_note": ("What backend/ holds and where it came from. scripts/backend.py checks every file "
                  "against these hashes, and the release, pin and generation, before a page uses it."),
        "schema": "plectis-atlas-backend-export/1",
        "backend": "Statement Map, by Will Cook (not yet published)",
        "backend_commit": git("rev-parse", "HEAD"),
        "acceptance_receipt": {"tested_commit": rdoc.get("tested_commit"),
                               "sha256": sha256(receipt) if receipt.exists() else None},
        "release_id": args.release,
        "pin": pin,
        "generation_id": generation,
        "reader_schema": web.get("schema"),
        "files": files,
    }
    (OUT / "EXPORT.json").write_text(json.dumps(export, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"backend/: {len(targets)} targets, overview {len(overview['families'])} families and "
          f"{len(overview['lean'])} Lean statements, generation {generation[:19]}")


if __name__ == "__main__":
    main()
