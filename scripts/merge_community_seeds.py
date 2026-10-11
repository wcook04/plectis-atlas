#!/usr/bin/env python3
"""Merge research seed files into curated/community.json for review.

    python3 scripts/merge_community_seeds.py SEED.json [SEED.json ...] [--write]

Each seed has the community_v1 shape (`efforts`, `findings`). Efforts merge on
`id`, then on URL; findings merge on URL plus family plus statement. Existing
curated rows win, so a reviewed row is never overwritten by a seed. Without
--write the merged result is printed as a summary only. Run
curated/check_community.py afterwards. Standard library only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "curated" / "community.json"


def norm_url(u: str) -> str:
    return (u or "").strip().rstrip("/").replace("http://", "https://").lower()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    cur = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"schema": "community_v1", "efforts": [], "findings": []}
    by_id = {e["id"]: e for e in cur["efforts"]}
    by_url = {norm_url(e["url"]): e["id"] for e in cur["efforts"]}
    seen_f = {(norm_url(f["url"]), f.get("family"), f.get("statement")) for f in cur["findings"]}
    added_e = added_f = 0
    for path in args:
        seed = json.loads(Path(path).read_text(encoding="utf-8"))
        remap = {}
        for e in seed.get("efforts", []):
            key = norm_url(e.get("url", ""))
            if e.get("id") in by_id:
                remap[e["id"]] = e["id"]
                continue
            if key and key in by_url:
                remap[e["id"]] = by_url[key]
                continue
            e.setdefault("families", [])
            e.setdefault("statements", [])
            e["source_seed"] = Path(path).name
            cur["efforts"].append(e)
            by_id[e["id"]] = e
            by_url[key] = e["id"]
            remap[e["id"]] = e["id"]
            added_e += 1
        for f in seed.get("findings", []):
            f["effort"] = remap.get(f.get("effort"), f.get("effort"))
            key = (norm_url(f.get("url", "")), f.get("family"), f.get("statement"))
            if key in seen_f:
                continue
            f["source_seed"] = Path(path).name
            cur["findings"].append(f)
            seen_f.add(key)
            added_f += 1
    cur["efforts"].sort(key=lambda e: (e.get("kind", ""), e.get("date", ""), e["id"]))
    cur["findings"].sort(key=lambda f: (f.get("family", ""), f.get("statement") or "", f.get("date", "")))
    print(f"merged: +{added_e} efforts, +{added_f} findings; now {len(cur['efforts'])} efforts, {len(cur['findings'])} findings")
    if write:
        OUT.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
