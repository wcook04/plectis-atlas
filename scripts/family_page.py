"""The family page: families/<id>.html, the beginning of mathematical work on one family.

DESIGN.md, "Reading a family", in the reading register of the Plectis maths pages:
the mathematics first, every state said in words, no symbol that needs a key.
Top to bottom: the trail, the family's name and OpenAI's catalogue description as a
credited quotation; the theorem, set as the page's centrepiece exactly as printed
(or, when the headline is unresolved, the candidate theorems after one sentence
saying so), with the formal status and the readable argument as two lines kept
apart; what the release's Lean states, beside the paper theorem it is paired with
and with the qualification at the join; who has checked it (the outside readers in
their own terms, the re-runs, checks by another method, problems reported by
others, explanations by others); what is left to check; the papers; connections;
how to explain, check or correct it; what people have said.

Every semantic decision comes from the family's reader packet (scripts/reader.py,
r.family(fid)) and the evidence vocabulary (scripts/evidence.py): which theorem is
the catalogue's candidate, what each Lean statement is paired with and by what
evidence, each outside reader's finding in their own term, which re-runs are
accepted at the release's pin, what is left to check. Nothing here recomputes a
pairing, a headline, a verdict or a count. Statement text that the packet does not
inline comes from the Atlas's own data/manuscripts.json, joined by the statement's
manuscript, file and line, and is rendered by build_site's TeX converter.

Supporting records (readings, runs, candidate statements, Lean names, check cards)
carry their full record in a <template> for the inspection rail
(site/assets/inspect.js), a quiet aid for detail on demand; everything a reader
needs is written in the reading column.

build_site.build_family(f) calls build(S, f) with the running build_site module, so
the shell, the TeX converter and the shared helpers are the build's own.
Standard library only.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from html import escape as _esc
from pathlib import Path
from urllib.parse import quote, urlparse

import evidence
import reader

ROOT = Path(__file__).resolve().parent.parent
WORDS = json.loads((ROOT / "site" / "copy_family.json").read_text(encoding="utf-8"))
say = evidence.say
CITED = ("producer-cited-association", "producer-declared-binding")


def W(key: str, **kw) -> str:
    node = WORDS
    for part in key.split("."):
        node = node[part]
    return node.format(**kw) if kw else node


def esc(s) -> str:
    return _esc(str(s if s is not None else ""), quote=True)


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def slug_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", s).strip("-")


def curly(s: str) -> str:
    """Typographic quotes in recorded prose: an apostrophe inside a word, and a pair of
    single or double quotes around words. Callers keep code spans apart."""
    t = re.sub(r"(?<=[A-Za-z0-9À-ɏ])'(?=[A-Za-z])", "’", s or "")
    t = re.sub(r"(?<=[a-z]s)'(?=\s)", "’", t)
    t = re.sub(r"(?<![\w'])'([^'\n]{1,80}?)'(?![\w'])", r"‘\1’", t)
    t = re.sub(r'(?<![\w"])"([^"\n]{1,120}?)"(?![\w"])', r"“\1”", t)
    return t


_MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$[^$]*\$|<[^>]+>)", re.S)


def curly_tex(s: str) -> str:
    """curly() outside formulas and tags, so a prime inside TeX stays a prime."""
    return "".join(p if _MATH.fullmatch(p) else curly(p) for p in _MATH.split(s or ""))


def sayc(key: str, **kw) -> str:
    """An evidence sentence from copy_evidence.json, with typographic quotes."""
    return curly(say(key, **kw)).replace("the release’s pin", "the release’s recorded version")


def code_spans(s: str) -> str:
    """Recorded prose with `code` spans, escaped, typographic quotes outside code."""
    parts = re.split(r"(`[^`]*`)", s or "")
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f'<code translate="no">{esc(p[1:-1])}</code>')
        else:
            out.append(esc(curly(p)))
    return "".join(out)


# ---- reading the packet ---------------------------------------------------------


def lean_pairings(S, doc) -> dict:
    """Each Lean statement's recorded pairing, from build_site.lean_pairing (the backend's
    selection, then a cited or declared correspondence, then a resolved source
    association, then the lexical selection), with the words a candidate pair shares."""
    corr = doc.get("correspondences") or []
    out = {}
    for l in doc.get("lean") or []:
        lid = l["id"]
        rec = dict(S.lean_pairing(doc, lid))
        rec["shared"] = []
        if rec.get("target"):
            for x in corr:
                if x.get("source") == lid and x.get("target") == rec["target"] and x.get("matched_terms"):
                    rec["shared"] = list(x["matched_terms"])
                    break
            else:
                for a in rec.get("alternatives") or []:
                    if a.get("target") == rec["target"]:
                        rec["shared"] = list(a.get("matched_terms") or [])
                        break
        else:
            rec["state"] = "unavailable"
        out[lid] = rec
    return out


def stmt_label(st: dict) -> str:
    """"Theorem 1.1" as the reading page prints it; an unnumbered or unavailable number
    says which, and never borrows a section number."""
    kind = st.get("display") or (st.get("statement_kind") or "").capitalize() or "Statement"
    if st.get("printed_number_status") == "recorded" and st.get("printed_number"):
        return W("claim.printed", kind=kind, number=st["printed_number"])
    if st.get("printed_number_status") == "unnumbered":
        return W("claim.unnumbered", kind=kind)
    return W("claim.unavailable", kind=kind)


def clip(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[: n - 1]
    sp = cut.rfind(" ")
    if sp > n * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,:;.-") + "…"


@lru_cache(maxsize=1)
def _reader():
    return reader.load()


@lru_cache(maxsize=1)
def _evidence() -> dict:
    return {ev.id: ev for ev in evidence.all_families(_reader())}


def first_sentence(s: str) -> str:
    m = re.search(r"(?<=[.;])\s", s or "")
    return (s[: m.start()] if m else s or "").rstrip(";.") + "."


def possessive(S, name: str) -> str:
    """Whose record a control opens, as prose says it: "Carlos Toledo’s cert-machine",
    "MathVet’s". A credited name with a comma is a person and their project."""
    return S.prose_credit(name) if ", " in (name or "") else f"{name}’s"


def join_and(S, items: list) -> str:
    """"a", "a and b", "a, b and c"."""
    items = [x for x in items if x]
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " " + S.C("family.and") + " " + items[-1]


# ---- what a check by another method checks ---------------------------------------------
#
# A cert-machine record names the certificate it decided in its own detail, by the
# paper's TeX labels ("every inequality of Lemma lem:finite-certificate ...; not ...").
# The statements named before the record states its limit are the checked object; each
# label is resolved through the paper's own labels (data/paper_labels.json, the numbers
# the reading pages print), so the page names it as the paper prints it and links its
# place on the reading page. A label the paper does not hold is never shown raw.

_KIND = r"(?:Lemmas?|Propositions?|Prop\.?|Theorems?|Corollar(?:y|ies)|Sections?|Appendix|Appendices|Tables?|Definitions?|Claims?)"
_LABEL = r"[A-Za-z][\w.-]*(?::[\w.-]*\w)+|[A-Za-z]\w*(?:-\w+)+"
_MENTION = re.compile(rf"\b({_KIND})\s+((?:{_LABEL})(?:\s*(?:,|,?\s+and)\s+(?:{_LABEL}))*)")
_SCOPE_HEAD = re.compile(r"^(?:a finite component|finite components only|the whole headline|the whole of|decided in part)\s*(?:--|—|–|:)?\s*", re.I)
_HEAD_STOP = re.compile(r";|:\s|\b(?:not|NOT|Not)\b")
_LABEL_PREFIX = {"lemma": "lem", "proposition": "prop", "prop": "prop", "theorem": "thm", "corollary": "cor",
                 "section": "sec", "appendix": "app", "table": "tab", "definition": "def", "claim": "claim"}
_PLURAL = {"Lemma": "Lemmas", "Proposition": "Propositions", "Theorem": "Theorems", "Corollary": "Corollaries",
           "Section": "Sections", "Appendix": "Appendices", "Table": "Tables", "Definition": "Definitions",
           "Claim": "Claims", "Figure": "Figures", "Remark": "Remarks"}


def _kind_key(word: str) -> str:
    w = word.rstrip(".").lower()
    return "corollary" if w == "corollaries" else "appendix" if w == "appendices" else w[:-1] if w.endswith("s") and w[:-1] in _LABEL_PREFIX else w


def checked_refs(S, slug: str, detail: str, root: str) -> list:
    """The statements a check's record names as what it decided, before it states its
    limit: [(word, [(number, href or None)], nested)], one group per mention, in the
    record's order. A mention set in brackets right after another ("Section
    sec:computation (Proposition comp:finite-soundness)") is nested in it; mentions
    inside other brackets count only when the record names nothing outside them."""
    labels = S.PAPER_LABELS.get(slug, {})
    t = _SCOPE_HEAD.sub("", (detail or "").strip())
    stop = _HEAD_STOP.search(t)
    t = t[: stop.start()] if stop else t
    found, prev_end = [], None
    for m in _MENTION.finditer(t):
        pre = t[: m.start()]
        depth = max(0, pre.count("(") - pre.count(")"))
        opened = pre.rfind("(")
        nested = depth == 1 and prev_end is not None and not t[prev_end:opened].strip() and not pre[opened + 1:].strip()
        lead = depth == 1 and not pre[:opened].strip()
        found.append((m, 0 if (nested or lead) else depth, nested))
        prev_end = m.end()
    top = [x for x in found if x[1] == 0] or [x for x in found if x[1] == 1]
    out = []
    for m, _, nested in top:
        kind = _kind_key(m.group(1))
        nums, word = [], None
        for lab in re.findall(_LABEL, m.group(2)):
            key = lab if lab in labels else f"{_LABEL_PREFIX.get(kind, '')}:{lab}"
            rec = labels.get(key)
            if not (rec and rec[2]):
                continue
            k, name, number = rec
            w = name or S.KIND_WORD.get(k) or (k or "").capitalize()
            if word is not None and w != word:
                out.append((word, nums, nested))
                nums, nested = [], False
            word = w
            href = f"{root}papers/{quote(slug)}.html#{quote(key, safe=':-_./')}" if slug in S.PAPER_READING else None
            nums.append((number, href))
        if nums:
            out.append((word, nums, nested))
    merged = []
    for word, nums, nested in out:
        if merged and merged[-1][0] == word and not nested and not merged[-1][2]:
            merged[-1][1].extend(nums)
        else:
            merged.append((word, list(nums), nested))
    return merged


def refs_text(S, groups, html: bool) -> str:
    """"Lemma 4.1", "Lemmas 3.2 and 4.1", "Section 7 (Proposition 7.1)", each number
    linked to its place on the reading page when html is set."""
    def one(word, nums):
        w = _PLURAL.get(word, word) if len(nums) > 1 else word
        if not html:
            return w + " " + join_and(S, [n for n, _ in nums])
        if len(nums) == 1:
            n, h = nums[0]
            return f'<a href="{esc(h)}">{esc(w)} {esc(n)}</a>' if h else esc(f"{w} {n}")
        return esc(w) + " " + join_and(S, [f'<a href="{esc(h)}">{esc(n)}</a>' if h else esc(n) for n, h in nums])
    parts = []
    for word, nums, nested in groups:
        s = one(word, nums)
        if nested and parts:
            parts[-1] += f" ({s})"
        else:
            parts.append(s)
    if len(parts) > 2 or (len(parts) == 2 and any(" and " in p for p in parts)):
        return ", ".join(parts[:-1]) + ", " + S.C("family.and") + " " + parts[-1]
    return join_and(S, parts)


# ---- page context ------------------------------------------------------------


class Ctx:
    """Everything one family page needs, read once."""

    def __init__(self, S, f):
        self.S = S
        self.f = f
        self.num = f["id"]
        self.fid = "f:" + self.num
        self.root = "../"
        self.r = _reader()
        self.doc = self.r.family(self.num)
        self.ev = _evidence()[self.fid]
        self.stmts = {s["id"]: s for s in self.doc.get("statements") or []}
        self.order = {s["id"]: i for i, s in enumerate(self.doc.get("statements") or [])}
        self.pairs = lean_pairings(S, self.doc)
        self.leans = list(self.doc.get("lean") or [])
        sel_lean = (self.doc.get("selection") or {}).get("lean")
        self.leans.sort(key=lambda l: (l["id"] != sel_lean,))
        self.tpls: dict = {}             # template id -> html
        self.macro_ids: list = []
        self.page_url = S.BASE_URL + f"families/{self.num}.html"
        comm = self.doc.get("community") or {}
        self.efforts = {e["id"]: e for e in comm.get("efforts") or []}
        self.cfind = {}
        for x in comm.get("findings") or []:
            self.cfind.setdefault(x.get("kind"), []).append(x)
        self.readings = {rd["source"]: rd for rd in self.doc.get("readings") or []}

    def catalogue(self) -> str:
        return ((self.doc.get("claim") or {}).get("catalogue_claim") or {}).get("text") or self.f.get("description") or ""

    def problems(self) -> list:
        return (self.cfind.get("error-reported") or []) + (self.cfind.get("correction") or [])

    # -- statements --

    def ms_of(self, sid):
        st = self.stmts.get(sid)
        if not st:
            return None, None, None
        slug = (st.get("manuscript_id") or "")[2:]
        m = self.S.MS.get(slug)
        if not m:
            return st, None, None
        src = st.get("source") or {}
        rel = (src.get("file") or "").removeprefix(f"preprints/{slug}/")
        hit = None
        for x in m.get("statements") or []:
            if x.get("file") == rel and x.get("line") == src.get("line"):
                hit = x
                break
        if hit is None:
            for x in m.get("statements") or []:
                if x.get("label") and x.get("label") == st.get("name"):
                    hit = x
                    break
        if m["id"] not in self.macro_ids:
            self.macro_ids.append(m["id"])
        return st, m, hit

    def readable(self, slug) -> bool:
        return slug in self.S.PAPER_READING

    def passage_href(self, sid) -> str | None:
        st = self.stmts.get(sid)
        if not st:
            return None
        slug = (st.get("manuscript_id") or "")[2:]
        if st.get("reading_page") and self.readable(slug):
            return self.root + st["reading_page"]
        return None

    def label(self, sid) -> str:
        st = self.stmts.get(sid)
        return stmt_label(st) if st else sid

    def paper_short(self, slug, n=70) -> str:
        m = self.S.MS.get(slug) or {}
        return clip(self.S.tex_plain(m.get("title") or slug), n)

    def short_title_tex(self, slug) -> str:
        """A paper's title cut at its colon when the part before it names it, as the map's
        labels do (build_universe.short_title); a cut never splits a formula."""
        t = (self.S.MS.get(slug) or {}).get("title") or slug
        head = t.split(": ", 1)[0]
        whole = head.count("\\(") == head.count("\\)")
        return head if whole and 12 <= len(self.S.tex_plain(head)) < len(self.S.tex_plain(t)) else t

    def short_title_html(self, slug) -> str:
        return f'<span class="tex-auto">{self.S.rich(curly_tex(self.short_title_tex(slug)))}</span>'

    def short_title_plain(self, slug) -> str:
        return curly(self.S.tex_plain(self.short_title_tex(slug)))

    def where_plain(self, sid) -> str:
        """"The Quasi-Riemann Hypothesis (alternate 11/12 proof), 5 October 2026": which
        paper a statement is from, in words, for an accessible name or a record's head."""
        st = self.stmts.get(sid) or {}
        slug = (st.get("manuscript_id") or "")[2:]
        date = self.S.date_words((self.S.MS.get(slug) or {}).get("date"))
        return self.short_title_plain(slug) + (f", {date}" if date else "")

    def stmt_body(self, sid) -> str:
        st, m, ms_st = self.ms_of(sid)
        text = (ms_st or {}).get("text") or (st or {}).get("text")
        if not (m and text):
            return f'<p class="fx-muted">{esc(W("claim.no_text"))}</p>'
        conv = self.S.LabelTexConv(m, self.root)
        body = self.S.glue(self.S.statement_blocks(conv, text, self.passage_href(sid)))
        return self.S.guard_labels(f"{m['id']} line {(st.get('source') or {}).get('line')}", body)

    def title_tex(self, sid) -> str:
        """The heading title the paper gives a statement ("Universal energy minimum"): the
        Atlas's extraction, else the backend's name for it when that name is a title rather
        than a TeX label (where both exist, the two agree on every statement)."""
        st, m, ms_st = self.ms_of(sid)
        if ms_st and ms_st.get("title"):
            return ms_st["title"]
        name = (st or {}).get("name") or ""
        return name if " " in name and ":" not in name else ""

    def title_plain(self, sid) -> str:
        t = self.title_tex(sid)
        return curly(self.S.tex_plain(t)) if t else ""

    def stmt_title_html(self, sid) -> str:
        st, m, ms_st = self.ms_of(sid)
        t = self.title_tex(sid)
        if t and m:
            conv = self.S.LabelTexConv(m, self.root)
            return f' <span class="fx-st__title">({conv.text(t, inline=True)})</span>'
        return ""

    def label_plain(self, sid) -> str:
        """"Theorem 1.1 (Universal energy minimum)": the printed label and title in words."""
        t = self.title_plain(sid)
        return self.label(sid) + (f" ({t})" if t else "")

    def stmt_where(self, sid) -> str:
        st, m, _ = self.ms_of(sid)
        if not m:
            return ""
        paper = f'<a href="{self.root}papers/{esc(m["id"])}.html"><span class="tex-auto">{self.S.rich(curly_tex(m["title"]))}</span></a>'
        date = self.S.date_words(m.get("date"))
        return W("claim.in_paper", paper=paper, date=f'<span class="fx-nw">, {esc(date)}</span>') if date else W("claim.in_paper_undated", paper=paper)

    def stmt_card(self, sid, *, aid: str, level: int = 3, state: str = "", note: str = "", big: bool = False, actions: str = "") -> str:
        """A paper statement exactly as printed: its number, the paper and date, then (in
        the same heading group, in the interface face) the atlas's qualification of why it
        is shown, the text, then the way into the paper at that passage (and any further
        actions). The heading group says what the object is and what the atlas proposes;
        the body is the paper's own words."""
        st, m, ms_st = self.ms_of(sid)
        if not st:
            return ""
        go = []
        href = self.passage_href(sid)
        if href:
            go.append(f'<a class="btn {"btn--ghost" if big else "btn--ghost btn--small"}" href="{esc(href)}">{esc(W("claim.read_passage"))}</a>')
        if actions:
            go.append(actions if big else actions.replace("btn btn--ghost", "btn btn--ghost btn--small"))
        if m:
            go.append(f'<a class="btn btn--quiet ext" href="{esc(m["pdf_url"])}" rel="noopener" aria-label="{esc(self.S.C("words.pdf_label", title=self.S.tex_plain(m["title"])))}">{esc(W("claim.pdf"))}</a>')
        tex = ""
        text = (ms_st or {}).get("text")
        if text:
            tex = (f'<button class="btn btn--quiet fx-st__tex" type="button" data-copy-text="{esc(text)}" '
                   f'data-copied="{esc(W("claim.tex_copied"))}">{esc(W("claim.tex_copy"))}</button>')
        h = f"h{level}"
        pdate = self.S.date_words(m.get("date")) if m else ""
        return (f'<article class="fx-st{" fx-st--big" if big else ""}" id="{esc(aid)}" data-macros="{esc(m["id"]) if m else ""}" aria-labelledby="{esc(aid)}-h" '
                f'data-paper="{esc(self.S.tex_plain(m["title"])) if m else ""}" data-date="{esc(pdate)}" '
                f'data-from="{esc(W("source.from"))}" data-open="{esc(W("source.open"))}" data-close="{esc(W("source.close"))}">'
                f'<header class="fx-st__hg{" fx-st__hg--state" if state else ""}">'
                + (f'<p class="fx-st__role">{esc(W("claim.role"))}</p>' if big else "") +
                f'<{h} class="fx-st__head" id="{esc(aid)}-h"><span class="fx-st__kind">{esc(self.label(sid))}</span>{self.stmt_title_html(sid)}</{h}>'
                f'<p class="fx-st__src">{self.stmt_where(sid)}</p>'
                + (f'<div class="fx-st__state">{state}</div>' if state else "") + '</header>'
                f'<div class="fx-st__body">{self.stmt_body(sid)}</div>{note}'
                f'<footer class="fx-st__foot"><p class="fx-st__acts">{"".join(go)}</p>{tex}</footer></article>')

    def stmt_tpl(self, sid, extra_rows=()) -> str:
        """The inspection record of a paper statement; returns its template id."""
        tid = "ins-st-" + slug_id(sid[2:])
        if tid in self.tpls:
            return tid
        st, m, _ = self.ms_of(sid)
        links = []
        href = self.passage_href(sid)
        if href:
            links.append((W("claim.read_passage"), href))
        if m:
            links.append((W("claim.pdf"), m["pdf_url"]))
        rows = [(W("inspect.paper"), self.stmt_where(sid))] + list(extra_rows)
        body = f'<div class="ins-rec__body">{self.stmt_body(sid)}</div>'
        self.tpls[tid] = record(W("inspect.kind_statement"), esc(self.label(sid)) + self.stmt_title_html(sid), rows, links,
                                body=body, macros=m["id"] if m else "")
        return tid

    def lean_tpl(self, lid) -> str:
        tid = "ins-lean-" + slug_id(lid[2:])
        if tid in self.tpls:
            return tid
        l = next(x for x in self.leans if x["id"] == lid)
        name = lid[2:]
        rec = self.pairs[lid]
        role = W("compare.lean_main") if l.get("main_result") else W("compare.lean_support")
        acc = [self.source_name(s) for s in l.get("accepted_current_sources") or []]
        paired = (esc(self.label(rec["target"])) + f' <span class="ins-rec__note">({esc(sayc("pairing_short." + rec["state"]))})</span>') if rec["target"] else esc(sayc("pairing.unavailable"))
        runs = runs_sentence(self, l)
        self.tpls[tid] = record(W("inspect.kind_lean"), f'<code translate="no">{esc(name)}</code>',
                                [(W("inspect.statement"), f'<span class="md-math">{esc(l.get("name") or "")}</span>'),
                                 (W("inspect.role"), esc(role)), (W("inspect.paired_with"), paired),
                                 (W("compare.runs_link"), esc(runs))],
                                [(W("compare.lean_open"), f"{self.root}statements/{name}.html")])
        return tid

    def source_name(self, src: str) -> str:
        for l in self.leans:
            for ru in l.get("runs") or []:
                if ru.get("source") == src:
                    return (ru.get("credit") or {}).get("name") or src
        rd = self.readings.get(src)
        if rd:
            return (rd.get("credit") or {}).get("name") or src
        return src

    def effort_credit(self, x) -> str:
        """The credit for a community finding: the authors and name of the effort it cites.
        When the packet holds no record of that effort, the finding is never shown bare: the
        credit is where its own link points, in plain words, or that the record names no author."""
        e = self.efforts.get(x.get("effort") or "")
        if e is None:
            site = link_site(x.get("url"))
            return W("said.from_site", site=site) if site else W("said.no_author")
        who = ", ".join(a.get("name") for a in e.get("authors") or [] if a.get("name"))
        return ", ".join(t for t in (who, e.get("name") or "") if t) or W("said.no_author")

    def templates(self) -> str:
        return "".join(f'<template id="{tid}">{html}</template>' for tid, html in self.tpls.items())


