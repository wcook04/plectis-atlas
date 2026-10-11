#!/usr/bin/env python3
"""Ingest the "OpenAI Math Tier List" (a public Claude artifact) as an atlas source.

    python3 scripts/ingest/tier_list.py SNAPSHOT.html [--date YYYY-MM-DD]

The page embeds one JSON row per result family (id, field, type, tier, lean,
papers, and prose fields). The atlas takes the page's own judgements and counts
(result type, significance tier, its count of Lean formalisations) and credits
them to the page at every point of use. The page states no licence, so its
prose (plain-language summaries and history notes) is linked rather than copied.

Writes curated/sources/tier-list.json. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://claude.ai/artifact/JSqNXXfsvRntB6cqoEENaN"
TYPES = {"P": "proof", "C": "counterexample", "A": "algorithm", "K": "construction"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot")
    ap.add_argument("--date", default="2026-10-11")
    a = ap.parse_args()
    html = Path(a.snapshot).read_text(encoding="utf-8", errors="replace")
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S)
    rows = next((json.loads(s) for s in scripts if s.lstrip().startswith('[{"id"')), None)
    if rows is None:
        sys.exit("no embedded family rows found in the snapshot")
    code = next((s for s in scripts if "const TIERS" in s), "")
    tiers = {int(n): name for n, name in re.findall(r"\{\s*n:\s*(\d+),\s*name:\s*(?:'([^']*)'|\"[^\"]*\")", code) if name}
    for n, name in re.findall(r'\{\s*n:\s*(\d+),\s*name:\s*"([^"]*)"', code):
        tiers[int(n)] = name
    families = {}
    for r in rows:
        families[r["id"]] = {
            "type": TYPES.get(r.get("type"), r.get("type")),
            "also": TYPES.get(r.get("also")) if r.get("also") else None,
            "tier": r.get("tier"),
            "lean_formalisations": r.get("lean"),
        }
    out = {
        "schema": "atlas_source_v1",
        "source": {
            "id": "tier-list",
            "name": "OpenAI Math Tier List",
            "url": URL,
            "authors": [{"name": "Author not stated (public Claude artifact)"}],
            "kind": "tier-list",
            "licence": "none stated",
            "reuse": "cite",
            "snapshot": a.date,
            "method": "The page's own judgements and counts, cited with credit; its prose is linked rather than copied. The page says its tiers assume each claim is correct as stated and that nothing on it is verified.",
            "fields": {
                "type": "Proof, counterexample, algorithm or construction, as the page classifies each family.",
                "tier": "How significant the page judges the result would be if it holds up, from 0 (highest) to 7.",
                "lean_formalisations": "The page's count of Lean formalisations per family.",
            },
            "tier_names": {str(k): v for k, v in sorted(tiers.items())},
        },
        "families": families,
    }
    dest = ROOT / "curated" / "sources" / "tier-list.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)}: {len(families)} families, {len(tiers)} tier names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
