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
    llms.txt, agents.md                           agent entry and map traversal guide
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
                for lid, (sids, state) in targets.items():
                    for sid in sids:
                        if sid not in rviews and sid in stmts:
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
                    _, state = targets.get(l["id"], ([], "unavailable"))
                    leans.append({"id": l["id"], "f": fi, "name": l["id"][2:],
                                  "label": plain(lsum.get("name_tex") or l.get("name") or l["id"][2:]),
                                  "acc": list(l.get("accepted_current_sources") or []),
                                  "main": bool(l.get("main_result")), "results": [], "pairing": state,
                                  "href": f"statements/{quote(l['id'][2:])}.html"})
                # A Lean statement paired with several theorems hangs under each of them,
                # the clearest first (the board draws its card there and a reference
                # under the others).
                for lid, (sids, state) in targets.items():
                    for sid in sids:
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
        """Lean id -> ([paper statement ids], pairing state), from build_site.pair_targets:
        the same pairing the family and statement pages show (a citation in the Lean
        source or a binding the release declares stands; otherwise the atlas's reading of
        the Lean text, which may pair one Lean statement with up to three theorems, or
        with none when no match is confident)."""
        return S.pair_targets(doc)


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
    # Which of this family's papers carry each citation (the board draws its lines to
    # them): papers citing that family's papers, and papers its papers cite.
    own = {model["papers"][p]["id"]: k for k, p in enumerate(f["papers"])}
    for g, e in ends.items():
        theirs = {model["papers"][p]["id"] for p in model["families"][g]["papers"]}
        out_p, in_p = set(), set()
        for edge in paper_citations():
            src, dst = "p:" + edge["source"], "p:" + (edge.get("target_latest") or edge["target"])
            if src in own and dst in theirs:
                out_p.add(own[src])
            if dst in own and src in theirs:
                in_p.add(own[dst])
        e["out"], e["in"] = sorted(out_p), sorted(in_p)
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
            fibres.append([r4(a), g, e["way"], e["out"], e["in"]])
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


def asset_version() -> str:
    """A short hash of the map's own script and stylesheet, so a browser fetches them anew
    whenever either changes (the data files carry the build's generation the same way)."""
    h = hashlib.sha256()
    for name in OWN_ASSETS:
        h.update((SITE / "assets" / name).read_bytes())
    return h.hexdigest()[:12]


_PAPER_CITATIONS = None


def paper_citations():
    """The citations between two papers of the release (data/graph.json)."""
    global _PAPER_CITATIONS
    if _PAPER_CITATIONS is None:
        _PAPER_CITATIONS = json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))
    return _PAPER_CITATIONS


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


def list_label_template(opt: str) -> str | None:
    """The label= key of an enumerate's options, or None (build_site.list_label_template)."""
    return import_site().list_label_template(opt)


