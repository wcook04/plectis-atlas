"""Share cards: the picture a family's link shows when someone posts it.

A card is a 1200 by 675 page drawn from the same records as the family page:
the family's name, the first sentence of OpenAI's catalogue description,
credited, what the release's Lean states according to each outside reader, in
their own term and in plain words, the re-runs, and the sentence that limits
what the card says (a candidate pairing, a disagreement, no Lean). Nothing on a card can be cropped away: a
card whose words overflow its frame, or whose formulas fail to typeset, is not
rendered, and that family's page keeps the generic picture.

    write_pages(S, r, out)   card pages under <out>/cards/families/<id>.html
    render(out)              PNGs under <out>/og/families/<id>.png when Playwright
                             is importable (optional); returns the ids rendered
    adopt(out, ids)          point each rendered family page's og:image at its card

S is the build_site module, r the checked Reader. Standard library only, except
the optional headless browser used to take the pictures.
"""
from __future__ import annotations

import json
from pathlib import Path

import evidence as E

CARD_W, CARD_H = 1200, 675
LEDE_MAX = 260   # a longer first sentence is left off rather than cut


def _e(s) -> str:
    from html import escape
    return escape(str(s), quote=True)


def _short_name(rd: E.Reading) -> str:
    return rd.name.split(",")[-1].strip() if "," in rd.name else rd.name


def _qualification(ev: E.FamilyEvidence) -> str:
    """The one sentence that most limits what the mark says."""
    if not ev.has_lean:
        return E.say("no_lean")
    if ev.agreement == "disagree":
        return ev.agreement_sentence()
    if ev.pairing_kind == "source-reading":
        return "An AI agent read both sources and linked the paper theorem to the Lean; nobody has reviewed the link."
    if ev.pairing == "candidate-pairing":
        return "The paper theorem paired with the Lean was found by shared words; nobody has reviewed the pairing."
    return ev.agreement_sentence()


