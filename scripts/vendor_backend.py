#!/usr/bin/env python3
"""Copy the slice of Statement Map's reader output that the site reads into backend/.

Statement Map is Will Cook's backend: it joins a release's paper statements,
Lean challenges, outside readings, recorded re-runs and contributions into
pinned records, and decides which theorem, pairing and evidence a reader sees,
with a receipt behind every count. The atlas renders those decisions; it does
not make them again. This script copies what the site reads:

    backend/catalog.json                     the backend's catalogue, as written
    backend/NOTICE.md                        the backend's credit and licence notices
    backend/<release>/targets.json           each object's contribution target and
                                             fingerprint, taken from objects.json
    backend/<release>/web/manifest.json      the backend's asset manifest, restricted
                                             to the packets copied here; every entry
                                             is the backend's own, byte for byte
    backend/<release>/web/<logical path>     each packet the site reads, as the
                                             backend's immutable asset bytes:
                                             family readers, the map's universe and
                                             overview, the numbers index with its
                                             receipts and member pages, and the
                                             search index with its shards
    backend/EXPORT.json                      what was exported, from which commit,
                                             runtime and generation

Run it against Statement Map's accepted output for the release whose pin
matches upstream.json:

    python3 scripts/vendor_backend.py --from ../statement-map --data ../statement-map/data-local/reader-v6

It refuses a release with another pin or schema, an asset whose bytes differ
from the manifest, and any packet from another release, pin or generation.
scripts/reader.py checks the same things again before a page uses a packet.
Standard library only.
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
SCHEMA = "statement-map-web/2"

# The packet kinds the site reads. Archival packets (full family records,
# manuscripts, Lean details, objects, navigation, the full numbers registry
# and the legacy search file) stay in Statement Map.
KINDS = ("family-reader", "universe", "overview", "numbers-index", "number-receipt",
         "number-members", "search-index", "search-shard", "search-entries")


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="src", required=True, help="a Statement Map checkout")
    ap.add_argument("--data", help="the accepted output directory (default: <checkout>/data)")
    ap.add_argument("--receipt", help="the acceptance receipt for that output "
                    "(default: the newest receipts/reader-v*-acceptance.json)")
    ap.add_argument("--release", default="openai-math")
    args = ap.parse_args()
    src = Path(args.src).resolve()
    data = Path(args.data).resolve() if args.data else src / "data"
    pin = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))["commit"]

    catalog = json.loads((data / "catalog.json").read_text(encoding="utf-8"))
    rel = next((r for r in catalog["releases"] if r["id"] == args.release), None)
    if rel is None:
        raise SystemExit(f"release {args.release} is not in the catalogue")
    if rel["pin"] != pin:
        raise SystemExit(f"release pin {rel['pin']} differs from upstream.json {pin}")
    web = rel["web"]
    if web.get("schema") != SCHEMA:
        raise SystemExit(f"the catalogue serves {web.get('schema')}; the site reads {SCHEMA}")
    generation = web["generation_id"]
    web_dir = (data / web["manifest"]).parent
    manifest = json.loads((data / web["manifest"]).read_text(encoding="utf-8"))
    ident = (SCHEMA, args.release, pin, generation)
    if tuple(manifest.get(k) for k in ("schema", "release_id", "pin", "generation_id")) != ident:
        raise SystemExit("the manifest is from another schema, release, pin or generation")

    def asset(logical: str) -> bytes:
        entry = manifest["assets"][logical]
        raw = (web_dir / entry["path"]).read_bytes()
        if len(raw) != entry["bytes"] or sha256_bytes(raw) != entry["sha256"]:
            raise SystemExit(f"{logical}: asset bytes differ from the manifest")
        return raw

    chosen = {k: v for k, v in manifest["assets"].items() if v.get("kind") in KINDS}
    missing = set(KINDS) - {v["kind"] for v in chosen.values()}
    if missing:
        raise SystemExit(f"the manifest has no {', '.join(sorted(missing))} packets")

    rel_dir = OUT / args.release
    if rel_dir.exists():
        shutil.rmtree(rel_dir)
    out_web = rel_dir / "web"
    for logical in sorted(chosen):
        raw = asset(logical)
        doc = json.loads(raw)
        if tuple(doc.get(k) for k in ("schema", "release_id", "pin", "generation_id")) != ident:
            raise SystemExit(f"{logical} is from another schema, release, pin or generation")
        dest = out_web / logical
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    sub = {k: v for k, v in manifest.items() if k != "assets"}
    sub["assets"] = dict(sorted(chosen.items()))
    sub["_vendored"] = ("Restricted by the Plectis Atlas to the packets it reads; every entry is "
                        "Statement Map's own. The full manifest has %d entries." % len(manifest["assets"]))
    (out_web / "manifest.json").write_text(json.dumps(sub, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    objects = json.loads(asset("objects.json"))
    targets = {}
    for o in objects["objects"]:
        t = o.get("contribution_target") or {}
        if t.get("id"):
            targets[o["id"]] = [t["id"], t.get("fingerprint"), t.get("grain")]
    tdoc = {"_note": ("Each object's contribution target and fingerprint, copied from Statement Map's "
                      "objects.json by scripts/vendor_backend.py. A target names the exact content a "
                      "contribution concerns; the fingerprint changes when that content changes."),
            "schema": "plectis-atlas-backend-targets/1", "release_id": args.release, "pin": pin,
            "generation_id": generation, "fields": ["target_id", "fingerprint", "grain"],
            "targets": dict(sorted(targets.items()))}
    (rel_dir / "targets.json").write_text(json.dumps(tdoc, ensure_ascii=False, separators=(",", ":")) + "\n",
                                          encoding="utf-8")
    shutil.copyfile(data / "catalog.json", OUT / "catalog.json")
    notice = src / "NOTICE.md"
    if notice.exists():
        shutil.copyfile(notice, OUT / "NOTICE.md")
    for stale in ("overview.json",):
        (OUT / args.release / stale).unlink(missing_ok=True)

    def git(*a):
        try:
            return subprocess.run(["git", "-C", str(src), *a], capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    receipts = sorted((src / "receipts").glob("reader-v*-acceptance.json"),
                      key=lambda p: int(p.name.split("-v")[1].split("-")[0]))
    receipt = Path(args.receipt).resolve() if args.receipt else (receipts[-1] if receipts else None)
    rdoc = json.loads(receipt.read_text(encoding="utf-8")) if receipt else {}
    files = {}
    for rel_path in ("catalog.json", "NOTICE.md", f"{args.release}/targets.json", f"{args.release}/web/manifest.json"):
        p = OUT / rel_path
        if p.exists():
            files[rel_path] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    export = {
        "_note": ("What backend/ holds and where it came from. scripts/reader.py checks these four files "
                  "against their hashes, every packet under web/ against the manifest, and the schema, "
                  "release, pin and generation of each packet, before a page uses it."),
        "schema": "plectis-atlas-backend-export/2",
        "backend": "Statement Map, by Will Cook (not yet published)",
        "backend_commit": git("rev-parse", "HEAD"),
        "acceptance_receipt": {"file": receipt.name if receipt else None,
                               "tested_commit": rdoc.get("tested_commit"),
                               "exporter": rdoc.get("exporter"),
                               "sha256": sha256(receipt) if receipt else None},
        "release_id": args.release,
        "pin": pin,
        "generation_id": generation,
        "reader_schema": SCHEMA,
        "packets": {"count": len(chosen), "bytes": sum(v["bytes"] for v in chosen.values()),
                    "kinds": sorted({v["kind"] for v in chosen.values()})},
        "files": files,
    }
    (OUT / "EXPORT.json").write_text(json.dumps(export, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"backend/: {len(chosen)} packets ({export['packets']['bytes'] / 1e6:.1f} MB), {len(targets)} targets, "
          f"generation {generation[:19]}, runtime {(rdoc.get('tested_commit') or '?')[:12]}")


if __name__ == "__main__":
    main()
