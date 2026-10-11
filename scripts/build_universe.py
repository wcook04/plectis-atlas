#!/usr/bin/env python3
"""Build the release universe: one map of every family of OpenAI's mathematics
release, each family drawn as a small map of its own, placed by discipline, with
the citations between families drawn as fibres. A family opens into its own map:
its papers as rings, each headline result a dot, its Lean statements, threads from
each paired result to its Lean statement and fibres out to the families it cites.

Writes, after scripts/build_site.py and scripts/build_papers.py have run (into the
same --out, default site/_build):

    index.html                                    the front page: the map, then its bands
    universe.html                                 a redirect to index.html, kept for old links
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

import argparse
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


NUMBERS = ROOT / "data" / "statement_numbers.json"


def load_printed_numbers() -> dict:
    """(manuscript, file, line) -> (kind, number or None) from data/statement_numbers.json,
    the number each statement prints on its reading page (build_papers.py writes it). A
    row is used only while its statement_sha256 matches the statement in manuscripts.json,
    so a changed statement never borrows an old number. A row whose number is null is an
    unnumbered statement; a statement with no row has no number available."""
    if not NUMBERS.exists():
        return {}
    raw = json.loads(NUMBERS.read_text(encoding="utf-8"))
    return {(r["manuscript"], r["file"], r["line"]): r for r in raw.get("rows") or []}


PRINTED = {}


def printed_head(slug: str, st: dict):
    """("Theorem 1.1", False), (None, True) for an unnumbered statement, or (None, False)."""
    r = PRINTED.get((slug, st.get("file"), st.get("line")))
    if not r or (r.get("statement_sha256") and st.get("sha256") and r["statement_sha256"] != st["sha256"]):
        return None, False
    if r.get("number") is None:
        return None, True
    return f'{r.get("kind") or st.get("display") or ""} {r["number"]}'.strip(), False


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
            for st in S.headline_statements(m):
                ri = len(results)
                papers[pi]["results"].append(ri)
                head, unnumbered = printed_head(slug, st)
                row = {"id": result_id(slug, st), "p": pi, "f": fi, "kind": st.get("display") or st.get("kind", "").title(),
                       "num": head, "title": plain(st["title"]) if st.get("title") else None, "lean": [],
                       "href": S.paper_statement_href(slug, st, "")}
                if unnumbered:
                    row["nn"] = 1
                results.append(row)
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
                    "html": keep_punctuation(conv.blocks(st["text"])),
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
        out.append(f'<details class="u-index__d" id="idx-{esc(d["id"][2:])}"><summary><span class="u-index__dn">{esc(d["name"])}</span> '
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


# Verdicts that would mean an outside group rejected a Lean file's proof. None of the
# recorded re-runs uses one today ("not-decided" is cert-machine refusing to decide,
# "built" is MathVet building without a verdict); the words stay ready if one does.
REJECTED = {"rejected", "failed", "fail"}


def rerun_records():
    """Per group: files re-run and how many of each verdict; per Lean file: accepted and
    rejected groups. Read from statements.json's sourced replay records."""
    by_group, by_file = {}, {}
    for st in S.STATEMENTS:
        acc, rej, any_run = set(), set(), False
        for v in S.sourced_all(st, "replay"):
            any_run = True
            g = by_group.setdefault(v["source"], {"runs": 0, "verdicts": {}})
            g["runs"] += 1
            verdict = v["value"].get("verdict") or "unknown"
            g["verdicts"][verdict] = g["verdicts"].get(verdict, 0) + 1
            if verdict == "accepted":
                acc.add(v["source"])
            elif verdict in REJECTED:
                rej.add(v["source"])
        by_file[st["id"]] = {"run": any_run, "acc": acc, "rej": rej}
    return by_group, by_file