def link_site(url) -> str:
    """Where a link points, in plain words: the site's name, with the account and project for
    GitHub and the account for a Mastodon-style address. Nothing is inferred beyond the address."""
    try:
        u = urlparse(url or "")
    except ValueError:
        return ""
    host = (u.netloc or "").lower().removeprefix("www.")
    if not host:
        return ""
    parts = [p for p in (u.path or "").split("/") if p]
    if host == "github.com" and parts:
        return host + "/" + "/".join(parts[:2])
    if parts and parts[0].startswith("@"):
        return host + "/" + parts[0]
    return host


def record(kind: str, title_html: str, rows, links, *, body: str = "", macros: str = "", sub: str = "") -> str:
    """One inspection record: kind, title (with the source it comes from under it, when two
    records could share a title), body, rows of facts, and real links."""
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows if v)
    ls = "".join(f'<li><a href="{esc(h)}"{" class=\"ext\" rel=\"noopener\"" if str(h).startswith("http") else ""}>{esc(t)}</a></li>'
                 for t, h in links if h)
    mac = f' data-macros="{esc(macros)}"' if macros else ""
    return (f'<div class="ins-rec"{mac}><p class="ins-rec__kind">{esc(kind)}</p><p class="ins-rec__title">{title_html}</p>'
            + (f'<p class="ins-rec__sub">{sub}</p>' if sub else "") + body
            + (f'<dl class="ins-rec__dl">{dl}</dl>' if dl else "") + (f'<ul class="ins-rec__links">{ls}</ul>' if ls else "") + "</div>")


