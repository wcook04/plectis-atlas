#!/usr/bin/env python3
"""Curate a research seed before it is merged into curated/community.json.

    python3 scripts/curate_community_seed.py SEED_IN SEED_OUT RULES.json

RULES.json:
  drop_effort_url_substrings  efforts (and their findings) whose URL contains any of these are
                              dropped: typically work the atlas already holds as a source in
                              curated/sources/, so it is not shown twice
  drop_finding_rules          [{"family": "NNN" or "*", "any_substring": [...]}], matched
                              against each finding's summary
  reclassify                  [{"summary_prefix": ..., "to": kind}]

A seed finding is also dropped when curated/community.json already holds a finding from the
same effort URL, family and kind that names a statement, since the seed's family-level copy
would repeat it. Prints what was dropped and why; run scripts/merge_community_seeds.py on the
output afterwards. Standard library only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def norm(u: str) -> str:
    return (u or "").strip().rstrip("/").replace("http://", "https://").lower()


def main() -> int:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    seed_in, seed_out, rules_path = map(Path, sys.argv[1:4])
    seed = json.loads(seed_in.read_text(encoding="utf-8"))
    cur = json.loads((ROOT / "curated" / "community.json").read_text(encoding="utf-8"))
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    drop_eff = {e["id"] for e in seed["efforts"] if any(s in e.get("url", "") for s in rules.get("drop_effort_url_substrings", []))}
    cur_url = {e["id"]: norm(e["url"]) for e in cur["efforts"]}
    seed_url = {e["id"]: norm(e["url"]) for e in seed["efforts"]}
    have = {(cur_url.get(f["effort"]), f["family"], f["kind"]) for f in cur["findings"] if f.get("statement")}
    stats = {"efforts_dropped": 0, "findings_dropped_source": 0, "findings_dropped_rule": 0,
             "findings_dropped_duplicate": 0, "reclassified": 0}
    findings = []
    for f in seed["findings"]:
        s = f.get("summary") or ""
        url = seed_url.get(f["effort"]) or cur_url.get(f["effort"]) or ""
        if f["effort"] in drop_eff or any(x in url for x in rules.get("drop_effort_url_substrings", [])):
            stats["findings_dropped_source"] += 1
            continue
        if any(r["family"] in ("*", f.get("family")) and any(x in s for x in r["any_substring"])
               for r in rules.get("drop_finding_rules", [])):
            stats["findings_dropped_rule"] += 1
            continue
        if not f.get("statement") and (url and (norm(url), f["family"], f["kind"]) in have):
            stats["findings_dropped_duplicate"] += 1
            continue
        for r in rules.get("reclassify", []):
            if s.startswith(r["summary_prefix"]) and f["kind"] != r["to"]:
                f["kind"] = r["to"]
                stats["reclassified"] += 1
        findings.append(f)
    efforts = [e for e in seed["efforts"] if e["id"] not in drop_eff]
    stats["efforts_dropped"] = len(seed["efforts"]) - len(efforts)
    seed_out.write_text(json.dumps({"efforts": efforts, "findings": findings}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    stats["efforts_out"], stats["findings_out"] = len(efforts), len(findings)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
