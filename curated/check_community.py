#!/usr/bin/env python3
"""Validate curated/community.json: everyone else's public work on the release, credited.

The file has two lists. `efforts` are projects, papers, posts, threads and
organisations; `findings` are concrete things an effort found or built about a
specific result (a replay, a reported error, a follow-up theorem, an
explanation, substantive commentary), each attached to a family and optionally
to a Lean statement. Every row names its authors and links its source.

    python3 curated/check_community.py            # validate, exit 1 on failure
    python3 curated/check_community.py --self-test

Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "curated" / "community.json"

EFFORT_KINDS = {"atlas", "explorer", "map", "tracker", "audit", "replay", "follow-up", "commentary",
                "explanation", "tier-list", "tooling", "analysis", "paper", "post", "thread", "press",
                "institution"}
FINDING_KINDS = {"replay-pass", "replay-fail", "error-reported", "correction", "follow-up-result",
                 "explanation", "commentary"}
REUSE = {"link", "cite", "import", "adopt"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https?://\S+$")
GENDERED = re.compile(r"\b(he|she|his|her|hers|him|himself|herself)\b", re.I)
# A summary cut off at a length limit ends on a word that cannot end a sentence.
TRUNCATED = re.compile(r"\b(and|or|then|but|with|of|to|the|a|an|in|on|for|by|as|that|which|while|because)\.\s*$", re.I)


def load_ids():
    fam = {f["id"] for f in json.loads((ROOT / "data" / "families.json").read_text(encoding="utf-8"))}
    st = {s["id"] for s in json.loads((ROOT / "data" / "statements.json").read_text(encoding="utf-8"))}
    return fam, st


def check(doc: dict, families: set, statements: set) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != "community_v1":
        errs.append("schema must be community_v1")
    efforts = doc.get("efforts", [])
    ids = set()
    for i, e in enumerate(efforts):
        where = f"efforts[{i}] {e.get('id', '?')}"
        for k in ("id", "name", "url", "kind", "authors", "licence", "date", "summary", "reuse"):
            if not e.get(k):
                errs.append(f"{where}: missing {k}")
        if e.get("id") in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(e.get("id"))
        if e.get("kind") and e["kind"] not in EFFORT_KINDS:
            errs.append(f"{where}: kind {e['kind']!r} not in {sorted(EFFORT_KINDS)}")
        if e.get("reuse") and e["reuse"] not in REUSE:
            errs.append(f"{where}: reuse {e['reuse']!r} not in {sorted(REUSE)}")
        if e.get("url") and not URL.match(e["url"]):
            errs.append(f"{where}: url is not http(s)")
        if e.get("date") and not DATE.match(e["date"]):
            errs.append(f"{where}: date must be YYYY-MM-DD")
        if e.get("reuse") == "import" and e.get("licence", "").lower() in ("", "none stated", "n/a", "unknown"):
            errs.append(f"{where}: reuse import needs a licence that allows it")
        for a in e.get("authors") or []:
            if not (a.get("name") or a.get("handle")):
                errs.append(f"{where}: an author has neither name nor handle")
        for f in e.get("families") or []:
            if f not in families and f != "release":
                errs.append(f"{where}: unknown family {f!r}")
        for s in e.get("statements") or []:
            if s not in statements:
                errs.append(f"{where}: unknown statement {s!r}")
        if "\N{EM DASH}" in (e.get("summary") or ""):
            errs.append(f"{where}: summary contains an em dash")
        if GENDERED.search(e.get("summary") or ""):
            errs.append(f"{where}: summary uses a gendered pronoun; a name does not tell anyone's pronouns, so write they/them or the name")
        if TRUNCATED.search(e.get("summary") or ""):
            errs.append(f"{where}: summary stops mid-sentence")
        for j, a in enumerate(e.get("adopted") or []):
            w2 = f"{where} adopted[{j}]"
            if a.get("kind") not in ("idea", "code", "data"):
                errs.append(f"{w2}: kind must be idea, code or data")
            if not a.get("what") or not a.get("where"):
                errs.append(f"{w2}: needs what and where")
            if a.get("kind") in ("code", "data") and (e.get("licence") or "").lower() in ("", "none stated", "n/a", "unknown", "noassertion"):
                errs.append(f"{w2}: copying {a.get('kind')} needs a licence that allows it; re-implement the idea and record kind idea")
    for i, f in enumerate(doc.get("findings", [])):
        where = f"findings[{i}]"
        for k in ("effort", "family", "kind", "summary", "url", "date"):
            if not f.get(k):
                errs.append(f"{where}: missing {k}")
        if f.get("effort") and f["effort"] not in ids:
            errs.append(f"{where}: effort {f['effort']!r} is not in efforts")
        if f.get("kind") and f["kind"] not in FINDING_KINDS:
            errs.append(f"{where}: kind {f['kind']!r} not in {sorted(FINDING_KINDS)}")
        if f.get("family") and f["family"] not in families and f["family"] != "release":
            errs.append(f"{where}: unknown family {f['family']!r}")
        if f.get("statement") and f["statement"] not in statements:
            errs.append(f"{where}: unknown statement {f['statement']!r}")
        if f.get("url") and not URL.match(f["url"]):
            errs.append(f"{where}: url is not http(s)")
        if f.get("date") and not DATE.match(f["date"]):
            errs.append(f"{where}: date must be YYYY-MM-DD")
        if "\N{EM DASH}" in (f.get("summary") or ""):
            errs.append(f"{where}: summary contains an em dash")
        if GENDERED.search(f.get("summary") or ""):
            errs.append(f"{where}: summary uses a gendered pronoun; a name does not tell anyone's pronouns, so write they/them or the name")
        if TRUNCATED.search(f.get("summary") or ""):
            errs.append(f"{where}: summary stops mid-sentence")
    return errs


def self_test(families, statements) -> int:
    fam = sorted(families)[0]
    good = {"schema": "community_v1",
            "efforts": [{"id": "x", "name": "X", "url": "https://example.org/x", "kind": "audit",
                         "authors": [{"name": "A. Person"}], "licence": "MIT", "date": "2026-10-08",
                         "summary": "Replays two statements.", "reuse": "cite", "families": [fam], "statements": []}],
            "findings": [{"effort": "x", "family": fam, "statement": None, "kind": "replay-pass",
                          "summary": "Comparator accepted the proof.", "url": "https://example.org/x/1", "date": "2026-10-08"}]}
    bad_cases = [
        ("unknown kind", {**good, "efforts": [{**good["efforts"][0], "kind": "rumour"}]}),
        ("missing licence", {**good, "efforts": [{**good["efforts"][0], "licence": ""}]}),
        ("import without licence", {**good, "efforts": [{**good["efforts"][0], "reuse": "import", "licence": "none stated"}]}),
        ("finding without effort", {**good, "findings": [{**good["findings"][0], "effort": "nope"}]}),
        ("unknown family", {**good, "findings": [{**good["findings"][0], "family": "999"}]}),
        ("bad date", {**good, "findings": [{**good["findings"][0], "date": "8 Oct"}]}),
        ("em dash", {**good, "efforts": [{**good["efforts"][0], "summary": "Replays \N{EM DASH} two."}]}),
        ("gendered pronoun", {**good, "findings": [{**good["findings"][0], "summary": "The author says he re-ran it."}]}),
        ("summary cut off", {**good, "efforts": [{**good["efforts"][0], "summary": "Replays two statements and."}]}),
        ("code copied without licence", {**good, "efforts": [{**good["efforts"][0], "licence": "none stated", "adopted": [{"kind": "code", "what": "parser", "where": "scripts/x.py"}]}]}),
        ("adopted without where", {**good, "efforts": [{**good["efforts"][0], "adopted": [{"kind": "idea", "what": "a layout"}]}]}),
    ]
    failures = 0
    if check(good, families, statements):
        print("FAIL: the good example was rejected:", check(good, families, statements))
        failures += 1
    for name, doc in bad_cases:
        if not check(doc, families, statements):
            print(f"FAIL: {name} was accepted")
            failures += 1
    print(f"self-test: {1 + len(bad_cases) - failures} of {1 + len(bad_cases)} checks passed")
    return 1 if failures else 0


def main() -> int:
    families, statements = load_ids()
    if "--self-test" in sys.argv:
        return self_test(families, statements)
    if not PATH.exists():
        print("curated/community.json not found (nothing to check)")
        return 0
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    errs = check(doc, families, statements)
    for e in errs:
        print("error:", e)
    eff, fnd = doc.get("efforts", []), doc.get("findings", [])
    people = {a.get("name") or a.get("handle") for e in eff for a in e.get("authors") or []}
    print(f"community.json: {len(eff)} efforts by {len(people)} people, {len(fnd)} findings; "
          + ("OK" if not errs else f"{len(errs)} errors"))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
