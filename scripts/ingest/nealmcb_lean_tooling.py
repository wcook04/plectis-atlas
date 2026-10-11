#!/usr/bin/env python3
"""Ingest Neal McBurnett's Comparator runs of openai/math as an atlas source.

    python3 scripts/ingest/nealmcb_lean_tooling.py PATH_TO_OPENAI_MATH_LEAN_TOOLING_CHECKOUT

openai-math-lean-tooling (https://github.com/nealmcb/openai-math-lean-tooling, MIT licence)
builds each challenge's solution and runs Comparator on it at the release's pinned commit,
recording the verdict, the check time and the peak memory (results/cmp-all/configs.csv; the
toolchain is pinned in MANIFEST.txt). The atlas takes each finished verdict per statement,
credits the run where it appears, and skips configurations still pending in the snapshot.
The data is MIT licensed, so the verdicts are copied; NOTICE carries the licence.

Writes curated/sources/nealmcb-lean-tooling.json. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/nealmcb/openai-math-lean-tooling"


def num(x: str):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkout")
    a = ap.parse_args()
    co = Path(a.checkout)
    commit = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    date = subprocess.run(["git", "-C", str(co), "log", "-1", "--format=%cs"], capture_output=True, text=True).stdout.strip()
    manifest = (co / "MANIFEST.txt").read_text(encoding="utf-8")
    pin = re.search(r"openai/math:\s*([0-9a-f]{40})", manifest)
    if not pin:
        sys.exit("MANIFEST.txt does not name the openai/math commit")
    toolchain = re.search(r"lean toolchain:\s*(\S+)", manifest)
    rows = list(csv.DictReader((co / "results" / "cmp-all" / "configs.csv").open(encoding="utf-8")))
    url = f"{REPO}/blob/{commit}/results/cmp-all/configs.csv"
    statements = {}
    pending = 0
    for r in rows:
        if r["status"] != "accepted":
            pending += 1
            continue
        secs, gib = num(r.get("check_wall_s")), num(r.get("check_peak_rss_gib"))
        extra = []
        if secs is not None:
            extra.append(f"the check took {secs:.0f} s")
        if gib is not None:
            extra.append(f"peak memory {gib:.1f} GiB")
        kernel = "with the nanoda kernel as well as Lean's" if r.get("nanoda") == "True" else "with Lean's kernel"
        statements[r["config"]] = {"replay": {
            "verdict": "accepted", "code": r["status"],
            "text": f"Re-run through Comparator {kernel}: accepted" + (f" ({'; '.join(extra)})." if extra else "."),
            "date": (r.get("started") or "")[:10] or None, "url": url}}
    out = {
        "schema": "atlas_source_v1",
        "source": {
            "id": "nealmcb-lean-tooling",
            "credit": "Neal McBurnett, openai-math-lean-tooling",
            "name": "Comparator runs of openai/math with build and memory measurements",
            "url": REPO,
            "repository": REPO,
            "authors": [{"name": "Neal McBurnett", "handle": "nealmcb"}],
            "kind": "replay",
            "licence": "MIT",
            "reuse": "import",
            "snapshot": date,
            "snapshot_commit": commit,
            "upstream_commit": pin.group(1),
            "method": ("Each challenge's solution is built and checked by Comparator at the pinned release, on Lean "
                       + (toolchain.group(1) if toolchain else "the release's toolchain")
                       + ", recording the verdict, the check time and the peak memory; the run was still in progress "
                       f"at this snapshot ({len(statements)} accepted, {pending} pending)."),
            "counts": {"accepted": len(statements), "pending": pending},
            "fields": {"replay": "Per challenge: its Comparator verdict, check time and peak memory in this run."},
            "adopted": [
                {"kind": "data", "what": "Its Comparator verdict for each challenge it has finished, with the check time and peak memory",
                 "where": "the Independent replay line on statement pages"},
            ],
        },
        "statements": statements,
    }
    dest = ROOT / "curated" / "sources" / "nealmcb-lean-tooling.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)}: {len(statements)} accepted, {pending} pending, read at {commit[:12]} "
          f"for release {pin.group(1)[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