def verdict_phrase(g) -> str:
    """"398 accepted and 18 not decided", "192 of 192 accepted": a group's verdicts in words."""
    parts = []
    order = ["accepted"] + sorted(k for k in g["verdicts"] if k != "accepted")
    for k in order:
        n = g["verdicts"].get(k, 0)
        if not n:
            continue
        if k == "accepted" and n == g["runs"]:
            parts.append(U("bands.verdict_accepted_all", n=n))
        elif ("verdict_" + k) in COPY_U["bands"]:
            parts.append(U("bands.verdict_" + k, n=n))
        else:
            parts.append(U("bands.verdict_other", n=n, verdict=k.replace("-", " ")))
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def ground_sentence() -> str:
    """The first screen's grounding of "checked": what the outside groups report, counted."""
    _, by_file = rerun_records()
    files = len(by_file)
    rerun = sum(1 for x in by_file.values() if x["run"])
    accepted = sum(1 for x in by_file.values() if x["acc"])
    rejected = sum(1 for x in by_file.values() if x["rej"])
    if rejected:
        return U("page.ground_rejected", rerun=rerun, files=files, accepted=accepted, rejected=rejected)
    if rerun == files:
        return U("page.ground_all", files=files, accepted=accepted)
    return U("page.ground_some", rerun=rerun, files=files, accepted=accepted)


KEEP_PUNCT = re.compile(r'(<span class="m">[^<]*</span>)([.,;:!?)\]]+)')


def keep_punctuation(html_text: str) -> str:
    """A formula keeps the punctuation that follows it on its own line: a full stop never
    wraps away from the formula before it."""
    return KEEP_PUNCT.sub(r'<span class="u-nobr">\1\2</span>', html_text)


def linked(template: str, **parts) -> str:
    """A copy sentence with its {placeholders} filled by HTML (each number a link);
    the sentence's own words are escaped."""
    out = esc(template)
    for k, v in parts.items():
        out = out.replace("{" + k + "}", v)
    return out


def num_link(n, href: str) -> str:
    return f'<a class="u-num" href="{esc(href)}">{n:,}</a>' if isinstance(n, int) else f'<a class="u-num" href="{esc(href)}">{esc(n)}</a>'


def ways_html(model) -> str:
    """Four ways in, chosen by how widely the problem is known, each a link to its
    family page that the map turns into a flight."""
    fam_by = {f["num"]: f for f in model["families"]}
    rows = []
    for w in COPY_U["ways"]["items"]:
        f = fam_by.get(w["family"])
        if not f:
            continue
        rows.append(f'<li><a class="u-way" href="{esc(f["href"])}" data-go="{esc(f["id"])}">'
                    f'<span class="u-way__t">{esc(w.get("name") or f["title"])}</span>'
                    f'<span class="u-way__w">{esc(w["why"])}</span></a></li>')
    key = (f'<ul class="u-keyline" aria-label="{esc(U("legend.heading"))}">'
           f'<li><svg class="u-sw u-sw-lean3" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 1.6 12.4 7 7 12.4 1.6 7Z"/></svg>{esc(U("ways.key_lean"))}</li>'
           f'<li><svg class="u-sw u-sw-paired" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="4"/></svg>{esc(U("ways.key_result"))}</li>'
           f'<li><svg class="u-sw u-sw-hol" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.4"/></svg>{esc(U("ways.key_ring"))}</li>'
           f'<li class="u-keyline__more"><a href="#u-legend-h">{esc(U("ways.key_more"))}</a></li></ul>')
    return (f'{key}<h2 class="u-h2 u-h2--ways">{esc(U("ways.heading"))}</h2><ul class="u-ways">{"".join(rows)}</ul>')


def exact_bench(f) -> bool:
    """A family whose bench is exact, the rule for the home page's worked example:
    - its papers have one headline theorem, and the family has one Lean statement;
    - the atlas pairs that Lean statement with that theorem (a candidate pairing);
    - both outside readers class the Lean as stating all of the headline (cert-machine
      "matches", MathVet "full"), and neither names a missing part: cert-machine records
      no gap, and MathVet's note says "None" or is empty, with no definitions to check."""
    if f.get("readers_agreement") != "agree-full" or len(f["statements"]) != 1:
        return False
    heads = [st for slug in f["manuscripts"] for st in S.headline_statements(S.MS[slug])]
    if len(heads) != 1:
        return False
    m, st, _ = S.pair_statement(S.ST[f["statements"][0]])
    if not m or st is not heads[0]:
        return False
    for v in S.sourced_all(f, "scope_reading"):
        val = v["value"]
        if v["source"] == "cert-machine" and (val.get("verdict") != "matches" or (val.get("gap") or "").strip()):
            return False
        if v["source"] == "mathvet":
            note = (val.get("note") or "").strip()
            defs = (val.get("definitions_to_check") or "").strip()
            if val.get("verdict") != "full" or not (note == "" or note.lower().startswith("none")) or defs not in ("", "None", "None."):
                return False
    return True


