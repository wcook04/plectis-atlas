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
            check(family_page.say("claim.unresolved") in unquote(html).replace("’", "'"), "the unresolved sentence is missing")
        for rc in doc.get("remaining_checks") or []:
            fp = (rc.get("contribution_target") or {}).get("fingerprint")
            if fp:
                check(fp in unquote(html), f"no contribution link carries {fp[:19]}")
        if doc.get("lean"):
            for l in doc["lean"]:
                check(f'id="lean-{l["id"][2:]}"' in html, f"no comparison for {l['id']}")
        check(" — " not in re.sub(r"“[^”]*”|<code.*?</code>|<pre.*?</pre>|<template.*?</template>", "", html, flags=re.S)
              .split("<main", 1)[-1].split("Their method", 1)[0], "an em dash in the page's own words")
    for f in fails:
        print("FAIL", f)
    print(f"family page: {len(SPECIMENS)} specimens, {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
