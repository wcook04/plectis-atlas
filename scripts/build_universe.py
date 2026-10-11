#!/usr/bin/env python3
"""Build the release universe: one map of every family of OpenAI's mathematics
release, each family drawn as a small map of its own, placed by discipline, with
the citations between families drawn as fibres. A family opens into its own map:
its papers as rings, each headline result a dot, its Lean statements, threads from
each paired result to its Lean statement and fibres out to the families it cites.

Writes, after scripts/build_site.py and scripts/build_papers.py have run:

    site/_build/universe.html                     the page (site header, nav and theme)
    site/_build/data/universe-data.json           what is drawn: ids, names, evidence
    site/_build/data/universe-layout.json         where it is drawn (same generation id)
    site/_build/data/universe-detail-<n>.json     the panel's statements, one file per discipline
    site/_build/data/universe-search.json         the search corpus, loaded on first use
    site/_build/assets/universe.js, universe.css

The geometry is computed here, once, so the map is the same place on every visit.
Data and geometry are separate files that carry one generation id; the page
refuses a pair whose ids differ. Every object's id comes from the release's own
names (family ids, Lean statement ids, manuscript slug plus TeX label, or
L-<file>-<line> when a statement has no label), so a deep link #o=<id> survives
a rebuild and a change of layout.

Layout patterns ported from Will Cook's ai_workflow at commit 4b1ebab611:
  - the radial sectors, hub angles and fibre bundling of the system map's Loom
    (sites/microcosm/assets/system-map.js), whose bundle() runs in the page;
  - the build-time layout written apart from the data, as in
    tools/meta/dissemination/build_plectis_maths_site.py (build_layout);
  - the band packing of the Plectis universe (each sector sized by its contents
    plus a floor).

Standard library only.
"""
from __future__ import annotations

import hashlib
import html
import importlib
import json
import math
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SITE = ROOT / "site"
OUT = SITE / "_build"
ASSETS = SITE / "assets"
COPY_U = json.loads((SITE / "copy_universe.json").read_text(encoding="utf-8"))
OWN_ASSETS = ("universe.js", "universe.css")

sys.path.insert(0, str(SCRIPTS))
S = None


def import_site(retries: int = 8, wait: float = 5.0):
    """Import build_site for its data, page() and helpers. Another desk may be
    editing it, so a failed import is retried before giving up."""
    global S
    if S is not None:
        return S
    last = None
    for _ in range(retries):
        try:
            S = importlib.import_module("build_site")
            return S
        except Exception as e:  # noqa: BLE001  (a half-written file can raise anything)
            last = e
            sys.modules.pop("build_site", None)
            time.sleep(wait)
    raise SystemExit(f"cannot import scripts/build_site.py: {last}")


def U(path: str, **kw) -> str:
    node = COPY_U
    for part in path.split("."):
        node = node[part]
    if kw:
        node = node.format(**{k: (f"{v:,}" if isinstance(v, int) else v) for k, v in kw.items()})
    return node


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def r4(v: float) -> float:
    return round(v, 4)


# ---------------------------------------------------------------- plain text

