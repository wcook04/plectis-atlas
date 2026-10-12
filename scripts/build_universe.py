#!/usr/bin/env python3
"""Build the front door: our map of the release beside a readable list.

The map draws every family of OpenAI's mathematics release as a small map of its
own, placed in its discipline's sector of one wheel; each discipline is named on
the drawing with plain counts, and each family is coloured by one meaning, what
the outside readers find the release's Lean states for its headline. A family
opens into its own map: its papers by short title and date, their results by
printed number, its Lean statements by name, and the pairings between them.
Citations are drawn only for the selected family. The panel beside the map is
the list: the release in sentences, search, the colours in words, the
disciplines, and inside a discipline its families as plain entries.

Statement Map (scripts/reader.py, scripts/evidence.py) decides every fact: the
disciplines and their families, results and their printed numbers, Lean
statements and their re-runs, pairings, readings, citations between families
and every number in a sentence. Statement text is typeset from the Atlas's own
data/manuscripts.json, joined by the backend statement's manuscript, file and
line. This script only lays things out and words them through
site/copy_universe.json and site/copy_evidence.json.

Writes, after scripts/build_site.py has run (into the same --out, default site/_build):

    index.html                                    the map and the list, then the bands
    universe.html                                 a redirect to index.html, kept for old links
    site/_build/data/universe-data.json           the first screen: disciplines, families, citations
    site/_build/data/universe-parts.json          papers, results and Lean statements, loaded after it
    site/_build/data/universe-layout.json         where it is drawn
    site/_build/data/universe-detail-<n>.json     the list's words, one file per discipline
    site/_build/data/universe-search.json         the map's own search rows
    site/_build/assets/universe.js, universe.css

Every data file carries the backend's generation id; the page refuses a file from
another generation. Ids are the backend's reader ids, so a deep link #o=<id>
survives a rebuild and a change of layout.

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
import evidence as E  # noqa: E402
import reader as R  # noqa: E402
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

MONTHS = "January February March April May June July August September October November December".split()


def date_british(s: str | None) -> str | None:
    """"September 24, 2026" (the manuscript record's form) as "24 September 2026"."""
    m = re.match(r"^([A-Z][a-z]+) (\d{1,2}), (\d{4})$", s or "")
    if not m or m.group(1) not in MONTHS:
        return s or None
    return f"{int(m.group(2))} {m.group(1)} {m.group(3)}"


def short_title(title: str) -> str:
    """A paper's title, cut at its colon when the part before it names it."""
    t = plain(title)
    head = t.split(": ", 1)[0]
    return head if 12 <= len(head) < len(t) else t


def tone_class(ev) -> str:
    """The one meaning a family's colour carries: what the two outside readers find
    the release's Lean states for the family's headline, as the backend records it.
    Disagreement is the backend's own comparison; a reader's term is never merged."""
    if not ev.has_lean:
        return "none"
    if ev.agreement == "disagree":
        return "split"
    tones = [t for t in ev.tones if t != "none"]
    if not tones:
        return "unread"
    if all(t == "full" for t in tones):
        return "all"
    if "part" in tones:
        return "part"
    return "other"


TONE_ORDER = ("all", "part", "other", "split", "none", "unread")


def statement_label(st: dict | None, rv: dict | None = None) -> tuple[str, str | None, bool]:
    """(kind, printed label or None, unnumbered) for a reader statement record."""
    src = st or rv or {}
    kind = (st or {}).get("display") or (src.get("statement_kind") or "statement").capitalize()
    status = src.get("printed_number_status")
    num = src.get("printed_number") if status == "recorded" else None
    return kind, (f"{kind} {num}" if num else None), status == "unnumbered"


class Model:
    """What the map draws, read once from Statement Map through scripts/reader.py."""

    def __init__(self, r):
        self.r = r
        self.gen = r.generation
        self.evs = {ev.id: ev for ev in E.all_families(r)}
        self.docs = {fid: r.family(fid) for fid in self.evs}
        views = {v["id"]: v for v in r.universe["family_views"]}
        rviews = {v["id"]: v for v in r.universe["result_views"]}
        disciplines, fams, papers, results, leans = [], [], [], [], []
        fi_of, res_of, lean_of = {}, {}, {}
        self.pairs = 0
        for di, d in enumerate(r.universe["disciplines"]):
            disciplines.append({"id": d["id"], "name": d["name"], "families": [], "withLean": 0})
            for fid in d["family_ids"]:
                ev, doc, v = self.evs[fid], self.docs[fid], views[fid]
                fi = len(fams)
                fi_of[fid] = fi
                disciplines[di]["families"].append(fi)
                if ev.has_lean:
                    disciplines[di]["withLean"] += 1
                fams.append({"id": fid, "num": ev.num, "title": plain(ev.name), "d": di, "papers": [], "lean": [],
                             "tone": tone_class(ev), "ring": bool(ev.checks), "href": f"families/{ev.num}.html"})
                stmts = {s["id"]: s for s in doc.get("statements") or []}
                names = {p["id"]: p.get("name") or p["id"][2:] for p in doc.get("paper_history") or []}
                by_ms: dict[str, list] = defaultdict(list)
                for rid in v.get("results") or []:
                    rv = rviews.get(rid) or {}
                    st = stmts.get(rid)
                    ms = (st or rv).get("manuscript_id")
                    by_ms[ms].append((rv.get("reading_order", 0), rid, st, rv))
                # A statement a Lean statement is paired with is drawn too, even when it is
                # not one of the paper's flagged headline results, so every thread lands.
                targets = self._pair_targets(doc)
                for lid, (sid, state) in targets.items():
                    if sid and sid not in rviews and sid in stmts:
                        st = stmts[sid]
                        if not any(sid == x[1] for x in by_ms[st.get("manuscript_id")]):
                            by_ms[st.get("manuscript_id")].append((10_000 + (st.get("source") or {}).get("line", 0), sid, st, {}))
                for k, pid in enumerate(v.get("papers") or []):
                    slug = pid[2:]
                    m = S.MS.get(slug) or {}
                    pi = len(papers)
                    fams[fi]["papers"].append(pi)
                    href = f"papers/{quote(slug)}.html" if slug in S.PAPER_READING else None
                    papers.append({"id": pid, "f": fi, "title": plain(names.get(pid) or m.get("title") or slug),
                                   "short": short_title(names.get(pid) or m.get("title") or slug),
                                   "date": date_british(m.get("date")), "lead": k == 0, "results": [],
                                   "href": href, "pdf": m.get("pdf_url")})
                    for _, rid, st, rv in sorted(by_ms.get(pid, []), key=lambda x: (x[0], x[1])):
                        if rid in res_of:
                            continue
                        kind, label, nn = statement_label(st, rv)
                        ri = len(results)
                        res_of[rid] = ri
                        papers[pi]["results"].append(ri)
                        row = {"id": rid, "p": pi, "f": fi, "kind": kind, "num": label, "title": None, "lean": [],
                               "href": (st or {}).get("reading_page") or href}
                        if nn:
                            row["nn"] = 1
                        if rid not in rviews:
                            row["extra"] = 1
                        results.append(row)
                for l in doc.get("lean") or []:
                    li = len(leans)
                    lean_of[l["id"]] = li
                    fams[fi]["lean"].append(li)
                    lsum = r.lean_summary(l["id"]) or {}
                    sid, state = targets.get(l["id"], (None, "unavailable"))
                    leans.append({"id": l["id"], "f": fi, "name": l["id"][2:],
                                  "label": plain(lsum.get("name_tex") or l.get("name") or l["id"][2:]),
                                  "acc": list(l.get("accepted_current_sources") or []),
                                  "main": bool(l.get("main_result")), "results": [], "pairing": state,
                                  "href": f"statements/{quote(l['id'][2:])}.html"})
                for lid, (sid, state) in targets.items():
                    if sid in res_of and lid in lean_of and results[res_of[sid]]["f"] == fi:
                        results[res_of[sid]]["lean"].append(lean_of[lid])
                        leans[lean_of[lid]]["results"].append(res_of[sid])
                        self.pairs += 1
        # A printed number can repeat inside a family (two editions or companions each
        # with a "Theorem 1.1"): such a label carries its paper's date, or its short
        # title when the dates are the same, so every label on the map names one thing.
        for f in fams:
            seen: dict[str, list] = defaultdict(list)
            for pi in f["papers"]:
                for ri in papers[pi]["results"]:
                    if results[ri]["num"]:
                        seen[results[ri]["num"]].append(ri)
            for num, ris in seen.items():
                if len(ris) < 2:
                    continue
                dates = [papers[results[ri]["p"]]["date"] for ri in ris]
                by_date = all(dates) and len(set(dates)) == len(dates)
                for ri in ris:
                    p = papers[results[ri]["p"]]
                    tag = U("result.edition", date=p["date"].rsplit(" ", 1)[0]) if by_date else p["short"]
                    results[ri]["lab"] = f"{num}, {tag}"
        # Citations between families: the backend's directed family counts (each a count
        # of citing pairs of papers; a citation is never a proof dependency).
        links = defaultdict(lambda: [0, 0])
        for e in r.universe["family_citations"]:
            a, b = fi_of[e["source"]], fi_of[e["target"]]
            lo, hi = min(a, b), max(a, b)
            links[(lo, hi)][0 if a == lo else 1] += e["value"]
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
        self.data = {"disciplines": disciplines, "families": fams, "papers": papers, "results": results,
                     "lean": leans, "links": link_rows}

    @staticmethod
    def _pair_targets(doc) -> dict:
        """Lean id -> (paper statement id or None, pairing state), as the backend records it:
        the family's selected Lean statement keeps the selection's own state (a candidate, a
        citation in the Lean source or a binding the release declares); the others keep their
        candidate pairing, or none when the backend abstained."""
        out = {}
        for p in doc.get("pairing_selections") or []:
            src = p.get("source")
            if not src:
                continue
            if p.get("status") == "candidate" and p.get("target"):
                out[src] = (p["target"], "candidate-pairing")
            else:
                out[src] = (None, "unavailable")
        sel = doc.get("selection") or {}
        if sel.get("lean"):
            if sel.get("paired_statement") and sel.get("pairing_state") in E.PAIRINGS[:3]:
                out[sel["lean"]] = (sel["paired_statement"], sel["pairing_state"])
        return out


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
    if not P:
        pass
    elif len(P) == 1:
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
    # Fibres: one end per other family that cites or is cited by this one (the backend's
    # family citation counts), leaving from the lead paper, aimed at that family's place.
    cx, cy = centre_of(fi)
    ends = {}
    for lo, hi, a, b in model["links"]:
        if fi not in (lo, hi):
            continue
        g = hi if fi == lo else lo
        out_w, in_w = (a, b) if fi == lo else (b, a)
        ends[g] = {"g": g, "way": (1 if out_w else 0) | (2 if in_w else 0), "papers": f["papers"][:1]}
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



# ---------------------------------------------------------------- the panel's words

MATH = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]|\$[^$]+\$", re.S)
ABBR = re.compile(r"(?:\b(?:e\.g|i\.e|cf|resp|et al|vs|approx|Thm|Prop|Lem|Cor|Sec|Ch|Fig|Eq|No|St|Jr|Dr|Prof)|\b[A-Z])\.$")
LEAN_LINK = re.compile(r"\s*\(\[Lean\]\([^)]*\)\)\s*$")