def example_family() -> str:
    """The example family: the copy's preferred family when its bench is exact, else the
    first exact bench in the release's order, else the second way in."""
    exact = [f["id"] for d in S.DISCIPLINES for f in (S.FAM[x] for x in d["families"]) if exact_bench(f)]
    preferred = COPY_U["bands"].get("example_family")
    if preferred in exact:
        return preferred
    return exact[0] if exact else COPY_U["ways"]["items"][1]["family"]


def example_band(model) -> str:
    """One family read in full: the family desk's claim card when it exists, and
    otherwise the family's title, OpenAI's description and its first headline theorem."""
    fid = example_family()
    f = next(x for x in model["families"] if x["num"] == fid)
    fam = S.FAM[fid]
    card = ""
    if hasattr(S, "family_claim_card"):
        try:
            card = keep_punctuation(S.family_claim_card(fid, ""))
        except Exception as e:  # noqa: BLE001  (the other desk's function may be mid-edit)
            print(f"universe: family_claim_card({fid}) failed, using the fallback: {e}", file=sys.stderr)
            card = ""
    macros = ""
    stacked = bool(card)
    if card and hasattr(S, "family_claim_macro_ids"):
        macros = S.macros_script(S.family_claim_macro_ids(fid))
    if not card:
        lead = S.MS[fam["manuscripts"][0]]
        heads = S.headline_statements(lead)
        theorem = ""
        if heads:
            theorem = (f'<h3 class="u-h3">{esc(U("bands.example_theorem"))}</h3>'
                       + S.render_paper_statement(lead, heads[0], "", S.TexConv(lead, "")))
            macros = S.macros_script([lead["id"]])
        card = (f'<div class="u-example__card"><p class="u-example__num">{esc(U("family.short", num=fid))}</p>'
                f'<h3 class="u-example__title tex-auto">{S.rich(fam["title"])}</h3>'
                f'<div class="u-example__desc tex-auto">{S.rich(fam["description"])}</div>{theorem}</div>')
    return f"""<section class="u-band u-band--example{' u-band--bench' if stacked else ''}" id="example" aria-labelledby="h-example">
 <div class="frame u-band__in">
  <div class="u-band__head">
   <h2 class="u-band__h" id="h-example">{esc(U('bands.example_heading'))}</h2>
   <p class="u-band__intro">{esc(U('bands.example_intro'))}</p>
   <p class="u-band__links"><a href="{esc(f['href'])}">{esc(U('bands.example_read'))}</a><a href="index.html#o={esc(f['id'])}" data-go="{esc(f['id'])}">{esc(U('bands.example_map'))}</a></p>
  </div>
  <div class="u-example">{card}</div>
 </div>
 {macros}
</section>"""


def release_band(model, counts) -> str:
    s = S.SUMMARY
    acc = [0, 0, 0, 0]
    for L in model["lean"]:
        acc[min(3, len(L["acc"]))] += 1
    n = lambda key: num_link(s[key], f"numbers.html#{key}")
    sentences = [
        linked(U("bands.release_s1"), papers=n("manuscripts_current"), families=n("families"), disciplines=n("disciplines")),
        linked(U("bands.release_s2"), lean=n("statements_lean"), families_with_lean=n("families_with_lean"),
               main=n("statements_lean_main_results")),
        linked(U("bands.release_s3"), lean=n("statements_lean"), acc3=num_link(acc[3], "statements.html"),
               acc0=num_link(acc[0], "statements.html")),
        esc(runs_sentence()),
        linked(U("bands.release_s4"), pairs=num_link(counts["pairs"], "statements.html")),
        linked(U("bands.release_s5"), edges=n("internal_citation_edges"), works=n("external_works_cited")),
        linked(U("bands.release_s6"), withdrawn=n("manuscripts_withdrawn"), previous=n("manuscripts_previous_editions")),
    ]
    return f"""<section class="u-band u-band--release" id="release" aria-labelledby="h-release">
 <div class="frame u-band__in u-band__in--split">
  <h2 class="u-band__h" id="h-release">{esc(U('bands.release_heading'))}</h2>
  <div class="u-sentences">{''.join(f'<p>{x}</p>' for x in sentences)}
   <p class="u-band__links"><a href="numbers.html">{esc(U('bands.release_numbers'))}</a><a href="tiles.html">{esc(U('bands.release_tiles'))}</a></p>
  </div>
 </div>
</section>"""


