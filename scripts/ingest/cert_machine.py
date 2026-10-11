#!/usr/bin/env python3
"""Ingest Carlos Toledo's cert-machine audit of openai/math as an atlas source.

    python3 scripts/ingest/cert_machine.py PATH_TO_CERT_MACHINE_CHECKOUT

cert-machine (https://github.com/carlostoledo1891/cert-machine, MIT licence) re-ran every
Comparator challenge of the release with the independent nanoda kernel switched on
(certs/openai-math-kernel.json, its "lane K") and read every family's challenge statements
against the headline OpenAI wrote for it (certs/openai-math-statements.json, "lane S").
The atlas takes its verdicts per statement and per family, keeps its own words and codes
beside a plain sentence, and credits the audit at every point of use. The data is MIT
licensed, so the verdicts are copied; NOTICE carries the licence.

Writes curated/sources/cert-machine.json. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/carlostoledo1891/cert-machine"

STATEMENT_WORDS = {
    "MATCHES": ("matches", "The challenge statements state the headline as OpenAI wrote it."),
    "NARROWER — DECLARED": ("narrower-declared", "The challenge statements state less than the headline, and OpenAI's Lean note says so."),
    "NARROWER — UNDECLARED": ("narrower-undeclared", "The challenge statements state less than the headline, and OpenAI's Lean note does not say so."),
    "NARROWER — UNLINKED": ("narrower-unlinked", "The challenge statements state less than the headline; the missing part comes from a paper the Lean note does not link."),
    "DIFFERENT": ("different", "The challenge statements state a different theorem from the headline."),
    "SUPPORT-ONLY": ("supporting-only", "The challenge statements state only supporting results."),
}


def kernel_reading(row: dict, commit: str) -> dict:
    last = (row.get("runs") or [{}])[-1]
    kernels = last.get("kernels") or []
    if row["word"] == "CERTIFIED":
        text = "Re-run through Comparator with the independent nanoda kernel switched on: Lean's kernel and nanoda both accept OpenAI's solution."
        verdict = "accepted"
    else:
        lean_ok = any("Lean default kernel accepts" in k for k in kernels)
        why = (row.get("why") or "").split(" | ")[0]
        text = ("Re-run through Comparator did not reach a verdict"
                + (" (Lean's default kernel accepts the solution; the nanoda replay stopped: " if lean_ok else " (")
                + why + ").")
        verdict = "not-decided"
    out = {"verdict": verdict, "code": row["word"], "text": text, "date": (last.get("at") or "")[:10] or None,
           "url": f"{REPO}/blob/{commit}/certs/openai-math-kernel.json"}
    if row.get("strict") or row.get("transfer") or row.get("displayed"):
        held = row.get("displayed") or {}
        word = held.get("word")
        if word == "PROVED":
            htext = "With the definition holes held to the displayed definitions, the solution proves the displayed statement."
        elif word == "OPEN":
            htext = "With the definition holes held fixed, neither the strict re-run nor the transfer check settles whether the solution proves the displayed statement."
        else:
            htext = None
        out["holes"] = {"code": word, "strict": (row.get("strict") or {}).get("word"),
                        "transfer": (row.get("transfer") or {}).get("word"), "text": htext,
                        "constants": (row.get("strict") or {}).get("constants") or []}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkout")
    a = ap.parse_args()
    co = Path(a.checkout)
    commit = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    date = subprocess.run(["git", "-C", str(co), "log", "-1", "--format=%cs"], capture_output=True, text=True).stdout.strip()
    k = json.loads((co / "certs" / "openai-math-kernel.json").read_text(encoding="utf-8"))
    s = json.loads((co / "certs" / "openai-math-statements.json").read_text(encoding="utf-8"))
    pin = k["release"]["commit"]
    if s.get("release") != pin:
        sys.exit(f"the two ledgers read different releases: {pin} and {s.get('release')}")
    statements = {r["challenge"]: {"replay": kernel_reading(r, commit)} for r in k["rows"]}
    families = {}
    for r in s["rows"]:
        word = r.get("word")
        code, text = STATEMENT_WORDS.get(word, (word, None))
        families[r["family"]] = {"scope_reading": {
            "verdict": code, "code": word, "text": text, "gap": r.get("gap"),
            "openai_note_on_gap": r.get("scopeNoteOnGap"), "confidence": r.get("confidence"),
            "second_reading": r.get("secondWord"), "disagreement": r.get("disagreement"),
            "url": f"{REPO}/blob/{commit}/certs/openai-math-statements.json"}}
    out = {
        "schema": "atlas_source_v1",
        "source": {
            "id": "cert-machine",
            "credit": "Carlos Toledo, cert-machine",
            "name": "cert-machine audit of openai/math",
            "url": "https://carlostoledo.co/reports/openai-math.html",
            "repository": REPO,
            "authors": [{"name": "Carlos Toledo", "handle": "carlostoledo1891"}],
            "kind": "audit",
            "licence": "MIT",
            "reuse": "import",
            "snapshot": date,
            "snapshot_commit": commit,
            "upstream_commit": pin,
            "method": ("Every Comparator challenge re-run on Linux with nanoda switched on, decided by a preregistered "
                       "rule; every family's challenge statements read against OpenAI's headline, clause by clause. "
                       "Decider: " + k.get("decider", "")[:240]),
            "counts": {"kernel": k.get("counts", {}).get("words"), "statements": s.get("counts", {}).get("words")},
            "fields": {
                "replay": "Per challenge: the audit's Comparator re-run with both kernels, and for files with definition holes whether the displayed statement is proved.",
                "scope_reading": "Per family: whether the challenge statements state OpenAI's headline, with the gap and whether OpenAI's Lean note declares it.",
            },
            "adopted": [
                {"kind": "data", "what": "Its re-run verdict for each of the 416 challenges, with the held-definition checks for the ten files with definition holes", "where": "the Independent replay line on statement pages"},
                {"kind": "data", "what": "Its reading of each of the 242 families against OpenAI's headline, with the gap and whether OpenAI's note declares it", "where": "the readings of the scope on family pages"},
                {"kind": "idea", "what": "Telling apart a gap OpenAI's note declares from one it does not", "where": "family pages"},
            ],
        },
        "statements": statements,
        "families": families,
    }
    dest = ROOT / "curated" / "sources" / "cert-machine.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)}: {len(statements)} statements, {len(families)} families, read at {commit[:12]} for release {pin[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