def sentences(text: str) -> list[str]:
    """A catalogue description split into sentences. A full stop inside a formula or
    after a common abbreviation or an initial never ends a sentence."""
    masks = []

    def keep(m):
        masks.append(m.group(0))
        return f"\x00{len(masks) - 1}\x00"
    t = MATH.sub(keep, text or "")
    out, start = [], 0
    for m in re.finditer(r"[.?!](?:\)|”|’)?\s+(?=[A-Z(<\x00“‘\[])", t):
        if ABBR.search(t[start:m.start() + 1].rstrip()):
            continue
        out.append(t[start:m.end()].strip())
        start = m.end()
    out.append(t[start:].strip())
    unmask = lambda s: re.sub(r"\x00(\d+)\x00", lambda mm: masks[int(mm.group(1))], s)
    return [unmask(LEAN_LINK.sub("", s)) for s in out if LEAN_LINK.sub("", s)]


def lead_sentences(text: str, limit: int = 360) -> tuple[str, bool]:
    """The first sentences of a description, at least one and up to about `limit`
    characters, and whether anything was left out."""
    ss = sentences(text)
    out, n = [], 0
    for s in ss:
        if out and n + len(s) > limit:
            break
        out.append(s)
        n += len(s) + 1
    return " ".join(out), len(out) < len(ss)


