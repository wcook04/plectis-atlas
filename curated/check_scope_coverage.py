#!/usr/bin/env python3
"""Check curated/scope_coverage.json against the atlas data and the upstream scope notes.

Usage:
    python3 curated/check_scope_coverage.py [--upstream PATH] [--file PATH]

The upstream checkout defaults to $OPENAI_MATH_UPSTREAM, then ../openai-math-upstream
beside the atlas, the same convention as scripts/build_data.py. Scope notes are read
at the commit the file pins (git show <commit>:lean/docs/<family>.md), so the check
does not depend on where the checkout's HEAD currently points.

What is checked:
  - the top-level object: schema "scope_coverage_v1", upstream_commit equal to the
    commit in upstream.json, a non-empty method, a list of rows;
  - exactly one row for every statement id in data/statements.json, and no others;
  - each row's family equals the statement's family in data/statements.json;
  - class (and the optional secondary_class) is one of the six classes;
  - scope_quote is a non-empty exact substring of lean/docs/<family>.md upstream;
  - paper_headline is null or names a manuscript of the family, and any file and
    line it gives exist upstream (with the label present in that file);
  - explanation is non-empty and free of em dashes; confidence is high, medium or
    low; needs_specialist is true or false.

Prints the number of rows in each class. Standard library only; Python 3.10 or newer.
Exit status: 0 when every check passes, 1 when any fails, 2 for a usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "curated" / "scope_coverage.json"
CLASSES = ["headline", "headline-part", "consequence", "weaker", "supporting", "unclear"]
CONFIDENCE = {"high", "medium", "low"}
ROW_KEYS = {"statement", "family", "class", "scope_quote", "paper_headline",
            "explanation", "confidence", "needs_specialist"}
OPTIONAL_KEYS = {"secondary_class"}


def git_show(upstream: Path, commit: str, rel: str) -> str | None:
    """Return the file at commit, or None when git cannot supply it."""
    try:
        out = subprocess.run(["git", "-C", str(upstream), "show", f"{commit}:{rel}"],
                             capture_output=True, check=False)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8")


def git_head(upstream: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=False)
    except OSError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", default=os.environ.get("OPENAI_MATH_UPSTREAM",
                                                         str(ROOT.parent / "openai-math-upstream")))
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    a = ap.parse_args()

    upstream = Path(a.upstream).expanduser().resolve()
    if not (upstream / "lean" / "docs").is_dir():
        print(f"usage error: no upstream checkout with lean/docs at {upstream}; "
              "pass --upstream or set OPENAI_MATH_UPSTREAM", file=sys.stderr)
        return 2
    try:
        doc = json.loads(Path(a.file).read_text(encoding="utf-8"))
        statements = json.loads((ROOT / "data" / "statements.json").read_text(encoding="utf-8"))
        families = json.loads((ROOT / "data" / "families.json").read_text(encoding="utf-8"))
        pin = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))["commit"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"usage error: cannot read inputs: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    # top level
    if not isinstance(doc, dict):
        print("FAIL: top level is not a JSON object")
        return 1
    if doc.get("schema") != "scope_coverage_v1":
        err(f"schema is {doc.get('schema')!r}, expected 'scope_coverage_v1'")
    commit = doc.get("upstream_commit")
    if commit != pin:
        err(f"upstream_commit {commit!r} differs from upstream.json {pin!r}")
    if not isinstance(doc.get("method"), str) or not doc["method"].strip():
        err("method is missing or empty")
    rows = doc.get("rows")
    if not isinstance(rows, list):
        print("FAIL: rows is not a list")
        return 1

    stmt_family = {s["id"]: s["families"][0] for s in statements}
    fam_manuscripts = {f["id"]: set(f.get("manuscripts") or []) for f in families}

    # read every needed note once, at the pinned commit
    notes: dict[str, str | None] = {}
    head = git_head(upstream)

    def note(fid: str) -> str | None:
        if fid not in notes:
            text = git_show(upstream, pin, f"lean/docs/{fid}.md")
            if text is None and head == pin:
                p = upstream / "lean" / "docs" / f"{fid}.md"
                text = p.read_text(encoding="utf-8") if p.exists() else None
            notes[fid] = text
        return notes[fid]

    seen: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    secondary: Counter[str] = Counter()
    confidence: Counter[str] = Counter()
    specialist = 0
    for i, row in enumerate(rows):
        where = f"row {i}"
        if not isinstance(row, dict):
            err(f"{where}: not an object")
            continue
        sid = row.get("statement")
        where = f"row {i} ({sid})"
        keys = set(row)
        if ROW_KEYS - keys:
            err(f"{where}: missing fields {sorted(ROW_KEYS - keys)}")
        if keys - ROW_KEYS - OPTIONAL_KEYS:
            err(f"{where}: unknown fields {sorted(keys - ROW_KEYS - OPTIONAL_KEYS)}")
        if sid not in stmt_family:
            err(f"{where}: not a statement id in data/statements.json")
            continue
        # An unreviewed reading says what a statement states; "certify" would claim a check nobody made.
        if re.search(r"\b[Cc]ertif(?:y|ies|ied)\b", str(row.get("explanation") or "")):
            err(f"{where}: explanation says 'certif...'; a draft reading says what the statement states")
        seen[sid] += 1
        fid = row.get("family")
        if fid != stmt_family[sid]:
            err(f"{where}: family {fid!r}, data/statements.json says {stmt_family[sid]!r}")
            fid = stmt_family[sid]
        cls = row.get("class")
        if cls not in CLASSES:
            err(f"{where}: class {cls!r} is not one of {CLASSES}")
        else:
            classes[cls] += 1
        if "secondary_class" in row:
            sec = row["secondary_class"]
            if sec not in CLASSES or sec == cls:
                err(f"{where}: secondary_class {sec!r} is not a different class from the list")
            else:
                secondary[sec] += 1
        quote = row.get("scope_quote")
        text = note(fid)
        if not isinstance(quote, str) or not quote.strip():
            err(f"{where}: scope_quote is missing or empty")
        elif text is None:
            err(f"{where}: cannot read lean/docs/{fid}.md at {pin}")
        elif quote not in text:
            err(f"{where}: scope_quote is not an exact substring of lean/docs/{fid}.md")
        ph = row.get("paper_headline")
        if ph is not None:
            if not isinstance(ph, dict) or not isinstance(ph.get("manuscript"), str):
                err(f"{where}: paper_headline must be null or an object with a manuscript")
            else:
                slug = ph["manuscript"]
                if slug not in fam_manuscripts.get(fid, set()):
                    err(f"{where}: manuscript {slug} is not in family {fid}")
                if ph.get("file") is not None:
                    src = git_show(upstream, pin, f"preprints/{slug}/{ph['file']}")
                    if src is None:
                        err(f"{where}: paper_headline file {ph['file']} not found upstream")
                    else:
                        line = ph.get("line")
                        if not isinstance(line, int) or not 1 <= line <= len(src.splitlines()):
                            err(f"{where}: paper_headline line {line!r} is out of range")
                        if ph.get("label") and ph["label"] not in src:
                            err(f"{where}: label {ph['label']} does not occur in {ph['file']}")
        expl = row.get("explanation")
        if not isinstance(expl, str) or not expl.strip():
            err(f"{where}: explanation is missing or empty")
        elif "\u2014" in expl:
            err(f"{where}: explanation contains an em dash")
        conf = row.get("confidence")
        if conf not in CONFIDENCE:
            err(f"{where}: confidence {conf!r} is not high, medium or low")
        else:
            confidence[conf] += 1
        ns = row.get("needs_specialist")
        if not isinstance(ns, bool):
            err(f"{where}: needs_specialist must be true or false")
        elif ns:
            specialist += 1

    for sid, n in seen.items():
        if n > 1:
            err(f"{sid}: {n} rows, expected one")
    missing = sorted(set(stmt_family) - set(seen))
    if missing:
        err(f"{len(missing)} statements have no row: {', '.join(missing[:10])}{' ...' if len(missing) > 10 else ''}")

    print(f"scope_coverage.json: {len(rows)} rows for {len(stmt_family)} statements, upstream {pin[:12]}")
    print("class counts:")
    for c in CLASSES:
        print(f"  {c:<14}{classes[c]:>5}")
    if secondary:
        print("secondary classes: " + ", ".join(f"{c} {secondary[c]}" for c in CLASSES if secondary[c]))
    print("confidence: " + ", ".join(f"{c} {confidence[c]}" for c in ("high", "medium", "low")))
    print(f"needs_specialist: {specialist}")
    if errors:
        print(f"FAIL: {len(errors)} problem(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK: every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