def runs_sentence() -> str:
    """Each group's verdicts, then whether any re-run reports a rejection."""
    by_group, by_file = rerun_records()
    parts = [U("bands.run_phrase", who=S.source_credit(g), verdicts=verdict_phrase(by_group[g]))
             for g in ("cert-machine", "mathvet", "nealmcb-lean-tooling") if g in by_group]
    parts += [U("bands.run_phrase", who=S.source_credit(g), verdicts=verdict_phrase(v))
              for g, v in sorted(by_group.items()) if g not in ("cert-machine", "mathvet", "nealmcb-lean-tooling")]
    joined = "; ".join(parts)
    joined = joined[:1].upper() + joined[1:]
    rejected = any(x["rej"] for x in by_file.values())
    return U("bands.release_runs_rejected" if rejected else "bands.release_runs", runs=joined)


def checked_band(model) -> str:
    """Who has checked what, each record credited to the person or group who reports it."""
    by_group, by_file = rerun_records()
    runs = {g: v["runs"] for g, v in by_group.items()}
    verdicts = {g: verdict_phrase(v) for g, v in by_group.items()}
    scope, finite, hol_fams, erdos_fams = {}, set(), set(), set()
    for f in S.FAMILIES:
        for v in S.sourced_all(f, "scope_reading"):
            scope[v["source"]] = scope.get(v["source"], 0) + 1
        if any(x.get("verdict") == "certified" for v in S.sourced_all(f, "finite_checks") for x in v["value"]):
            finite.add(f["id"])
        if S.sourced_all(f, "hol_checks"):
            hol_fams.add(f["id"])
        if S.sourced_all(f, "erdos_problems"):
            erdos_fams.add(f["id"])
    rows = []

    def row(src, sentence):
        if src not in S.SOURCES:
            return
        rows.append(f'<li><a class="u-who__n" href="sources.html#src-{esc(src)}">{esc(S.source_credit(src))}</a> '
                    f'<span class="u-who__w">{esc(sentence)}</span></li>')
    row("cert-machine", U("bands.checked_cert", runs=runs.get("cert-machine", 0), verdicts=verdicts.get("cert-machine", ""),
                         finite=len(finite), scope=scope.get("cert-machine", 0)))
    row("mathvet", U("bands.checked_mathvet", runs=runs.get("mathvet", 0), verdicts=verdicts.get("mathvet", ""),
                    scope=scope.get("mathvet", 0)))
    row("nealmcb-lean-tooling", U("bands.checked_neal", runs=runs.get("nealmcb-lean-tooling", 0),
                                 verdicts=verdicts.get("nealmcb-lean-tooling", "")))
    row("hol-cards", U("bands.checked_hol", families=len(hol_fams)))
    none_rejected = "" if any(x["rej"] for x in by_file.values()) else f'<p class="u-band__note">{esc(U("bands.checked_none_rejected"))}</p>'
    # A link to the problems a family addresses is not a check of it: Thomas Bloom's
    # erdosproblems.com stands on its own line after the checks.
    erdos = ""
    if "erdos-problems" in S.SOURCES:
        who = f'<a href="sources.html#src-erdos-problems">{esc(S.source_credit("erdos-problems"))}</a>'
        erdos = f'<p class="u-band__note">{linked(U("bands.checked_erdos", families=len(erdos_fams), who="{who}"), who=who)}</p>'
    # The same count and definition as the Sources page's own lede.
    people = len({(a.get("name") or a.get("handle")) for e in S.COMMUNITY["list"] for a in (e.get("authors") or [])})
    findings = len(S.COMMUNITY["findings"])
    return f"""<section class="u-band u-band--checked" id="checked" aria-labelledby="h-checked">
 <div class="frame u-band__in">
  <h2 class="u-band__h" id="h-checked">{esc(U('bands.checked_heading'))}</h2>
  <p class="u-band__intro">{esc(U('bands.checked_intro'))}</p>
  <ul class="u-who">{''.join(rows)}</ul>
  {none_rejected}
  {erdos}
  <p class="u-band__links"><span>{esc(U('bands.checked_more', people=people, findings=findings))}</span><a href="sources.html">{esc(U('bands.checked_more_link'))}</a></p>
 </div>
</section>"""