def ins_button(tid: str, label_html: str, cls: str = "", name: str = "") -> str:
    """A trigger that opens a record in the rail. name is its accessible name, which starts
    with the visible words and says whose record it opens (WCAG 2.5.3)."""
    aria = f' aria-label="{esc(name)}"' if name else ""
    return f'<button class="ins{(" " + cls) if cls else ""}" type="button" data-inspect="{tid}"{aria}>{label_html}</button>'


def finds_list(c: Ctx, items) -> str:
    """Credited community items: who and when first, so the reader knows who is speaking,
    then what they say, with the link to where they said it."""
    out = []
    for x in sorted(items, key=lambda x: x.get("date") or "", reverse=True):
        who = c.effort_credit(x)
        when = c.S.date_words(x.get("date"))
        out.append(f'<li class="fx-find"><p class="fx-find__who">{esc(", ".join(t for t in (curly(who), when) if t))}{". " if (who or when) else ""}'
                   f'<a class="ext" href="{esc(x.get("url") or "")}" rel="noopener">{esc(c.S.C("community.source"))}</a></p>'
                   f'<p class="fx-find__what">{esc(curly(x.get("summary") or ""))}</p></li>')
    return '<ul class="fx-finds">' + "".join(out) + "</ul>"


def folded(items_html: list, keep: int, more_label: str) -> str:
    if len(items_html) <= keep + 1:
        return "".join(items_html)
    return "".join(items_html)


# ---- the head -----------------------------------------------------------------


def catalogue_link(c: Ctx) -> str:
    return f'<a class="ext" href="{c.S.BASE_BLOB}CONTENTS.md" rel="noopener">{esc(W("head.catalogue"))}</a>'


def head_html(c: Ctx) -> str:
    """The trail, the family's name and OpenAI's catalogue description, credited. When the
    headline is unresolved the whole description is shown, since it leads the claim."""
    S, f, root, doc = c.S, c.f, c.root, c.doc
    di = S.DISC_OF[c.num]
    disc = S.DISCIPLINES[di]["name"]
    trail = (f'<nav class="trail fx-trail" aria-label="{esc(S.C("nav.breadcrumb"))}"><a href="{root}index.html">{esc(W("trail.map"))}</a>'
             f'<span class="trail__sep" aria-hidden="true">/</span><a href="{root}index.html#o=d%3A{S.DISC_SLUG[di]}">{esc(disc)}</a>'
             f'<span class="trail__sep" aria-hidden="true">/</span><span aria-current="page">{esc(W("trail.family", num=c.num))}</span></nav>')
    tools = (f'<p class="fx-tools"><a class="btn btn--small" href="{root}index.html#o=f%3A{c.num}">{esc(W("actions.plate"))}</a>'
             f'<button class="btn btn--small" type="button" data-copy-text="{esc(c.page_url)}" data-copied="{esc(W("actions.copied"))}">{esc(W("actions.copy"))}</button></p>')
    title_plain = S.tex_plain(f["title"])
    cat = c.catalogue()
    lead, more = cat, ""
    quote = (f'<figure class="fx-quote" id="h-desc"><figcaption class="fx-quote__src">{W("head.quote_credit", link=catalogue_link(c))}</figcaption>'
             f'<blockquote class="fx-quote__q"><p class="tex-auto">{S.glue(S.rich(curly_tex(lead), "", root, link_results=True))}</p>{more}</blockquote></figure>')
    extra = []
    erd = S.sourced(f, "erdos_problems")
    if erd and erd.get("value"):
        probs_ = [f'<a class="ext" href="{esc(p["url"])}" rel="noopener">{esc(W("head.erdos_number", n=p["number"]))}</a>' for p in erd["value"]]
        joined = probs_[0] if len(probs_) == 1 else ", ".join(probs_[:-1]) + " " + S.C("family.and") + " " + probs_[-1]
        extra.append(W("head.erdos", problems=joined, source=S.credit_link(erd["source"], root)))
    probs = c.problems()
    if probs:
        p = W("head.problems_one") if len(probs) == 1 else W("head.problems_many", n=cap(S.say(len(probs))))
        extra.append(f'<a href="#problems">{esc(p)}</a>')
    facts = "".join(f'<p class="fx-fact">{x}</p>' for x in extra)
    return f"""<header class="fx-head">
 <div class="fx-bar">{trail}{tools}</div>
 <h1 class="fx-title{' fx-title--long' if len(title_plain) > 64 else ''}"><span class="tex-auto">{S.rich(curly_tex(f["title"]))}</span></h1>
 {quote}{facts}
</header>"""


def status_runs(c: Ctx) -> str:
    """Who reports accepting a re-run, counted by the outside groups in each Lean statement's
    accepted_current_sources (the backend's record), never by the number of Lean statements.
    When every accepting group re-ran the same statement their number is exact; across
    several statements the groups are counted only to tell one group from several."""
    n = len(c.leans)
    accepted = [l for l in c.leans if l.get("accepted_current_sources")]
    groups = {s for l in accepted for s in l.get("accepted_current_sources") or []}
    by = "one" if len(groups) == 1 else "many"
    g = c.S.say(len(groups))
    if not accepted:
        return W("status.runs_none")
    if n == 1:
        return W(f"status.runs_it_by_{by}", g=g)
    if len(accepted) == 1:
        return W(f"status.runs_one_by_{by}", g=g)
    if len(accepted) == n:
        return W(f"status.runs_all_by_{by}", g=g)
    return W(f"status.runs_some_by_{by}", k=c.S.say(len(accepted)), g=g)


def status_html(c: Ctx) -> str:
    """Two lines kept apart: the formal status and the readable argument."""
    S = c.S
    n = len(c.leans)
    if not n:
        formal = esc(W("status.formal_none"))
    else:
        runs = status_runs(c)
        lean = W("status.lean_one") if n == 1 else W("status.lean_many", n=S.say(n))
        formal = f'<a href="#compare">{esc(cap(lean))}</a> ' + esc(W("status.formal_some", runs=runs))
    cur = [h for h in c.doc.get("paper_history") or [] if h.get("status") == "current"]
    k = sum(1 for h in cur if c.readable(h["id"][2:]))
    if k == len(cur) and k:
        reading = W("status.reading_one") if k == 1 else W("status.reading_all")
    elif k:
        reading = W("status.reading_some", k=S.say(k))
    else:
        reading = W("status.reading_none")
    paper = W("status.readable_papers_one", reading=reading) if len(cur) == 1 else W("status.readable_papers_many", n=cap(S.say(len(cur))), reading=reading)
    readable = f'<a href="#papers">{esc(paper)}</a>'
    rev = S.reviewed_explanations(c.num)
    if rev:
        links = ", ".join(f'<a href="{c.root}{S.explanation_rel(e, c.num)}">{esc(e.get("title") or S.C("explanation.untitled"))}</a>' for e in rev)
        readable += " " + W("status.explained_reviewed", links=links)
    ex = c.cfind.get("explanation") or []
    if ex:
        n_ex = W("status.explained_others_one") if len(ex) == 1 else W("status.explained_others_many", n=cap(S.say(len(ex))))
        readable += f' <a href="#explanations">{esc(n_ex)}</a>'
    return (f'<dl class="fx-status" id="h-standing">'
            f'<div class="fx-status__row"><dt>{esc(W("status.formal"))}</dt><dd>{formal}</dd></div>'
            f'<div class="fx-status__row"><dt>{esc(W("status.readable"))}</dt><dd>{readable}</dd></div></dl>')


# ---- the theorem -------------------------------------------------------------------


def why_button(c: Ctx, sid: str, terms, *, primary: bool, lean: str | None = None, label_key: str = "why.button") -> str:
    """The quiet route to how a passage was found: the exact shared words and the
    backend's reason, in the rail. The state itself stays visible on the card."""
    claim = c.doc.get("claim") or {}
    tid = "ins-why-" + slug_id(sid[2:]) + (f"-{slug_id(lean)}" if lean else "")
    # Two papers can each have a Theorem 1.1: the record's head names the paper and date.
    sub = esc(W("why.from", where=c.where_plain(sid)))
    if lean and tid not in c.tpls:
        rows = [(W("why.method"), esc(W("why.method_lean", name=lean))),
                (W("why.words"), esc(", ".join(terms)) if terms else esc(W("claim.shared_none"))),
                (W("why.review"), esc(W("why.review_lean")))]
        c.tpls[tid] = record(W("why.kind"), esc(c.label(sid)) + c.stmt_title_html(sid), rows, [], sub=sub)
    if tid not in c.tpls:
        rows = [(W("why.method"), esc(W("why.method_text"))),
                (W("why.words"), esc(", ".join(terms)) if terms else esc(W("claim.shared_none"))),
                (W("why.review"), esc(W("why.review_text")))]
        if claim.get("reason"):
            rows.append((W("why.reason"), esc(claim["reason"])))
        c.tpls[tid] = record(W("why.kind"), esc(c.label(sid)) + c.stmt_title_html(sid), rows, [], sub=sub)
    return ins_button(tid, esc(W(label_key)), "fx-why",
                      name=W("why.button_label", button=W(label_key), label=c.label_plain(sid), where=c.where_plain(sid)))


def theorem_html(c: Ctx) -> str:
    """The page's centrepiece: the theorem the backend names as the candidate for the
    catalogue's headline, exactly as printed, with the way into the paper and to the Lean.
    When the headline is unresolved the catalogue's words (above) lead, one sentence says
    so, and the possible matches follow in the backend's order, each typeset with its
    paper. Each card says its state in one line; how it was found is one step away."""
    S, doc = c.S, c.doc
    claim = doc.get("claim") or {}
    alts = [a for a in claim.get("alternatives") or [] if a.get("statement_id") in c.stmts]
    cand = claim.get("primary_candidate")
    parts = []

    def state(sid, primary, extra=""):
        """The qualification, in the card's heading group beside the paper and date: what
        the atlas proposes (a possible match, found from shared wording, not reviewed) and
        the quiet way to how it was found."""
        terms = next((a.get("matched_terms") for a in alts if a.get("statement_id") == sid), None) or []
        words = W("claim.state_primary") if primary else W("claim.state_alt")
        return f'<p class="fx-st__qual">{esc(words)} {why_button(c, sid, terms, primary=primary)}</p>{extra}'

    def unpaired(sid):
        return f'<p class="fx-cand">{esc(W("claim.no_lean_paired"))}</p>' if c.leans and not compare_action(c, sid) else ""

    if claim.get("state") == "candidate" and cand in c.stmts:
        rest = [a for a in alts if a.get("statement_id") != cand]
        parts.append(c.stmt_card(cand, aid="claim-theorem", level=2, big=True, actions=compare_action(c, cand),
                                 state=state(cand, True, alt_line(c, cand, rest)), note=unpaired(cand)))
        if len(rest) > ALT_INLINE:
            parts.append(f'<div class="fx-others" id="claim-more"><h3 class="fx-h3">{esc(more_label(c, len(rest)))}</h3>{alt_list(c, rest)}</div>')
        parts.append(status_html(c))
    else:
        parts.append(f'<h2 class="fx-h2 fx-h2--theorem" id="claim-h">{esc(W("claim.heading_unresolved"))}</h2>'
                     f'<p class="fx-cand fx-cand--open">{esc(W("claim.unresolved"))}</p>')
        if alts:
            tied = tie_order(c, alts)[:3]
            rest = [a for a in alts if a not in tied]
            parts.append(claim_index(c, tied, rest))
            for i, a in enumerate(tied):
                parts.append(c.stmt_card(a["statement_id"], aid=f"claim-alt-{i + 1}", level=3, big=len(tied) == 1,
                                         state=state(a["statement_id"], False), note=unpaired(a["statement_id"]),
                                         actions=compare_action(c, a["statement_id"])))
            if rest:
                parts.append(f'<div class="fx-others" id="claim-more"><h3 class="fx-h3">{esc(more_label(c, len(rest)))}</h3>{alt_list(c, rest)}</div>')
        parts.append(status_html(c))
    lab = "claim-theorem-h" if (claim.get("state") == "candidate" and cand in c.stmts) else "claim-h"
    return (f'<section class="fx-sec fx-sec--theorem" id="claim" aria-labelledby="{lab}">'
            f'<span class="fx-alias" id="h-bench"></span><span class="fx-alias" id="bench-theorem"></span>{"".join(parts)}</section>')


