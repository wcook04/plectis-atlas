#!/usr/bin/env python3
"""List candidate contributions using the recorded coverage and source metadata.

Usage (from the repository root):
    python3 skills/start-here/find_work.py --kind check [--discipline "number theory"] [--limit 5]
    python3 skills/start-here/find_work.py --kind explanation [--discipline algebra]
    python3 skills/start-here/find_work.py --kind credit [--discipline topology]
    python3 skills/start-here/find_work.py --kind replay [--main-results]
    python3 skills/start-here/find_work.py --disciplines

It reads data/*.json and the files under contributions/. It cannot see GitHub
issues. Optional announcements use the "claim" label and reserve nothing.
The ordering describes source metadata, not mathematical difficulty. A recorded
check can remain unresolved; this is not the complete review queue.

Standard library only; Python 3.10 or newer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_root(start: Path) -> Path | None:
    for folder in [start, *start.parents]:
        if (folder / "data").is_dir() and (folder / "contributions").is_dir():
            return folder
    return None


def load(root: Path, name: str) -> list[dict]:
    path = root / "data" / f"{name}.json"
    if not path.is_file():
        sys.exit(f"{path} is missing; run python3 scripts/build_data.py first (see skills/improve-the-atlas/SKILL.md)")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get(name, list(raw.values()))
    return [r for r in raw if isinstance(r, dict)]


def existing(root: Path, folder: str) -> dict[str, int]:
    """Number of contribution files per subfolder of contributions/<folder>."""
    base = root / "contributions" / folder
    counts: dict[str, int] = {}
    if base.is_dir():
        for sub in base.iterdir():
            if sub.is_dir() and not sub.name.startswith((".", "_")):
                count = sum(1 for p in sub.rglob("*") if p.is_file() and p.suffix in (".md", ".json"))
                if count:
                    counts[sub.name] = count
    return counts


def matches(discipline: str | None, family: dict | None) -> bool:
    if not discipline:
        return True
    return bool(family) and discipline.lower() in str(family.get("discipline", "")).lower()


def shorten(text: str, width: int = 96) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description="List candidate contributions using recorded coverage and source metadata.")
    parser.add_argument("--kind", choices=("check", "explanation", "credit", "replay"), default="check")
    parser.add_argument("--discipline", help="part of a discipline name, for example 'number theory'")
    parser.add_argument("--main-results", action="store_true", help="only statements marked as main results")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--disciplines", action="store_true", help="list the disciplines and stop")
    parser.add_argument("--root", type=Path, help="repository root (found automatically)")
    args = parser.parse_args()

    root = args.root or find_root(Path.cwd()) or find_root(Path(__file__).resolve().parent)
    if root is None:
        sys.exit("run this from inside the atlas repository")
    families = {f["id"]: f for f in load(root, "families")}

    if args.disciplines:
        counts: dict[str, int] = {}
        for fam in families.values():
            counts[fam.get("discipline", "?")] = counts.get(fam.get("discipline", "?"), 0) + 1
        for name, n in sorted(counts.items()):
            print(f"{name}: {n} families")
        return 0

    manuscripts = {m["id"]: m for m in load(root, "manuscripts")}
    shown = 0

    if args.kind in ("check", "replay"):
        statements = load(root, "statements")
        done = existing(root, "checks" if args.kind == "check" else "replays")
        rows = []
        for s in statements:
            fam_id = (s.get("families") or [None])[0]
            fam = families.get(fam_id)
            if s["id"] in done or not matches(args.discipline, fam):
                continue
            if args.main_results and not s.get("main_result"):
                continue
            rows.append((s.get("vocabulary_count", 999), s.get("statement_lines", 999), s["id"], s, fam))
        rows.sort(key=lambda r: (r[0], r[1], r[2]) if args.kind == "check" else (not r[3].get("main_result"), r[2]))
        print(f"{len(rows)} {'main-result ' if args.main_results else ''}statements have no {args.kind} yet"
              f"{' in ' + args.discipline if args.discipline else ''}. "
              f"{'Fewest custom definitions first' if args.kind == 'check' else 'Main results first'}:\n")
        for _, _, sid, s, fam in rows[: args.limit]:
            shown += 1
            paper = manuscripts.get((s.get("papers") or [None])[0]) or {}
            print(f"{sid}  (family {fam.get('id') if fam else '?'}, {fam.get('discipline', '?') if fam else '?'})")
            print(f"    {shorten(fam.get('title', '')) if fam else ''}")
            n_defs = s.get("vocabulary_count", "?")
            print(f"    {n_defs} custom definition{'' if n_defs == 1 else 's'}, {s.get('statement_lines', '?')} "
                  f"lines of Lean to read, main result: {'yes' if s.get('main_result') else 'no'}")
            definition_holes = (s.get("comparator") or {}).get("definition_names") or []
            if definition_holes:
                print(f"    has definition holes ({len(definition_holes)}): read the solution's definitions too")
            if args.kind == "replay":
                print(f"    Comparator builds: {(s.get('comparator') or {}).get('solution_module', '?')}")
            print(f"    Lean file:   {s.get('url', s.get('file', ''))}")
            if fam and fam.get("lean_doc"):
                print(f"    Scope note:  {fam['lean_doc'].get('url', '')}")
            if paper:
                print(f"    Paper:       {shorten(paper.get('title', ''), 80)}")
                print(f"                 {paper.get('pdf_url', '')}")
            print()
        if shown:
            if args.kind == "check":
                print("Next: mkdir -p contributions/checks/<StatementId>\n"
                      "      cp contributions/_templates/statement-check.md "
                      "contributions/checks/<StatementId>/<your-github-handle>.md\n"
                      "      then follow skills/check-a-statement/SKILL.md")
            else:
                print("Next: follow skills/replay-a-proof/SKILL.md; the receipt goes in "
                      "contributions/replays/<StatementId>/<your-github-handle>-<YYYYMMDD>.json")
        return 0

    if args.kind == "explanation":
        done = existing(root, "explanations")
        checks = existing(root, "checks")
        rows = []
        for fam in families.values():
            if fam["id"] in done or not matches(args.discipline, fam):
                continue
            stmts = fam.get("statements") or []
            rows.append((not stmts, len(fam.get("manuscripts") or []), fam["id"], fam, stmts))
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        print(f"{len(rows)} families have no explanation yet"
              f"{' in ' + args.discipline if args.discipline else ''}. "
              "Families with a Lean statement and fewer manuscripts first:\n")
        for _, n_ms, fid, fam, stmts in rows[: args.limit]:
            shown += 1
            checked = sum(1 for s in stmts if s in checks)
            print(f"Family {fid}  ({fam.get('discipline', '?')}): {shorten(fam.get('title', ''), 80)}")
            print(f"    {shorten(fam.get('description', ''), 160)}")
            print(f"    {n_ms} manuscript{'s' if n_ms != 1 else ''}, {len(stmts)} Lean statement"
                  f"{'s' if len(stmts) != 1 else ''} ({checked} with a statement check)")
            print()
        if shown:
            print("Next: follow skills/explain-a-result/SKILL.md. Your file belongs at\n"
                  "      contributions/explanations/<family>/<your-github-handle>/explanation.md\n"
                  "      Extend an existing file; never overwrite it. Announcing work is optional.")
        return 0

    # credits
    done = existing(root, "credits")
    rows = []
    for fam in families.values():
        if not matches(args.discipline, fam):
            continue
        current = [manuscripts[m] for m in fam.get("manuscripts") or [] if m in manuscripts]
        refs = sum(len(m.get("references") or []) for m in current)
        rows.append((done.get(fam["id"], 0), -refs, fam["id"], fam, current, refs))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    print("Families with the fewest credits first, then the longest bibliographies:\n")
    for credits, _, fid, fam, current, refs in rows[: args.limit]:
        shown += 1
        print(f"Family {fid}  ({fam.get('discipline', '?')}): {shorten(fam.get('title', ''), 80)}")
        print(f"    {credits} credit{'s' if credits != 1 else ''} so far; {refs} bibliography entries "
              f"across {len(current)} manuscript{'s' if len(current) != 1 else ''}")
        for m in current[:3]:
            print(f"    {shorten(m.get('title', ''), 80)}: {m.get('pdf_url', '')}")
        print()
    if shown:
        print("Next: cp contributions/_templates/credit.md "
              "contributions/credits/<family>/<your-github-handle>-<short-slug>.md\n"
              "      and follow skills/trace-a-credit/SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