def help_band() -> str:
    start_here = S.REPO + "/tree/main/skills/start-here"
    return f"""<section class="u-band u-band--help" id="help" aria-labelledby="h-help">
 <div class="frame u-band__in">
  <h2 class="u-band__h" id="h-help">{esc(U('bands.help_heading'))}</h2>
  <p class="u-band__intro">{esc(U('bands.help_intro'))}</p>
  <div class="u-help2">
   <div><h3 class="u-h3">{esc(U('bands.help_without_heading'))}</h3><p>{esc(U('bands.help_without'))}</p><p><a href="contribute.html">{esc(U('bands.help_without_link'))}</a></p></div>
   <div><h3 class="u-h3">{esc(U('bands.help_with_heading'))}</h3><p>{esc(U('bands.help_with'))}</p><p><a class="ext" href="{esc(start_here)}" rel="noopener">{esc(U('bands.help_with_link'))}</a></p></div>
  </div>
  <p class="u-band__links"><span>{esc(U('bands.help_queue'))}</span><a href="explain.html#careful-reading">{esc(U('bands.help_queue_link'))}</a></p>
 </div>
</section>"""


def legend_html(model, sources) -> str:
    """The map's key, the same marks the canvas draws (universe.js keeps the glyph
    shapes in step), each with its count across the release."""
    acc, holes = [0, 0, 0, 0], 0
    for L in model["lean"]:
        acc[min(3, len(L["acc"]))] += 1
        holes += 1 if L["holes"] else 0
    paired = sum(1 for r in model["results"] if r["lean"])
    hol = sum(1 for f in model["families"] if f["hol"])
    fin = sum(1 for f in model["families"] if f["fin"])
    groups = [sources[k] for k in sources if any(k in L["acc"] for L in model["lean"])]
    by_group, _ = rerun_records()
    coverage = ", ".join(f'{sources.get(g, g)} {v["runs"]}' for g, v in by_group.items())

    def lean(n, with_holes=False):
        hole = '<circle cx="7" cy="7" r="1.8" class="u-sw-hole"/>' if with_holes else ""
        return (f'<svg class="u-sw u-sw-lean{n}{" u-sw-holes" if with_holes else ""}" viewBox="0 0 14 14" aria-hidden="true">'
                f'<path d="M7 1.6 12.4 7 7 12.4 1.6 7Z"/>{hole}</svg>')

    def dot(paired_):
        return f'<svg class="u-sw {"u-sw-paired" if paired_ else "u-sw-unpaired"}" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="4"/></svg>'

    def ring(cls):
        return f'<svg class="u-sw {cls}" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.4"/></svg>'

    def fib(cls):
        return f'<svg class="u-sw {cls}" viewBox="0 0 14 14" aria-hidden="true"><path d="M1 10 C5 10 9 4 13 4"/></svg>'

    def row(glyph, text, n=None):
        num = "" if n is None else f'<span class="u-key__n">{n:,}</span>'
        return f'<li><span class="u-key__g">{glyph}</span><span class="u-key__t">{esc(text)}</span>{num}</li>'

    return (f'<p class="u-note">{esc(U("legend.colour_note"))}</p>'
            f'<h3 class="u-h3">{esc(U("legend.lean_heading"))}</h3><ul class="u-key">'
            + row(lean(3), U("legend.lean_3"), acc[3]) + row(lean(2), U("legend.lean_2"), acc[2])
            + row(lean(1), U("legend.lean_1"), acc[1]) + row(lean(0), U("legend.lean_0"), acc[0])
            + row(lean(2, True), U("legend.lean_holes"), holes) + "</ul>"
            f'<p class="u-note">{esc(U("legend.lean_groups", groups="; ".join(groups)))}</p>'
            f'<p class="u-note">{esc(U("legend.coverage", runs=coverage))}</p>'
            f'<h3 class="u-h3">{esc(U("legend.result_heading"))}</h3><ul class="u-key">'
            + row(dot(True), U("legend.result_paired"), paired) + row(dot(False), U("legend.result_unpaired"), len(model["results"]) - paired) + "</ul>"
            f'<p class="u-note">{esc(U("legend.pair_note"))}</p>'
            f'<h3 class="u-h3">{esc(U("legend.family_heading"))}</h3><ul class="u-key">'
            + row(ring("u-sw-hol"), U("legend.family_hol"), hol) + row(ring("u-sw-fin"), U("legend.family_finite"), fin) + "</ul>"
            f'<h3 class="u-h3">{esc(U("legend.fibre_heading"))}</h3><ul class="u-key">'
            + row(fib("u-sw-cites"), U("legend.fibre_cites")) + row(fib("u-sw-cited"), U("legend.fibre_cited")) + "</ul>"
            f'<p class="u-note">{esc(U("legend.fibre_note"))}</p>')