def tie_order(c: Ctx, alts) -> list:
    """The candidates the backend ties (equal score, the highest), in the order the page
    shows them: the one a Lean statement is paired with first, then the lead paper's, then
    the backend's own order. The tie and its words stay the backend's."""
    top = max((a.get("score") or 0) for a in alts) if alts else 0
    tied = [a for a in alts if (a.get("score") or 0) == top]
    lead = next((h.get("id") for h in c.doc.get("paper_history") or [] if h.get("status") == "current"), None)
    def key(ia):
        i, a = ia
        sid = a["statement_id"]
        return (paired_lean(c, sid) is None, c.stmts[sid].get("manuscript_id") != lead, i)
    return [a for _, a in sorted(enumerate(tied), key=key)]


def claim_index(c: Ctx, tied: list, rest: list) -> str:
    """When the headline is unresolved, one line before the cards names every possible
    match shown in full (its printed number and paper, linked to its card) and how many
    more are listed after them, so a reader sees what there is before the long cards."""
    if len(tied) < 2 and not rest:
        return ""
    items = []
    for i, a in enumerate(tied):
        sid = a["statement_id"]
        slug = (c.stmts[sid].get("manuscript_id") or "")[2:]
        where = esc(W("claim.alt_in", paper="\x00")).replace("\x00", c.short_title_html(slug))
        items.append(f'<a class="fx-st__altk" href="#claim-alt-{i + 1}">{esc(c.label(sid))}</a> {where}')
    line = esc(W("claim.index_shown", items="\x00")).replace("\x00", join_and(c.S, items))
    if rest:
        listed = f'<a href="#claim-more">{esc(W("claim.listed_after_them" if len(tied) > 1 else "claim.listed_after_it"))}</a>'
        more = W("claim.index_rest_one", listed="\x01") if len(rest) == 1 else W("claim.index_rest_many", n=cap(c.S.say(len(rest))), listed="\x01")
        line += " " + esc(more).replace("\x01", listed)
    return f'<p class="fx-cand-idx">{line}</p>'


ALT_INLINE = 2   # up to this many other possible matches are named, with their records, in the card itself


def alt_line(c: Ctx, cand: str, rest: list) -> str:
    """The other possible matches, named in the candidate card's heading group: which
    statement and which paper, each linked to its passage. With at most ALT_INLINE of them
    each carries its own route to why it is listed, and there is no list below the card;
    a longer list is below the card, and the first two are named here."""
    if not rest:
        return ""
    home = c.stmts[cand].get("manuscript_id")
    inline = len(rest) <= ALT_INLINE
    items = []
    for a in rest[:2]:
        sid = a["statement_id"]
        st = c.stmts[sid]
        slug = (st.get("manuscript_id") or "")[2:]
        href = c.passage_href(sid) or f"{c.root}papers/{quote(slug)}.html"
        if st.get("manuscript_id") == home:
            where = esc(W("claim.alt_same"))
        else:
            where = esc(W("claim.alt_in", paper="\x00")).replace("\x00", c.short_title_html(slug))
        why = (" (" + why_button(c, sid, a.get("matched_terms") or [], primary=False, label_key="why.button_alt") + ")") if inline else ""
        items.append(f'<span class="fx-st__altv"><a class="fx-st__altk" href="{esc(href)}">{esc(c.label(sid))}</a>{c.stmt_title_html(sid)} {where}{why}</span>')
    named = join_and(c.S, items)
    if len(rest) == 1:
        line = esc(W("claim.alt_one", items="\x00")).replace("\x00", named)
    elif len(rest) == 2:
        line = esc(W("claim.alt_two", items="\x00")).replace("\x00", named)
    else:
        listed = f'<a href="#claim-more">{esc(W("claim.alt_listed"))}</a>'
        line = (esc(W("claim.alt_many", n=cap(c.S.say(len(rest))), listed="\x01", items="\x00"))
                .replace("\x01", listed).replace("\x00", named))
    return f'<p class="fx-st__alt">{line}</p>'


def paired_lean(c: Ctx, sid: str) -> str | None:
    """The first Lean statement of the family (in the page's order) whose recorded pairing
    targets this paper statement, or None. Only such a statement has a Lean to compare."""
    return next((l["id"][2:] for l in c.leans if c.pairs[l["id"]].get("target") == sid), None)


def compare_action(c: Ctx, sid: str) -> str:
    """"Compare with Lean" on a theorem card, only when a Lean statement is paired with that
    theorem; it opens that pairing's comparison."""
    name = paired_lean(c, sid)
    return f'<a class="btn btn--ghost" href="#lean-{esc(name)}">{esc(W("actions.compare"))}</a>' if name else ""


def more_label(c: Ctx, n: int) -> str:
    return W("claim.more_one") if n == 1 else W("claim.more_many", n=cap(c.S.say(n)))


def alt_list(c: Ctx, alts, keep: int = 0, lean: str | None = None) -> str:
    """Statements that share words with a description or a Lean statement, as a short
    visible list: each linked by its printed number to its passage, with its paper and
    the words it shares. The statement itself is on the reading page and in its record."""
    rows = []
    for a in alts:
        sid = a.get("statement_id") or a.get("target")
        if sid not in c.stmts:
            continue
        terms = a.get("matched_terms") or []
        st = c.stmts[sid]
        slug = (st.get("manuscript_id") or "")[2:]
        m = c.S.MS.get(slug) or {}
        href = c.passage_href(sid) or f"{c.root}papers/{esc(slug)}.html"
        date = c.S.date_words(m.get("date"))
        # Which paper, by its short title typeset as the map labels it, and its date.
        where = esc(W("claim.alt_in", paper="\x00")).replace("\x00", c.short_title_html(slug)) + (f", {esc(date)}" if date else "")
        rows.append(f'<li class="fx-alt"><a class="fx-alt__k" href="{esc(href)}">{esc(c.label(sid))}</a>{c.stmt_title_html(sid)} '
                    f'<span class="fx-alt__p">{where}.</span> {why_button(c, sid, terms, primary=False, lean=lean)}</li>')
    return f'<ul class="fx-alts">{"".join(rows)}</ul>' if rows else ""


# ---- the Lean beside the theorem -------------------------------------------------------


def lean_card(c: Ctx, l) -> str:
    S = c.S
    name = l["id"][2:]
    s = S.ST.get(name)
    role = W("compare.lean_main") if l.get("main_result") else W("compare.lean_support")
    code = ""
    more = ""
    if s:
        names = s["comparator"]["theorem_names"] or s["theorems"][:1]
        first = dict(s, comparator=dict(s["comparator"], theorem_names=names[:1]))
        code = f'<pre class="lean lean--snippet fx-lean__code"><code>{S.lean_breaks(S.lean_snippet_html(first, max_lines=16))}</code></pre>'
        if len(names) > 1:
            lines = {d["name"]: d["line"] for d in s.get("declarations") or []}
            items = ", ".join(f'<a href="{c.root}statements/{esc(name)}.html' + (f'#L{lines[n_]}' if n_ in lines else "")
                              + f'"><code translate="no">{S.lean_breaks(">" + esc(n_.split(".")[-1]))[1:]}</code></a>' for n_ in names[1:])
            lead = W("compare.lean_more_one") if len(names) == 2 else W("compare.lean_more_many", n=S.say(len(names) - 1))
            more = f'<p class="fx-lean__more">{esc(lead)} {items}.</p>'
    holes = l.get("definition_holes") if isinstance(l.get("definition_holes"), list) else []
    holes_html = ""
    if holes:
        shown = ", ".join(f'<code translate="no">{esc(h.split(".")[-1])}</code>' for h in holes[:6]) + (f" {esc(W('left.names_more', n=len(holes) - 6))}" if len(holes) > 6 else "")
        holes_html = f'<p class="fx-lean__note">{W("compare.holes_one", names=shown) if len(holes) == 1 else W("compare.holes_many", n=cap(S.say(len(holes))), names=shown)}</p>'
    acc = [c.source_name(x) for x in l.get("accepted_current_sources") or []]
    runs = runs_sentence(c, l)
    terms = run_terms(c, l)
    return (f'<article class="fx-lean" aria-labelledby="lean-{esc(name)}-h">'
            f'<h4 class="fx-lean__head" id="lean-{esc(name)}-h"><a href="{c.root}statements/{esc(name)}.html"><span class="md-math">{esc(curly_tex(l.get("name") or name))}</span></a></h4>'
            f'<p class="fx-lean__file"><code translate="no">{S.lean_breaks(">" + esc(name))[1:]}.lean</code>, {esc(role)}.</p>'
            f'{code}' + (f'<p class="fx-lean__note">{W("compare.sorry")}</p>' if code and "sorry" in (s or {}).get("lean", "") else "") + f'{more}{holes_html}'
            f'<p class="fx-lean__runs">{esc(runs)} <a href="#reruns-{esc(name)}">{esc(W("compare.runs_link"))}</a></p>'
            + (f'<ul class="fx-lean__terms">{"".join(f"<li>{esc(t)}</li>" for t in terms)}</ul>' if terms else "")
            + f'<p class="fx-lean__note">{esc(sayc("reruns.what_it_checks"))}</p>'
            f'<p class="fx-lean__go"><a href="{c.root}statements/{esc(name)}.html">{esc(W("compare.lean_open"))}</a></p></article>')


def comparison_one(c: Ctx, l, *, first: bool) -> str:
    """One Lean statement beside the paper theorem it is paired with. The words at the
    join say how the two were joined and that nobody has reviewed the match."""
    lid = l["id"]
    name = lid[2:]
    rec = c.pairs[lid]
    state = rec["state"] if rec["target"] else "unavailable"
    if rec["target"] in c.stmts:
        paper = c.stmt_card(rec["target"], aid=f"paired-{slug_id(name)}", level=4)
    else:
        why = f'<p class="fx-cmp__why">{esc(W("compare.no_pair_reason", reason=rec["reason"]))}</p>' if rec.get("reason") else ""
        alts = [dict(a, statement_id=a.get("target")) for a in rec["alternatives"]]
        alt = (f'<p class="fx-cmp__why">{esc(W("compare.no_pair_alternatives"))}</p>' + alt_list(c, alts, lean=name)) if alts else ""
        paper = f'<div class="fx-st fx-st--none"><p class="fx-st__none">{esc(W("compare.no_pair"))}</p>{why}{alt}</div>'
    words = ""
    if rec["target"] and rec["shared"] and state == "candidate-pairing":
        words = esc(W("compare.shared", words=", ".join(rec["shared"])))
    for sa in c.doc.get("source_associations") or []:
        if sa.get("challenge") == name and rec["target"] in (sa.get("local_statement_ids") or []):
            q = ((sa.get("source") or {}).get("quote") or "").strip()
            if q:
                words += f' <span class="fx-join__quote">{W("compare.cited_quote", quote=code_spans(q))}</span>'
    lean_head = (f'<p class="fx-cmp__state">{esc(W("compare.state_head." + state))}</p>'
                 f'<p class="fx-cmp__qual">{esc(W("compare.state_qual." + state))}</p>')
    join = f'<p class="fx-join fx-join--{esc(state)}">{words}</p>' if words else ""
    aliases = ('<span class="fx-alias" id="bench-lean"></span>' + (f'<span class="fx-alias" id="thread-{esc(c.num)}"></span>' if rec["target"] else "")) if first else ""
    return (f'<section class="fx-cmp" id="lean-{esc(name)}" data-cmp aria-labelledby="lean-{esc(name)}-ch">{aliases}'
            f'<h3 class="fx-cmp__h" id="lean-{esc(name)}-ch"><code translate="no">{esc(name)}</code></h3>'
            f'<div class="fx-cmp__grid fx-cmp__grid--{esc(state)}">'
            f'<div class="fx-cmp__paper"><p class="fx-cmp__side">{esc(W("compare.paper_side"))}</p>{paper}</div>'
            f'{join}'
            f'<div class="fx-cmp__lean"><div class="fx-cmp__lhead">{lean_head}</div>{lean_card(c, l)}</div>'
            f'</div></section>')