BB = {c: chr(0x1D538 + i) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
BB.update({"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"})
CAL = {"O": "𝒪", "L": "ℒ", "H": "ℋ", "F": "ℱ", "M": "ℳ", "B": "ℬ", "E": "ℰ", "R": "ℛ", "I": "ℐ"}
WORD_OPS = {"log", "ln", "exp", "sin", "cos", "tan", "det", "dim", "deg", "max", "min", "sup", "inf", "lim", "Re", "Im", "gcd", "rank", "Hom", "Spec", "Gal"}
SYM = {"le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "lt": "<", "gt": ">", "ne": "≠", "neq": "≠", "cdot": "·",
       "times": "×", "to": "→", "infty": "∞", "in": "∈", "subset": "⊂", "subseteq": "⊆", "pm": "±", "sim": "∼",
       "approx": "≈", "ell": "ℓ", "partial": "∂", "nabla": "∇", "cap": "∩", "cup": "∪", "circ": "∘", "mid": "∣",
       "ldots": "…", "dots": "…", "cdots": "⋯", "prime": "′", "otimes": "⊗", "oplus": "⊕", "emptyset": "∅",
       "rightarrow": "→", "mapsto": "↦", "langle": "⟨", "rangle": "⟩", ",": " ", ";": " ", "!": "", "quad": " ",
       "qquad": " ", "colon": ":", "{": "{", "}": "}", "%": "%", "&": "&", "_": "_", "#": "#"}
RELATIONS = set("≤≥<>≠∈⊂⊆→↦≈∼")
SUP = str.maketrans("0123456789+-=()niakjmt", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵏʲᵐᵗ")
SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")


def _group(t: str, i: int):
    """The braced group or single token starting at t[i] (after spaces): (text, next index)."""
    while i < len(t) and t[i] == " ":
        i += 1
    if i >= len(t):
        return "", i
    if t[i] == "{":
        depth, j = 0, i
        while j < len(t):
            if t[j] == "{":
                depth += 1
            elif t[j] == "}":
                depth -= 1
                if depth == 0:
                    return t[i + 1:j], j + 1
            j += 1
        return t[i + 1:], len(t)
    if t[i] == "\\":
        m = re.match(r"\\([A-Za-z]+|.)", t[i:])
        return m.group(0), i + len(m.group(0))
    return t[i], i + 1


def plain_math(t: str) -> str:
    """A formula from a title, as plain Unicode text for the drawing. Short titles
    only: it knows the commands that appear in the release's titles."""
    out, i = [], 0
    while i < len(t):
        c = t[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", t[i:])
            name = m.group(1)
            i += len(m.group(0))
            if name in ("mathbb", "mathbf", "mathrm", "mathsf", "mathit", "operatorname", "text", "mathcal", "mathfrak",
                        "mathscr", "overline", "bar", "widetilde", "tilde", "hat", "widehat"):
                arg, i = _group(t, i)
                inner = plain_math(arg)
                if name == "mathbb":
                    inner = "".join(BB.get(ch, ch) for ch in inner)
                elif name == "mathcal":
                    inner = "".join(CAL.get(ch, ch) for ch in inner)
                elif name in ("overline", "bar"):
                    inner = "".join(ch + "\u0305" for ch in inner) if len(inner) <= 2 else inner
                elif name in ("widetilde", "tilde"):
                    inner = inner + "\u0303" if len(inner) == 1 else inner
                elif name in ("hat", "widehat"):
                    inner = inner + "\u0302" if len(inner) == 1 else inner
                if name == "operatorname" or name == "text":
                    inner = " " + inner + " "
                out.append(inner)
            elif name in WORD_OPS:
                out.append(" " + name + " ")
            elif name in S.GREEK:
                out.append(S.GREEK[name])
            elif name in SYM:
                v = SYM[name]
                out.append(f" {v} " if v in RELATIONS else v)
            elif name in ("left", "right", "big", "Big", "bigl", "bigr", "Bigl", "Bigr", "displaystyle"):
                pass
            else:
                out.append(name)
        elif c in "^_":
            arg, i = _group(t, i + 1)
            inner = plain_math(arg).strip()
            table = SUP if c == "^" else SUB
            allowed = "0123456789+-=()niakjmt" if c == "^" else "0123456789+-=()"
            if inner and all(ch in allowed for ch in inner):
                out.append(inner.translate(table))
            elif len(inner) <= 1 or re.fullmatch(r"[\w.]+", inner):
                out.append(c + inner)
            else:
                out.append(c + "(" + inner + ")")
        elif c in "{}":
            i += 1
        elif c in "<>=":
            out.append(f" {c} ")
            i += 1
        else:
            out.append(c)
            i += 1
    s = "".join(out)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\( ", "(", s)
    s = re.sub(r" \)", ")", s)
    return s


def plain(s: str) -> str:
    """A title as plain words and Unicode for the canvas and plates."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\\\((.*?)\\\)", lambda m: plain_math(m.group(1)).strip(), s, flags=re.S)
    s = re.sub(r"\$([^$]+)\$", lambda m: plain_math(m.group(1)).strip(), s)
    s = re.sub(r"\\textup\{([^{}]*)\}|\\emph\{([^{}]*)\}|\\textit\{([^{}]*)\}", lambda m: next(g for g in m.groups() if g is not None), s)
    s = s.replace("~", " ").replace("--", "–")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- the model

def result_id(slug: str, st: dict) -> str:
    return "r:" + slug + ":" + (st.get("label") or f'L-{st.get("file")}-{st.get("line")}')


PR_THM = re.compile(r'<div class="pr-thm[^"]*"[^>]*?data-src="([^"]+):(\d+)"[^>]*>')
PR_NUM = re.compile(r'<span class="pr-thm-n">([^<]*)</span>')


def printed_numbers(slug: str) -> dict:
    """(file, line) -> the statement's printed head on the reading page ("Theorem 1.1")."""
    p = OUT / "papers" / f"{slug}.html"
    if not p.exists():
        return {}
    t = p.read_text(encoding="utf-8")
    out = {}
    for m in PR_THM.finditer(t):
        window = t[m.end():m.end() + 900]
        nxt = window.find('<div class="pr-thm')
        if nxt >= 0:
            window = window[:nxt]
        n = PR_NUM.search(window)
        if n:
            out[(m.group(1), int(m.group(2)))] = html.unescape(n.group(1)).strip()
    return out


def build_model():
    fams, papers, results, leans = [], [], [], []
    fam_index = {f["id"]: i for i, f in enumerate(S.FAMILIES)}
    lean_index = {}
    disc_of = {}
    disciplines = []
    for di, d in enumerate(S.DISCIPLINES):
        disciplines.append({"id": "d:" + S.DISC_SLUG[di], "name": d["name"], "families": []})
        for fid in d["families"]:
            disc_of[fid] = di
    # Families in OpenAI's order: discipline by discipline, as disciplines.json lists them.
    order = [fid for d in S.DISCIPLINES for fid in d["families"]]
    assert len(order) == len(set(order)) == len(S.FAMILIES), "every family sits in exactly one discipline"
    fi_of = {}
    for fid in order:
        f = S.FAM[fid]
        fi = len(fams)
        fi_of[fid] = fi
        disciplines[disc_of[fid]]["families"].append(fi)
        hol = sum(len(v["value"]) for v in S.sourced_all(f, "hol_checks"))
        fin_c = fin_o = 0
        for v in S.sourced_all(f, "finite_checks"):
            for x in v["value"]:
                if x.get("verdict") == "certified":
                    fin_c += 1
                else:
                    fin_o += 1
        fams.append({"id": "f:" + fid, "num": fid, "title": plain(f["title"]), "d": disc_of[fid], "papers": [], "lean": [],
                     "hol": hol, "fin": fin_c, "finOther": fin_o, "readers": f.get("readers_agreement") or "none",
                     "href": f"families/{fid}.html",
                     "findings": len(S.COMMUNITY["by_family"].get(fid, []))})
    numbers_cache = {}
    for fid in order:
        f, fi = S.FAM[fid], fi_of[fid]
        for k, slug in enumerate(f["manuscripts"]):
            m = S.MS[slug]
            assert m["status"] == "current", slug
            pi = len(papers)
            fams[fi]["papers"].append(pi)
            href = f"papers/{quote(slug)}.html" if slug in S.PAPER_READING else None
            papers.append({"id": "p:" + slug, "f": fi, "title": plain(m["title"]), "lead": k == 0, "results": [],
                           "href": href, "pdf": m["pdf_url"]})
            nums = numbers_cache.setdefault(slug, printed_numbers(slug))
            for st in S.headline_statements(m):
                ri = len(results)
                papers[pi]["results"].append(ri)
                head = nums.get((st.get("file"), st.get("line")))
                results.append({"id": result_id(slug, st), "p": pi, "f": fi, "kind": st.get("display") or st.get("kind", "").title(),
                                "num": head, "title": plain(st["title"]) if st.get("title") else None, "lean": [],
                                "href": S.paper_statement_href(slug, st, "")})
        for sid in f["statements"]:
            s = S.ST[sid]
            assert s["families"] == [fid], sid
            li = len(leans)
            lean_index[sid] = li
            fams[fi]["lean"].append(li)
            acc = sorted({r["source"] for r in S.sourced_all(s, "replay") if r["value"].get("verdict") == "accepted"})
            leans.append({"id": "l:" + sid, "f": fi, "name": sid, "label": plain((s.get("labels") or [sid])[0]),
                          "acc": acc, "holes": len(s["comparator"].get("definition_names") or []),
                          "main": bool(s.get("main_result")), "results": [], "href": f"statements/{quote(sid)}.html"})
    res_of = {r["id"]: i for i, r in enumerate(results)}
    assert len(res_of) == len(results), "result ids are unique"
    # Candidate pairings, chosen automatically by word overlap (build_site.pair_statement).
    pairs = 0
    for sid, li in lean_index.items():
        m, st, why = S.pair_statement(S.ST[sid])
        if not m:
            continue
        ri = res_of.get(result_id(m["id"], st))
        if ri is None:
            continue
        if results[ri]["f"] != leans[li]["f"]:
            continue
        results[ri]["lean"].append(li)
        leans[li]["results"].append(ri)
        pairs += 1
    # Citations between families, from the manuscripts' bibliographies (graph.json):
    # each current-to-current manuscript edge across two families, kept per paper.
    pi_of = {p["id"][2:]: i for i, p in enumerate(papers)}
    links = defaultdict(lambda: [0, 0])   # (lo, hi) -> [lo cites hi, hi cites lo]
    paper_links = []                        # [citing paper, cited paper]
    seen = set()
    for e in S.GRAPH:
        a, b = pi_of.get(e["source"]), pi_of.get(e.get("target_latest") or e["target"])
        if a is None or b is None:
            continue
        fa, fb = papers[a]["f"], papers[b]["f"]
        if fa == fb or (a, b) in seen:
            continue
        seen.add((a, b))
        paper_links.append([a, b])
        lo, hi = min(fa, fb), max(fa, fb)
        links[(lo, hi)][0 if fa == lo else 1] += 1
    link_rows = [[lo, hi, w[0], w[1]] for (lo, hi), w in sorted(links.items())]
    for f in fams:
        f["cites"], f["citedBy"] = [], []
    for lo, hi, a, b in link_rows:
        if a:
            fams[lo]["cites"].append([hi, a])
            fams[hi]["citedBy"].append([lo, a])
        if b:
            fams[hi]["cites"].append([lo, b])
            fams[lo]["citedBy"].append([hi, b])
    for d in disciplines:
        d["results"] = sum(len(papers[p]["results"]) for fi in d["families"] for p in fams[fi]["papers"])
        d["lean"] = sum(len(fams[fi]["lean"]) for fi in d["families"])
        d["papers"] = sum(len(fams[fi]["papers"]) for fi in d["families"])
    return {"disciplines": disciplines, "families": fams, "papers": papers, "results": results, "lean": leans,
            "links": link_rows, "paperLinks": paper_links, "pairs": pairs}


# ---------------------------------------------------------------- one family's map

TAU = 2 * math.pi


def wrap(a):
    a %= TAU
    return a + TAU if a < 0 else a


def turn(a, b):
    d = wrap(b - a)
    return d - TAU if d > math.pi else d


def circ_mean(angles):
    x = sum(math.cos(a) for a in angles)
    y = sum(math.sin(a) for a in angles)
    return math.atan2(y, x) if abs(x) + abs(y) > 1e-9 else angles[0]


def spread(pref, min_gap, fixed_weight=0.35, rounds=400):
    """Angles near their preferred places, no two closer than min_gap round the circle."""
    n = len(pref)
    if n <= 1:
        return list(pref)
    min_gap = min(min_gap, TAU / n * 0.98)
    a = list(pref)
    for _ in range(rounds):
        order = sorted(range(n), key=lambda i: wrap(a[i]))
        moved = False
        for k in range(n):
            i, j = order[k], order[(k + 1) % n]
            gap = wrap(a[j] - a[i]) if n > 1 else TAU
            if gap < min_gap - 1e-9:
                push = (min_gap - gap) / 2
                a[i] -= push
                a[j] += push
                moved = True
        for i in range(n):
            a[i] += turn(a[i], pref[i]) * fixed_weight * 0.05
        if not moved:
            break
    return [wrap(x) for x in a]


def family_map(model, fi, centre_of):
    """One family's map in its own unit disc (the family's cloud radius is 1).

    The lead paper is a ring at the centre with its headline results on it in
    reading order, clockwise from the top. Other papers are arcs of an orbit round
    it, each as long as its results need, in the family's order. The Lean
    statements stand on an outer ring, each turned toward the results paired with
    it. Citations to other families leave as fibres to an edge circle, each aimed
    at the other family's place in the release, so a fibre points the way to fly."""
    f = model["families"][fi]
    P = [model["papers"][p] for p in f["papers"]]
    has_lean = bool(f["lean"])
    outer = 0.72 if has_lean else 0.9
    rings, dots = [], {}
    top = -math.pi / 2
    if len(P) == 1:
        r = 0.58 * outer
        rings.append([0.0, 0.0, r4(r), r4(top), r4(top + TAU)])
        res = P[0]["results"]
        for j, ri in enumerate(res):
            a = top + TAU * j / max(1, len(res))
            dots[ri] = (r * math.cos(a), r * math.sin(a), a)
    else:
        lead = P[0]
        r0 = (0.27 if len(lead["results"]) <= 4 else 0.34) * outer
        rings.append([0.0, 0.0, r4(r0), r4(top), r4(top + TAU)])
        for j, ri in enumerate(lead["results"]):
            a = top + TAU * j / max(1, len(lead["results"]))
            dots[ri] = (r0 * math.cos(a), r0 * math.sin(a), a)
        r1 = 0.86 * outer
        others = P[1:]
        gap = min(0.22, 1.4 / len(others))
        weights = [len(p["results"]) + 0.9 for p in others]
        room = TAU - gap * len(others)
        a = top + gap / 2
        for p, w in zip(others, weights):
            span = room * w / sum(weights)
            rings.append([0.0, 0.0, r4(r1), r4(a), r4(a + span)])
            n = len(p["results"])
            for j, ri in enumerate(p["results"]):
                t = a + span * (j + 0.5) / n
                dots[ri] = (r1 * math.cos(t), r1 * math.sin(t), t)
            a += span + gap
    res_xy = {ri: [r4(x), r4(y)] for ri, (x, y, _) in dots.items()}
    lean_xy = {}
    rl = 0.93
    if has_lean:
        L = f["lean"]
        free = [top + TAU * (k + 0.5) / len(L) for k in range(len(L))]
        pref = []
        for k, li in enumerate(L):
            paired = [dots[ri][2] for ri in model["lean"][li]["results"] if ri in dots]
            pref.append(circ_mean(paired) if paired else free[k])
        ang = spread(pref, 0.34)
        for li, a in zip(L, ang):
            lean_xy[li] = [r4(rl * math.cos(a)), r4(rl * math.sin(a))]
    # Fibres: one end per other family, aimed at that family's place in the release.
    cx, cy = centre_of(fi)
    ends = {}
    for pa, pb in model["paperLinks"]:
        fa, fb = model["papers"][pa]["f"], model["papers"][pb]["f"]
        if fa == fi:
            g, own, way = fb, pa, 1
        elif fb == fi:
            g, own, way = fa, pb, 2
        else:
            continue
        e = ends.setdefault(g, {"g": g, "way": 0, "papers": []})
        e["way"] |= way
        if own not in e["papers"]:
            e["papers"].append(own)
    fibres = []
    if ends:
        gs = sorted(ends)
        pref = []
        for g in gs:
            gx, gy = centre_of(g)
            pref.append(math.atan2(gy - cy, gx - cx))
        ang = spread(pref, 0.42, rounds=600)
        for g, a in zip(gs, ang):
            e = ends[g]
            fibres.append([r4(a), g, e["way"], [f["papers"].index(p) for p in e["papers"]]])
    return {"rings": rings, "res": res_xy, "lean": lean_xy, "leanR": rl if has_lean else 0, "fibres": fibres}


# ---------------------------------------------------------------- the wheel

def cloud_radius(n: int) -> float:
    return 0.95 * math.sqrt(max(1, n)) + 0.75


def pack_sector(items, a0, a1, r_in, gap):
    """Pack circles into the annular sector [a0, a1] beyond r_in, nearest the
    inner rim first and, among equals, earliest round the sector, so a sector
    fills row by row in the family order. items: [(key, r)] -> {key: (rho, theta)}."""
    placed = []  # (x, y, r)
    out = {}
    step = 0.0035
    for key, r in items:
        best = None
        th = a0
        while th <= a1 + 1e-9:
            rho = r_in + r
            for _ in range(60):
                # Respect the sector's sides at this radius.
                half = math.asin(min(1.0, (r + gap * 0.5) / rho))
                if th - half < a0 - 1e-9 or th + half > a1 + 1e-9:
                    # Further out the sector is wider: go out until the circle fits between its sides.
                    side = min(th - a0, a1 - th)
                    if side <= 1e-4:
                        rho = None
                        break
                    rho = max(rho + 1e-6, (r + gap * 0.5) / math.sin(min(side, math.pi / 2 - 1e-3)))
                    continue
                x, y = rho * math.cos(th), rho * math.sin(th)
                hit = None
                for (px, py, pr) in placed:
                    need = r + pr + gap
                    dx, dy = x - px, y - py
                    if dx * dx + dy * dy < need * need - 1e-9:
                        # The smallest radius along this ray past which it clears this circle.
                        b = px * math.cos(th) + py * math.sin(th)
                        c = px * px + py * py - need * need
                        disc = b * b - c
                        far = b + math.sqrt(max(0.0, disc))
                        hit = max(hit or 0.0, far + 1e-6)
                if hit is None:
                    break
                rho = hit
            if rho is not None and (best is None or rho < best[0] - 1e-6):
                best = (rho, th)
            th += step
        if best is None:
            raise SystemExit(f"sector too narrow for item {key}")
        rho, th = best
        placed.append((rho * math.cos(th), rho * math.sin(th), r))
        out[key] = (rho, th)
    return out


def build_layout(model):
    fams = model["families"]
    n_dots = [sum(len(model["papers"][p]["results"]) for p in f["papers"]) + len(f["lean"]) for f in fams]
    radii = [cloud_radius(n) for n in n_dots]
    gap = 0.9
    discs = model["disciplines"]
    # Each sector as wide as its families need, with a floor, OpenAI's order clockwise from the top.
    area = [sum(math.pi * (radii[fi] + gap / 2) ** 2 for fi in d["families"]) for d in discs]
    sector_gap = 0.045
    floor = 0.16
    room = TAU - sector_gap * len(discs)
    total = sum(area)
    share = [max(floor, room * a / total) for a in area]
    scale = room / sum(share)
    share = [s * scale for s in share]
    r_in = 46.0
    sectors, centre = [], {}
    a = -math.pi / 2 + sector_gap / 2
    for di, d in enumerate(discs):
        a0, a1 = a, a + share[di]
        items = [(fi, radii[fi]) for fi in d["families"]]
        got = pack_sector(items, a0, a1, r_in, gap)
        for fi, (rho, th) in got.items():
            centre[fi] = (rho * math.cos(th), rho * math.sin(th), th)
        r_out = max(got[fi][0] + radii[fi] for fi in d["families"])
        sectors.append([r4(a0), r4(a1), r4((a0 + a1) / 2), r4(r_out)])
        a = a1 + sector_gap
    r_out = max(s[3] for s in sectors)
    fam_rows = [[r4(centre[fi][0]), r4(centre[fi][1]), r4(radii[fi]), r4(centre[fi][2])] for fi in range(len(fams))]
    maps = [family_map(model, fi, lambda g: centre[g][:2]) for fi in range(len(fams))]
    res_pos = [None] * len(model["results"])
    lean_pos = [None] * len(model["lean"])
    paper_rings = [None] * len(model["papers"])
    fibres, lean_r = [], []
    for fi, mp in enumerate(maps):
        for ri, xy in mp["res"].items():
            res_pos[ri] = xy
        for li, xy in mp["lean"].items():
            lean_pos[li] = xy
        for k, p in enumerate(fams[fi]["papers"]):
            paper_rings[p] = mp["rings"][k]
        fibres.append(mp["fibres"])
        lean_r.append(mp["leanR"])
    missing = [model["results"][i]["id"] for i, v in enumerate(res_pos) if v is None]
    missing += [model["lean"][i]["id"] for i, v in enumerate(lean_pos) if v is None]
    assert not missing, f"objects without a place: {missing[:5]}"
    return {"wheel": {"rIn": r_in, "rOut": r4(r_out), "sectors": sectors, "gap": sector_gap},
            "families": fam_rows, "papers": paper_rings, "results": res_pos, "lean": lean_pos,
            "leanR": lean_r, "fibres": fibres}


# ---------------------------------------------------------------- panel detail

def source_names():
    return {k: S.source_credit(k) for k in S.SOURCES}


def finding_rows(finds):
    rows = []
    for f in sorted(finds, key=lambda x: x["date"]):
        e = S.COMMUNITY["efforts"].get(f["effort"], {})
        kinds = S.C("community.finding_kinds") if isinstance(S.C("community.finding_kinds"), dict) else {}
        rows.append({"kind": kinds.get(f["kind"], f["kind"]), "summary": f["summary"], "who": S.credit_names(e),
                     "effort": e.get("name", ""), "date": f["date"], "url": f["url"]})
    return rows


def build_detail(model):
    """The panel's words, one shard per discipline: each result's statement typeset
    as the family pages typeset it (TeX spans for KaTeX), each Lean statement's
    re-runs and holes, each family's description and outside checks."""
    shards = [{"results": {}, "lean": {}, "families": {}, "macros": {}} for _ in model["disciplines"]]
    for fi, f in enumerate(model["families"]):
        fid = f["num"]
        fam = S.FAM[fid]
        sh = shards[f["d"]]
        hol = [{"card": c.get("card"), "text": c.get("certifies"), "url": c.get("url")}
               for v in S.sourced_all(fam, "hol_checks") for c in v["value"]]
        fin = [{"verdict": c.get("verdict"), "text": c.get("text"), "scope": c.get("scope"), "url": c.get("url") or ""}
               for v in S.sourced_all(fam, "finite_checks") for c in v["value"]]
        sh["families"][f["id"]] = {
            "titleHtml": S.rich(fam["title"]),
            "description": S.rich(fam["description"]),
            "hol": hol, "finite": fin,
            "findings": finding_rows(S.COMMUNITY["by_family"].get(fid, [])),
        }
        for pi in f["papers"]:
            p = model["papers"][pi]
            slug = p["id"][2:]
            m = S.MS[slug]
            sh["macros"][p["id"]] = (m.get("tex") or {}).get("macros") or {}
            conv = S.TexConv(m, "")
            stmts = {result_id(slug, st): st for st in S.headline_statements(m)}
            for ri in p["results"]:
                r = model["results"][ri]
                st = stmts[r["id"]]
                sec = U("result.appendix") if st.get("appendix") else U("result.section", n=st.get("section") or "?")
                sh["results"][r["id"]] = {
                    "html": conv.blocks(st["text"]),
                    "titleHtml": conv.text(st["title"], inline=True) if st.get("title") else None,
                    "where": sec + (f', {st["section_title"]}' if st.get("section_title") else ""),
                    "paperHtml": S.rich(m["title"]),
                    "source": f'{S.BASE_BLOB}preprints/{slug}/{st["file"]}#L{st["line"]}',
                }
        for li in f["lean"]:
            L = model["lean"][li]
            s = S.ST[L["name"]]
            reruns = [{"source": v["source"], "verdict": v["value"].get("verdict"), "text": v["value"].get("text"),
                       "date": v["value"].get("date"), "url": v["value"].get("url")} for v in S.sourced_all(s, "replay")]
            sh["lean"][L["id"]] = {
                "docs": s.get("docstrings") or [],
                "labels": s.get("labels") or [],
                "snippet": S.lean_snippet_html(s, max_lines=14),
                "reruns": reruns,
                "holes": [n.split(".")[-1] for n in s["comparator"].get("definition_names") or []],
                "findings": finding_rows(S.COMMUNITY["by_statement"].get(L["name"], [])),
            }
    return shards


def build_search(model):
    rows = []
    for f in model["families"]:
        rows.append([f["id"], (f["num"] + " " + f["title"]).lower()])
    for p in model["papers"]:
        rows.append([p["id"], p["title"].lower()])
    for r in model["results"]:
        p = model["papers"][r["p"]]
        slug = p["id"][2:]
        st = next(st for st in S.headline_statements(S.MS[slug]) if result_id(slug, st) == r["id"])
        text = " ".join(x for x in [r["num"] or r["kind"], r["title"] or "", plain(st["text"]), st.get("label") or ""] if x)
        rows.append([r["id"], re.sub(r"\s+", " ", text).lower()])
    for L in model["lean"]:
        s = S.ST[L["name"]]
        text = " ".join([L["name"], " ".join(s.get("labels") or []), " ".join(s["comparator"]["theorem_names"]),
                         " ".join(s.get("docstrings") or []), " ".join(d["name"] for d in s.get("declarations") or [])])
        rows.append([L["id"], re.sub(r"\s+", " ", text).lower()])
    return rows


# ---------------------------------------------------------------- the page

def index_html(model):
    """The no-JavaScript map: every family to its results, with links."""
    out = ['<div class="u-index">']
    for d in model["disciplines"]:
        out.append(f'<details class="u-index__d"><summary><span class="u-index__dn">{esc(d["name"])}</span> '
                   f'<span class="u-index__dc">{esc(U("counts.families", n=len(d["families"])))}</span></summary><ul class="u-index__fams">')
        for fi in d["families"]:
            f = model["families"][fi]
            fam = S.FAM[f["num"]]
            out.append(f'<li class="u-index__f" data-o="{esc(f["id"])}"><a href="{esc(f["href"])}"><span class="u-index__num">{esc(f["num"])}</span> '
                       f'<span class="tex-auto">{S.rich(fam["title"])}</span></a>')
            out.append('<ul class="u-index__papers">')
            for pi in f["papers"]:
                p = model["papers"][pi]
                link = p["href"] or p["pdf"]
                out.append(f'<li data-o="{esc(p["id"])}"><a href="{esc(link)}">{esc(p["title"])}</a>')
                if p["results"]:
                    out.append('<ul class="u-index__results">')
                    for ri in p["results"]:
                        r = model["results"][ri]
                        name = r["num"] or r["kind"]
                        if r["title"]:
                            name += f' ({r["title"]})'
                        href = r["href"] or link
                        out.append(f'<li data-o="{esc(r["id"])}"><a href="{esc(href)}">{esc(name)}</a></li>')
                    out.append("</ul>")
                out.append("</li>")
            out.append("</ul>")
            if f["lean"]:
                out.append('<ul class="u-index__lean">')
                for li in f["lean"]:
                    L = model["lean"][li]
                    out.append(f'<li data-o="{esc(L["id"])}"><a href="{esc(L["href"])}"><code>{esc(L["name"])}</code></a> {esc(L["label"])}</li>')
                out.append("</ul>")
            out.append("</li>")
        out.append("</ul></details>")
    out.append("</div>")
    return "".join(out)


def page_body(model, gen, counts):
    data_v = gen[:12]
    lede = U("page.lede", families=counts["families"])
    summary = U("release.summary", **{k: counts[k] for k in ("families", "disciplines", "papers", "results", "lean")})
    canvas_label = U("controls.canvas_label", families=counts["families"], disciplines=counts["disciplines"])
    copy_json = json.dumps(COPY_U, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<div class="u-explorer" data-universe data-view="list"
 data-universe-data="data/universe-data.json?v={data_v}" data-universe-layout="data/universe-layout.json?v={data_v}"
 data-universe-detail="data/universe-detail-{{d}}.json?v={data_v}" data-universe-search="data/universe-search.json?v={data_v}"
 data-generation="{esc(gen)}">
 <div class="u-switch" role="group" aria-label="{esc(U('switch.label'))}">
  <button type="button" class="u-switch__b" data-u-show="list" aria-pressed="true">{esc(U('switch.list'))}</button>
  <button type="button" class="u-switch__b" data-u-show="map" aria-pressed="false">{esc(U('switch.map'))}</button>
 </div>
 <aside class="u-panel" aria-labelledby="u-title">
  <div class="u-panel__head">
   <nav class="u-trail" aria-label="{esc(U('levels.trail_label'))}" data-u-trail></nav>
   <h1 class="u-title" id="u-title">{esc(U('page.title'))}</h1>
   <form class="u-search" role="search" data-u-search-form onsubmit="return false">
    <label class="u-visually-hidden" for="u-search-in">{esc(U('search.label'))}</label>
    <input id="u-search-in" class="u-search__in" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(U('search.placeholder'))}" data-u-search>
   </form>
  </div>
  <div class="u-panel__body" data-u-scroll>
   <div class="u-results" data-u-results hidden></div>
   <div class="u-view" data-u-view>
    <p class="u-lede">{esc(lede)}</p>
    <p class="u-summary">{esc(summary)}</p>
    <p class="u-note">{esc(U('controls.help'))}</p>
   </div>
   <section class="u-legend" aria-labelledby="u-legend-h" data-u-legend>
    <h2 class="u-h2" id="u-legend-h">{esc(U('legend.heading'))}</h2>
    <div data-u-legend-body></div>
   </section>
   <section class="u-listsec" aria-labelledby="u-index-h">
    <h2 class="u-h2" id="u-index-h">{esc(U('release.index_heading'))}</h2>
    <p class="u-note">{esc(U('release.index_intro'))}</p>
    <noscript><p class="u-note">{esc(U('page.noscript'))}</p></noscript>
    {index_html(model)}
   </section>
  </div>
 </aside>
 <div class="u-stage" data-u-stage>
  <canvas class="u-canvas" role="img" aria-label="{esc(canvas_label)}" tabindex="0" data-u-canvas></canvas>
  <div class="u-plate-live u-visually-hidden" aria-live="polite" data-u-live></div>
  <div class="u-tools">
   <button type="button" class="u-tool" data-u-zoom="in" aria-label="{esc(U('controls.zoom_in'))}" title="{esc(U('controls.zoom_in'))}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg></button>
   <button type="button" class="u-tool" data-u-zoom="out" aria-label="{esc(U('controls.zoom_out'))}" title="{esc(U('controls.zoom_out'))}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10"/></svg></button>
   <button type="button" class="u-tool" data-u-zoom="fit" aria-label="{esc(U('controls.fit'))}" title="{esc(U('controls.fit'))}"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5"/><circle cx="8" cy="8" r="1.4"/></svg></button>
  </div>
  <p class="u-status" data-u-status>{esc(U('status.loading'))}</p>
 </div>
 <script type="application/json" id="universe-copy">{copy_json}</script>
</div>"""


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def main():
    import_site()
    if not (OUT / "index.html").exists():
        raise SystemExit("site/_build is missing: run scripts/build_site.py (and build_papers.py) first")
    model = build_model()
    layout = build_layout(model)
    detail = build_detail(model)
    search = build_search(model)
    counts = {"families": len(model["families"]), "disciplines": len(model["disciplines"]),
              "papers": len(model["papers"]), "results": len(model["results"]), "lean": len(model["lean"]),
              "pairs": model["pairs"], "links": sum(a + b for _, _, a, b in model["links"]),
              "familyPairs": len(model["links"])}
    data = {k: model[k] for k in ("disciplines", "families", "papers", "results", "lean", "links")}
    data["sources"] = source_names()
    data["counts"] = counts
    # The generation id is the hash of the data, the geometry and the panel's words,
    # so an unchanged release rebuilds to the same id and the same links.
    h = hashlib.sha256()
    h.update(canonical(data))
    h.update(canonical(layout))
    for sh in detail:
        h.update(canonical(sh))
    gen = h.hexdigest()[:20]
    contract = [{"generation_id": gen, "upstream_commit": S.COMMIT, "counts": counts,
                 "ids": "f:<family id>, d:<discipline slug>, p:<manuscript slug>, r:<manuscript slug>:<TeX label or L-<file>-<line>>, l:<Lean statement id>",
                 "pairing": "build_site.pair_statement: chosen automatically by word overlap, not reviewed"}]
    data = {"generation_id": gen, "contract": contract, **data}
    layout = {"generation_id": gen, "contract": contract, **layout}
    ddir = OUT / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    (ddir / "universe-data.json").write_text(dump(data), encoding="utf-8")
    (ddir / "universe-layout.json").write_text(dump(layout), encoding="utf-8")
    for di, sh in enumerate(detail):
        (ddir / f"universe-detail-{di}.json").write_text(dump({"generation_id": gen, **sh}), encoding="utf-8")
    (ddir / "universe-search.json").write_text(dump({"generation_id": gen, "rows": search}), encoding="utf-8")
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    for name in OWN_ASSETS:
        shutil.copy(ASSETS / name, OUT / "assets" / name)
    extra = ('<link rel="stylesheet" href="assets/universe.css">\n'
             '<link rel="preload" href="data/universe-data.json?v=' + gen[:12] + '" as="fetch" crossorigin>\n'
             '<link rel="preload" href="data/universe-layout.json?v=' + gen[:12] + '" as="fetch" crossorigin>\n'
             '<meta name="format-detection" content="telephone=no">\n'
             '<script defer src="assets/universe.js"></script>')
    body = page_body(model, gen, counts)
    html_text = S.page("universe.html", U("page.title"), U("page.description"), body, current="atlas",
                       extra_head=extra, main_class="u-main")
    (OUT / "universe.html").write_text(html_text, encoding="utf-8")
    sizes = {p.name: p.stat().st_size for p in sorted(ddir.glob("universe-*.json"))}
    total_detail = sum(v for k, v in sizes.items() if "detail" in k)
    print(f"universe: generation {gen}; {counts['families']} families, {counts['papers']} papers, "
          f"{counts['results']} headline results, {counts['lean']} Lean statements, {counts['pairs']} candidate pairings, "
          f"{counts['familyPairs']} family pairs from {counts['links']} citing links")
    print(f"universe: data {sizes['universe-data.json']:,} B, layout {sizes['universe-layout.json']:,} B, "
          f"search {sizes['universe-search.json']:,} B, detail {total_detail:,} B in {len(detail)} files; "
          f"page {(OUT / 'universe.html').stat().st_size:,} B")


if __name__ == "__main__":
    main()