def page_body(model, gen, counts):
    data_v = gen[:12]
    lede = U("page.lede", families=counts["families"])
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
   <p class="u-ground" data-u-ground>{esc(ground_sentence())}</p>
   <form class="u-search" role="search" data-u-search-form onsubmit="return false">
    <label class="u-visually-hidden" for="u-search-in">{esc(U('search.label'))}</label>
    <input id="u-search-in" class="u-search__in" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(U('search.placeholder'))}" data-u-search>
   </form>
  </div>
  <div class="u-panel__body" data-u-scroll>
   <div class="u-results" data-u-results hidden></div>
   <div class="u-view" data-u-view>
    <p class="u-lede">{esc(lede)}</p>
    {ways_html(model)}
   </div>
   <section class="u-legend" aria-labelledby="u-legend-h" data-u-legend>
    <h2 class="u-h2" id="u-legend-h">{esc(U('legend.heading'))}</h2>
    <noscript><p class="u-note">{esc(U('page.noscript'))} <a href="#catalogue">{esc(U('bands.index_heading'))}</a></p></noscript>
    <div data-u-legend-body>{legend_html(model, source_names())}</div>
    <p class="u-note">{esc(U('controls.help'))}</p>
    <p class="u-note"><a href="tiles.html">{esc(U('legend.tiles'))}</a></p>
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
</div>
{example_band(model)}
{release_band(model, counts)}
{checked_band(model)}
{help_band()}
<section class="u-band u-band--index" id="catalogue" aria-labelledby="h-index" tabindex="-1">
 <div class="frame u-band__in">
  <h2 class="u-band__h" id="h-index">{esc(U('bands.index_heading'))}</h2>
  <p class="u-band__intro">{esc(U('bands.index_intro'))}</p>
  {index_html(model)}
 </div>
</section>"""


def redirect_stub() -> str:
    """universe.html, kept for old links: the map moved to the front page, deep link and all."""
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(U('page.redirect_title'))} | {esc(S.C('site.name'))}</title>
<link rel="canonical" href="{esc(S.BASE_URL)}">
<meta name="color-scheme" content="light dark">
<script>location.replace('index.html' + location.hash);</script>
<meta http-equiv="refresh" content="0; url=index.html">
</head>
<body>
<p>{esc(U('page.redirect_text'))} <a href="index.html">{esc(U('page.redirect_link'))}</a></p>
</body>
</html>
"""


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def main():
    global OUT, PRINTED
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", help="the built site to add the front page to (default site/_build)")
    args = ap.parse_args()
    if args.out:
        OUT = Path(args.out).resolve()
    import_site()
    if not (OUT / "tiles.html").exists() or not (OUT / "families").is_dir():
        raise SystemExit(f"{OUT} is not a built site: run scripts/build_site.py (and build_papers.py) with the same --out first")
    PRINTED = load_printed_numbers()
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
    h.update(canonical(search))
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
    if hasattr(S, "family_claim_card") and hasattr(S, "family_head"):
        extra = S.family_head("") + "\n" + extra
    html_text = S.page("index.html", U("page.title"), U("page.description"), body, current="map",
                       extra_head=extra, main_class="u-main")
    (OUT / "index.html").write_text(html_text, encoding="utf-8")
    (OUT / "universe.html").write_text(redirect_stub(), encoding="utf-8")
    sizes = {p.name: p.stat().st_size for p in sorted(ddir.glob("universe-*.json"))}
    total_detail = sum(v for k, v in sizes.items() if "detail" in k)
    print(f"universe: generation {gen}; {counts['families']} families, {counts['papers']} papers, "
          f"{counts['results']} headline results, {counts['lean']} Lean statements, {counts['pairs']} candidate pairings, "
          f"{counts['familyPairs']} family pairs from {counts['links']} citing links")
    print(f"universe: data {sizes['universe-data.json']:,} B, layout {sizes['universe-layout.json']:,} B, "
          f"search {sizes['universe-search.json']:,} B, detail {total_detail:,} B in {len(detail)} files; "
          f"page {(OUT / 'index.html').stat().st_size:,} B; numbered {sum(1 for r in model['results'] if r['num'])}, "
          f"unnumbered {sum(1 for r in model['results'] if r.get('nn'))}, of {len(model['results'])}")


if __name__ == "__main__":
    main()
