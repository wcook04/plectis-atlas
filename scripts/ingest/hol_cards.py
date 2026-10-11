#!/usr/bin/env python3
"""Ingest Ben Knill's HOL Light proof cards for openai/math as an atlas source.

    python3 scripts/ingest/hol_cards.py PATH_TO_OPENAI_MATH_HOL_CARDS_CHECKOUT

openai-math-hol-cards (https://github.com/BenKnill/openai-math-hol-cards) checks selected
steps of eleven families in HOL Light, a proof assistant independent of Lean, each with
negative controls that must fail. Its README table says, per card, what HOL certifies and
how that relates to the release's Lean. The author states that no card proves a headline
theorem of the release. Code is MIT licensed and explanatory prose CC BY 4.0, so the
atlas quotes each card's two sentences with attribution and links the card.

The cards were first compared at release commit adc7f124; on 8 October the author updated
the table for fd4aeeb2, the atlas's pin, which is the commit recorded here.

Writes curated/sources/hol-cards.json. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/BenKnill/openai-math-hol-cards"
PIN = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"


def cells(line: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [p.strip().replace("\\|", "|") for p in parts]


def plain(md: str) -> str:
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    md = md.replace("`", "")
    return re.sub(r"\s+", " ", md).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkout")
    a = ap.parse_args()
    co = Path(a.checkout)
    commit = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    date = subprocess.run(["git", "-C", str(co), "log", "-1", "--format=%cs"], capture_output=True, text=True).stdout.strip()
    readme = (co / "README.md").read_text(encoding="utf-8")
    if PIN not in readme:
        sys.exit(f"the README no longer mentions {PIN[:8]}; check which release its table describes")
    lines = readme.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| Card | Family | What HOL certifies"))
    families: dict[str, dict] = {}
    for l in lines[start + 2:]:
        if not l.startswith("|"):
            break
        c = cells(l)
        if len(c) < 7:
            continue
        link = re.search(r"\[([^\]]+)\]\(([^)]+)\)", c[0])
        card, path = (link.group(1), link.group(2)) if link else (plain(c[0]), "")
        fam = re.match(r"\s*(\d{3})", c[1])
        if not fam:
            continue
        families.setdefault(fam.group(1), {"hol_checks": []})["hol_checks"].append({
            "card": card,
            "certifies": plain(c[2]),
            "relation": plain(c[3]),
            "warm": plain(c[5]), "cold": plain(c[6]),
            "url": f"{REPO}/blob/{commit}/{path}" if path else REPO,
        })
    out = {
        "schema": "atlas_source_v1",
        "source": {
            "id": "hol-cards",
            "credit": "Ben Knill, openai-math-hol-cards",
            "name": "HOL Light proof cards for openai/math",
            "url": REPO,
            "repository": REPO,
            "authors": [{"name": "Ben Knill", "handle": "BenKnill"}],
            "kind": "replay",
            "licence": "MIT (code); CC BY 4.0 (explanatory prose)",
            "reuse": "import",
            "snapshot": date,
            "snapshot_commit": commit,
            "upstream_commit": PIN,
            "method": ("Selected steps of eleven families proved again in HOL Light, independently of Lean, each card "
                       "with negative controls that must fail; warm and cold runs recorded on 8 October. The author "
                       "states that no card proves a headline theorem of the release. Compared first at release commit "
                       "adc7f124 and updated by the author for fd4aeeb2."),
            "counts": {"cards": sum(len(v["hol_checks"]) for v in families.values()), "families": len(families)},
            "fields": {"hol_checks": "Per family: what each HOL Light card certifies and how it relates to the release's Lean, in the author's words."},
            "adopted": [
                {"kind": "data", "what": "What each card certifies and its relation to the release's Lean, quoted under CC BY 4.0",
                 "where": "family pages, under checks in another proof assistant"},
            ],
        },
        "families": families,
    }
    dest = ROOT / "curated" / "sources" / "hol-cards.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)}: {out['source']['counts']['cards']} cards in {len(families)} families, read at {commit[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