def family_card(S, r, ev: E.FamilyEvidence) -> str:
    """The card page for one family: words and typeset mathematics only."""
    doc = r.family(ev.num)
    claim = (doc.get("claim") or {}).get("catalogue_claim") or {}
    lede, _rest = S.head_lede(claim.get("text") or "")
    lede_html = ""
    if lede and len(lede) <= LEDE_MAX:
        lede_html = (f'<p class="cd-lede"><span class="cd-src">OpenAI&rsquo;s catalogue</span> '
                     f'<span class="tex-auto">{S.rich(lede)}</span></p>')
    disc = next((d for d in r.universe.get("disciplines") or [] if d["id"] == ev.discipline), None)
    where = f'{_e(disc["name"])}, family {ev.num}' if disc else f"Family {ev.num}"
    if ev.has_lean:
        k = len(ev.lean)
        lean_words = E.say("sentence.lean_one") if k == 1 else E.say("sentence.lean_many", n=k)
        rows = "".join(
            f'<li><span class="cd-who">{_e(_short_name(rd))}</span> '
            f'<span class="cd-says">{_e(E.say("tone." + rd.tone))}</span> '
            f'<span class="cd-term">({_e(rd.term)})</span></li>' if rd.term else
            f'<li><span class="cd-who">{_e(_short_name(rd))}</span> <span class="cd-says">{_e(E.say("tone.none"))}</span></li>'
            for rd in ev.readers)
        accepted = max((len(l.accepted) for l in ev.lean), default=0)
        runs = (E.say("reruns.none") if not accepted else
                f"Outside groups report re-running it and accepting the proof: up to {accepted} per statement.")
        lean_html = (f'<div class="cd-lean"><p class="cd-h">The release has {lean_words}. '
                     f'Does it state the headline?</p><ul>{rows}</ul><p class="cd-runs">{_e(runs)}</p></div>')
    else:
        lean_html = f'<div class="cd-lean"><p class="cd-h">{_e(E.say("no_lean"))}</p></div>'
    problems = ev.community_count("error-reported") + ev.community_count("correction")
    qual = _qualification(ev)
    if problems:
        qual += f" {problems} problem report{'s' if problems != 1 else ''} from others, not judged by the atlas."
    host = _e(S.BASE_URL.replace("https://", "").rstrip("/"))
    return f"""<!doctype html><html lang="en-GB" data-theme="light"><head><meta charset="utf-8">
<link rel="stylesheet" href="../../{S.KATEX_DIR}/katex.min.css">
<link rel="stylesheet" href="../../assets/atlas.css">
<style>
html,body{{margin:0;background:var(--page)}}
.cd{{box-sizing:border-box;width:{CARD_W}px;height:{CARD_H}px;padding:46px 60px 40px;display:grid;
  grid-template-rows:auto 1fr auto;row-gap:18px;overflow:hidden;color:var(--ink);font-family:var(--sans)}}
.cd-brand,.cd-foot{{display:flex;justify-content:space-between;align-items:center;font-size:19px;color:var(--muted)}}
.cd-brand b{{color:var(--ink);font-weight:600;display:inline-flex;gap:10px;align-items:center}}
.cd-main{{align-self:center;min-height:0;display:grid;grid-template-columns:1fr 380px;column-gap:48px;align-items:center}}
.cd h1{{margin:0 0 16px;font-family:var(--serif);font-weight:500;font-size:44px;line-height:1.12;letter-spacing:-0.01em;text-wrap:balance}}
.cd-lede{{margin:0 0 14px;font-family:var(--serif);font-size:22px;line-height:1.4;color:var(--ink-soft)}}
.cd-src{{font-family:var(--sans);color:var(--muted);font-size:17px;margin-right:4px}}
.cd-qual{{margin:0;font-size:19px;line-height:1.4;color:var(--ink-soft)}}
.cd-lean{{border-left:2px solid var(--steel);padding:4px 0 4px 22px}}
.cd-h{{margin:0 0 10px;font-size:19px;line-height:1.35;color:var(--ink)}}
.cd-lean ul{{list-style:none;margin:0 0 10px;padding:0;display:grid;gap:8px;font-size:18px;line-height:1.35}}
.cd-who{{font-weight:600}}
.cd-term{{color:var(--muted)}}
.cd-runs{{margin:0;font-size:17px;line-height:1.35;color:var(--muted)}}
</style></head>
<body class="card-family"><div class="cd" id="card">
<div class="cd-brand"><b>{S.MARK_SVG} Plectis Atlas</b><span>{where}</span></div>
<div class="cd-main"><div><h1><span class="tex-auto">{S.rich(ev.name)}</span></h1>{lede_html}<p class="cd-qual">{_e(qual)}</p></div>{lean_html}</div>
<div class="cd-foot"><span>{host}/families/{ev.num}.html</span><span>Release pinned at {_e(r.pin[:7])}</span></div>
</div>
<script defer src="../../{S.KATEX_DIR}/katex.min.js"></script>
<script defer src="../../{S.KATEX_DIR}/contrib/auto-render.min.js"></script>
<script defer src="../../assets/atlas.js"></script>
</body></html>
"""


def site_card(S, r) -> str:
    """The site's own card, in words: what the atlas is and what it holds."""
    def n(key):
        v = r.number(key).get("value")
        return f"{v:,}" if isinstance(v, int) else "?"
    host = _e(S.BASE_URL.replace("https://", "").rstrip("/"))
    return f"""<!doctype html><html lang="en-GB" data-theme="light"><head><meta charset="utf-8">
<link rel="stylesheet" href="../assets/atlas.css">
<style>
html,body{{margin:0;background:var(--page)}}
.stc{{box-sizing:border-box;width:{CARD_W}px;height:{CARD_H}px;padding:64px 72px 52px;display:grid;grid-template-rows:auto 1fr auto;overflow:hidden;font-family:var(--sans);color:var(--ink)}}
.stc b{{display:inline-flex;gap:12px;align-items:center;font-size:22px;font-weight:600}}
.stc-mid{{align-self:center}}
.stc h1{{font-family:var(--serif);font-weight:500;font-size:64px;line-height:1.08;letter-spacing:-0.015em;margin:0 0 26px;max-width:15em;text-wrap:balance}}
.stc p{{font-size:25px;line-height:1.45;color:var(--ink-soft);margin:0;max-width:44em}}
.stc-foot{{font-size:20px;color:var(--muted)}}
</style></head>
<body class="site-card"><div class="stc" id="card"><b>{S.MARK_SVG} Plectis Atlas</b>
<div class="stc-mid"><h1>OpenAI&rsquo;s mathematics release, read and checked</h1>
<p>{n("manuscripts_current")} papers in {n("families")} families across {n("disciplines")} disciplines. For each family: the claim, the theorem in the paper, what the release&rsquo;s Lean states, and who has checked it, credited by name.</p></div>
<div class="stc-foot">{host}</div></div></body></html>
"""