def printed_list_conv():
    """The family pages' TeX reader. build_site's TexConv.list_env labels each item of an
    enumerate as the paper labels it (label=(G\\arabic*) prints (G1), (G2), (G3)), so the
    map's cards and the family pages print the same labels."""
    return import_site().LabelTexConv


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
    conv = printed_list_conv()(m, "")
    sec =U("result.appendix") if hit.get("appendix") else U("result.section", n=hit.get("section") or "?")
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
    shards = [{"families": {}, "results": {}, "papers": {}, "lean": {}, "macros": {}} for _ in D["disciplines"]]
    for fi, f in enumerate(D["families"]):
        ev, doc = M.evs[f["id"]], M.docs[f["id"]]
        sh = shards[f["d"]]
        cat = ((doc.get("claim") or {}).get("catalogue_claim") or {}).get("text") or ""
        ss = sentences(cat)
        kinds = [E.say("check_kind." + c) for c in ev.checks if c in E.WORDS["check_kind"]]
        claim = doc.get("claim") or {}
        sh["families"][f["id"]] = {
            "titleHtml": no_links(S.rich(ev.name)),
            "first": no_links(S.rich(ss[0] if ss else "")),
            "desc": S.rich(cat),
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
            sh["papers"][p["id"]] = {"abstract": S.rich(m.get("abstract") or "")}
            sh["macros"][p["id"]] = (m.get("tex") or {}).get("macros") or {}
            for ri in p["results"]:
                res = D["results"][ri]
                st = stmts.get(res["id"])
                det = statement_html(slug, st, res["id"]) or {}
                det["paperHtml"] = S.rich(m.get("title") or p["title"])
                det["date"] = p["date"]
                sh["results"][res["id"]] = det
        lean_doc = {l["id"]: l for l in doc.get("lean") or []}
        # The words a candidate pairing was found by: the Lean's own words when the atlas
        # read the Lean text, the catalogue's words for the backend's fallback candidate.
        shared = {}
        for lid in lean_doc:
            pinfo = S.lean_pairing(doc, lid)
            if pinfo.get("state") == "candidate-pairing" and pinfo.get("target"):
                t = S.pairing_terms(pinfo)
                shared[lid] = t["lean"] + t["title"] + t["note"] + t["catalogue"]
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


# ---------------------------------------------------------------- search words

# The site's search (window.AtlasSearch in assets/atlas.js) matches Statement Map's
# exact tokens. These files, in data/universe-search/, let it say why an entry matched
# and forgive the usual variations, without changing what the backend's index holds.
# Every list is in the index's entry order.
#   words.json        which vocabulary files exist, and the size of a text block
#   vocab-<c>.json    every indexed word starting with c, with how many entries hold it: for
#                     a prefix of the last word, plural and singular forms, and spellings
#                     with or without a hyphen
#   names.json        the name each statement prints ("Proposition 4.2"), or null
#   atoms.json        each short formula word ("L^2", "W^{1,p}") with the entries holding it
#   text-<n>.json     per block of entries, the text a result line quotes: the statement,
#                     the Lean source, the abstract or the catalogue's description
TEXT_BLOCK = 64
TEXT_CAP = {"statement": 1600, "lean": 2400, "manuscript": 1400, "family": 1200, "discipline": 0}
_CMD_ARG = re.compile(r"\\(?:emph|textit|textbf|textup|textrm|textsc|textsf|texttt|mbox|hbox|underline|uline|textnormal)\s*\{([^{}]*)\}")
_DROP_ARG = re.compile(r"\\(?:label|index|footnote|vspace|hspace|phantom|nocite)\*?\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}")
_CITE = re.compile(r"\\(?:cite[a-z]*|citet|citep)\*?\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}")
_REF = re.compile(r"\\(eqref|ref|cref|Cref|autoref|Autoref)\*?\s*\{([^{}]*)\}")
_ENV_MATH = re.compile(r"\\begin\{(equation|align|gather|multline|eqnarray|displaymath|flalign|alignat)(\*?)\}(?:\{[^{}]*\})?(.*?)\\end\{\1\2\}", re.S)
_ENV = re.compile(r"\\(?:begin|end)\{[^{}]*\}(?:\[[^\]]*\])?")


def snippet_tex(text: str, labels: dict) -> str:
    """A statement's TeX as one line a result list can quote: prose as prose, each formula
    kept whole between dollars for KaTeX, references printed as the paper prints them."""
    t = re.sub(r"(?<!\\)%[^\n]*", "", text or "")

    def ref(m):
        rec = labels.get(m.group(2).split(",")[0].strip())
        if not rec or not rec[2]:
            return "??"
        if m.group(1) == "eqref" or rec[0] == "equation":
            return f"({rec[2]})"
        if m.group(1) in ("cref", "Cref", "autoref", "Autoref"):
            return f"{rec[1] or S.KIND_WORD.get(rec[0]) or ''} {rec[2]}".strip()
        return rec[2]

    def display(body: str) -> str:
        body = re.sub(r"\\\\(\[[^\]]*\])?", " ", body).replace("&", " ")
        body = re.sub(r"\\(?:nonumber|notag|label\{[^{}]*\})", "", body)
        return " $" + re.sub(r"\s+", " ", body).strip() + "$ "

    t = _ENV_MATH.sub(lambda m: display(m.group(3)), t)
    t = re.sub(r"\\\[(.*?)\\\]", lambda m: display(m.group(1)), t, flags=re.S)
    t = re.sub(r"\$\$(.*?)\$\$", lambda m: display(m.group(1)), t, flags=re.S)
    t = re.sub(r"\\\((.*?)\\\)", lambda m: "$" + m.group(1).strip() + "$", t, flags=re.S)
    t = _REF.sub(ref, t)
    t = _DROP_ARG.sub("", t)
    t = _CITE.sub("", t)
    for _ in range(3):
        t = _CMD_ARG.sub(r"\1", t)
    t = _ENV.sub(" ", t)
    t = re.sub(r"\\item\s*(\[[^\]]*\])?", lambda m: " " + (m.group(1)[1:-1] + " " if m.group(1) else ""), t)
    t = t.replace("~", " ").replace("``", "“").replace("''", "”")
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\s+([.,;:])", r"\1", t)


def cap_text(t: str, n: int) -> str:
    """At most about n characters, cut between formulas and at a word, with an ellipsis."""
    if len(t) <= n:
        return t
    cut, inside = 0, False
    for i, ch in enumerate(t[:n]):
        if ch == "$" and (i == 0 or t[i - 1] != "\\"):
            inside = not inside
        if ch == " " and not inside:
            cut = i
    return t[:cut or n].rstrip(" ,;:") + "…"


def lean_snippet(src: str) -> str:
    """A Lean file as a result line quotes it: from its first docstring or declaration,
    without imports and options."""
    lines = [ln for ln in (src or "").splitlines() if not re.match(r"\s*(import|open|set_option|namespace|end|section|noncomputable section)\b", ln)]
    t = "\n".join(lines)
    m = re.search(r"/--|^\s*(?:theorem|lemma|def|abbrev|structure|class|instance|axiom)\b", t, re.M)
    t = t[m.start():] if m else t
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def vocab_shard(term: str) -> str:
    """The file a word's vocabulary row is in (mirrors vocabShard in site/assets/atlas.js)."""
    c = term[:1]
    return c if re.fullmatch(r"[a-z0-9]", c) else "_"


# A short formula a reader types as a search word: a letter with a superscript or a
# subscript ("L^2", "W^{1,p}", "\\ell_1"), read as one word. The key drops braces and
# spaces (mirrors mathAtoms in site/assets/atlas.js).
ATOM = re.compile(r"(?<![A-Za-z\\])([A-Za-z]|\\ell|\\mathbb\s*\{[A-Z]\}|\\mathcal\s*\{[A-Z]\})\s*([\^_])\s*(\{[^{}$]{1,12}\}|\\[A-Za-z]+|[0-9A-Za-z])")


def atom_key(base: str, op: str, sup: str) -> str:
    return re.sub(r"[\s{}]", "", base) + op + re.sub(r"[\s{}]", "", sup)


def atom_postings(entries, texts) -> dict:
    """Each formula word, with the entries whose name or quoted text holds it."""
    out = defaultdict(set)
    for i, (e, t) in enumerate(zip(entries, texts)):
        for m in ATOM.finditer((e.get("name") or "") + " " + (t if e["kind"] != "lean" else "")):
            out[atom_key(*m.groups())].add(i)
    return {k: sorted(v) for k, v in sorted(out.items()) if len(v) <= 4000}


def build_search_words(M):
    """vocab.json and text-<n>.json for the site's search (see the note above)."""
    r = M.r
    idx = r.search_index
    entries = []
    for k, chunk in enumerate(idx["entry_chunks"]):
        doc = r.packet(chunk)
        if doc.get("start") != k * idx["entry_chunk_size"]:
            raise SystemExit(f"{chunk} starts at {doc.get('start')}")
        entries.extend(doc["entries"])
    if len(entries) != idx["entry_count"]:
        raise SystemExit(f"search entries: {len(entries)} read, the index says {idx['entry_count']}")
    df = defaultdict(int)
    for logical in idx["shards"].values():
        for term, post in (r.packet(logical).get("terms") or {}).items():
            df[term] += len(post)
    vocab = sorted(df)
    lean_src = {s["id"]: s.get("lean") or "" for s in S.STATEMENTS}
    fam_desc = {f["id"]: f.get("description") or "" for f in S.FAMILIES}
    names, texts = [], []
    for e in entries:
        kind, eid = e["kind"], e["id"]
        name, text = None, ""
        if kind == "statement":
            slug, _, label = eid[2:].partition(":")
            ms = S.MS.get(slug) or {}
            st = next((x for x in ms.get("statements") or [] if x.get("label") == label), None)
            if st:
                row = S.STATEMENT_NUMBERS.get((slug, st.get("file"), st.get("line")))
                if row and row.get("statement_sha256") == st.get("sha256"):
                    name = f'{row["kind"]} {row["number"]}' if row.get("number") else U("result.unnumbered_label", kind=row["kind"])
                text = snippet_tex(st.get("text") or "", S.PAPER_LABELS.get(slug, {}))
        elif kind == "lean":
            text = lean_snippet(lean_src.get(eid[2:], ""))
        elif kind == "manuscript":
            text = snippet_tex((S.MS.get(eid[2:]) or {}).get("abstract") or "", {})
        elif kind == "family":
            text = snippet_tex(fam_desc.get(eid[2:], ""), {})
        names.append(name)
        texts.append(cap_text(text, TEXT_CAP.get(kind, 0)))
    blocks = [{"generation_id": M.gen, "start": s, "text": texts[s:s + TEXT_BLOCK]}
              for s in range(0, len(entries), TEXT_BLOCK)]
    # The vocabulary in files by first letter: a prefix, a plural and a spelling with or
    # without a hyphen all share their word's first letter. Long bare numbers are left out.
    shards = defaultdict(list)
    for t in vocab:
        if re.fullmatch(r"[0-9]{5,}", t):
            continue
        shards[vocab_shard(t)].append(f"{t}\t{df[t]}")
    words = {"generation_id": M.gen, "schema": "plectis-atlas-search-words/1", "text_block": TEXT_BLOCK,
             "entry_count": len(entries), "vocab_shards": sorted(shards),
             "names": {"generation_id": M.gen, "names": names},
             "atoms": {"generation_id": M.gen, "atoms": atom_postings(entries, texts)}}
    vocab_files = {k: {"generation_id": M.gen, "terms": "\n".join(v)} for k, v in shards.items()}
    return words, blocks, vocab_files


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


# Each colour's families on the Families list (explain.html), by its two reader
# columns: l is MathVet's reading, r is cert-machine's, c a class. A colour whose
# families no filter there selects exactly is counted without a link.
# Each colour's count links to the Families list filtered by the same colour: the list's
# rows carry the map's colour (data-t, from tone_class), so every count reproduces exactly.
KEY_FILTERS = {t: f"t={t}" for t in TONE_ORDER}


def explain_rows() -> dict:
    """The Families list's rows as built (explain.html in --out): family number -> its
    filter attributes, so each colour's link is checked to select exactly its families."""
    page = OUT / "explain.html"
    rows = {}
    if not page.exists():
        return rows
    for m in re.finditer(r'<tr id="f-(\d+)"([^>]*)>', page.read_text(encoding="utf-8")):
        attrs = dict(re.findall(r'data-([a-z])="([^"]*)"', m.group(2)))
        rows[m.group(1)] = attrs
    return rows


def filter_selects(rows: dict, query: str) -> set:
    """The family numbers explain.html?<query> shows (mirrors data-filter-families in atlas.js)."""
    want = dict(kv.split("=", 1) for kv in query.split("&"))
    out = set()
    for num, a in rows.items():
        if all((k == "c" and v in a.get("c", "").split()) or (k != "c" and a.get(k) == v) for k, v in want.items()):
            out.add(num)
    return out


def key_html(M) -> str:
    """The colour key: one line for each meaning, with how many families it covers, each
    count linked to the same families on the Families list; then what the counts count."""
    counts = {t: 0 for t in TONE_ORDER}
    members = defaultdict(set)
    for f in M.data["families"]:
        counts[f["tone"]] += 1
        members[f["tone"]].add(f["num"])
    listed = explain_rows()
    rows = []
    for t in TONE_ORDER:
        if not counts[t]:
            continue
        n = esc(counts[t])
        q = KEY_FILTERS.get(t)
        if q and filter_selects(listed, q) != members[t]:
            print(f"universe: the colour key's link explain.html?{q} does not select exactly the {counts[t]} families coloured {t}; left unlinked")
            q = None
        num = (f'<a class="u-key__n" href="explain.html?{esc(q)}" aria-label="{esc(U("key.count_link", n=counts[t]))}">{n}</a>'
               if q else f'<span class="u-key__n">{n}</span>')
        rows.append(f'<li data-tone="{t}"><span class="u-dot u-dot--{t}" aria-hidden="true"></span>'
                    f'<span class="u-key__t">{esc(U("key." + t))}</span>{num}</li>')
    counted = linked(U("key.counted"), files=esc(U("key.counted_files", n=M.r.number("statements_lean").get("value") or 0)),
                     numbers=f'<a href="numbers.html#n-statements_lean">{esc(U("key.counted_numbers"))}</a>',
                     drafts=f'<a href="numbers.html#h-n-scope">{esc(U("key.counted_drafts"))}</a>')
    return (f'<h2 class="u-h2" id="u-key-h">{esc(U("key.heading"))}</h2>'
            f'<p class="u-note">{esc(U("key.intro"))} <a href="sources.html">{esc(U("key.readers"))}</a></p><ul class="u-key" aria-labelledby="u-key-h">{"".join(rows)}</ul>'
            f'<p class="u-note u-key__counted">{counted}</p>'
            f'<p class="u-note">{esc(U("key.size"))} {esc(U("key.citations"))}</p>')


def since_html(M) -> str:
    """Since the release: the withdrawn papers by name, each linked to its page, and how
    many papers OpenAI replaced with later editions (Statement Map's receipts)."""
    wd = M.r.number_receipt("manuscripts_withdrawn")
    members = wd.get("members") or []
    if len(members) != wd.get("value"):
        raise SystemExit(f"withdrawn papers: {len(members)} named, the receipt counts {wd.get('value')}")
    links = []
    for pid in members:
        ms = S.MS.get(pid[2:])
        if not ms:
            raise SystemExit(f"withdrawn paper {pid} is not in data/manuscripts.json")
        links.append(f'<a href="papers/{esc(quote(pid[2:]))}.html">{esc(S.tex_plain(ms["title"]))}</a>')
    eds = M.r.number("manuscripts_previous_editions").get("value")
    papers = links[0] if len(links) == 1 else ", ".join(links[:-1]) + U("since.and") + links[-1]
    withdrawn = U("since.withdrawn_one") if len(links) == 1 else U("since.withdrawn", n=len(links))
    text = linked(U("since.text"), withdrawn=esc(withdrawn), papers=papers,
                  editions=f'<a href="numbers.html#n-manuscripts_previous_editions">{esc(U("since.editions", n=eds))}</a>')
    return f'<p class="u-since"><b class="u-since__h">{esc(U("since.heading"))}</b> {text}</p>'


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


def page_body(M, gen, data_version=None) -> str:
    data_v = data_version or gen[7:19]
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
   <nav class="u-step" aria-label="{esc(U('step.label'))}" data-u-step hidden></nav>
   <h1 class="u-title" id="u-title">{esc(U('page.title'))}</h1>
   <p class="u-ground" data-u-ground>{esc(U('page.independent'))}</p>
   <form class="u-search" role="search" data-u-search-form onsubmit="return false">
    <label class="u-visually-hidden" for="u-search-in">{esc(U('search.label'))}</label>
    <input id="u-search-in" class="u-search__in" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(U('search.placeholder'))}" data-u-search>
   </form>
  </div>
  <div class="u-panel__body" data-u-scroll>
   <div class="u-results" data-u-results hidden></div>
   <div class="u-view" data-u-view>
    <p class="u-lede">{number_sentence(M, 's1')} {number_sentence(M, 's2')}</p>
    {since_html(M)}
    <section class="u-keysec" id="u-key">{key_html(M)}</section>
    <p class="u-nojs">{esc(U('page.nojs'))}</p>
    <p class="u-keyjump"><a href="#u-key" data-u-keyjump>{esc(U('key.heading'))}</a></p>
    <section class="u-discsec">{discipline_rows(M)}</section>
    <section class="u-wayssec">{ways_html(M)}</section>
   </div>
  </div>
 </aside>
 <div class="u-stage" data-u-stage>
  <canvas class="u-canvas" role="img" aria-label="{esc(canvas_label)}" tabindex="0" data-u-canvas></canvas>
  <div class="u-visually-hidden" aria-live="polite" data-u-live></div>
  <div class="u-maplegend" data-u-legend hidden></div>
  <div class="u-board" data-u-board role="region" aria-label="{esc(U('board.label'))}"></div>
  <div class="u-mapbar" data-u-bar>
   <button type="button" class="u-mapkey-btn" data-u-mapkey aria-expanded="false" aria-controls="u-mapkey">{esc(U('mapkey.button'))}</button>
   <div class="u-capbox">
    <p class="u-cap" data-u-cap>{esc(U('chart.release_cap', families=len(M.data['families']), disciplines=len(M.data['disciplines'])))}</p>
    <p class="u-cap u-cap--hover" data-u-hovercap aria-hidden="true"></p>
   </div>
  </div>
  <div class="u-mapkey" id="u-mapkey" data-u-mapkey-panel hidden></div>
 </div>
 <p class="u-status" data-u-status role="status">{esc(U('status.loading'))}</p>
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