def lean_index(c: Ctx) -> str:
    """Every Lean statement in the family, one entry each, every entry in the same rhythm:
    its mathematical name (the link that chooses it), its formal identifier on a line of
    its own, then two labelled lines with separate jobs, the paper theorem it is paired
    with (and by what evidence) and who reports re-running it."""
    rows = []
    for i, l in enumerate(c.leans):
        name = l["id"][2:]
        rec = c.pairs[l["id"]]
        if rec["target"] in c.stmts:
            slug = (c.stmts[rec["target"]].get("manuscript_id") or "")[2:]
            key = {"candidate-pairing": "row_candidate", "producer-cited-association": "row_cited",
                   "producer-declared-binding": "row_declared"}.get(rec["state"], "row_candidate")
            pair = W("compare." + key, label=c.label(rec["target"]), paper=c.short_title_plain(slug))
        else:
            pair = W("compare.row_none")
        runs = runs_sentence(c, l)
        role = W("compare.index_main") if l.get("main_result") else W("compare.index_support")
        rows.append(f'<li class="fx-idx__i"><a class="fx-idx__a" href="#lean-{esc(name)}" data-cmp-tab="lean-{esc(name)}"{" aria-current=\"true\"" if i == 0 else ""}>'
                    f'<span class="fx-idx__t md-math">{esc(curly_tex(l.get("name") or name))}</span></a>'
                    f'<p class="fx-idx__id"><code translate="no">{c.S.lean_breaks(">" + esc(name))[1:]}</code><span class="fx-idx__role">, {esc(role)}</span></p>'
                    f'<dl class="fx-idx__dl"><div><dt>{esc(W("compare.index_paper"))}</dt><dd>{esc(pair)}</dd></div>'
                    f'<div><dt>{esc(W("compare.index_runs"))}</dt><dd>{esc(runs)}</dd></div></dl></li>')
    return (f'<nav class="fx-idx" id="h-index" aria-label="{esc(W("toc.compare"))}">'
            f'<ol class="fx-idx__list">{"".join(rows)}</ol></nav>')


def runs_sentence(c: Ctx, l) -> str:
    """What the outside re-runs of one Lean statement establish, with the credited groups."""
    acc = [c.source_name(x) for x in l.get("accepted_current_sources") or []]
    if not acc:
        return sayc("reruns.none")
    names = evidence.join_names(acc)
    return sayc("reruns.one", names=names) if len(acc) == 1 else sayc("reruns.many", n=c.S.say(len(acc)), names=names)


def run_terms(c: Ctx, l) -> list:
    """Each accepting group's run as its own entry, in that group's own term."""
    acc = set(l.get("accepted_current_sources") or [])
    out, seen = [], set()
    for ru in l.get("runs") or []:
        src = ru.get("source")
        if src in acc and src not in seen and ru.get("state") == "reported-accepted":
            seen.add(src)
            out.append(sayc("reruns.source_term", name=(ru.get("credit") or {}).get("name") or src, term=ru.get("source_term") or ""))
    return out


def comparison_html(c: Ctx) -> str:
    S = c.S
    alias = '<span class="fx-alias" id="h-lean"></span>'
    if not c.leans:
        body = (f'<p class="fx-prose">{esc(W("compare.nolean"))} '
                f'<a class="ext" href="{esc(S.suggest_url(c.page_url, S.C("issues.family_name", id=c.num, title=S.tex_plain(c.f["title"]))))}" rel="noopener">{esc(S.C("words.suggest_change"))}</a></p>')
        return (f'<section class="fx-sec" id="compare" aria-labelledby="compare-h">{alias}<span class="fx-alias" id="bench-lean"></span>'
                f'<h2 class="fx-h2" id="compare-h">{esc(W("toc.compare"))}</h2>{body}</section>')
    sel = c.doc.get("selection") or {}
    supporting = sel.get("scope_context") == "supporting-or-different"
    n = len(c.leans)
    heading = W("compare.heading_one") if n == 1 else W("compare.heading_many", n=cap(S.say(n)))
    intro = W("compare.index_intro") if n > 1 else W("compare.intro_one")
    if supporting:
        intro += " " + sayc("scope_context.supporting-or-different")
    idx = lean_index(c) if n > 1 else ""
    cmps = "".join(comparison_one(c, l, first=(i == 0)) for i, l in enumerate(c.leans))
    return (f'<section class="fx-sec" id="compare" aria-labelledby="compare-h" data-cmp-host>{alias}'
            f'<h2 class="fx-h2" id="compare-h">{esc(heading)}</h2><p class="fx-intro">{esc(intro)}</p>'
            f'{idx}<div class="fx-cmps">{cmps}</div>{formulations_html(c)}</section>')


def formulations_html(c: Ctx) -> str:
    """OpenAI's other formulations in the release's Lean library (atlas data): a visible
    list of their names, each linked to its line in the source."""
    S = c.S
    fam_claims = S.CLAIMS_BY_FAMILY.get(c.num, [])
    stmts_c = [x for x in fam_claims if x["kind"] == "statement"]
    thms_c = [x for x in fam_claims if x["kind"] in ("theorem", "lemma")]
    if not stmts_c:
        return ""
    items = []
    for x in stmts_c:
        cmp_note = f' <span class="fx-tag">{esc(S.C("family.formulation_checked", id=x["comparator_statement"]))}</span>' if x.get("comparator_statement") else ""
        items.append(f'<li><a class="ext" href="{esc(S.BASE_BLOB + x["file"] + "#L" + str(x["line"]))}" rel="noopener"><code translate="no">{esc(x["name"].split(".")[-1])}</code></a>'
                     f' <span class="fx-muted small">{esc(x["file"].split("/")[-1])}, line {x["line"]}</span>{cmp_note}</li>')
    thm_line = f'<p class="fx-muted small">{esc(S.C("family.formulations_theorems", n=len(thms_c)))}</p>' if thms_c else ""
    return (f'<div class="fx-forms-wrap" id="h-form"><h3 class="fx-h3">{esc(S.C("family.formulations_heading"))}</h3>'
            f'<p class="fx-intro">{esc(S.C("family.formulations_intro"))}</p><ul class="fx-plain fx-forms">{"".join(items)}</ul>{thm_line}</div>')


# ---- who has checked it ----------------------------------------------------------------


def reading_says(rd) -> str:
    """One reader's finding as a sentence: their name, what they find the Lean states
    (from the backend's normalised state) and their own term."""
    state = rd.state or "none"
    return W("readings.says", name=rd.name, finds=W("readings.state").get(state, sayc("tone." + rd.tone)), term=rd.term or "")


def readings_html(c: Ctx) -> str:
    S, ev = c.S, c.ev
    head = f'<h3 class="fx-h3" id="readings">{esc(W("readings.heading"))}</h3>'
    if not c.leans and not c.readings:
        return f'<span class="fx-alias" id="h-readings"></span>{head}<p class="fx-prose">{esc(W("readings.nolean"))}</p>'
    a, b = (list(ev.readers) + [None, None])[:2]
    lead = esc(ev.agreement_sentence())
    if ev.agreement == "disagree" and a and b and a.term and b.term:
        lead += " " + esc(W("readings.both", left=reading_says(a).rstrip("."), right=reading_says(b)))
    cols = []
    for rd in ev.readers:
        rec = c.readings.get(rd.source)
        if not rec:
            cols.append(f'<div class="fx-rd fx-rd--none"><p class="fx-rd__v">{esc(W("readings.none_says", name=rd.name))}</p></div>')
            continue
        sv = rec.get("source_value") or {}
        credit = rec.get("credit") or {}
        tid = f"ins-rd-{slug_id(rd.source)}"
        notes = []
        for key, lab in (("gap", "readings.gap"), ("note", "readings.note"), ("definitions_to_check", "readings.defs")):
            if sv.get(key):
                notes.append(f'<p class="fx-rd__note"><span class="fx-rd__k">{esc(W(lab))}:</span> <span class="md-math">{code_spans(sv[key])}</span></p>')
        method = first_sentence(credit.get("method") or "")
        links = []
        if sv.get("url"):
            links.append(f'<a class="ext" href="{esc(sv["url"])}" rel="noopener">{esc(W("readings.record"))}</a>')
        if credit.get("url"):
            links.append(f'<a class="ext" href="{esc(credit["url"])}" rel="noopener">{esc(W("readings.method_link", name=rd.name))}</a>')
        version = (credit.get("pin") or "")[:7]
        c.tpls[tid] = record(W("inspect.kind_reading"), esc(rd.name),
                             [(W("readings.term"), f"“{esc(rd.term or '')}”"), (W("readings.definition"), code_spans(sv.get("text") or "")),
                              (W("readings.method"), code_spans(credit.get("method") or "")),
                              (W("inspect.version"), f'<code translate="no">{esc(version)}</code>' if version else ""),
                              (W("inspect.licence"), esc(credit.get("license") or ""))],
                             [(W("readings.record"), sv.get("url")), (W("readings.method"), credit.get("url"))])
        # Who supplied the assessment leads it, set apart by weight from what they find.
        says = esc(W("readings.says", name="\x00", finds=W("readings.state").get(rd.state or "none", sayc("tone." + rd.tone)), term=rd.term or ""))
        says = says.replace("\x00", '<span class="fx-rd__who">' + esc(rd.name) + "</span>")
        cols.append(f'<div class="fx-rd">'
                    f'<p class="fx-rd__v">{says}</p>'
                    f'{"".join(notes)}'
                    f'<p class="fx-rd__def">{esc(W("readings.definition_of", term=rd.term or ""))} {code_spans(sv.get("text") or "")}</p>'
                    + (f'<p class="fx-rd__method">{esc(W("readings.method"))}: {code_spans(method)}</p>' if method else "")
                    + f'<p class="fx-rd__links">{" ".join(links)} '
                    f'{ins_button(tid, esc(W("readings.details")), name=W("readings.details_label", who=possessive(S, rd.name), num=c.num))}</p></div>')
    # The AI agent's draft classifications: their own subordinate group, after the outside
    # readers and OpenAI's note, each naming the Lean statement it classifies.
    drafts = []
    for l in c.leans:
        sd = l.get("scope_draft") or {}
        val = sd.get("value") or {}
        if sd.get("state") != "ai-draft" or not val:
            continue
        cls = evidence.WORDS["draft_class"].get(val.get("class"), val.get("class") or "")
        lname = l.get("name") or ""
        obj = (f'<span class="fx-draft__t md-math">{esc(curly_tex(lname))}</span> ' if lname and lname != l["id"][2:] else "")
        drafts.append(f'<li class="fx-draft__i"><p class="fx-draft__obj">{obj}<code translate="no">{esc(l["id"][2:])}</code></p>'
                      f'<p class="fx-draft__v"><span class="fx-draft__k">{esc(W("readings.draft_says"))}</span> {esc(cls)}. '
                      f'<span class="md-math">{code_spans(val.get("note") or "")}</span></p></li>')
    draft_html = ""
    if drafts:
        draft_html = (f'<div class="fx-drafts" aria-labelledby="h-drafts"><h4 class="fx-h4 fx-drafts__h" id="h-drafts">{esc(W("readings.draft_heading"))}</h4>'
                      f'<ul class="fx-draft">{"".join(drafts)}</ul></div>')
    ps = c.doc.get("producer_scope") or {}
    pv = ps.get("value") or {}
    producer = ""
    if pv.get("scope"):
        paras = [S.curly(p) for p in re.split(r"\n\s*\n", pv["scope"].strip()) if p.strip()]
        rest = S.md_paragraphs(chr(10) + chr(10).join(paras[1:])) if len(paras) > 1 else ""
        producer = (f'<div class="fx-producer"><p class="fx-producer__h"><a class="ext" href="{esc(pv.get("url") or "")}" rel="noopener">{esc(W("readings.producer"))}</a></p>'
                    f'<blockquote class="fx-producer__q md-math">{S.md_paragraphs(paras[0])}{rest}</blockquote></div>')
    return (f'<span class="fx-alias" id="h-readings"></span>{head}<p class="fx-lead-s">{lead}</p>'
            f'<p class="fx-intro">{esc(W("readings.intro"))}</p>'
            f'<div class="fx-rds">{"".join(cols)}</div>{producer}{draft_html}')