def write_pages(S, r, out: Path) -> list[str]:
    """Write every family's card page and the site card; return the family numbers written."""
    out = Path(out)
    (out / "cards").mkdir(parents=True, exist_ok=True)
    (out / "cards" / "site.html").write_text(site_card(S, r), encoding="utf-8")
    done = []
    for ev in E.all_families(r):
        p = out / "cards" / "families" / f"{ev.num}.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(family_card(S, r, ev), encoding="utf-8")
        done.append(ev.num)
    return done


def render(out: Path, nums: list[str], workers: int = 4) -> list[str]:
    """Photograph each card page to og/families/<id>.png with a headless browser.
    Returns the family numbers whose card was rendered and passed: every formula
    typeset and nothing overflowing the frame. Optional: returns [] without Playwright."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: optional
    except Exception:
        print("cards: Playwright is not importable; family cards were not rendered")
        return []
    import threading
    import http.server
    import functools
    from concurrent.futures import ThreadPoolExecutor

    out = Path(out)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"

    def run(chunk):
        good = []
        with sync_playwright() as p:
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception:
                b = p.chromium.launch()
            pg = b.new_page(viewport={"width": CARD_W, "height": CARD_H}, device_scale_factor=1, color_scheme="light")
            for n in chunk:
                page = "cards/site.html" if n == "site" else f"cards/families/{n}.html"
                pg.goto(f"{base}{page}", wait_until="load")
                try:
                    pg.wait_for_function("() => !!(window.katex && window.atlasRenderMath) || "
                                         "document.body.classList.contains('site-card')", timeout=15000)
                except Exception:
                    print(f"cards: {n}: the typesetter did not load; no card")
                    continue
                pg.evaluate("() => { if (window.atlasRenderMath) window.atlasRenderMath(document); }")
                pg.evaluate("document.fonts.ready.then(() => true)")
                pg.wait_for_timeout(120)
                st = pg.evaluate(r"""() => { const c = document.getElementById('card');
                    const m = c.querySelector('.cd-main') || c;
                    return {failed: (window.__atlasMath || {}).failed || 0,
                            overflow: c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1
                                      || m.scrollHeight > m.clientHeight + 1,
                            raw: /\\\(|\\\)/.test(m.textContent)}; }""")
                if st["failed"] or st["overflow"] or st["raw"]:
                    print(f"cards: {n}: rejected ({st})")
                    continue
                dst = (out / "assets" / "social-card.png") if n == "site" else (out / "og" / "families" / f"{n}.png")
                dst.parent.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(dst), clip={"x": 0, "y": 0, "width": CARD_W, "height": CARD_H})
                if dst.exists() and dst.stat().st_size:
                    good.append(n)
            b.close()
        return good

    try:
        workers = max(1, min(workers, len(nums)))
        chunks = [nums[i::workers] for i in range(workers)]
        with ThreadPoolExecutor(workers) as ex:
            got = [n for part in ex.map(run, chunks) for n in part]
    finally:
        srv.shutdown()
    return sorted(got)


def adopt(out: Path, nums: list[str], generic: str, base_url: str) -> int:
    """Point each rendered family page's og:image and twitter:image at its own card.
    Pages whose card was not rendered keep the generic picture. Returns pages changed."""
    out = Path(out)
    changed = 0
    for n in nums:
        page = out / "families" / f"{n}.html"
        if not page.exists():
            continue
        html = page.read_text(encoding="utf-8")
        own = f"{base_url}og/families/{n}.png"
        new = html.replace(f"{base_url}{generic}", own)
        if new != html:
            page.write_text(new, encoding="utf-8")
            changed += 1
    return changed


if __name__ == "__main__":
    import sys
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser(description="Write and render family share cards into a built site.")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "site" / "_build"))
    ap.add_argument("--only", nargs="*", help="family numbers (default: all)")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()
    import build_site as S  # noqa: E402  (module-level data loads, as build_universe does)
    import reader
    r = reader.load()
    nums = write_pages(S, r, Path(args.out))
    if args.only:
        nums = [n for n in nums if n in set(args.only)]
    if not args.no_render:
        got = render(Path(args.out), nums + ["site"])
        fams = [n for n in got if n != "site"]
        print(json.dumps({"written": len(nums), "rendered": len(fams), "site_card": "site" in got,
                          "adopted": adopt(Path(args.out), fams, S.GENERIC_OG, S.BASE_URL)}))