def packet_version(directory: Path) -> str:
    """Invalidate cached map packets when rendering changes at the same source pin."""
    digest = hashlib.sha256()
    for packet in sorted(directory.glob("universe-*.json")):
        digest.update(packet.name.encode("utf-8") + b"\0")
        digest.update(packet.read_bytes())
    return digest.hexdigest()[:12]


def build_agent_navigation(model, generation: str, version: str) -> dict[str, str]:
    """Describe the existing map packets without duplicating or changing their schema.

    These are ordinary static resources, never loaded by the browser application.
    Absolute URLs retain config.json's project path when read away from the site.
    """
    base = S.BASE_URL
    repo = S.REPO
    packet = lambda name: f"{base}data/{name}?v={version}"
    llms = f"""# Plectis Atlas

> An independent reader's atlas to OpenAI's mathematics release. The website and its map can be navigated without JavaScript through static HTML and JSON.

Read the navigation guide before interpreting map edges. Citation links are not proof dependencies; automatically proposed paper-to-Lean pairings remain unreviewed. A reported proof replay checks its formal statement, not its match to a paper. The original PDF remains the reference.

## Start

- [Agent navigation]({base}agents.md): packet fields, stable identifiers, traversal example and source limits.
- [Map overview JSON]({packet('universe-data.json')}): all disciplines and families, directed citations, source contract and counts.
- [Map parts JSON]({packet('universe-parts.json')}): all papers, displayed results and Lean statements in the map, joined by indices.
- [Browse families]({base}explain.html): static HTML links to every family.
- [Sources and credits]({base}sources.html): attributed outside readings and reported replays.
- [Site sitemap]({base}sitemap.xml): published HTML reading routes.
- [Repository]({repo}): source, build instructions, licences and contribution skills.
"""
    guide = f"""# Navigate Plectis Atlas as an agent

The website is agent-navigable using HTTP GET requests. No browser, account, JavaScript execution or installation is needed to read the map. This guide describes the same packets the human map uses; it adds no data fetch to human page loads. `llms.txt` is an optional discovery convention, not an access requirement or a guarantee about any crawler.

## Entry points

- [Concise entry]({base}llms.txt)
- [All families in static HTML]({base}explain.html)
- [Lean statements]({base}statements.html)
- [Sources and credits]({base}sources.html)
- [Counts and their definitions]({base}numbers.html)
- [Page sitemap]({base}sitemap.xml)
- [Repository instructions]({repo}/blob/main/AGENTS.md) and [source architecture]({repo}/blob/main/docs/ARCHITECTURE.md)

## Fetch the complete map

Fetch these two JSON packets to obtain all the map's nodes and relationships. Layout coordinates are unnecessary for research.

1. [Overview]({packet('universe-data.json')}): `disciplines`, `families`, `links`, `sources`, `counts`, `catalogue_url` and `contract`.
2. [Parts]({packet('universe-parts.json')}): `papers`, `results` and `lean`.

Both packets must have the same `generation_id`. This build uses `{generation}` from Statement Map, reading `openai/math` at `{S.COMMIT}`. Check `contract[0].upstream_commit` in the overview. The query version is a cache key for the built packet bytes, not an archived snapshot. A generation mismatch detects different backend exports; it does not detect every rendering-only deployment. On a mismatch, reload this guide and both packets. For reproducible archival work, pin a repository commit and retain the packets together. Array indices are local to that packet set; store an object's `id`, never its array position.

The map contains {len(model['disciplines'])} disciplines, {len(model['families'])} families, {len(model['papers'])} papers, {len(model['results'])} displayed results and {len(model['lean'])} Lean statements. Displayed results include the headline selection and additional pairing targets; this is not every theorem-like environment in every paper. Follow each paper's page for its full text and conversion limits.

## Nodes and edges

Every node has a stable backend `id`: `d:` for a discipline, `f:` for a family, `p:` for a paper, `r:` for a displayed paper result, and `l:` for a Lean statement. Read names from `name`, `title`, `label` or the result's `kind` and `num`. A missing title or printed number remains unknown.

All numeric references below are zero-based array indices in the two packets fetched together:

| From | Relationship | Target |
|---|---|---|
| `disciplines[i].families` | contains | indices in `families` |
| `families[i].d` | belongs to | index in `disciplines` |
| `families[i].papers`, `.lean` | contains | indices in `papers`, `lean` |
| `papers[i].f`, `.results` | belongs to family; contains results | index in `families`; indices in `results` |
| `results[i].p`, `.f` | belongs to paper and family | indices in `papers`, `families` |
| `results[i].lean` | paper-to-Lean pairing | indices in `lean` |
| `lean[i].f`, `.results` | belongs to family; paired results | index in `families`; indices in `results` |
| `families[i].cites` | cites another family | pairs `[family_index, citing_paper_pair_count]` |
| `families[i].citedBy` | cited by another family | the reverse directed citation pairs |

`links` records the same family citations compactly as `[a, b, a_to_b_count, b_to_a_count]`. Each positive count is a directed citation between those family indices, measured in citing pairs of papers. A citation is not a proof dependency. A zero count means no edge in that direction.

Keep `lean[i].pairing` with a pairing edge. `candidate-pairing` is unreviewed. Keep `acc` as the attributed sources reporting accepted replays, not an Atlas verification claim. Read the family or Lean page for the precise evidence and limits.

Resolve each non-null `href` relative to `{base}`, including its fragment. Some nodes can have a null `href`; use the parent family or the paper's `pdf` instead of inventing a URL. Open a subject on the map with `{base}#o=` followed by its URL-encoded `id` (`d:…`); the same address with a family, paper, result or Lean `id` opens that object's own page. Readable page URLs are preferable when a client cannot execute JavaScript.

## A small traversal

This standard-library example fetches the existing map packets and follows a family's papers, Lean statements and outgoing citations. Replace `f:159` with another returned family ID.

```python
import json
from urllib.parse import urljoin
from urllib.request import urlopen

base = {base!r}
version = {version!r}

def fetch(name):
    with urlopen(urljoin(base, 'data/' + name + '?v=' + version), timeout=30) as response:
        return json.load(response)

overview = fetch('universe-data.json')
parts = fetch('universe-parts.json')
if overview['generation_id'] != parts['generation_id']:
    raise RuntimeError('Deployment changed: reload agents.md and both packets')
family = next(row for row in overview['families'] if row['id'] == 'f:159')
print(family['id'], family['title'], urljoin(base, family['href']))
for kind in ('papers', 'lean'):
    for index in family[kind]:
        node = parts[kind][index]
        target = urljoin(base, node['href']) if node.get('href') else node.get('pdf')
        print(kind, node['id'], target)
for index, count in family['cites']:
    target = overview['families'][index]
    print('cites', target['id'], count, urljoin(base, target['href']))
```

For a selected family's extra wording, fetch `data/universe-detail-<d>.json` using its `d` index and check the generation. [Map search rows]({packet('universe-search.json')}) offer names and result labels without downloading the separate full-text search shards. The [backend export]({repo}/blob/main/backend/EXPORT.json) identifies the source receipts; [source indexes]({repo}/tree/main/data) contain the extracted text and source locations. Respect their source, version, attribution and licence.

## Interpretation and contribution

Atlas is independent of OpenAI. It presents source records and attributed outside readings. It does not establish new mathematical results or equate a successful formal proof replay with a paper-to-Lean match. Paper conversions can be partial; the original PDF is the reference. Preserve unknown, candidate, unreviewed, withdrawn and source-attributed states when reporting findings.

Read [contribution instructions]({repo}/blob/main/CONTRIBUTING.md) before proposing changes. Signed contributions need the required human identity and review. An agent may report an unreviewed observation through the repository's dedicated form only when its operator and platform permit posting; reading this guide does not authorise a submission.
"""
    return {"llms.txt": llms, "agents.md": guide}


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
                 "pairing": "build_site.lean_pairing: Statement Map's citations and bindings, else the atlas's reading of the Lean text; candidate pairings are unreviewed"}]
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
    words, blocks, vocab_files = build_search_words(M)
    wdir = ddir / "universe-search"
    if wdir.is_dir():
        shutil.rmtree(wdir)
    wdir.mkdir(parents=True)
    for part in ("names", "atoms"):
        (wdir / f"{part}.json").write_text(dump(words.pop(part)), encoding="utf-8")
    (wdir / "words.json").write_text(dump(words), encoding="utf-8")
    for k, v in vocab_files.items():
        (wdir / f"vocab-{k}.json").write_text(dump(v), encoding="utf-8")
    for b in blocks:
        (wdir / f"text-{b['start'] // TEXT_BLOCK:04d}.json").write_text(dump(b), encoding="utf-8")
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    for name in OWN_ASSETS:
        shutil.copy(ASSETS / name, OUT / "assets" / name)
    v = packet_version(ddir)
    for name, content in build_agent_navigation(model, gen, v).items():
        (OUT / name).write_text(content, encoding="utf-8")
    extra = ('<link rel="stylesheet" href="assets/lean.css">\n'
             f'<link rel="stylesheet" href="assets/universe.css?v={asset_version()}">\n'
             f'<link rel="preload" href="data/universe-data.json?v={v}" as="fetch" crossorigin>\n'
             f'<link rel="preload" href="data/universe-layout.json?v={v}" as="fetch" crossorigin>\n'
             '<meta name="format-detection" content="telephone=no">\n'
             f'<script defer src="assets/universe.js?v={asset_version()}"></script>')
    body = page_body(M, gen, v)
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
          f"search names {(wdir / 'names.json').stat().st_size:,} B, formulas {(wdir / 'atoms.json').stat().st_size:,} B, vocabulary {sum(p.stat().st_size for p in wdir.glob('vocab-*.json')):,} B, "
          f"text {sum(p.stat().st_size for p in wdir.glob('text-*.json')):,} B in {len(blocks)} files; "
          f"page {(OUT / 'index.html').stat().st_size:,} B")


if __name__ == "__main__":
    main()