def _bytes(n) -> str:
    return f"{n / 2**30:.1f} GiB" if n else ""


def run_fields(ru) -> str:
    """The toolchain, kernels, axioms used, time and memory a re-run report gives as fields
    of their own, as one sentence, or "" when it gives none. A field the report leaves
    empty is left out rather than called unrecorded: its account may still name it."""
    vals = {"toolchain": ru.get("toolchain") or "",
            "kernels": ", ".join(ru["kernels"]) if ru.get("kernels") else "",
            "axioms": ", ".join(ru["used_axioms"]) if ru.get("used_axioms") else "",
            "time": f'{ru["wall_seconds"]} s' if ru.get("wall_seconds") else "",
            "memory": _bytes(ru.get("peak_memory_bytes"))}
    parts = [W("reruns.field." + k, v=v) for k, v in vals.items() if v]
    return cap("; ".join(parts)) + "." if parts else ""


def reruns_html(c: Ctx) -> str:
    S = c.S
    others = (c.cfind.get("replay-pass") or []) + (c.cfind.get("replay-fail") or [])
    if not c.leans and not others:
        return ""
    groups = []
    any_detail = False
    cols = W("reruns.cols")
    for l in c.leans:
        name = l["id"][2:]
        runs = {ru["id"]: ru for ru in l.get("runs") or []}
        shown = [runs[rid] for g in l.get("run_groups") or [] for rid in g.get("run_ids") or [] if rid in runs]
        # A fact moves into the group's heading only when it holds for every record in it.
        one_pin = len(shown) > 0 and all(ru.get("pin_state") == "current" for ru in shown)
        rows = []
        for ru in shown:
            rid = ru["id"]
            credit = ru.get("credit") or {}
            sv = ru.get("source_value") or {}
            who = credit.get("name") or ru.get("source")
            whose = possessive(S, who)
            when = S.date_words(ru.get("date"))
            pin = W("reruns.at_pin") if ru.get("pin_state") == "current" else W("reruns.other_pin")
            # Only the fields the report gives as fields of their own are listed; a missing
            # field is never called unrecorded, since the report's account may name it.
            det = run_fields(ru)
            recorded = bool(det)
            any_detail = any_detail or recorded
            tid = "ins-run-" + slug_id(rid[4:])
            c.tpls[tid] = record(W("inspect.kind_run"), f'{esc(who)}, <code translate="no">{esc(name)}</code>',
                                 [(W("reruns.said"), f"“{esc(ru.get('source_term') or '')}”"),
                                  (W("reruns.account"), esc(S.curly(sv.get("text") or ""))),
                                  (W("inspect.date"), esc(when or W("reruns.undated"))), (W("inspect.version"), esc(pin)),
                                  (W("readings.method"), code_spans(first_sentence(credit.get("method") or ""))),
                                  (W("reruns.recorded"), esc(det))],
                                 [(W("reruns.receipt"), ru.get("receipt"))])
            date_cell = esc(when or W("reruns.undated")) + ("" if one_pin else f'<span class="fx-rt__pin">, {esc(pin)}</span>')
            receipt = (f'<a class="ext" href="{esc(ru.get("receipt") or "")}" rel="noopener" '
                       f'aria-label="{esc(W("reruns.receipt_label", who=whose, name=name))}">{esc(W("reruns.receipt"))}</a>' if ru.get("receipt") else "")
            details = ins_button(tid, esc(W("readings.details")), name=W("reruns.details_label", who=whose, name=name))
            rows.append(f'<tr><th scope="row" data-label="{esc(cols["who"])}"><span class="fx-rt__v">{esc(who)}</span></th>'
                        f'<td data-label="{esc(cols["term"])}"><span class="fx-rt__v fx-rt__term">“{esc(ru.get("source_term") or "")}”</span></td>'
                        f'<td data-label="{esc(cols["account"])}"><span class="fx-rt__v">{esc(S.curly(sv.get("text") or ""))}'
                        + (f' <span class="fx-run__det">{esc(det)}</span>' if recorded else "") + '</span></td>'
                        f'<td data-label="{esc(cols["date"])}"><span class="fx-rt__v fx-rt__date">{date_cell}</span></td>'
                        f'<td data-label="{esc(cols["receipt"])}"><span class="fx-rt__v fx-rt__go">{receipt} {details}</span></td></tr>')
        title = l.get("name") or ""
        head = ((f'<span class="fx-rg__t md-math">{esc(curly_tex(title))}</span> ' if title and title != name else "")
                + f'<code translate="no">{S.lean_breaks(">" + esc(name))[1:]}</code>')
        if rows:
            n = len(rows)
            common = W("reruns.common_pin_one") if n == 1 and one_pin else W("reruns.common_pin_many", n=cap(S.say(n))) if one_pin else W("reruns.common_one") if n == 1 else W("reruns.common_many", n=cap(S.say(n)))
            head_cells = "".join(f'<th scope="col">{esc(cols[k])}</th>' for k in ("who", "term", "account", "date", "receipt"))
            body = (f'<p class="fx-rg__common">{esc(common)}</p>'
                    f'<table class="fx-rt" aria-labelledby="reruns-{esc(name)}-h">'
                    f'<thead><tr>{head_cells}</tr></thead><tbody>{"".join(rows)}</tbody></table>')
        else:
            body = f'<p class="fx-muted">{esc(W("reruns.none"))}</p>'
        groups.append(f'<section class="fx-rg" id="reruns-{esc(name)}" aria-labelledby="reruns-{esc(name)}-h">'
                      f'<h4 class="fx-rg__h" id="reruns-{esc(name)}-h">{head}</h4>{body}</section>')
    note = "" if any_detail or not c.leans else f'<p class="fx-muted small">{esc(W("reruns.details_none"))}</p>'
    oth = ""
    if others:
        items = [finds_list(c, [x]) for x in sorted(others, key=lambda x: x.get("date") or "", reverse=True)]
        tag = "h4" if c.leans else "h3"
        cls = "fx-h4" if c.leans else "fx-h3"
        oth = (f'<{tag} class="{cls}" id="h-reported">{esc(W("reruns.others_heading"))}</{tag}><p class="fx-intro">{esc(W("reruns.others_intro"))}</p>'
               + folded(items, 3, S.C("family.show_all", n=len(items))))
    head = f'<span class="fx-alias" id="h-reruns"></span>' + (f'<h3 class="fx-h3" id="reruns">{esc(W("reruns.heading"))}</h3>' if c.leans else "")
    intro = f'<p class="fx-intro">{esc(W("reruns.intro"))} {esc(sayc("reruns.what_it_checks"))}</p>' if c.leans else ""
    return f'{head}{intro}{note}{"".join(groups)}{oth}'


def other_checks_html(c: Ctx) -> str:
    S, doc = c.S, c.doc
    cards = doc.get("independent_check_cards") or []
    unav = doc.get("unavailable_check_reports") or []
    if not cards and not unav:
        return ""
    parts = []
    if cards:
        items = []
        idents = [check_identity(c, card) for card in cards]
        plain = [p for _, _, p in idents]
        for i, card in enumerate(cards):
            v = card.get("value") or {}
            credit = card.get("credit") or {}
            kind = sayc("check_kind." + card["field"]) if card.get("field") in evidence.WORDS["check_kind"] else card.get("field")
            state = W("checks.states").get(card.get("state"), card.get("state") or "")
            what = v.get("certifies") or v.get("text") or ""
            verdict = v.get("code") or v.get("verdict") or v.get("cold") or ""
            who = credit.get("name") or card.get("source")
            whose = possessive(S, who)
            tid = f"ins-card-{i}"
            covers, whole = card_covers(v)
            covers_html = (f"“{code_spans(covers)}”" if whole else code_spans(covers)) if covers else ""
            ident_html, sub, ident = idents[i]
            # Records that look alike are never merged; when two would carry the same
            # identity, the record's own report id says what separates them.
            if plain.count(ident) > 1 and v.get("id"):
                sub = (sub + " " if sub else "") + esc(W("checks.report_id", id=v["id"]))
                ident = f"{ident} ({W('checks.report_id', id=v['id'])})"
            rows = [(W("checks.verdict"), f"“{esc(verdict)}”" if verdict else ""), (W("checks.certifies"), code_spans(what)),
                    (W("checks.relation"), covers_html),
                    (W("checks.detail"), "" if whole else code_spans(v.get("detail") or "")),
                    (W("inspect.version"), f'<code translate="no">{esc((credit.get("pin") or "")[:7])}</code>' if credit.get("pin") else "")]
            c.tpls[tid] = record(W("inspect.kind_card"), ident_html, rows, [(W("inspect.link"), v.get("url") or credit.get("url"))],
                                 sub=esc(f"{cap(kind)}, {who}"))
            # The record's outcome in its own term, then what that outcome means: the record's
            # statement of it where it gives one, else the atlas's plain words for the state.
            gloss = v.get("text") if not v.get("certifies") and v.get("text") else cap(state)
            outcome = ((f"“{esc(verdict)}” " if verdict else "") + f'<span class="fx-fields__gloss">{esc(curly(gloss).rstrip(".") + ".")}</span>'
                       if gloss else (f"“{esc(verdict)}”" if verdict else ""))
            method = W("checks.method").get(card.get("field"), cap(kind or ""))
            report = (f'<a class="ext" href="{esc(v.get("url") or credit.get("url") or "")}" rel="noopener" '
                      f'aria-label="{esc(W("checks.report_label", who=whose, what=ident))}">{esc(W("checks.report"))}</a>')
            details = ins_button(tid, esc(W("readings.details")), name=W("checks.details_label", who=whose, what=ident))
            # The record's own scope and its limits ("not the theorem") are what tell these records
            # apart, so they are set in the reading ink and size; the outcome's plain gloss, the
            # same on every record of a state, is quieter.
            fields = [(W("checks.who"), esc(who), ""), (W("checks.method_label"), esc(method), ""), (W("checks.verdict"), outcome, ""),
                      (W("checks.relation"), covers_html, "fx-fields__scope"), (W("checks.receipt"), f'{report} {details}', "")]
            dl = "".join(f'<div><dt>{esc(k)}</dt><dd{f" class={chr(34)}{cl}{chr(34)}" if cl else ""}>{val}</dd></div>' for k, val, cl in fields if val)
            items.append(f'<li class="fx-card"><p class="fx-card__id">{ident_html}</p>'
                         + (f'<p class="fx-card__sub">{sub}</p>' if sub else "")
                         + f'<dl class="fx-fields">{dl}</dl></li>')
        lst = f'<ul class="fx-cards">{"".join(items)}</ul>'
        parts.append(f'<span class="fx-alias" id="h-hol"></span><span class="fx-alias" id="h-finite"></span>{lst}')
    if unav:
        items = "".join(f'<li><a class="ext" href="{esc(u.get("url") or "")}" rel="noopener">{esc(u.get("name") or u.get("source") or u.get("url"))}</a></li>' for u in unav)
        parts.append(f'<h4 class="fx-h4">{esc(W("checks.unavailable_heading"))}</h4><ul class="fx-plain">{items}</ul>')
    return f'<h3 class="fx-h3" id="other-checks">{esc(W("checks.heading"))}</h3><p class="fx-intro">{esc(checks_intro(c, cards))}</p>{"".join(parts)}'