def no_links(h: str) -> str:
    """HTML for inside a link (a list entry is one): its own links become plain text."""
    return re.sub(r"</?a\b[^>]*>", "", h)


def join_words(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def run_names(M) -> dict:
    """Each re-run source's credited name, as the backend's run records give it."""
    out = {}
    for doc in M.docs.values():
        for l in doc.get("lean") or []:
            for run in l.get("runs") or []:
                c = run.get("credit") or {}
                if c.get("source") and c.get("name"):
                    out[c["source"]] = c["name"]
    return out


def reruns_sentence(accepted, names) -> str:
    acc = [names.get(s, s) for s in accepted]
    if not acc:
        return E.say("reruns.none")
    return E.say("reruns.one", names=acc[0]) if len(acc) == 1 else E.say("reruns.many", n=len(acc), names=E.join_names(acc))


def evidence_words(M, ev, names) -> str:
    """One plain sentence or three: what the release's Lean states for the family's
    headline, by each outside reader's finding, and who re-ran it."""
    if not ev.has_lean:
        return U("evidence.no_lean")
    n = len(ev.lean)
    parts = [U("evidence.lean_one") if n == 1 else U("evidence.lean_many", n=n)]
    found = [f"{rd.name} {E.say('tone.' + rd.tone)}" for rd in ev.readers]
    parts.append(join_words(found)[:1].upper() + join_words(found)[1:] + ".")
    parts.append(ev.agreement_sentence())
    if n == 1:
        parts.append(reruns_sentence(ev.lean[0].accepted, names))
    else:
        k = sum(1 for lm in ev.lean if lm.accepted)
        # Groups are counted from each statement's accepted sources: one group is never "groups".
        one = len({s for lm in ev.lean for s in lm.accepted}) == 1
        parts.append(U("evidence.reruns_some_one" if one else "evidence.reruns_some", k=k, n=n) if k
                     else E.say("reruns.none").replace("this Lean statement", "these Lean statements"))
    return " ".join(parts)


def statement_html(slug: str, st_backend: dict | None, rid: str):
    """The statement typeset as the family pages typeset it (TeX spans for KaTeX), from
    the Atlas's own data/manuscripts.json, joined by the backend statement's manuscript,
    file and line, or its label."""
    m = S.MS.get(slug)
    if not m:
        return None
    src = (st_backend or {}).get("source") or {}
    line, file_ = src.get("line"), (src.get("file") or "")
    label = (st_backend or {}).get("name")
    hit = None
    for st in m.get("statements") or []:
        if line and st.get("line") == line and file_.endswith("/" + (st.get("file") or "~")):
            hit = st
            break
    if hit is None and label:
        hit = next((st for st in m.get("statements") or [] if st.get("label") == label), None)
    if hit is None:
        return None
    conv = S.TexConv(m, "")
    sec = U("result.appendix") if hit.get("appendix") else U("result.section", n=hit.get("section") or "?")
    return {
        "html": keep_punctuation(conv.blocks(hit["text"])),
        "titleHtml": conv.text(hit["title"], inline=True) if hit.get("title") else None,
        "where": sec + (f', {hit["section_title"]}' if hit.get("section_title") else ""),
        "source": f'{S.BASE_BLOB}preprints/{slug}/{hit["file"]}#L{hit["line"]}',
    }


def reader_rows(ev, doc) -> list:
    points = {p.get("reading"): p for p in (doc.get("reader_comparison") or {}).get("points") or []}
    by_source = {rd["source"]: rd for rd in doc.get("readings") or []}
    out = []
    for rd_ev in ev.readers:
        rd = by_source.get(rd_ev.source)
        if not rd:
            out.append({"name": rd_ev.name, "url": rd_ev.url, "words": E.say("tone.none")})
            continue
        pt = points.get(rd["id"]) or {}
        note = pt.get("gap") or pt.get("note") or ""
        if len(note) > 280:
            note = note[:279].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
        out.append({"name": rd_ev.name, "url": rd_ev.url, "term": rd.get("source_term"),
                    "words": E.say("tone." + rd_ev.tone), "note": note,
                    "rec": (rd.get("source_value") or {}).get("url")})
    return out


def build_detail(M, names):
    """The panel's words, one shard per discipline: each family's catalogue sentences and
    evidence in words, each result's statement typeset as printed, each Lean statement's
    re-runs and pairing."""
    D = M.data
    shards = [{"families": {}, "results": {}, "lean": {}, "macros": {}} for _ in D["disciplines"]]
    for fi, f in enumerate(D["families"]):
        ev, doc = M.evs[f["id"]], M.docs[f["id"]]
        sh = shards[f["d"]]
        cat = ((doc.get("claim") or {}).get("catalogue_claim") or {}).get("text") or ""
        ss = sentences(cat)
        lead, more = lead_sentences(cat)
        kinds = [E.say("check_kind." + c) for c in ev.checks if c in E.WORDS["check_kind"]]
        claim = doc.get("claim") or {}
        sh["families"][f["id"]] = {
            "titleHtml": no_links(S.rich(ev.name)),
            "first": no_links(S.rich(ss[0] if ss else "")),
            "desc": S.rich(lead), "descMore": more,
            "evidence": evidence_words(M, ev, names),
            "agree": ev.agreement_sentence() if ev.has_lean else "",
            "readers": reader_rows(ev, doc) if ev.has_lean else [],
            "checks": E.say("other_checks", kinds=join_words(kinds)) if kinds else "",
            "explained": ev.community_count("explanation"),
            "problems": ev.community_count("error-reported") + ev.community_count("correction"),
            "headline": "candidate" if claim.get("state") == "candidate" else "unresolved",
            "candidate": claim.get("primary_candidate") if claim.get("state") == "candidate" else None,
            "editions": ev.editions, "withdrawn": ev.withdrawn,
        }
        stmts = {s["id"]: s for s in doc.get("statements") or []}
        for pi in f["papers"]:
            p = D["papers"][pi]
            slug = p["id"][2:]
            m = S.MS.get(slug) or {}
            sh["macros"][p["id"]] = (m.get("tex") or {}).get("macros") or {}
            for ri in p["results"]:
                res = D["results"][ri]
                st = stmts.get(res["id"])
                det = statement_html(slug, st, res["id"]) or {}
                det["paperHtml"] = S.rich(m.get("title") or p["title"])
                det["date"] = p["date"]
                sh["results"][res["id"]] = det
        lean_doc = {l["id"]: l for l in doc.get("lean") or []}
        # The words a candidate pairing was found by, as the backend records them.
        shared = {}
        for p in doc.get("pairing_selections") or []:
            alt = next((a for a in p.get("alternatives") or [] if a.get("target") == p.get("target")), None)
            if p.get("source") and alt:
                shared[p["source"]] = list(alt.get("matched_terms") or [])
        for li in f["lean"]:
            L = D["lean"][li]
            l = lean_doc.get(L["id"]) or {}
            st = S.ST.get(L["name"]) if hasattr(S, "ST") else None
            runs = []
            for run in l.get("runs") or []:
                c = run.get("credit") or {}
                runs.append({"who": c.get("name") or run.get("source"), "state": run.get("state"),
                             "term": run.get("source_term"), "date": run.get("date"),
                             "current": run.get("pin_state") == "current",
                             "url": run.get("receipt") or c.get("url")})
            holes = l.get("definition_holes") or []
            sh["lean"][L["id"]] = {
                "snippet": S.lean_snippet_html(st, max_lines=14) if st else "",
                "runs": runs,
                "reruns": reruns_sentence(L["acc"], names),
                "holes": [h.get("name", h) if isinstance(h, dict) else str(h) for h in holes],
                "pairing": E.say("pairing." + L["pairing"]),
                "terms": shared.get(L["id"], []),
            }
    return shards


def build_search(M):
    """The map's own search rows, [id, lowercase text], used when the site's search
    (window.AtlasSearch) is not on the page."""
    D = M.data
    rows = []
    for f in D["families"]:
        rows.append([f["id"], (f["num"] + " " + f["title"]).lower()])
    for p in D["papers"]:
        rows.append([p["id"], p["title"].lower()])
    for r in D["results"]:
        p = D["papers"][r["p"]]
        rows.append([r["id"], f'{r["num"] or r["kind"]} {p["short"]}'.lower()])
    for L in D["lean"]:
        rows.append([L["id"], f'{L["name"]} {L["label"]}'.lower()])
    return rows


# ---------------------------------------------------------------- the page

def num_link(M, key: str) -> str:
    """A number in a sentence, from the backend's numbers index, linked to its receipt.
    A number that is not computed says so; it never shows as zero."""
    n = M.r.number(key)
    href = f"numbers.html#n-{quote(key)}"
    state, value = n.get("state"), n.get("value")
    if state == "computed" and value is not None:
        text = f"{value:,}" if isinstance(value, int) else str(value)
    elif state == "reported" and value is not None:
        text = U("numbers.reported", value=value)
    elif n.get("known_value") is not None:
        text = U("numbers.incomplete", value=n["known_value"])
    else:
        text = U("numbers.unavailable")
    return f'<a class="u-num" href="{esc(href)}">{esc(text)}</a>'


def number_sentence(M, key: str) -> str:
    tpl = COPY_U["release"][key]
    return linked(tpl, **{k: num_link(M, k) for k in re.findall(r"\{(\w+)\}", tpl)})


def key_html(M) -> str:
    """The colour key: one line for each meaning, with how many families it covers."""
    counts = {t: 0 for t in TONE_ORDER}
    for f in M.data["families"]:
        counts[f["tone"]] += 1
    rows = []
    for t in TONE_ORDER:
        if not counts[t]:
            continue
        rows.append(f'<li data-tone="{t}"><span class="u-dot u-dot--{t}" aria-hidden="true"></span>'
                    f'<span class="u-key__t">{esc(U("key." + t))}</span><span class="u-key__n">{counts[t]}</span></li>')
    return (f'<h2 class="u-h2" id="u-key-h">{esc(U("key.heading"))}</h2>'
            f'<p class="u-note">{esc(U("key.intro"))} <a href="sources.html">{esc(U("key.readers"))}</a></p><ul class="u-key" aria-labelledby="u-key-h">{"".join(rows)}</ul>'
            f'<p class="u-note">{esc(U("key.size"))} {esc(U("key.citations"))}</p>')


def discipline_rows(M) -> str:
    D = M.data
    rows = []
    for d in D["disciplines"]:
        rows.append(f'<li><a class="u-row" href="index.html#o={quote(d["id"], safe="")}" data-go="{esc(d["id"])}">'
                    f'<span class="u-row__t">{esc(d["name"])}</span>'
                    f'<span class="u-row__n">{esc(disc_counts(d))}</span></a></li>')
    return (f'<h2 class="u-h2" id="u-disc-h">{esc(U("release.disciplines_heading"))}</h2>'
            f'<ul class="u-rows" aria-labelledby="u-disc-h">{"".join(rows)}</ul>')


def disc_counts(d) -> str:
    n, k = len(d["families"]), d["withLean"]
    if k == 0:
        return U("counts.disc_none", n=n)
    if k == n:
        return U("counts.disc_all", n=n)
    return U("counts.disc_some", n=n, k=k)


def ways_html(M) -> str:
    """Four ways in, chosen by how widely the problem is known; each line of prose is
    checked against the backend's records (see copy_universe.json)."""
    fam_by = {f["num"]: f for f in M.data["families"]}
    rows = []
    for w in COPY_U["ways"]["items"]:
        f = fam_by.get(w["family"])
        if not f:
            continue
        rows.append(f'<li><a class="u-way" href="{esc(f["href"])}" data-go="{esc(f["id"])}">'
                    f'<span class="u-way__t"><span class="u-dot u-dot--{f["tone"]}" aria-hidden="true"></span>{esc(w["name"])}</span>'
                    f'<span class="u-way__w">{esc(w["why"])}</span></a></li>')
    return f'<h2 class="u-h2 u-h2--ways" id="u-ways-h">{esc(U("ways.heading"))}</h2><ul class="u-ways" aria-labelledby="u-ways-h">{"".join(rows)}</ul>'


def index_html(M) -> str:
    """The list without JavaScript: every discipline and its families, each a link."""
    D = M.data
    out = ['<div class="u-index">']
    for d in D["disciplines"]:
        out.append(f'<section class="u-index__d" id="idx-{esc(d["id"][2:])}"><h3 class="u-index__dn">{esc(d["name"])} '
                   f'<span class="u-index__dc">{esc(disc_counts(d))}</span></h3><ul class="u-index__fams">')
        for fi in d["families"]:
            f = D["families"][fi]
            out.append(f'<li><a href="{esc(f["href"])}"><span class="u-dot u-dot--{f["tone"]}" aria-hidden="true"></span>'
                       f'<span class="tex-auto">{S.rich(M.evs[f["id"]].name)}</span></a></li>')
        out.append("</ul></section>")
    out.append("</div>")
    return "".join(out)


def release_band(M) -> str:
    sentences_ = [number_sentence(M, k) for k in ("s3", "s4", "s5")]
    return f"""<section class="u-band u-band--release" id="release" aria-labelledby="h-release">
 <div class="frame u-band__in u-band__in--split">
  <h2 class="u-band__h" id="h-release">{esc(U('bands.release_heading'))}</h2>
  <div class="u-sentences">{''.join(f'<p>{x}</p>' for x in sentences_)}
   <p class="u-band__links"><a href="numbers.html">{esc(U('bands.release_numbers'))}</a></p>
  </div>
 </div>
</section>"""


def checked_band() -> str:
    rows = []
    for src, key in (("cert-machine", "checked_cert"), ("mathvet", "checked_mathvet"),
                     ("nealmcb-lean-tooling", "checked_neal"), ("hol-cards", "checked_hol"),
                     ("erdos-problems", "checked_erdos")):
        if src not in S.SOURCES:
            continue
        rows.append(f'<li><a class="u-who__n" href="sources.html#src-{esc(src)}">{esc(S.source_credit(src))}</a> '
                    f'<span class="u-who__w">{esc(U("bands." + key))}</span></li>')
    return f"""<section class="u-band u-band--checked" id="checked" aria-labelledby="h-checked">
 <div class="frame u-band__in">
  <h2 class="u-band__h" id="h-checked">{esc(U('bands.checked_heading'))}</h2>
  <p class="u-band__intro">{esc(U('bands.checked_intro'))}</p>
  <ul class="u-who">{''.join(rows)}</ul>
  <p class="u-band__links"><a href="sources.html">{esc(U('bands.checked_more_link'))}</a></p>
 </div>
</section>"""


def page_body(M, gen) -> str:
    data_v = gen[7:19]
    copy = json.loads(json.dumps(COPY_U))
    # Two of the reader's sentences are the shared evidence vocabulary's own.
    copy["lean"]["what_it_checks"] = E.say("reruns.what_it_checks")
    copy["lean"]["source_term"] = E.WORDS["reruns"]["source_term"]
    copy_json = json.dumps(copy, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    D = M.data
    canvas_label = U("controls.canvas_label", families=len(D["families"]), disciplines=len(D["disciplines"]))
    return f"""<div class="u-explorer" data-universe data-view="list"
 data-universe-data="data/universe-data.json?v={data_v}" data-universe-parts="data/universe-parts.json?v={data_v}" data-universe-layout="data/universe-layout.json?v={data_v}"
 data-universe-detail="data/universe-detail-{{d}}.json?v={data_v}" data-universe-search="data/universe-search.json?v={data_v}"
 data-generation="{esc(gen)}">
 <div class="u-switch" role="group" aria-label="{esc(U('switch.label'))}">
  <button type="button" class="u-switch__b" data-u-show="list" aria-pressed="true">{esc(U('switch.list'))}</button>
  <button type="button" class="u-switch__b" data-u-show="map" aria-pressed="false">{esc(U('switch.map'))}</button>
 </div>
 <aside class="u-panel" aria-labelledby="u-title">
  <div class="u-panel__head">
   <nav class="u-trail" aria-label="{esc(U('levels.trail_label'))}" data-u-trail hidden></nav>
   <h1 class="u-title" id="u-title">{esc(U('page.title'))}</h1>
   <form class="u-search" role="search" data-u-search-form onsubmit="return false">
    <label class="u-visually-hidden" for="u-search-in">{esc(U('search.label'))}</label>
    <input id="u-search-in" class="u-search__in" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(U('search.placeholder'))}" data-u-search>
   </form>
  </div>
  <div class="u-panel__body" data-u-scroll>
   <div class="u-results" data-u-results hidden></div>
   <div class="u-view" data-u-view>
    <p class="u-lede">{number_sentence(M, 's1')} {number_sentence(M, 's2')}</p>
    {key_html(M)}
    {discipline_rows(M)}
    {ways_html(M)}
   </div>
  </div>
 </aside>
 <div class="u-stage" data-u-stage>
  <canvas class="u-canvas" role="img" aria-label="{esc(canvas_label)}" tabindex="0" data-u-canvas></canvas>
  <div class="u-visually-hidden" aria-live="polite" data-u-live></div>
  <div class="u-maplegend" data-u-legend hidden></div>
  <button type="button" class="u-mapkey-btn" data-u-mapkey aria-expanded="false" aria-controls="u-mapkey">{esc(U('mapkey.button'))}</button>
  <div class="u-mapkey" id="u-mapkey" data-u-mapkey-panel hidden></div>
  <div class="u-tools">
   <button type="button" class="u-tool" data-u-zoom="in" aria-label="{esc(U('controls.zoom_in'))}" title="{esc(U('controls.zoom_in'))}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg></button>
   <button type="button" class="u-tool" data-u-zoom="out" aria-label="{esc(U('controls.zoom_out'))}" title="{esc(U('controls.zoom_out'))}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10"/></svg></button>
   <button type="button" class="u-tool" data-u-zoom="fit" aria-label="{esc(U('controls.fit'))}" title="{esc(U('controls.fit'))}"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5"/><circle cx="8" cy="8" r="1.4"/></svg></button>
  </div>
  <p class="u-status" data-u-status>{esc(U('status.loading'))}</p>
 </div>
 <script type="application/json" id="universe-copy">{copy_json}</script>
</div>
<section class="u-band u-band--index" id="catalogue" aria-labelledby="h-index" tabindex="-1">
 <div class="frame u-band__in">
  <h2 class="u-band__h" id="h-index">{esc(U('bands.index_heading'))}</h2>
  <p class="u-band__intro">{esc(U('bands.index_intro'))}</p>
  {index_html(M)}
 </div>
</section>
{release_band(M)}
{checked_band()}
{help_band()}"""


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


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def main():
    global OUT
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", help="the built site to add the front page to (default site/_build)")
    args = ap.parse_args()
    if args.out:
        OUT = Path(args.out).resolve()
    import_site()
    if not (OUT / "families").is_dir():
        raise SystemExit(f"{OUT} is not a built site: run scripts/build_site.py with the same --out first")
    M = Model(R.load())
    model = M.data
    layout = build_layout(model)
    names = run_names(M)
    detail = build_detail(M, names)
    search = build_search(M)
    counts = {"families": len(model["families"]), "disciplines": len(model["disciplines"]),
              "papers": len(model["papers"]), "results": len(model["results"]), "lean": len(model["lean"]),
              "pairs": M.pairs}
    data = dict(model)
    data["sources"] = names
    data["catalogue_url"] = S.BASE_BLOB + "CONTENTS.md"
    data["counts"] = counts
    # The page carries the backend's generation, so every file it fetches is checked
    # against the backend's records; the drawing's own hash is kept beside it.
    gen = M.gen
    h = hashlib.sha256()
    h.update(canonical(data))
    h.update(canonical(layout))
    contract = [{"generation_id": gen, "drawing_sha256": h.hexdigest()[:20], "upstream_commit": S.COMMIT,
                 "ids": "Statement Map's reader ids: d:, f:, p:, r:, l:",
                 "pairing": "Statement Map's pairing_selections and selection; candidate pairings are unreviewed"}]
    data = {"generation_id": gen, "contract": contract, **data}
    layout = {"generation_id": gen, "contract": contract, **layout}
    ddir = OUT / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    for old in ddir.glob("universe-*.json"):
        old.unlink()
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    # The first screen draws the release's families only; the papers, results and Lean
    # statements inside them load after it, for the zoom and the panel.
    parts = {"generation_id": gen, **{k: data.pop(k) for k in ("papers", "results", "lean")}}
    (ddir / "universe-data.json").write_text(dump(data), encoding="utf-8")
    (ddir / "universe-parts.json").write_text(dump(parts), encoding="utf-8")
    (ddir / "universe-layout.json").write_text(dump(layout), encoding="utf-8")
    for di, sh in enumerate(detail):
        (ddir / f"universe-detail-{di}.json").write_text(dump({"generation_id": gen, **sh}), encoding="utf-8")
    (ddir / "universe-search.json").write_text(dump({"generation_id": gen, "rows": search}), encoding="utf-8")
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    for name in OWN_ASSETS:
        shutil.copy(ASSETS / name, OUT / "assets" / name)
    v = gen[7:19]
    extra = ('<link rel="stylesheet" href="assets/lean.css">\n'
             '<link rel="stylesheet" href="assets/universe.css">\n'
             f'<link rel="preload" href="data/universe-data.json?v={v}" as="fetch" crossorigin>\n'
             f'<link rel="preload" href="data/universe-layout.json?v={v}" as="fetch" crossorigin>\n'
             '<meta name="format-detection" content="telephone=no">\n'
             '<script defer src="assets/universe.js"></script>')
    body = page_body(M, gen)
    html_text = S.page("index.html", U("page.title"), U("page.description"), body, current="map",
                       extra_head=extra, main_class="u-main")
    (OUT / "index.html").write_text(html_text, encoding="utf-8")
    (OUT / "universe.html").write_text(redirect_stub(), encoding="utf-8")
    sizes = {p.name: p.stat().st_size for p in sorted(ddir.glob("universe-*.json"))}
    total_detail = sum(v for k, v in sizes.items() if "detail" in k)
    print(f"universe: generation {gen[:19]}; {counts['families']} families, {counts['papers']} papers, "
          f"{counts['results']} results drawn, {counts['lean']} Lean statements, {counts['pairs']} pairings drawn")
    print(f"universe: data {sizes['universe-data.json']:,} B, parts {sizes['universe-parts.json']:,} B, layout {sizes['universe-layout.json']:,} B, "
          f"search {sizes['universe-search.json']:,} B, detail {total_detail:,} B in {len(detail)} files; "
          f"page {(OUT / 'index.html').stat().st_size:,} B")


if __name__ == "__main__":
    main()
