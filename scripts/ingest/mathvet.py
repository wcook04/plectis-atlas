#!/usr/bin/env python3
"""Ingest MathVet's fidelity review of openai/math as an atlas source.

    python3 scripts/ingest/mathvet.py PATH_TO_MATHVET_CHECKOUT

MathVet (https://math.vet, https://github.com/mathvet/mathvet, Apache License 2.0) reviews,
independently of every lab, whether each family's Comparator challenge statements state the
headline claim, and records its own machine checks of each challenge. The atlas takes its
family verdict with the review note and its per-challenge check, credits MathVet at every
point of use, and keeps MathVet's own rubric words. The data is Apache-2.0, so the verdicts
are copied; NOTICE carries the licence.

Writes curated/sources/mathvet.json. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/mathvet/mathvet"

VERDICTS = {  # MathVet's rubric (PROTOCOL.md), in plain words
    "full": "The challenge statements imply the headline claim after unpacking definitions or one routine step.",
    "partial": "Only a special case is stated, or a co-equal headline claim has no challenge statement.",
    "weaker-statement": "The challenge statements do not imply the headline claim: they state a nontrivially weaker statement.",
    "supporting-only": "The challenge statements state a lemma or auxiliary result, not the headline.",
}
CHECKS = {  # MathVet's own labels for its machine checks; its STATUS.md calls a pass "accepted"
    "comparator-sandboxed-pass": ("accepted", "Re-run through Comparator in a sandboxed virtual machine: accepted."),
    "comparator-pass": ("accepted", "Re-run through Comparator: accepted."),
    "closure-pass": ("built", "The solution was built and its dependency closure checked; Comparator was not run."),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkout")
    a = ap.parse_args()
    co = Path(a.checkout)
    commit = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    date = subprocess.run(["git", "-C", str(co), "log", "-1", "--format=%cs"], capture_output=True, text=True).stdout.strip()
    rev = co / "reviews" / "openai-math"
    status = json.loads((co / "docs" / "openai-math" / "data.json").read_text(encoding="utf-8"))["status"]
    pin = status["upstream_commit"]
    fam_rows = list(csv.DictReader((rev / "fidelity-table.csv").open(encoding="utf-8")))
    st_rows = list(csv.DictReader((rev / "challenge-status.csv").open(encoding="utf-8")))
    families = {}
    for r in fam_rows:
        v = r["verdict"]
        families[r["family"]] = {"scope_reading": {
            "verdict": v, "code": v, "text": VERDICTS.get(v), "note": r.get("review_note") or None,
            "definitions_to_check": r.get("definitions_to_check") or None,
            "url": f"{REPO}/blob/{commit}/reviews/openai-math/fidelity-table.csv"}}
    statements = {}
    for r in st_rows:
        mc = r.get("machine_check") or "none"
        if mc not in CHECKS:
            continue
        verdict, text = CHECKS[mc]
        when = (r.get("cloud_finished") or r.get("comparator_finished") or "")[:10] or None
        statements[r["challenge"]] = {"replay": {
            "verdict": verdict, "code": mc, "text": text, "date": when,
            "url": f"{REPO}/blob/{commit}/reviews/openai-math/challenge-status.csv"}}
    out = {
        "schema": "atlas_source_v1",
        "source": {
            "id": "mathvet",
            "credit": "MathVet",
            "name": "MathVet fidelity review of openai/math",
            "url": "https://math.vet",
            "repository": REPO,
            "authors": [{"name": "MathVet maintainers"}],
            "kind": "audit",
            "licence": "Apache-2.0",
            "reuse": "import",
            "snapshot": date,
            "snapshot_commit": commit,
            "upstream_commit": pin,
            "method": ("An independent, pre-referee review of each family's challenge statements against its headline "
                       "claim under a published rubric (PROTOCOL.md), with its own Comparator runs per challenge. "
                       "MathVet publishes the error rate of its own verdicts."),
            "counts": {"families": {k: sum(1 for r in fam_rows if r["verdict"] == k) for k in VERDICTS},
                       "challenges_checked": len(statements)},
            "fields": {
                "scope_reading": "Per family: MathVet's verdict on whether the challenge statements state the headline claim, with its review note.",
                "replay": "Per challenge: MathVet's own machine check.",
            },
            "adopted": [
                {"kind": "data", "what": "Its verdict and review note for each of the 242 families with Lean", "where": "the readings of the scope on family pages"},
                {"kind": "data", "what": "Its Comparator check for each challenge it ran", "where": "the Independent replay line on statement pages"},
                {"kind": "idea", "what": "A published rubric with a stated error rate for statement-fidelity verdicts", "where": "the about and numbers pages"},
            ],
        },
        "statements": statements,
        "families": families,
    }
    dest = ROOT / "curated" / "sources" / "mathvet.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)}: {len(statements)} statements, {len(families)} families, read at {commit[:12]} for release {pin[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