def check_identity(c: Ctx, card) -> tuple:
    """What a check by another method concerns, said first: (html, sub html, plain words).
    An exact check names the statements its record says it decided, as the paper prints
    them and linked to their places on the reading page, then the paper's short title and
    date; with no statement it can name, the paper alone. A HOL Light card checks the fact
    its record states, under the card's name."""
    v = card.get("value") or {}
    if v.get("certifies"):
        sub = esc(W("checks.hol_card", card=v["card"])) if v.get("card") else ""
        return (f'<span class="fx-card__what md-math">{code_spans(v["certifies"])}</span>', sub,
                curly(v["certifies"]))
    slug = v.get("manuscript") or ""
    m = c.S.MS.get(slug)
    if not m:
        return esc(slug), "", slug
    date = c.S.date_words(m.get("date"))
    groups = checked_refs(c.S, slug, v.get("detail") or v.get("scope") or "", c.root)
    paper_html = c.short_title_html(slug)
    paper_plain = c.short_title_plain(slug)
    when = f'<span class="fx-card__date">, {esc(date)}</span>' if date else ""
    if groups:
        html = esc(W("checks.id_refs", refs="\x00", paper="\x01")).replace("\x00", refs_text(c.S, groups, True)).replace("\x01", paper_html) + when
        return html, "", W("checks.id_refs", refs=refs_text(c.S, groups, False), paper=paper_plain)
    html = f'<a href="{c.root}papers/{quote(slug)}.html">{paper_html}</a>{when}'
    return html, "", paper_plain


def card_covers(v) -> tuple:
    """What a check card covers, as its record states it, and whether that is the record's
    whole statement (shown in quotation marks as the checker's words). A HOL Light card's
    relation is short and carries its own limit. An exact check's scope is only the head of
    its detail, cut at the first colon by the ingest, once inside a label ("Section
    sec:computation"); the detail states what was decided and what was not ("NOT the
    theorem"), so whenever it begins with the scope it is shown whole, never cut."""
    if v.get("relation"):
        return v["relation"], False
    scope, detail = (v.get("scope") or "").strip(), (v.get("detail") or "").strip()
    if scope and detail.startswith(scope):
        return detail, True
    return scope, False


def checks_intro(c: Ctx, cards) -> str:
    """The section's opening sentence, naming only the kinds of check this family's cards carry."""
    words = W("checks.intro_kind")
    fields = {card.get("field") for card in cards if card.get("field")}
    kinds = [words[k] for k in words if k in fields] + sorted(f for f in fields if f not in words)
    if not kinds:
        return W("checks.intro_none")
    named = kinds[0] if len(kinds) == 1 else ", ".join(kinds[:-1]) + " " + c.S.C("family.and") + " " + kinds[-1]
    return W("checks.intro", kinds=named)


def checked_html(c: Ctx) -> str:
    """Who has checked it: the outside readers, the re-runs, checks by another method,
    problems reported by others, notes on the records, and explanations by others."""
    probs = c.problems()
    finds = c.doc.get("findings") or []
    ex = c.cfind.get("explanation") or []
    parts = [readings_html(c), reruns_html(c), other_checks_html(c)]
    if probs:
        parts.append(f'<h3 class="fx-h3" id="problems"><span class="fx-alias" id="h-problems"></span>{esc(W("checks.problems_heading"))}</h3>'
                     f'<p class="fx-intro">{esc(W("checks.problems_intro"))}</p>{finds_list(c, probs)}')
    if ex:
        parts.append(f'<h3 class="fx-h3" id="explanations">{esc(W("claim.explanations_heading"))}</h3>'
                     f'<p class="fx-intro">{esc(W("claim.explanations_intro"))}</p>{finds_list(c, ex)}')
    if finds:
        items = "".join(f'<li><code translate="no">{esc(x.get("row_id") or "")}</code>: {code_spans(x.get("message") or "")}</li>' for x in finds)
        parts.append(f'<h3 class="fx-h3" id="findings">{esc(W("checks.findings_heading"))}</h3><p class="fx-intro">{esc(W("checks.findings_intro"))}</p><ul class="fx-plain">{items}</ul>')
    return (f'<section class="fx-sec" id="checks" aria-labelledby="checks-h"><span class="fx-alias" id="h-checks"></span>'
            f'<h2 class="fx-h2" id="checks-h">{esc(W("checked.heading"))}</h2>{"".join(p for p in parts if p)}</section>')


# ---- what is left to check ----------------------------------------------------------------


def left_html(c: Ctx) -> str:
    S = c.S
    items = c.doc.get("remaining_checks") or []
    if not items:
        return ""
    groups: dict = {}
    for x in items:
        groups.setdefault(x["kind"], []).append(x)
    out = []
    for kind, xs in groups.items():
        what = W("left.kinds").get(kind, kind)
        rows = []
        for x in xs:
            t = x.get("contribution_target") or {}
            tgt = x.get("target") or ""
            target = f'{t.get("id")} {t.get("fingerprint")}' if t.get("id") else None
            if tgt.startswith("l:"):
                name = tgt[2:]
                label = ins_button(c.lean_tpl(tgt), f'<code translate="no">{esc(name)}</code>') if any(l["id"] == tgt for l in c.leans) else f'<code translate="no">{esc(name)}</code>'
                stmt = name
            else:
                label = esc(W("trail.family", num=c.num))
                stmt = (c.doc.get("selection") or {}).get("lean", "") or ""
                stmt = stmt[2:] if stmt else ""
            title = f"{what}: {S.tex_plain(c.f['title'])} ({W('trail.family', num=c.num)})" + (f", {stmt}" if tgt.startswith("l:") else "")
            if kind == "replay":
                url = S.issue_url("replay", S.C("issues.replay", statement=stmt), statement=stmt, target=target or "")
            elif kind in ("scope-review", "definition-review", "pairing-review", "reader-request", "claim-identification"):
                url = S.issue_url("check", title, statement=stmt if tgt.startswith("l:") else "", upstream_commit=S.COMMIT, target=target or "")
            else:
                url = S.issue_url("problem", f"{title} [{target}]" if target else title, page=c.page_url)
            reason = x.get("reason") or ""
            credit = (x.get("credit") or {}).get("name")
            names = x.get("names") or []
            extra = ""
            if names:
                shown = ", ".join(f'<code translate="no">{esc(n.split(".")[-1])}</code>' for n in names[:8])
                extra = f' <span class="fx-left__names">{shown}{(" " + esc(W("left.names_more", n=len(names) - 8))) if len(names) > 8 else ""}</span>'
            who = f'{esc(credit)}: ' if credit else ""
            rows.append(f'<li class="fx-left__i"><span class="fx-left__t">{label}</span> '
                        f'<span class="fx-left__r md-math">{who}{code_spans(reason)}</span>{extra} '
                        f'<a class="ext fx-left__go" href="{esc(url)}" rel="noopener" aria-label="{esc(W("left.go_label", what=what.lower()))}">{esc(W("left.go"))}</a></li>')
        body = folded(rows, 4, S.C("family.show_all", n=len(rows))) if len(rows) > 5 else "".join(rows)
        out.append(f'<div class="fx-left__g"><h3 class="fx-h3">{esc(what)}</h3><ul class="fx-left">{body}</ul></div>')
    return (f'<section class="fx-sec" id="left" aria-labelledby="left-h"><span class="fx-alias" id="h-left"></span>'
            f'<h2 class="fx-h2" id="left-h">{esc(W("left.heading"))}</h2><p class="fx-intro">{esc(W("left.intro"))}</p>{"".join(out)}</section>')


# ---- papers, connections, explain, said ------------------------------------------------------


def paper_row(c: Ctx, m, seen: set) -> str:
    """One current paper, everything visible: where to read it, its date and edition, its
    abstract. Its statements are on its reading page; the anchors earlier pages linked
    to (the paper's slug, its earlier editions, its opening statements) are kept."""
    S, root = c.S, c.root
    reading = c.readable(m["id"])
    meta = S.C("family.paper_meta", date=S.date_words(m.get("date")) or S.C("family.undated"), status=S.status_label(m["status"]).lower())
    read = f'<a class="btn btn--ghost btn--small" href="{root}papers/{esc(m["id"])}.html">{esc(S.C("family.read_here") if reading else S.C("family.open_page"))}</a>'
    note = f'<div class="pp__note md-math">{S.md_paragraphs(m["version_note"], "preprints/" + m["id"] + "/")}</div>' if m.get("version_note") else ""
    prev = ""
    if m.get("previous_versions"):
        lst = ", ".join(f'<a href="{root}papers/{esc(p)}.html">{esc(S.date_words(S.MS[p]["date"]) or p) if p in S.MS else esc(p)}</a>' for p in m["previous_versions"])
        prev = f'<p class="pp__prev">{esc(S.C("family.previous_editions"))}: {lst}</p>'
    aliases = ""
    for st in S.headline_statements(m):
        aid = f'st-{S.slugify(m["id"])[:40]}-{S.slugify(st.get("label") or str(st["line"]))}'
        if aid not in seen:
            seen.add(aid)
            aliases += f'<span class="fam-alias" id="{esc(aid)}"></span>'
    for p in m.get("previous_versions") or []:
        if p not in seen and p not in c.f.get("manuscripts", []):
            seen.add(p)
            aliases += f'<span class="fam-alias" id="{esc(p)}"></span>'
    abstract = f'<div class="pp__abstract tex-auto">{S.rich(curly_tex(m.get("abstract") or ""))}</div>' if m.get("abstract") else ""
    return (f'<article class="pp" id="{esc(m["id"])}">{aliases}'
            f'<h3 class="pp__title"><a href="{root}papers/{esc(m["id"])}.html"><span class="tex-auto">{S.rich(curly_tex(m["title"]))}</span></a></h3>'
            f'<p class="pp__meta">{esc(meta)}</p><p class="pp__acts">{read}{S.pdf_button(m, "btn btn--quiet")}</p>{note}{prev}{abstract}</article>')


def papers_html(c: Ctx) -> str:
    S, root = c.S, c.root
    hist = c.doc.get("paper_history") or []
    seen: set = set()
    prev = [h for h in hist if h.get("status") == "previous-edition"]
    for h in prev:
        seen.add(h["id"][2:])
    cur = [S.MS[h["id"][2:]] for h in hist if h.get("status") == "current" and h["id"][2:] in S.MS]
    rows = "".join(paper_row(c, m, seen) for m in cur)
    for m in cur:
        if m["id"] not in c.macro_ids:
            c.macro_ids.append(m["id"])
    prev_html = ""
    if prev:
        items = []
        for h in prev:
            slug = h["id"][2:]
            m = S.MS.get(slug) or {}
            status = sayc("paper_status.previous-edition")
            items.append(f'<li class="fx-pp" id="{esc(slug)}"><a href="{root}papers/{esc(slug)}.html">{S.ms_title_html(m) if m else esc(slug)}</a> '
                         f'<span class="fx-pp__m">{esc(W("papers.status", status=status, date=S.date_words(m.get("date")) or ""))}</span>'
                         + (f' <a class="ext fx-pp__pdf" href="{esc(m["pdf_url"])}" rel="noopener" aria-label="{esc(S.C("words.pdf_label", title=S.tex_plain(m["title"])))}">{esc(W("papers.pdf"))}</a>' if m.get("pdf_url") else "")
                         + "</li>")
        prev_html = f'<h3 class="fx-h3" id="previous">{esc(W("papers.previous"))}</h3><ul class="fx-pps">{"".join(items)}</ul>'
    rs = c.f.get("reasoning_summary")
    reasoning = (f'<p class="fx-prose small">{esc(S.C("family.reasoning_summary"))} '
                 f'<a class="ext" href="{esc(rs["url"])}" rel="noopener">{esc(rs["title"])}</a></p>') if rs else ""
    return (f'<section class="fx-sec" id="papers" aria-labelledby="papers-h"><span class="fx-alias" id="h-ms"></span>'
            f'<h2 class="fx-h2" id="papers-h">{esc(W("papers.heading"))}</h2><p class="fx-intro">{S.ctext(S.C("family.papers_intro"))}</p>'
            f'<div class="pps">{rows}</div>{reasoning}{prev_html}{S.withdrawn_from_family_html(c.num, root)}</section>')


