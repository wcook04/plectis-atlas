"""Checks for the family page (scripts/family_page.py) on the specimen families.

Builds the pages into a temporary directory and checks what DESIGN.md and the brief
pin: the anchors other pages link to, the theorem shown only when the backend names a
candidate, every state in words (no symbol mark), every inspection trigger with its
record, no repeated ids, and every "what is left to check" link carrying its target's
exact fingerprint. Standard library only: python3 scripts/test_family_page.py
"""
from __future__ import annotations

import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site as S  # noqa: E402
import family_page  # noqa: E402

SPECIMENS = ["001", "003", "017", "032", "159", "260", "099", "312", "238", "090", "081", "102"]
ANCHORS = ["h-desc", "h-lean", "h-ms", "h-explain", "h-checks", "compare", "claim", "h-bench", "h-cites", "h-readings"]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="atlas-family-"))
    S.OUT = tmp
    fails = []
    for fid in SPECIMENS:
        family_page.build(S, S.FAM[fid])
        html = (tmp / "families" / f"{fid}.html").read_text(encoding="utf-8")
        doc = family_page._reader().family(fid)

        def check(ok, what):
            if not ok:
                fails.append(f"{fid}: {what}")
        ids = re.findall(r' id="([^"]+)"', html)
        for a in ANCHORS:
            check(a in ids, f"anchor #{a} missing")
        dup = [k for k, v in Counter(ids).items() if v > 1]
        check(not dup, f"repeated ids {dup[:4]}")
        for h in set(re.findall(r'href="#([^"]+)"', html)):
            check(h in ids, f"in-page link #{h} has no target")
        for t in set(re.findall(r'data-inspect="([^"]+)"', html)):
            check(f'<template id="{t}">' in html, f"inspection record {t} missing")
        check("<details" not in html, "a fold on the page")
        check('class="sp ' not in html and "sp-half" not in html, "a symbol mark is drawn")
        check("assets/evidence.css" not in html and "assets/figure.css" not in html, "a retired sheet is linked")
        claim = doc["claim"]
        if claim["state"] == "candidate" and claim.get("primary_candidate"):
            check('id="claim-theorem"' in html, "the candidate theorem is not the centrepiece")
        else:
            check('id="claim-theorem"' not in html, "an unresolved headline shows a single theorem")
            check(family_page.W("claim.unresolved") in unquote(html), "the unresolved sentence is missing")
        for rc in doc.get("remaining_checks") or []:
            fp = (rc.get("contribution_target") or {}).get("fingerprint")
            if fp:
                check(fp in unquote(html), f"no contribution link carries {fp[:19]}")
        if doc.get("lean"):
            for l in doc["lean"]:
                check(f'id="lean-{l["id"][2:]}"' in html, f"no comparison for {l['id']}")
        check(" — " not in re.sub(r"“[^”]*”|<code.*?</code>|<pre.*?</pre>|<template.*?</template>", "", html, flags=re.S)
              .split("<main", 1)[-1].split("Their method", 1)[0], "an em dash in the page's own words")
        for what in compare_buttons(fid, html):
            check(False, what)
    fails += status_group_counts()
    for f in fails:
        print("FAIL", f)
    print(f"family page: {len(SPECIMENS)} specimens, {len(fails)} failures")
    return 1 if fails else 0


def compare_buttons(fid: str, html: str) -> list:
    """"Compare with Lean" sits only on a theorem card whose statement a Lean statement is
    paired with, and opens that pairing; a card no Lean is paired with says so instead."""
    c = family_page.Ctx(S, S.FAM[fid])
    claim = c.doc.get("claim") or {}
    if claim.get("state") == "candidate" and claim.get("primary_candidate") in c.stmts:
        shown = [claim["primary_candidate"]]
    else:
        alts = [a for a in claim.get("alternatives") or [] if a.get("statement_id") in c.stmts]
        top = max([a.get("score") or 0 for a in alts] or [0])
        shown = [a["statement_id"] for a in alts if (a.get("score") or 0) == top][:3]
    section = html.split('id="claim"', 1)[-1].split("</section>", 1)[0]
    cards = re.findall(r'<article class="fx-st[^"]*" id="claim-[^"]+"(.*?)</article>', section, flags=re.S)
    out = []
    for sid, body in zip(shown, cards):
        lean = family_page.paired_lean(c, sid)
        hrefs = re.findall(r'href="#([^"]+)"[^>]*>' + re.escape(family_page.W("actions.compare")) + "<", body)
        if lean and hrefs != [f"lean-{lean}"]:
            out.append(f"{sid}: paired with {lean}, but its compare links are {hrefs}")
        if not lean and hrefs:
            out.append(f"{sid}: no Lean statement is paired with it, yet it offers {hrefs}")
        if not lean and c.leans and family_page.W("claim.no_lean_paired") not in body:
            out.append(f"{sid}: no Lean statement is paired with it, and the card does not say so")
    return out


NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def status_group_counts() -> list:
    """Every family's status line counts the outside groups in accepted_current_sources:
    one group is never "groups", and on a single Lean statement the number is exact."""
    fails = []
    for fid in S.FAM:
        c = family_page.Ctx(S, S.FAM[fid])
        if not c.leans:
            continue
        line = family_page.status_runs(c)
        groups = {s for l in c.leans for s in l.get("accepted_current_sources") or []}
        if not groups:
            ok = line.startswith("no outside group")
        elif len(groups) == 1:
            ok = line.startswith("one outside group ") and "groups" not in line
        else:
            ok = "outside groups" in line and not line.startswith("one outside group")
            if len(c.leans) == 1 or sum(1 for l in c.leans if l.get("accepted_current_sources")) == 1:
                ok = ok and line.startswith(f"{NUMBER_WORDS.get(len(groups), len(groups))} outside groups ")
        if not ok:
            fails.append(f"{fid}: status line {line!r} for {len(groups)} accepting groups")
    return fails


if __name__ == "__main__":
    sys.exit(main())
