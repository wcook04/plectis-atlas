#!/usr/bin/env python3
"""Ingest Thomas Bloom's list of Erdős problems addressed by the release as an atlas source.

    python3 scripts/ingest/erdos_problems.py SNAPSHOT.html [--date YYYY-MM-DD]

Bloom's post "Erdős problems in the OpenAI proofs" (https://www.erdosproblems.com/forum/thread/blog:10)
gives one section per problem (or group of problems), linking the release's manuscript and,
where one exists, its Comparator challenge. The atlas takes the problem numbers, Bloom's short
section titles and the links, maps each manuscript to its family, and credits Bloom wherever a
problem appears. The post states no licence, so its prose is linked rather than copied.

Writes curated/sources/erdos-problems.json. Standard library only.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.erdosproblems.com/forum/thread/blog:10"


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot")
    ap.add_argument("--date", default="2026-10-11")
    a = ap.parse_args()
    s = Path(a.snapshot).read_text(encoding="utf-8", errors="replace")
    ms = json.loads((ROOT / "data" / "manuscripts.json").read_text(encoding="utf-8"))
    fam_of = {m["id"]: m.get("family") for m in ms}
    heads = list(re.finditer(r"<h2[^>]*>(Problems? .*?)</h2>", s, flags=re.S))
    families: dict[str, dict] = {}
    unmapped = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(s)
        reply = s.find('class="post', h.end())  # forum replies start here; the post's own sections end before them
        if 0 <= reply < end:
            end = reply
        body = s[h.end(): end]
        nums = [int(n) for n in re.findall(r'href="/(\d+)"', h.group(1))]
        title = text(h.group(1)).split(" - ", 1)[-1] if " - " in text(h.group(1)) else None
        slugs = sorted(set(re.findall(r"github\.com/openai/math/(?:blob|tree)/[^/]+/preprints/([^/\"]+)/", body)))
        challenges = sorted(set(re.findall(r"ComparatorChallenges/([A-Za-z0-9_]+)\.lean", body)))
        fids = sorted({fam_of[sl] for sl in slugs if fam_of.get(sl)})
        if not fids:
            unmapped.append(nums)
            continue
        for fid in fids:
            entry = families.setdefault(fid, {"erdos_problems": []})
            for n in nums:
                if not any(p["number"] == n for p in entry["erdos_problems"]):
                    entry["erdos_problems"].append({"number": n, "title": title, "url": f"https://www.erdosproblems.com/{n}",
                                                    "challenges": challenges, "post": URL})
    out = {
        "schema": "atlas_source_v1",
        "source": {
            "id": "erdos-problems",
            "credit": "Thomas Bloom, erdosproblems.com",
            "name": "Erdős problems in the OpenAI proofs",
            "url": URL,
            "authors": [{"name": "Thomas Bloom"}],
            "kind": "tracker",
            "licence": "none stated",
            "reuse": "cite",
            "snapshot": a.date,
            "method": ("Bloom's post lists the Erdős problems the release makes claims about, one section per problem, with the "
                       "manuscript and any Comparator challenge. The atlas maps each manuscript to its family and links Bloom's "
                       "problem pages; his remarks are linked, not copied. The post makes no judgement about novelty or attribution."),
            "fields": {"erdos_problems": "The Erdős problems Bloom's post connects to a family, with links to each problem page."},
            "adopted": [
                {"kind": "data", "what": "The problem numbers and short titles in his list, with the manuscripts and challenges each section links (facts, cited)", "where": "family pages"},
            ],
        },
        "families": families,
    }
    dest = ROOT / "curated" / "sources" / "erdos-problems.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_problems = sum(len(v["erdos_problems"]) for v in families.values())
    print(f"wrote {dest.relative_to(ROOT)}: {len(heads)} sections, {n_problems} problem links in {len(families)} families"
          + (f"; sections with no mapped manuscript: {unmapped}" if unmapped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