def connections_html(c: Ctx) -> str:
    S, f, root = c.S, c.f, c.root
    mss = [S.MS[s] for s in f["manuscripts"] if s in S.MS]
    cites_items, seen = [], set()
    for m in mss:
        for r in m.get("rests_on") or []:
            if r["manuscript"] not in seen:
                seen.add(r["manuscript"])
                cites_items.append((r["manuscript"], r["status"], r["has_lean"]))
    cited_items, seen = [], set()
    for m in mss:
        for x in m.get("cited_by_in_collection") or []:
            if x not in seen and x not in f["manuscripts"]:
                seen.add(x)
                cm = S.MS.get(x, {})
                cited_items.append((x, cm.get("status", "current"), cm.get("has_lean", False)))
    cites = S.related_list(cites_items, root, c.num) if cites_items else f'<p class="fx-muted">{esc(S.C("family.cites_none"))}</p>'
    cited = S.related_list(cited_items, root, c.num) if cited_items else f'<p class="fx-muted">{esc(S.C("family.cited_none"))}</p>'
    refs_html = []
    for m in mss:
        refs = m.get("references") or []
        if refs:
            refs_html.append(f'<li><a href="{root}papers/{esc(m["id"])}.html">{esc(S.C("family.refs_summary", count=len(refs), title=S.tex_plain(m["title"])))}</a></li>')
        else:
            refs_html.append(f'<li class="fx-muted">{esc(S.C("family.refs_none_in", title=S.tex_plain(m["title"])))}</li>')
    fol = c.cfind.get("follow-up-result") or []
    fol_html = ""
    if fol:
        items = [finds_list(c, [x]) for x in sorted(fol, key=lambda x: x.get("date") or "", reverse=True)]
        fol_html = f'<h3 class="fx-h3" id="h-followups">{esc(W("followups.heading"))}</h3>' + folded(items, 3, S.C("family.show_all", n=len(items)))
    return (f'<section class="fx-sec" id="cites" aria-labelledby="cites-h"><span class="fx-alias" id="h-cites"></span>'
            f'<h2 class="fx-h2" id="cites-h">{esc(S.C("family.citations_heading"))}</h2><p class="fx-intro">{esc(S.C("family.citations_intro"))}</p>'
            f'<div class="fx-cols2"><div><h3 class="fx-h3">{esc(S.C("family.cites_heading"))}</h3>{cites}</div>'
            f'<div><h3 class="fx-h3">{esc(S.C("family.cited_heading"))}</h3>{cited}</div></div>{fol_html}'
            f'<div class="fx-refs" id="h-refs"><h3 class="fx-h3">{esc(S.C("family.refs_heading"))}</h3><p class="fx-intro">{esc(W("papers.refs_intro"))} <a href="{root}references-outside.html">{esc(S.C("references_outside.title"))}</a></p><ul class="fx-plain">{"".join(refs_html)}</ul></div></section>')


def explain_html(c: Ctx) -> str:
    S, f, root, fid = c.S, c.f, c.root, c.num
    title_plain = S.tex_plain(f["title"])
    _, ex = S.family_exposition_status(fid)
    for e in S.reviewed_explanations(fid):
        S.build_explanation(f, e)
    claim = S.issue_url("claim", S.C("issues.claim", id=fid, title=title_plain), family=fid)
    credit = S.issue_url("credit", S.C("issues.credit", id=fid, title=title_plain), family=fid, upstream_commit=S.COMMIT)
    suggest = S.suggest_url(c.page_url, S.C("issues.family_name", id=fid, title=title_plain))
    credits = S.CONTRIB["credits"].get(fid, [])
    names = [n_ for e in ex for n_ in e["names"]] + [n_ for c_ in credits for n_ in c_["names"]]
    contributors = f'<h3 class="fx-h3">{esc(S.C("family.contributors_heading"))}</h3><p>{esc(", ".join(dict.fromkeys(names)))}</p>' if names else ""
    return f"""<section class="fx-sec" id="explain" aria-labelledby="explain-h"><span class="fx-alias" id="h-explain"></span>
 <h2 class="fx-h2" id="explain-h">{esc(S.C('family.explain_heading'))}</h2>
 {explanations_html(c)}
 <div class="fx-contrib" id="h-contrib">
  <p class="fx-intro">{esc(S.C('family.contribute_intro'))}</p>
  <p class="actions"><a class="btn btn--ghost ext" href="{esc(claim)}" rel="noopener">{esc(S.C('family.claim_button'))}</a>{check_buttons(c)}<a class="btn btn--ghost ext" href="{esc(credit)}" rel="noopener">{esc(S.C('family.credit_button'))}</a><a class="btn btn--quiet ext" href="{esc(suggest)}" rel="noopener">{esc(S.C('words.suggest_change'))}</a></p>
 </div>
 {contributors}
</section>"""


def explanations_html(c: Ctx) -> str:
    """Explanations written for the atlas: reviewed ones as reading routes, drafts as a
    visible list, an invitation when there are none."""
    S, fid, root = c.S, c.num, c.root
    ex = S.CONTRIB["explanations"].get(fid, [])
    parts = []
    for e in [e for e in ex if e["status"] == "reviewed"]:
        href = f'{root}{S.explanation_rel(e, fid)}'
        parts.append(f'<article class="exrec"><h3 class="fx-h3 md-math"><a href="{href}">{esc(e.get("title") or S.C("explanation.untitled"))}</a></h3>'
                     f'{S.explanation_meta_html(e, fid, root)}<p class="actions"><a class="btn btn--ghost" href="{href}">{esc(S.C("family.read_explanation"))}</a></p></article>')
    drafts = [e for e in ex if e["status"] != "reviewed"]
    if drafts:
        items = "".join(f'<li><span class="md-math">{esc(e.get("title") or S.C("explanation.untitled"))}</span>, {esc(S.people(e["names"]))} '
                        f'<span class="fx-muted small">({esc(S.C("family.explain_status_" + ("ready" if e["status"] == "ready-for-review" else "draft")))})</span> '
                        f'<a class="ext small" href="{esc(S.REPO + "/blob/main/" + e["path"])}" rel="noopener">{esc(S.C("family.explain_draft_source"))}</a></li>' for e in drafts)
        parts.append(f'<h3 class="fx-h3">{esc(S.C("family.explain_progress_heading"))}</h3><p class="fx-intro">{esc(S.C("family.explain_progress_intro"))}</p><ul class="fx-plain">{items}</ul>')
    if not any(e["status"] == "reviewed" for e in ex):
        parts.insert(0, f'<p class="fam-invite">{esc(S.C("family.explain_none"))}</p>')
    return "".join(parts)


def check_buttons(c: Ctx) -> str:
    """A form to check each Lean statement, every one visible."""
    S = c.S
    sids = [s for s in c.f.get("statements") or [] if s in S.ST]
    if not sids:
        return ""
    if len(sids) == 1:
        return f'<a class="btn btn--ghost ext" href="{esc(S.check_url(sids[0]))}" rel="noopener">{esc(S.C("family.check_button"))}</a>'
    links = ", ".join(f'<a class="ext" href="{esc(S.check_url(s))}" rel="noopener"><code translate="no">{esc(s)}</code></a>' for s in sids)
    return f'<span class="fx-checks">{esc(W("left.check_each"))} {links}</span>'


def said_html(c: Ctx) -> str:
    S, f = c.S, c.f
    said = list(c.cfind.get("commentary") or [])
    items = [finds_list(c, [x]) for x in sorted(said, key=lambda x: x.get("date") or "", reverse=True)]
    ty, tier = S.sourced(f, "type"), S.sourced(f, "tier")
    if ty and tier and tier.get("value") is not None:
        tsrc = S.SOURCES.get(tier["source"]) or {}
        tname = (tsrc.get("tier_names") or {}).get(str(tier["value"]))
        what = S.C("sources.type_words").get(ty["value"], ty["value"])
        if tname:
            items.insert(0, f'<ul class="fx-finds"><li class="fx-find"><p class="fx-find__what">{esc(S.C("family.tier_said", name=S.curly(tsrc.get("name") or ""), type=what, tier=S.curly(tname)))}</p>'
                            f'<p class="fx-find__who">{esc(S.C("family.tier_credit"))}. <a class="ext" href="{esc(tsrc.get("url") or "")}" rel="noopener">{esc(S.C("community.source"))}</a></p></li></ul>')
    if not items:
        return ""
    return (f'<section class="fx-sec fx-sec--quiet" id="said" aria-labelledby="said-h"><span class="fx-alias" id="h-said"></span>'
            f'<h2 class="fx-h2" id="said-h">{esc(W("said.heading"))}</h2><p class="fx-intro">{esc(W("said.intro"))}</p>'
            + folded(items, 4, S.C("family.show_all", n=len(items))) + "</section>")


# ---- the page --------------------------------------------------------------------------------


def toc_html(c: Ctx, present: list) -> str:
    unresolved = not ((c.doc.get("claim") or {}).get("state") == "candidate" and (c.doc.get("claim") or {}).get("primary_candidate") in c.stmts)
    label = lambda k: W("toc.claim_unresolved") if (k == "claim" and unresolved) else W("toc." + k)
    items = "".join(f'<li><a href="#{k}">{esc(label(k))}</a></li>' for k in present)
    return f'<nav class="fx-toc" aria-labelledby="toc-h"><p class="fx-toc__h" id="toc-h">{esc(W("toc.label"))}</p><ol>{items}</ol></nav>'


def rail_html() -> str:
    return (f'<section class="ins-rail" data-ins-rail hidden data-ins-hint="{esc(W("inspect.hint"))}" data-ins-close="{esc(W("inspect.close"))}" '
            f'data-ins-pinned="{esc(W("inspect.pinned"))}"><div class="ins-rail__bar"><p class="ins-rail__h" id="ins-rail-h" tabindex="-1">{esc(W("inspect.pinned"))}</p>'
            f'<button class="ins-rail__close" type="button">{esc(W("inspect.close"))}</button></div><div class="ins-rail__body"></div></section>')


def build(S, f) -> None:
    """Write families/<id>.html."""
    c = Ctx(S, f)
    rel = f"families/{c.num}.html"
    head = head_html(c)
    sections = [("claim", theorem_html(c)), ("compare", comparison_html(c)), ("checks", checked_html(c)),
                ("left", left_html(c)), ("papers", papers_html(c)), ("cites", connections_html(c)),
                ("explain", explain_html(c)), ("said", said_html(c))]
    present = [k for k, h in sections if h]
    body = f"""<div class="frame page fx">
{head}
<div class="fx-body">
 <div class="fx-main">
{"".join(h for _, h in sections)}
 </div>
 <aside class="fx-aside" aria-label="{esc(W('toc.label'))}"><div class="fx-aside__in">{rail_html()}{toc_html(c, present)}</div></aside>
</div>
</div>
{c.templates()}
{S.macros_script(list(dict.fromkeys(c.macro_ids)))}"""
    lead, _ = S.head_lede(c.catalogue())
    desc = S.tex_plain(re.sub(r"\(\[Lean\]\([^)]*\)\)", "", lead)).strip()
    title = f"{S.tex_plain(f['title'])}, family {c.num}"
    S.write_page(rel, S.page(rel, title, desc, body, page_type="article", extra_head=head_assets(S, c.root)))


def head_assets(S, root: str) -> str:
    """The sheets and scripts a family page needs (and any page that uses the inspection
    pattern). KaTeX's two commonest fonts load early so the
    statements do not reflow when it first draws."""
    fonts = "".join(f'<link rel="preload" href="{root}{S.KATEX_DIR}/fonts/KaTeX_{name}.woff2" as="font" type="font/woff2" crossorigin>\n'
                    for name in ("Main-Regular", "Math-Italic"))
    return (f'{fonts}<link rel="stylesheet" href="{root}assets/inspect.css">\n'
            f'<link rel="stylesheet" href="{root}assets/family.css">\n'
            f'<script defer src="{root}assets/inspect.js"></script>\n<script defer src="{root}assets/family.js"></script>')
