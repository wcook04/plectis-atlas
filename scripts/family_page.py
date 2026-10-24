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


# A source location written into a reader's note ("01-introduction.tex:58-67",
# "Gap.lean:12"). The reader's record is linked beside the note, so the location is
# dropped from the prose rather than read out as words.
_FILE_REF = r"[\w./-]+\.(?:tex|lean|md|py|bib|txt|json|yaml):\d+(?:[-–]\d+)?"
_FILE_REFS = rf"{_FILE_REF}(?:\s*(?:,|;|and)\s*{_FILE_REF})*"


def drop_file_refs(s: str) -> str:
    """A recorded note without its file:line locations, its own words otherwise kept."""
    t = s or ""
    t = re.sub(rf"\s*\((?:see\s+|cf\.\s+)?{_FILE_REFS}\)", "", t)
    t = re.sub(rf"\s*,?\s+(?:at|in|see|from)\s+{_FILE_REFS}", "", t)
    t = re.sub(_FILE_REFS, "", t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+([,.;)])", r"\1", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


# House terms linked to their glossary entry at their first use on a page.
GLOSSARY_FIRST = (("comparator", r"\bComparator\b"), ("nanoda", r"\bnanoda\b"),
                  ("challenge", r"\bchallenge files?\b"), ("headline", r"\bheadline\b"))
_NO_TERM = {"a", "button", "code", "pre", "script", "style", "template", "blockquote", "title",
            "h1", "h2", "h3", "h4", "h5", "h6", "figcaption", "summary", "label", "dt", "th", "svg"}
_VOID = {"br", "img", "input", "meta", "link", "hr", "wbr", "source", "col", "area", "base", "embed", "track"}


def link_first_terms(html: str) -> str:
    """Link the first use of each house term in the page's own words to the glossary. Text
    inside links, controls, code, headings, quotations and recorded notes (md-math) is left
    alone, as is any term the page already links."""
    done = {tid for tid, _ in GLOSSARY_FIRST if f'data-term="{tid}"' in html}
    parts = re.split(r"(<[^>]+>)", html)
    stack: list = []
    for i, p in enumerate(parts):
        if p.startswith("<"):
            m = re.match(r"<\s*(/)?\s*([a-zA-Z][\w-]*)", p)
            if not m:
                continue
            tag = m.group(2).lower()
            if m.group(1):
                while stack:
                    if stack.pop()[0] == tag:
                        break
            elif tag not in _VOID and not p.endswith("/>"):
                cls = re.search(r'class="([^"]*)"', p)
                quiet = tag in _NO_TERM or bool(cls and re.search(r"\b(md-math|fx-rt__term|tex-auto)\b", cls.group(1)))
                stack.append((tag, quiet))
            continue
        if not p.strip() or any(q for _, q in stack):
            continue
        for tid, pat in GLOSSARY_FIRST:
            if tid in done:
                continue
            bits = re.split(r'(<a class="term".*?</a>)', p)
            for j in range(0, len(bits), 2):
                m = re.search(pat, bits[j])
                if m:
                    bits[j] = (bits[j][:m.start()] + f'<a class="term" href="__ROOT__glossary.html#{tid}" data-term="{tid}">{m.group(0)}</a>'
                               + bits[j][m.end():])
                    done.add(tid)
                    break
            p = "".join(bits)
        parts[i] = p
    return "".join(parts)


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
    """Each Lean statement's pairing, from build_site.lean_pairing (a citation or binding
    the backend records, else the atlas's reading of the Lean text, else the backend's
    catalogue-word candidate as a labelled fallback), with the words a candidate pair was
    found by: the Lean's own words first, then the paper title's, then the note's."""
    out = {}
    for l in doc.get("lean") or []:
        lid = l["id"]
        rec = dict(S.lean_pairing(doc, lid))
        rec["shared"] = []
        rec["shared_by"] = {}
        if rec.get("target"):
            rec["targets"] = list(rec.get("targets") or [rec["target"]])
            for tg in rec["targets"]:
                t = S.pairing_terms(rec, tg)
                rec["shared_by"][tg] = t["lean"] + t.get("title", []) + t["note"] + t["catalogue"]
            rec["shared"] = rec["shared_by"][rec["target"]]
        else:
            rec["state"] = "unavailable"
            rec["targets"] = []
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


@lru_cache(maxsize=1)
def reader_names() -> dict:
    """{credited name: the one name the page uses} for the outside readers credited as
    "person, project" ("Carlos Toledo, cert-machine" -> "cert-machine"); also keyed by the
    reader's source id, so a reader who has not read a family is still named."""
    out, by_source = {}, {}
    for ev in _evidence().values():
        for rd in ev.readers:
            if rd.name and rd.name != rd.source:
                by_source.setdefault(rd.source, rd.name)
            if ", " in (rd.name or ""):
                out[rd.name] = rd.name.split(", ", 1)[1]
    for src, name in by_source.items():
        out.setdefault(src, out.get(name, name))
    return out


@lru_cache(maxsize=1)
def reader_full_names() -> dict:
    """{reader source id: its credited name}, from every family that reader has read."""
    out = {}
    for ev in _evidence().values():
        for rd in ev.readers:
            if rd.name and rd.name != rd.source:
                out.setdefault(rd.source, rd.name)
    return out


def reader_credit(S, name: str) -> str:
    """The reader with its person credited, as prose says it once: "Carlos Toledo’s cert-machine"."""
    return S.prose_credit(name) if ", " in (name or "") else name


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
        # One name per outside reader: a reader credited as "person, project" is called by its
        # project ("cert-machine"); the person is credited once, where the readers are introduced.
        self.full_names = reader_names()

    def disp(self, name: str) -> str:
        """The one name the page uses for a credited source."""
        return self.full_names.get(name or "", name or "")

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

    def stmt_card(self, sid, *, aid: str, level: int = 3, state: str = "", note: str = "", big: bool = False, actions: str = "", flat: bool = False, foot: bool = True) -> str:
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
        return (f'<article class="fx-st{" fx-st--big" if big else ""}{" fx-st--flat" if flat else ""}" id="{esc(aid)}" data-macros="{esc(m["id"]) if m else ""}" aria-labelledby="{esc(aid)}-h" '
                f'data-paper="{esc(self.S.tex_plain(m["title"])) if m else ""}" data-date="{esc(pdate)}" '
                f'data-from="{esc(W("source.from"))}" data-open="{esc(W("source.open"))}" data-close="{esc(W("source.close"))}">'
                f'<header class="fx-st__hg{" fx-st__hg--state" if state else ""}">'
                + (f'<p class="fx-st__role">{esc(W("claim.role"))}</p>' if big else "") +
                f'<{h} class="fx-st__head" id="{esc(aid)}-h">' + (f'<a class="fx-st__kind" href="{esc(href)}">{esc(self.label(sid))}</a>' if href and not foot else f'<span class="fx-st__kind">{esc(self.label(sid))}</span>') + f'{self.stmt_title_html(sid)}</{h}>'
                f'<p class="fx-st__src">{self.stmt_where(sid)}</p>'
                + (f'<div class="fx-st__state">{state}</div>' if state else "") + '</header>'
                f'<div class="fx-st__body">{self.stmt_body(sid)}</div>{note}'
                + (f'<footer class="fx-st__foot"><p class="fx-st__acts">{"".join(go)}</p>{tex}</footer>' if foot else "") + '</article>')

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
                    return self.disp((ru.get("credit") or {}).get("name") or src)
        rd = self.readings.get(src)
        if rd:
            return self.disp((rd.get("credit") or {}).get("name") or src)
        return self.disp(src)

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


def find_card(c: Ctx, x, kind: str = "") -> str:
    """One credited community item as a card: who and when as its head, so the reader
    knows who is speaking, then what they say, with the link to where they said it."""
    who = c.effort_credit(x)
    when = c.S.date_words(x.get("date"))
    k = f'<p class="fx-c__kind">{esc(kind)}</p>' if kind else ""
    # The credit is the one link (to where they said it), the date quiet under it, so each
    # record is a title, a date and the atlas's summary, with no detached "Source" link.
    url = x.get("url") or ""
    name = (f'<a class="ext fx-find__name" href="{esc(url)}" rel="noopener">{esc(curly(who))}</a>' if url
            else f'<span class="fx-find__name">{esc(curly(who))}</span>')
    return (f'<li class="fx-c fx-find">{k}<p class="fx-find__who">{name}'
            + (f'<span class="fx-find__when">{esc(when)}</span>' if when else "") + '</p>'
            f'<p class="fx-find__what">{esc(curly(x.get("summary") or ""))}</p></li>')


def finds_list(c: Ctx, items, kind: str = "", unsigned: str = "") -> str:
    """Credited community items, newest first (an item with no named author last), so a
    long discussion uses the screen's width rather than one narrow list."""
    items = sorted(items, key=lambda x: x.get("date") or "", reverse=True)
    items.sort(key=lambda x: c.effort_credit(x) == W("said.no_author"))
    out = [find_card(c, x, kind) for x in items]
    return f'<ul class="fx-finds {flow_class(len(out) + bool(unsigned))}">' + "".join(out) + unsigned + "</ul>"


def flow_class(n: int, wide: bool = False) -> str:
    """A few cards stand in one row of equal width (a grid), so no column is left empty
    beside them; more flow in balanced columns, so no row leaves a hole beside a short card."""
    return ("fx-grid" + (" fx-grid--wide" if wide else "")) if n <= 3 else ("fx-flow" + (" fx-flow--wide" if wide else ""))


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
    # The site's one breadcrumb grammar: Map / subject / Family N: short title (build_site.trail).
    trail = S.trail(root, [(esc(disc), f"{root}index.html#o=d%3A{S.DISC_SLUG[di]}"),
                           (W("trail.family_titled", num=esc(c.num), title=trail_title(c)), None)])
    tools = (f'<p class="fx-tools"><a class="btn btn--small" href="{root}index.html#o=d%3A{S.DISC_SLUG[di]}">{esc(W("actions.plate"))}</a>'
             f'<button class="btn btn--small" type="button" data-copy-text="{esc(c.page_url)}" data-copied="{esc(W("actions.copied"))}">{esc(W("actions.copy"))}</button></p>')
    title_plain = S.tex_plain(f["title"])
    # The catalogue's bare "(Lean)" link says where it goes.
    cat = re.sub(r"\(\[Lean\]\(([^)]*)\)\)", lambda m: f"([{W('head.lean_note')}]({m.group(1)}))", c.catalogue())
    lead = cat
    # The verdict is said once, as the lead of the glance beside this column.
    extra = [papers_line(c)]
    erd = S.sourced(f, "erdos_problems")
    if erd and erd.get("value"):
        probs_ = [f'<a class="ext" href="{esc(p["url"])}" rel="noopener">{esc(W("head.erdos_number", n=p["number"]))}</a>' for p in erd["value"]]
        joined = probs_[0] if len(probs_) == 1 else ", ".join(probs_[:-1]) + " " + S.C("family.and") + " " + probs_[-1]
        extra.append(W("head.erdos", problems=joined, source=S.credit_link(erd["source"], root)))
    probs = c.problems()
    if probs:
        p = W("head.problems_one") if len(probs) == 1 else W("head.problems_many", n=cap(S.say(len(probs))))
        extra.append(f'<a href="#problems">{esc(p)}</a>')
    facts = "".join(f'<p class="fx-fact{" fx-fact--lede" if i < 2 else ""}">{x}</p>' for i, x in enumerate(extra) if x)
    # The first screen is the evidence itself (Klara Kaleb's reading, 23 October 2026): the
    # paper's exact statement beside the Lean OpenAI wrote, then what each outside group
    # says, in its own words. OpenAI's description stands where the groups judge it (it is
    # what they compared the Lean with); the papers follow as background.
    pair, shown = board_pair(c)
    quote = (f'<figure class="fx-quote" id="h-desc"><figcaption class="fx-quote__src">{W("board.desc_credit", link=catalogue_link(c))}</figcaption>'
             f'<blockquote class="fx-quote__q"><p class="tex-auto">{S.glue(S.rich(curly_tex(lead), "", root, link_results=True))}</p></blockquote></figure>')
    bq = f'<h2 class="fx-q" id="claimed-h">{esc(W("board.desc_h"))}</h2>{quote}'
    papers = brief_html(c, lean=False)
    groups_desc = ""
    if not shown:
        # No paper statement is identified: OpenAI's description is the claim, in the paper's
        # place, under the side's own heading.
        pair = pair.replace("\x02", quote)
        bq = ""
    elif c.readings:
        groups_desc, bq = quote, ""
    if not c.leans:
        # No Lean: the description, papers and facts fill the sheet's second column.
        pair = pair.replace("\x03", (f'<div class="fx-bd__sidedesc">{quote}</div>' if bq else "") + papers + facts)
        bq = papers = facts = ""
    groups = groups_board(c, desc=groups_desc) if (c.leans or c.readings) else ""
    back = (f'<div class="fx-bd__back"><div class="fx-bd__desc">{bq}{facts}</div>'
            + (f'<div class="fx-bd__papers">{papers}</div>' if papers else "") + '</div>') if (bq or facts or papers) else ""
    overview = f'<div class="fx-bd">{pair}{groups}{back}</div>'
    header = f"""<header class="fx-head">
 <div class="fx-bar">{trail}{tools}</div>
 {S.sibling_nav("family", S.family_siblings(c.num, root), discipline=disc)}
 <h1 class="fx-title{' fx-title--long' if len(title_plain) > 64 else ''}"><span class="tex-auto">{S.rich(curly_tex(f["title"]))}</span></h1>
</header>"""
    # The overview is the first tab, so every other tab opens straight into its own task.
    return header, f'<section class="fx-sec fx-sec--overview" id="overview" aria-label="{esc(W("tabs.overview"))}"><span class="fx-alias" id="left"></span><span class="fx-alias" id="explain"></span>{"".join(f'<span class="fx-alias" id="{a}"></span>' for a in ("h-left", "h-explain", "h-contrib"))}{overview}</section>'


TRAIL_TITLE_MAX = 48


def trail_title(c: Ctx) -> str:
    """The family's title as the breadcrumb's last step, short enough for one line: whole
    when it fits, else the part before a colon when that names it, else cut at a word. A
    title with mathematics is never cut inside a formula: it is shown whole."""
    S, t = c.S, c.f["title"]
    plain = S.tex_plain(t)
    if len(plain) <= TRAIL_TITLE_MAX:
        return f'<span class="tex-auto">{S.rich(curly_tex(t))}</span>'
    head = t.split(": ", 1)[0]
    if head != t and head.count("\\(") == head.count("\\)") and "$" not in head and 12 <= len(S.tex_plain(head)) <= TRAIL_TITLE_MAX:
        return f'<span class="tex-auto">{S.rich(curly_tex(head))}</span>'
    if "$" in t or "\\(" in t:
        return f'<span class="tex-auto">{S.rich(curly_tex(t))}</span>'
    return esc(curly(clip(plain, TRAIL_TITLE_MAX)))


BRIEF_KEEP = 5


def brief_html(c: Ctx, lean: bool = True) -> str:
    """Under the claim, what the family holds, each a direct link: its current papers
    (reading page and date) and, unless the evidence board already shows them (lean=False),
    the Lean statements selected for checking."""
    S, root = c.S, c.root
    cur = [S.MS[h["id"][2:]] for h in c.doc.get("paper_history") or [] if h.get("status") == "current" and h["id"][2:] in S.MS]

    def more(n, href):
        return f'<li class="fx-brief__more"><a href="{href}" data-fx-go>{esc(W("brief.more", n=S.say(n)))}</a></li>' if n > 0 else ""
    papers = "".join(f'<li><a href="{root}papers/{esc(m["id"])}.html"><span class="tex-auto">{S.rich(curly_tex(m["title"]))}</span></a>'
                     f' <span class="fx-brief__m">{esc(S.date_words(m.get("date")) or "")}</span></li>' for m in cur[:BRIEF_KEEP])
    papers += more(len(cur) - BRIEF_KEEP, "#papers")
    leans = "".join(f'<li><a href="{root}statements/{esc(l["id"][2:])}.html"><code translate="no">{esc(l["id"][2:])}</code></a>'
                    + (f' <span class="fx-brief__m md-math">{esc(curly_tex(l["name"]))}</span>' if l.get("name") and l["name"] != l["id"][2:] else "")
                    + "</li>" for l in c.leans[:BRIEF_KEEP])
    leans += more(len(c.leans) - BRIEF_KEEP, "#compare")
    parts = []
    if papers:
        parts.append(f'<h2 class="fx-q">{esc(W("brief.papers_one") if len(cur) == 1 else W("brief.papers_many", n=S.say(len(cur))))}</h2><ul class="fx-brief__l">{papers}</ul>')
    if leans and lean:
        # The answer first, then Lean and a Lean statement defined where they are first needed.
        names = [f'<code translate="no">{esc(l["id"][2:])}</code>' for l in c.leans]
        ans = (W("brief.lean_ans_one", name="\x00") if len(c.leans) == 1 else W("brief.lean_ans_many", n=S.say(len(c.leans))))
        ans = esc(ans).replace("\x00", names[0])
        parts.append(f'<h2 class="fx-q">{esc(W("first.lean"))}</h2>'
                     f'<p class="fx-qa">{ans} {S.ctext(W("brief.lean_def"))}</p><ul class="fx-brief__l">{leans}</ul>')
    return f'<div class="fx-brief">{"".join(parts)}</div>' if parts else ""


def glance_runs(c: Ctx) -> tuple:
    """Every group's Comparator runs, {source: [(Lean name, run)]}, and the groups in the
    page's order (the scope readers first, then any group that only reports runs)."""
    order = [rd.source for rd in c.ev.readers]
    names = {rd.source: c.disp(rd.name) for rd in c.ev.readers}
    runs: dict = {}
    for l in c.leans:
        by_id = {ru["id"]: ru for ru in l.get("runs") or []}
        for g in l.get("run_groups") or []:
            for rid in g.get("run_ids") or []:
                ru = by_id.get(rid)
                if not ru:
                    continue
                src = ru.get("source") or g.get("source")
                runs.setdefault(src, []).append((l["id"][2:], ru))
                names.setdefault(src, c.disp((ru.get("credit") or {}).get("name") or src))
                if src not in order:
                    order.append(src)
    return runs, order, names


def reason_text(S, note: str, limit: int = 300) -> str:
    """A group's reason for its label, in its own words without file locations: whole when
    it is short (a note's second clause is often the reason, as MathVet's on 017 is), else
    cut at a word with the full note one link away."""
    t = re.sub(r"^\s*None\s*[;.:]\s*", "", drop_file_refs(note or ""))
    return S.short(cap(t), limit) if t else ""


def proof_answer(c: Ctx, runs: dict, names: dict, order: list) -> str:
    """The Comparator question's answer in one sentence, naming who reports what of which
    Lean statement, from each statement's accepted_current_sources (the backend's record)."""
    S = c.S
    n = len(c.leans)
    rank = {s: i for i, s in enumerate(order)}
    acc = {l["id"][2:]: [names.get(s, c.source_name(s)) for s in sorted(l.get("accepted_current_sources") or [], key=lambda s: rank.get(s, 99))]
           for l in c.leans}
    if n == 1:
        name, who = next(iter(acc.items()))
        lean = f'<code translate="no">{esc(name)}</code>'
        others = [names.get(src, src) for src, xs in runs.items() if all(ru.get("state") != "reported-accepted" for _, ru in xs)]
        if not who:
            out = esc(W("first.proof_none_one", lean="\x00")).replace("\x00", lean)
        else:
            key = "first.proof_one_by_one" if len(who) == 1 else "first.proof_one_by_many"
            out = esc(W(key, names=join_and(S, who), lean="\x00")).replace("\x00", lean)
        if others:
            out += " " + esc(W("first.proof_other_one" if len(others) == 1 else "first.proof_other_many", names=join_and(S, others)))
        return out
    done = [k for k, v in acc.items() if v]
    if not done:
        return esc(W("first.proof_none_many", n=S.say(n)))
    if len(done) == n:
        least = min(len(v) for v in acc.values())
        return esc(W("first.proof_all_least_one" if least == 1 else "first.proof_all_least_many", n=S.say(n), k=S.say(least)))
    which = join_and(S, [f'<code translate="no">{esc(k)}</code>' for k in done])
    return esc(W("first.proof_some", k=S.say(len(done)), n=S.say(n), which="\x00")).replace("\x00", which)


# Words in the groups' quoted notes that a newcomer may not know, linked once each to the
# glossary's short definition (the quotation's words are unchanged).
NOTE_TERMS = (("mathlib", r"\bMathlib\b"), ("headline", r"\b[Hh]eadline\b"), ("nanoda", r"\bnanoda\b"))


def gloss_terms(S, html: str, terms=NOTE_TERMS) -> str:
    """Link the first use of each term in html's text (outside tags and links) to the glossary."""
    parts = re.split(r"(<[^>]+>)", html)
    depth, done = 0, set()
    for i, part in enumerate(parts):
        if part.startswith("<"):
            if re.match(r"<a[\s>]", part):
                depth += 1
            elif part.startswith("</a"):
                depth = max(0, depth - 1)
            continue
        if depth:
            continue
        for tid, pat in terms:
            if tid in done or tid not in S.GLOSSARY:
                continue
            m = re.search(pat, part)
            if m:
                part = part[:m.start()] + S.term_link(tid, m.group(0)) + part[m.end():]
                done.add(tid)
        parts[i] = part
    return "".join(parts)


def group_name_html(S, src: str, name: str) -> str:
    """A group's name, defined at first use by its glossary entry where the glossary has one."""
    return S.term_link(src, esc(name)) if src in S.GLOSSARY else esc(name)


def run_tone(ru) -> str:
    """A run's outcome class from its recorded state: accepted, ended without a verdict,
    built without Comparator, or any other state reported."""
    return {"reported-accepted": "yes", "reported-undecided": "undecided", "reported-built": "built"}.get(ru.get("state") or "", "other")


def run_word(ru, ok: bool) -> str:
    """The plain outcome a reader sees before the group's own label (cert-machine's
    "REFUSED" on 005 is a run that ended without a verdict, not a proof found invalid)."""
    return W("glance.run.accepted") if ok else W("glance.run." + run_tone(ru))


def proof_cell(c: Ctx, src: str, mine: list) -> str:
    """One group's answer to "did OpenAI's proof pass Comparator?": a plain word first, from
    the backend's accepted_current_sources, then the group's own word, the date and its own
    account; with several Lean statements, which ones it ran and which it did not."""
    S = c.S
    if not mine:
        return f'<p class="fx-ev__none">{esc(W("glance.runs_none"))}</p>'
    acc = {l["id"][2:]: set(l.get("accepted_current_sources") or []) for l in c.leans}
    link = lambda t: f'<a class="fx-vt" href="#{group_id(src)}">“{esc(t)}”</a>' if t else ""
    if len(c.leans) == 1:
        name, ru = mine[0]
        ok = src in acc.get(name, set())
        when = S.date_words(ru.get("date"))
        acct = curly((ru.get("source_value") or {}).get("text") or "")
        word = esc(run_word(ru, ok))
        inner = esc(W("glance.their_label")) + " " + link(ru.get("source_term") or "") + (f', <span class="fx-ev__date">{esc(when)}</span>' if when else "")
        return (f'<p class="fx-ev__out fx-ev__out--{"yes" if ok else run_tone(ru)}">{word}</p><p class="fx-ev__term">{inner}</p>'
                + (f'<p class="fx-ev__acct">{esc(acct)}</p>' if acct else ""))
    ran = {k: ru for k, ru in mine}
    yes = [k for k in ran if src in acc.get(k, set())]
    no = [k for k in ran if k not in yes]
    unrun = [l["id"][2:] for l in c.leans if l["id"][2:] not in ran]
    code = lambda ks: join_and(S, [f'<code translate="no">{esc(k)}</code>' for k in ks])
    # Each group's label stands beside the statements it was given for, never pooled.
    terms_of = lambda ks: ", ".join(link(t) for t in dict.fromkeys(ran[k].get("source_term") or "" for k in ks) if t)
    terms = terms_of(yes)
    forx = lambda ks: esc(W("glance.for", which="\x00")).replace("\x00", code(ks))
    bits = []
    if yes:
        which = esc(W("glance.for_all", n=S.say(len(c.leans)))) if len(yes) == len(c.leans) else forx(yes)
        bits.append(f'<span class="fx-ev__w fx-ev__w--yes">{esc(W("glance.run.accepted"))}</span> ({terms}) {which}')
    for state in dict.fromkeys(run_tone(ran[k]) for k in no):
        ks = [k for k in no if run_tone(ran[k]) == state]
        own = terms_of(ks)
        bits.append(f'<span class="fx-ev__w">{esc(run_word(ran[ks[0]], False))}</span>' + (f' ({own})' if own else "") + f' {forx(ks)}')
    if unrun:
        bits.append(esc(W("glance.not_run", which="\x00")).replace("\x00", code(unrun)))
    return f'<p class="fx-ev__multi">{"; ".join(bits)}.</p>'


def group_assessments(c: Ctx) -> list:
    """Each outside group's answer, in the page's order, as (source, name html, tone, their
    term html, the plain gloss, their reason html, their Comparator run html). A group that
    only reports runs has no term or reason. Atlas adds no synthesis of its own."""
    S, ev = c.S, c.ev
    runs, order, names = glance_runs(c)
    out = []
    for src in order:
        rd = next((x for x in ev.readers if x.source == src), None)
        rec = c.readings.get(src) if rd else None
        who = group_name_html(S, src, names.get(src, src))
        tone, term, gloss, why = "none", "", "", ""
        if rec:
            sv = rec.get("source_value") or {}
            # A group's note is quoted whole: a cut once hid MathVet's Flint–Hills clause.
            reason = reason_text(S, sv.get("gap") or sv.get("note") or "", limit=4000)
            tone = {"full": "all", "part": "part", "other": "other"}.get(rd.tone, "none")
            defn = curly(drop_file_refs(sv.get("text") or ""))
            tip = W("glance.term_tip", term=rd.term or "", who=names[src], text=defn) if defn else ""
            term = (f'<a class="fx-vt" href="#{group_def_id(src)}" title="{esc(tip)}">“{esc(rd.term or "")}”</a>'
                    if defn else f'<span class="fx-vt">“{esc(rd.term or "")}”</span>')
            gloss = cap(W("readings.state").get(rd.state or "", sayc("tone." + rd.tone))) + "."
            link = (f' <a class="ext fx-ev__go" href="{esc(sv["url"])}" rel="noopener" aria-label="{esc(W("glance.record_label", who=names[src]))}">{esc(W("glance.record"))}</a>'
                    if sv.get("url") else "")
            why = (f'<blockquote class="fx-vd__why md-math"><p>“{code_spans(reason)}”{link}</p></blockquote>' if reason
                   else f'<p class="fx-vd__why fx-vd__why--none">{esc(W("glance.no_reason"))}{link}</p>')
            why = gloss_terms(S, why)
        run = proof_cell(c, src, runs.get(src) or []) if c.leans else ""
        run = gloss_terms(S, run, (("nanoda", NOTE_TERMS[2][1]),))
        out.append((src, who, tone, term, gloss, why, run))
    return out


def board_verdicts(c: Ctx) -> str:
    """One line in the sheet's foot naming what each group finds, each name a link to its
    card below, so the assessments reach the first screen without repeating the cards."""
    bits = []
    for rd in c.ev.readers:
        if rd.source not in c.readings:
            continue
        short = W("board.short").get(rd.state or "", "")
        if short:
            bits.append(W("board.finds", who=f'<a href="#vd-{slug_id(rd.source)}">{esc(c.disp(rd.name))}</a>', what=esc(short)))
    return f'<p class="fx-bd__verdicts">{esc(W("board.verdicts_h"))} {"; ".join(bits)}.</p>' if bits else ""


def board_pair(c: Ctx) -> tuple:
    """The board's first row: what the paper states beside what OpenAI's Lean states, joined
    by the pairing's words. The paper side shows the statement the selected Lean statement is
    paired with, else the opening theorem the backend names. The paper's other statements that
    match OpenAI's description but no Lean statement is paired with follow (after the Lean on
    a phone), with OpenAI's own sentence on what its Lean leaves out, so an omission is on the
    page rather than described. The foot says how the two were paired and what each group
    finds. With no Lean the paper takes the sheet's whole width. Returns (html, statement ids
    shown); with no statement to show, \\x02 marks where OpenAI's description stands in."""
    S = c.S
    l = c.leans[0] if c.leans else None
    rec = c.pairs[l["id"]] if l else {}
    shown = [t for t in rec.get("targets") or [] if t in c.stmts][:2]
    full, _ = opening_statements(c)
    if not shown and full:
        shown = full[:1]
    extra = [s for s in full if s not in shown and (not c.leans or not paired_lean(c, s))][:2]
    if shown:
        paper = "".join(c.stmt_card(t, aid="ov-theorem" if k == 0 else f"ov-theorem-{k + 1}", level=3, flat=True)
                        for k, t in enumerate(shown))
    else:
        paper = "\x02"
    extra_html = ""
    if extra:
        note = W("board.extra_nolean") if c.leans else W("board.extra")
        extra_html = (f'<p class="fx-bd__xh">{esc(note)}</p>'
                      + "".join(c.stmt_card(t, aid=f"ov-extra-{k + 1}", level=4, flat=True, foot=False) for k, t in enumerate(extra)))
        out_ = producer_left_out(c)
        if out_ and c.leans:
            pv = (c.doc.get("producer_scope") or {}).get("value") or {}
            src_ = (f'<a class="ext" href="{esc(pv.get("url") or "")}" rel="noopener">{esc(W("glance.left_openai"))}</a>'
                    if pv.get("url") else esc(W("glance.left_openai")))
            extra_html += f'<p class="fx-bd__said">{src_} “<span class="tex-auto">{S.rich(curly_tex(" ".join(out_)))}</span>”</p>'
            c.board_said = True
        extra_html = f'<div class="fx-bd__extra">{extra_html}</div>'
    paper_h = f'<h2 class="fx-bd__side fx-bd__side--paper" id="ov-paper-h">{esc(W("board.paper_h") if shown else W("board.paper_h_desc"))}</h2>'
    if not l:
        # No Lean: the sheet's second column says so and holds the papers and facts (\x03),
        # travelling beside a long theorem so no part of the sheet stands empty.
        side = (f'<div class="fx-bd__lean fx-bd__lean--none"><div class="fx-bd__in">'
                f'<h2 class="fx-bd__side fx-bd__side--lean">{S.ctext(W("board.lean_none_h"))}</h2>'
                f'<p class="fx-bd__none">{S.ctext(W("board.nolean"))}</p>\x03</div></div>')
        return (f'<section class="fx-bd__pair fx-bd__pair--nolean" aria-labelledby="ov-paper-h">'
                f'<div class="fx-bd__paper"><div class="fx-bd__in">{paper_h}{paper}</div></div>{side}{extra_html}</section>'), shown
    name = l["id"][2:]
    s = S.ST.get(name)
    code = ""
    if s:
        names = s["comparator"]["theorem_names"] or s["theorems"][:1]
        first = dict(s, comparator=dict(s["comparator"], theorem_names=names[:1]))
        code = f'<pre class="lean lean--snippet fx-bd__code"><code>{S.lean_breaks(S.lean_snippet_html(first, max_lines=14))}</code></pre>'
        if names and "sorry" in s["lean"]:
            code += f'<p class="fx-bd__sorry">{W("board.sorry")}</p>'
    title = l.get("name") or ""
    t_html = f'<span class="md-math">{esc(curly_tex(title))}</span>' if title and title != name else ""
    others = ""
    if len(c.leans) > 1:
        links = join_and(S, [f'<a href="#lean-{esc(x["id"][2:])}"><code translate="no">{S.lean_breaks(">" + esc(x["id"][2:]))[1:]}</code></a>' for x in c.leans[1:6]])
        n_more = len(c.leans) - 1
        others = (f'<p class="fx-bd__more">' + esc(W("board.more_one" if n_more == 1 else "board.more_many", n=S.say(n_more), which="\x00")).replace("\x00", links)
                  + (f' {esc(W("brief.more", n=S.say(n_more - 5)))}' if n_more > 5 else "") + '</p>')
    lean = (f'<div class="fx-bd__lean"><div class="fx-bd__in"><h2 class="fx-bd__side fx-bd__side--lean">{S.ctext(W("board.lean_h"))}</h2>'
            f'<h3 class="fx-bd__lname"><a href="{c.root}statements/{esc(name)}.html">{t_html or f"<code translate=\"no\">{esc(name)}</code>"}</a></h3>'
            + (f'<p class="fx-bd__lid"><code translate="no">{S.lean_breaks(">" + esc(name))[1:]}</code></p>' if t_html else "")
            + f'{code}<p class="fx-bd__go"><a href="{c.root}statements/{esc(name)}.html">{esc(W("compare.lean_open"))}</a>'
            f' <a href="#lean-{esc(name)}">{esc(W("board.compare_tab"))}</a></p>{others}</div></div>')
    state = rec["state"] if rec.get("target") else "unavailable"
    why = ""
    if rec.get("target") and state == "candidate-pairing" and rec.get("shared"):
        why = " " + why_button(c, rec["target"], rec["shared"], primary=False, lean=name)
    join = f'<p class="fx-bd__join fx-bd__join--{esc(state)}">{esc(W("board.join." + state))}{why}</p>'
    foot = f'<div class="fx-bd__foot2">{join}{board_verdicts(c)}</div>'
    return (f'<section class="fx-bd__pair fx-bd__pair--{esc(state)}" aria-labelledby="ov-paper-h">'
            f'<div class="fx-bd__paper"><div class="fx-bd__in">{paper_h}{paper}</div></div>{lean}{extra_html}{foot}</section>'), shown


def groups_board(c: Ctx, desc: str = "") -> str:
    """The board's second row: what the groups compared (OpenAI's description, quoted here
    when the sheet shows a theorem, since that is what they judged), whether they agree, then
    one card per outside group, side by side: its finding in plain words, its own term as a
    small tag, its reason quoted whole, and its Comparator run. The route to the groups'
    full reasons closes the row."""
    S, ev = c.S, c.ev
    cards = []
    for src, who, tone, term, gloss, why, run in group_assessments(c):
        head = f'<header class="fx-vd__hd"><h3 class="fx-vd__who">{who}</h3>{f"<p class=\"fx-vd__term\">{term}</p>" if term else ""}</header>'
        body = (f'<p class="fx-vd__out"><span class="u-dot u-dot--{tone}" title="{esc(W("glance.dot"))}" aria-hidden="true"></span>{esc(gloss)}</p>{why}'
                if gloss else f'<p class="fx-ev__none">{esc(W("glance.not_read"))}</p>')
        run_h = f'<div class="fx-vd__run"><p class="fx-vd__rk">{S.ctext(W("board.run_k"))}</p>{run}</div>' if run else ""
        cards.append(f'<article class="fx-vd fx-vd--{tone}" id="vd-{slug_id(src)}">{head}{body}{run_h}</article>')
    k = len(c.readings)
    lead = f'<p class="fx-bd__lead">{esc(W("board.compared_here" if desc else "board.compared_above"))}</p>' if k else ""
    agree = f'<p class="fx-bd__agree">{esc(ev.agreement_sentence())}</p>' if k else ""
    head = f'<h2 class="fx-bd__h" id="glance-h">{esc(W("board.groups_h"))}</h2>{lead}{agree}'
    if desc and k:
        # The section's words beside the description they refer to, so neither runs the
        # full width with an empty half.
        head = f'<div class="fx-bd__ghead"><div class="fx-bd__gtext">{head}</div><div class="fx-bd__gdesc">{desc}</div></div>'
    return (f'<section class="fx-glance fx-bd__groups" aria-labelledby="glance-h">{head}'
            f'<div class="fx-vds">{"".join(cards)}</div>{glance_left(c, board=True)}</section>')


def help_q(step: str, label: str) -> str:
    """The site guide's "?" opener (atlas.js), at the guide's step for this control."""
    return f'<button type="button" class="help-q" data-help="{esc(step)}" aria-label="{esc(label)}">?</button>'


# OpenAI's own note says what its Lean leaves out in sentences like these; the glance
# quotes them, exactly, as what is left outside the checked statement.
_LEFT_OUT = re.compile(r"\b(?:outside (?:this|the) (?:selected )?statement|outside the formali[sz]ation|not included|are excluded|is excluded|not formali[sz]ed|not stated)\b", re.I)


def producer_left_out(c: Ctx) -> list:
    """The sentences of OpenAI's note on its Lean that say what the Lean leaves out, verbatim."""
    pv = (c.doc.get("producer_scope") or {}).get("value") or {}
    text = " ".join((pv.get("scope") or "").split())
    sents = re.split(r"(?<=[.])\s+(?=[A-Z])", text)
    return [s for s in sents if _LEFT_OUT.search(s)][:2]


def glance_left(c: Ctx, board: bool = False) -> str:
    """The glance's end: what nobody has checked yet (the review no one has recorded, named
    by its Lean statement where there is one, and OpenAI's own sentence on what its Lean
    leaves out, quoted exactly), then the route to each group's full report. It states what
    is unreviewed as evidence; it does not ask the reader to do the review."""
    S = c.S
    items = c.doc.get("remaining_checks") or []
    bits = []
    pairing = any(x.get("kind") == "pairing-review" for x in items)
    # On the evidence board the join under a paired Lean statement already says no review is recorded.
    said_at_join = board
    if pairing and not said_at_join:
        if len(c.leans) == 1:
            bits.append(esc(W("glance.left_pairing_one", lean="\x00")).replace("\x00", f'<code translate="no">{esc(c.leans[0]["id"][2:])}</code>'))
        else:
            bits.append(esc(W("glance.left_pairing")))
    # The board quotes OpenAI's sentence beside the statement it leaves out; it is not said twice.
    out_ = [] if getattr(c, "board_said", False) else producer_left_out(c)
    pv = (c.doc.get("producer_scope") or {}).get("value") or {}
    if out_:
        src_ = (f'<a class="ext" href="{esc(pv.get("url") or "")}" rel="noopener">{esc(W("glance.left_openai"))}</a>'
                if pv.get("url") else esc(W("glance.left_openai")))
        bits.append(f'{src_} “<span class="tex-auto">{S.rich(curly_tex(" ".join(out_)))}</span>”')
    btns = [f'<a class="btn btn--small fx-go" href="#readings" data-fx-go>{esc(W("glance.more"))}</a>']
    lt = (f'<div class="fx-glance__lt"><h2 class="fx-q" id="left-q">{esc(W("first.left_pairing" if pairing and not said_at_join else "first.left"))}</h2>'
          f'<p class="fx-qa">{" ".join(bits)}</p></div>') if bits else ""
    if board:
        # The board ends on Comparator's limit and the route to the groups' full reasons, in one row.
        foot = f'<p class="fx-bd__foot">{esc(W("glance.left_atlas"))}</p>' if c.leans else ""
        return f'<div class="fx-glance__left fx-bd__end">{lt}<div class="fx-bd__endrow">{foot}<p class="fx-glance__go">{"".join(btns)}</p></div></div>'
    return f'<div class="fx-glance__left">{lt}<p class="fx-glance__go">{"".join(btns)}</p></div>'


def tone_class(c: Ctx) -> str:
    """The one meaning the family's colour carries on the map: what the outside readers find
    the release's Lean states for the headline (the map's own rule, build_universe.tone_class,
    read from the same backend records)."""
    ev = c.ev
    if not ev.has_lean:
        return "none"
    if ev.agreement == "disagree":
        return "split"
    tones = [t for t in ev.tones if t != "none"]
    if not tones:
        return "unread"
    if all(t == "full" for t in tones):
        return "all"
    return "part" if "part" in tones else "other"


def verdict_line(c: Ctx) -> str:
    """Under the title: the outside readers' verdict in words, the meaning the map's colour
    carries, linked to their readings."""
    tone = tone_class(c)
    if tone in ("all", "part", "other"):
        read = [rd for rd in c.ev.readers if rd.tone != "none"]
        line = W(f"head.verdict.{tone}_both") if len(read) > 1 else W(f"head.verdict.{tone}_one", name=c.disp(read[0].name))
    else:
        line = W("head.verdict." + tone)
    link = f' <a href="#readings">{esc(W("head.verdict.link"))}</a>' if tone != "none" else ""
    return f'<span class="fx-verdict">{esc(line)}</span>{link}'


def _date_key(d: str):
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, fmt)
        except (TypeError, ValueError):
            pass
    return datetime.max


def papers_line(c: Ctx) -> str:
    """Under the title: how many papers are current, and how many were withdrawn or replaced
    by a later edition, from the family's paper history."""
    S = c.S
    hist = c.doc.get("paper_history") or []
    cur = sum(1 for h in hist if h.get("status") == "current")
    wd = [h["id"][2:] for h in hist if h.get("status") == "withdrawn"]
    ed = sum(1 for h in hist if h.get("status") == "previous-edition")
    current = W("head.papers_line.current_one") if cur == 1 else W("head.papers_line.current_many", n=cap(S.say(cur)))
    rest = []
    if wd:
        days = sorted({(S.MS.get(s) or {}).get("withdrawn_on") for s in wd if (S.MS.get(s) or {}).get("withdrawn_on")},
                      key=_date_key)
        words = [S.date_words(d) for d in days if S.date_words(d)]
        if words:
            dates = join_and(S, words)
            rest.append(W("head.papers_line.withdrawn_one", dates=dates) if len(wd) == 1 else W("head.papers_line.withdrawn_many", n=S.say(len(wd)), dates=dates))
        else:
            rest.append(W("head.papers_line.withdrawn_undated_one") if len(wd) == 1 else W("head.papers_line.withdrawn_undated_many", n=S.say(len(wd))))
    if ed:
        rest.append(W("head.papers_line.editions_one") if ed == 1 else W("head.papers_line.editions_many", n=S.say(ed)))
    if not rest:
        return ""
    text = W("head.papers_line.joined", current=current, rest=join_and(S, rest))
    return f'<a href="#papers">{esc(text)}</a>'


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
            f'<div class="fx-c fx-status__row"><dt class="fx-c__h">{esc(W("status.formal"))}</dt><dd>{formal}</dd></div>'
            f'<div class="fx-c fx-status__row"><dt class="fx-c__h">{esc(W("status.readable"))}</dt><dd>{readable}</dd></div></dl>')


# ---- the theorem -------------------------------------------------------------------


def why_button(c: Ctx, sid: str, terms, *, primary: bool, lean: str | None = None, label_key: str = "why.button") -> str:
    """The quiet route to how a passage was found: the exact shared words and the
    backend's reason, in the rail. The state itself stays visible on the card."""
    claim = c.doc.get("claim") or {}
    tid = "ins-why-" + slug_id(sid[2:]) + (f"-{slug_id(lean)}" if lean else "")
    # Two papers can each have a Theorem 1.1: the record's head names the paper and date.
    sub = esc(W("why.from", where=c.where_plain(sid)))
    if lean and tid not in c.tpls:
        # With no shared words the method row alone says how it was chosen.
        rows = [(W("why.method"), esc(W("why.method_lean", name=lean)))]
        rows += [(W("why.words"), esc(", ".join(terms)))] if terms else []
        rows += [(W("why.review"), esc(W("why.review_lean")))]
        c.tpls[tid] = record(W("why.kind"), esc(c.label(sid)) + c.stmt_title_html(sid), rows, [], sub=sub)
    if tid not in c.tpls:
        rows = [(W("why.method"), esc(W("why.method_text")))]
        rows += [(W("why.words"), esc(", ".join(terms)))] if terms else []
        rows += [(W("why.review"), esc(W("why.review_text")))]
        if claim.get("reason"):
            rows.append((W("why.reason"), esc(claim["reason"])))
        c.tpls[tid] = record(W("why.kind"), esc(c.label(sid)) + c.stmt_title_html(sid), rows, [], sub=sub)
    return ins_button(tid, esc(W(label_key)), "fx-why",
                      name=W("why.button_label_lean" if lean else "why.button_label", button=W(label_key),
                             label=c.label_plain(sid), where=c.where_plain(sid), lean=lean or ""))


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

    full, rest = opening_statements(c)
    if claim.get("state") == "candidate" and len(full) > 1:
        # Two candidates disagree, or there are only two: both are shown whole, the paper's
        # main theorem before a corollary or lemma that shares more of the description's words.
        parts.append(f'<h2 class="fx-h2 fx-h2--theorem" id="claim-h">{esc(claim_heading(c))}</h2>')
        for i, sid in enumerate(full):
            main = is_main(c.stmts[sid])
            words = W("claim.state_primary" if (sid == cand and main) else "claim.state_words" if sid == cand
                      else "claim.state_main" if main else "claim.state_alt")
            terms = next((a.get("matched_terms") for a in alts if a.get("statement_id") == sid), None) or []
            st_html = f'<p class="fx-st__qual">{esc(words)} {why_button(c, sid, terms, primary=(sid == cand))}</p>'
            parts.append(c.stmt_card(sid, aid="claim-theorem" if i == 0 else f"claim-alt-{i}", level=3,
                                     state=st_html, note=unpaired(sid), actions=compare_action(c, sid)))
        main_first = is_main(c.stmts[full[0]]) and not is_main(c.stmts[full[1]])
        parts.append(f'<p class="fx-cand fx-cand--note">{esc(W("claim.two_note" if main_first else "claim.two_note_same"))}</p>')
        if rest:
            parts.append(f'<div class="fx-others" id="claim-more"><h3 class="fx-h3">{esc(more_label(c, len(rest)))}</h3>{alt_list(c, rest)}</div>')
        parts.append(status_html(c))
    elif claim.get("state") == "candidate" and cand in c.stmts:
        rest = [a for a in alts if a.get("statement_id") != cand]
        parts.append(f'<h2 class="fx-h2 fx-h2--theorem" id="claim-h">{esc(claim_heading(c))}</h2>')
        parts.append(c.stmt_card(cand, aid="claim-theorem", level=3, big=True, actions=compare_action(c, cand),
                                 state=state(cand, True, alt_line(c, cand, rest)), note=unpaired(cand)))
        if len(rest) > ALT_INLINE:
            parts.append(f'<div class="fx-others" id="claim-more"><h3 class="fx-h3">{esc(more_label(c, len(rest)))}</h3>{alt_list(c, rest)}</div>')
        parts.append(status_html(c))
    else:
        # No pairing is decided: the page still leads with mathematics. The statements the
        # papers print come first, each with its own one-line state; how they were chosen
        # follows them as information, with the open task it names.
        parts.append(f'<h2 class="fx-h2 fx-h2--theorem" id="claim-h">{esc(claim_heading(c))}</h2>')
        n_tied = len(tie_order(c, alts)[:3]) if alts else 0
        note = W("claim.unresolved_none") if not alts else W("claim.unresolved_one") if n_tied == 1 else W("claim.unresolved")
        note_html = esc(note)
        if alts:
            tied = tie_order(c, alts)[:3]
            rest = [a for a in alts if a not in tied]
            for i, a in enumerate(tied):
                parts.append(c.stmt_card(a["statement_id"], aid=f"claim-alt-{i + 1}", level=3, big=len(tied) == 1,
                                         state=state(a["statement_id"], False), note=unpaired(a["statement_id"]),
                                         actions=compare_action(c, a["statement_id"])))
            parts.append(f'<p class="fx-cand fx-cand--note">{note_html}</p>')
            if rest:
                parts.append(f'<div class="fx-others" id="claim-more"><h3 class="fx-h3">{esc(more_label(c, len(rest)))}</h3>{alt_list(c, rest)}</div>')
        else:
            parts.append(f'<p class="fx-cand fx-cand--open">{note_html}</p>')
        parts.append(status_html(c))
    lab = "claim-h"
    # The two status lines repeated the overview's evidence beside the theorem; the overview
    # now opens the page, so only their old address (#h-standing) is kept, on the theorem.
    parts.pop()
    head = [p for p in parts if p.startswith("<h2")]
    body = [p for p in parts if not p.startswith("<h2")]
    cards = [p for p in body if p.startswith("<article")]
    rest = [p for p in body if not p.startswith("<article")]
    many = len(cards) > 1
    cards_html = f'<div class="fx-grid fx-grid--st">{"".join(cards)}</div>' if many else "".join(cards)
    return (f'<section class="fx-sec fx-sec--theorem" id="claim" aria-labelledby="{lab}">'
            f'<span class="fx-alias" id="h-bench"></span><span class="fx-alias" id="bench-theorem"></span><span class="fx-alias" id="h-standing"></span>{"".join(head)}'
            f'<div class="fx-claim{" fx-claim--many" if many else ""}"><div class="fx-claim__main">{cards_html}{"".join(rest)}</div>'
            f'</div></section>')


def claim_heading(c: Ctx) -> str:
    """The result tab's question: what the paper (or papers) claims."""
    cur = [h for h in c.doc.get("paper_history") or [] if h.get("status") == "current"]
    return W("claim.heading_one") if len(cur) <= 1 else W("claim.heading_many")


_MAIN_LABEL = re.compile(r"(?:^|[:_-])main(?:$|[:_-])", re.I)


def is_main(st: dict) -> bool:
    """Whether a paper statement is the paper's main theorem by how the paper prints or labels
    it: Theorem 1.1, Theorem 1 or Theorem A, or a TeX label naming it main ("thm:main",
    "main:theorem") on a statement of the paper's opening section."""
    num = (st.get("printed_number") or "") if st.get("printed_number_status") == "recorded" else ""
    opening = not num or bool(re.fullmatch(r"1(?:\.\d+)*|[A-Z]", num))
    if _MAIN_LABEL.search(st.get("name") or "") and opening:
        return True
    return st.get("statement_kind") == "theorem" and bool(re.fullmatch(r"1\.1|1|[A-Z]", num))


def opening_statements(c: Ctx) -> tuple:
    """Which candidate statements the opening block shows whole, and the rest. A candidate the
    backend names is ranked against the others: the main theorem of the lead paper or of the
    candidate's own paper comes before a corollary or a lemma, then the backend's word
    overlap, then its order. The first is shown whole; so is the
    candidate with the most shared words when that is a different statement, and the other one
    when there are exactly two. Returns ([statement ids shown whole], [the other alternatives])."""
    claim = c.doc.get("claim") or {}
    alts = [a for a in claim.get("alternatives") or [] if a.get("statement_id") in c.stmts]
    cand = claim.get("primary_candidate")
    if claim.get("state") != "candidate" or cand not in c.stmts:
        return [], alts
    if len(alts) < 2:
        return [cand], [a for a in alts if a["statement_id"] != cand]
    lead = next((h.get("id") for h in c.doc.get("paper_history") or [] if h.get("status") == "current"), None)
    home = {lead, c.stmts[cand].get("manuscript_id")}

    def key(ia):
        i, a = ia
        st = c.stmts[a["statement_id"]]
        return (not (is_main(st) and st.get("manuscript_id") in home), -(a.get("score") or 0), i)
    ranked = [a["statement_id"] for _, a in sorted(enumerate(alts), key=key)]
    full = [ranked[0]]
    if cand != ranked[0]:
        full.append(cand)
    elif len(alts) == 2:
        full.append(ranked[1])
    return full, [a for a in alts if a["statement_id"] not in full]


def tie_order(c: Ctx, alts) -> list:
    """The candidates the backend ties (equal score, the highest), in the order the page
    shows them: the one a Lean statement is paired with first, then the lead paper's, then
    a main theorem before a corollary or lemma, then the backend's own order. The tie and its
    words stay the backend's."""
    top = max((a.get("score") or 0) for a in alts) if alts else 0
    tied = [a for a in alts if (a.get("score") or 0) == top]
    lead = next((h.get("id") for h in c.doc.get("paper_history") or [] if h.get("status") == "current"), None)
    def key(ia):
        i, a = ia
        sid = a["statement_id"]
        return (paired_lean(c, sid) is None, c.stmts[sid].get("manuscript_id") != lead, not is_main(c.stmts[sid]), i)
    return [a for _, a in sorted(enumerate(tied), key=key)]


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
    return next((l["id"][2:] for l in c.leans if sid in (c.pairs[l["id"]].get("targets") or [])), None)


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
    return (f'<article class="fx-lean" aria-labelledby="lean-{esc(name)}-h">'
            f'<h4 class="fx-lean__head" id="lean-{esc(name)}-h"><a href="{c.root}statements/{esc(name)}.html"><span class="md-math">{esc(curly_tex(l.get("name") or name))}</span></a></h4>'
            f'<p class="fx-lean__file"><code translate="no">{S.lean_breaks(">" + esc(name))[1:]}.lean</code>, {esc(role)}.</p>'
            f'{code}' + (f'<p class="fx-lean__note">{W("compare.sorry")}</p>' if code and s["comparator"]["theorem_names"] and "sorry" in s["lean"] else "") + f'{more}{holes_html}'
            + f'<p class="fx-lean__go"><a href="{c.root}statements/{esc(name)}.html">{esc(W("compare.lean_open"))}</a></p>'
            + f'<p class="fx-lean__go"><a href="#readings" data-fx-go>{esc(W("compare.runs_tab", name=name))}</a></p></article>')


def run_chips(c: Ctx, l) -> str:
    """Each group's Comparator run of one Lean statement as a compact chip, in that group's
    own word, linked to the run on the group's card; then the line that says what the runs
    establish. A statement nobody has run says so."""
    name = l["id"][2:]
    by_id = {ru["id"]: ru for ru in l.get("runs") or []}
    chips = []
    for g in l.get("run_groups") or []:
        for rid in g.get("run_ids") or []:
            ru = by_id.get(rid)
            if not ru:
                continue
            src = ru.get("source") or g.get("source")
            who = c.disp((ru.get("credit") or {}).get("name") or src)
            ok = ru.get("state") == "reported-accepted"
            chips.append(f'<li><a class="fx-chip{" fx-chip--ok" if ok else ""}" href="#{run_id(src, name)}">'
                         f'<span class="fx-chip__who">{esc(who)}</span> “{esc(ru.get("source_term") or "")}”</a></li>')
    line = f'<p class="fx-chips__line">{esc(runs_sentence(c, l))}</p>'
    return (f'<div class="fx-chips"><p class="fx-chips__h">{esc(W("compare.runs_h"))}</p>'
            + (f'<ul class="fx-chips__l">{"".join(chips)}</ul>' if chips else "") + line + "</div>")


def comparison_one(c: Ctx, l, *, first: bool, rest: bool = False) -> str:
    """One Lean statement beside the paper theorem it is paired with. The words at the
    join say how the two were joined and that nobody has reviewed the match. With several
    Lean statements, every one but the first is marked fx-cmp--rest at build time, which
    hides it only when scripts run (family.css), so the first paint shows one comparison
    and nothing is hidden after it."""
    lid = l["id"]
    name = lid[2:]
    rec = c.pairs[lid]
    state = rec["state"] if rec["target"] else "unavailable"
    shown = [t for t in rec.get("targets") or [] if t in c.stmts]
    if shown:
        # A Lean statement paired with several theorems shows each of them, the clearest first.
        paper = "".join(c.stmt_card(t, aid=f"paired-{slug_id(name)}" + (f"-{k + 1}" if k else ""), level=4)
                        for k, t in enumerate(shown))
        if len(shown) > 1:
            labels = join_and(c.S, [esc(c.label(t)) for t in shown])
            many = esc(W("compare.paired_many", labels="\x00")).replace("\x00", labels)
            paper = f'<p class="fx-cmp__many">{many}</p>' + paper
    else:
        why = f'<p class="fx-cmp__why">{esc(W("compare.no_pair_reason", reason=rec["reason"]))}</p>' if rec.get("reason") else ""
        alts = [dict(a, statement_id=a.get("target")) for a in rec["alternatives"]]
        alt = (f'<p class="fx-cmp__why">{esc(W("compare.no_pair_alternatives"))}</p>' + alt_list(c, alts, lean=name)) if alts else ""
        paper = f'<div class="fx-st fx-st--none"><p class="fx-st__none">{esc(W("compare.no_pair"))}</p>{why}{alt}</div>'
    words = ""
    if rec["target"] and state == "candidate-pairing":
        if len(shown) > 1:
            each = [W("compare.shared_each", label=c.label(t), words=", ".join(rec["shared_by"].get(t) or []))
                    for t in shown if rec["shared_by"].get(t)]
            words = esc(W("compare.shared_many", each="; ".join(each))) if each else ""
        elif rec["shared"]:
            words = esc(W("compare.shared", words=", ".join(rec["shared"])))
    for sa in c.doc.get("source_associations") or []:
        if sa.get("challenge") == name and rec["target"] and rec["target"] in (sa.get("local_statement_ids") or []):
            q = ((sa.get("source") or {}).get("quote") or "").strip()
            if q:
                words += f' <span class="fx-join__quote">{W("compare.cited_quote", quote=code_spans(q))}</span>'
    lean_head = (f'<p class="fx-cmp__state">{esc(W("compare.state_head." + state))}</p>'
                 f'<p class="fx-cmp__qual">{esc(W("compare.state_qual." + state))}</p>')
    join = f'<p class="fx-join fx-join--{esc(state)}">{words}</p>' if words else ""
    aliases = ('<span class="fx-alias" id="bench-lean"></span>' + (f'<span class="fx-alias" id="thread-{esc(c.num)}"></span>' if rec["target"] else "")) if first else ""
    title = l.get("name") or ""
    t_html = f'<span class="fx-cmp__t md-math">{esc(curly_tex(title))}</span> ' if title and title != name else ""
    # One wide row per Lean statement: its name and the groups' Comparator runs as its
    # head, then the paper theorem and the Lean side by side, the pairing's words between.
    return (f'<section class="fx-cmp" id="lean-{esc(name)}" data-cmp aria-labelledby="lean-{esc(name)}-ch">{aliases}'
            f'<header class="fx-cmp__top"><h3 class="fx-cmp__h" id="lean-{esc(name)}-ch">{t_html}<code translate="no">{esc(name)}</code></h3>'
            f'{run_chips(c, l)}</header>'
            f'<div class="fx-cmp__grid fx-cmp__grid--{esc(state)}">'
            f'<div class="fx-cmp__paper"><p class="fx-cmp__side">{esc(W("compare.paper_side"))}</p>{paper}</div>'
            f'{join}'
            f'<div class="fx-cmp__lean"><div class="fx-cmp__lhead">{lean_head}</div>{lean_card(c, l)}</div>'
            f'</div></section>')


def pair_sentence(c: Ctx, l) -> str:
    """Which paper theorem a Lean statement is paired with, by what evidence, and that the
    match is unreviewed, in one sentence."""
    rec = c.pairs[l["id"]]
    shown = [t for t in rec.get("targets") or [] if t in c.stmts]
    if not shown:
        return W("compare.row_none")
    slug = (c.stmts[shown[0]].get("manuscript_id") or "")[2:]
    key = {"candidate-pairing": "row_candidate", "producer-cited-association": "row_cited",
           "producer-declared-binding": "row_declared"}.get(rec["state"], "row_candidate")
    same = all((c.stmts[t].get("manuscript_id") or "")[2:] == slug for t in shown)
    label = join_and(c.S, [c.label(t) if same or t == shown[0] else
                           W("compare.label_in", label=c.label(t), paper=c.short_title_plain((c.stmts[t].get("manuscript_id") or "")[2:]))
                           for t in shown])
    return W("compare." + key, label=label, paper=c.short_title_plain(slug))


def lean_index(c: Ctx) -> str:
    """Every Lean statement in the family, one entry each, every entry in the same rhythm:
    its mathematical name (the link that chooses its comparison on this page), its formal
    identifier on a line of its own (the link that opens its Lean page), then two labelled lines with separate jobs, the paper theorem it is paired
    with (and by what evidence) and who reports re-running it."""
    rows = []
    for i, l in enumerate(c.leans):
        name = l["id"][2:]
        pair = pair_sentence(c, l)
        runs = runs_sentence(c, l)
        role = W("compare.index_main") if l.get("main_result") else W("compare.index_support")
        rows.append(f'<li class="fx-c fx-idx__i"><a class="fx-idx__a" href="#lean-{esc(name)}">'
                    f'<span class="fx-idx__t md-math">{esc(curly_tex(l.get("name") or name))}</span></a>'
                    f'<p class="fx-idx__id"><a class="fx-idx__lean" href="{c.root}statements/{esc(name)}.html" title="{esc(W("compare.lean_open"))}"><code translate="no">{c.S.lean_breaks(">" + esc(name))[1:]}</code></a><span class="fx-idx__role">, {esc(role)}</span></p>'
                    f'<dl class="fx-idx__dl"><div><dt>{esc(W("compare.index_paper"))}</dt><dd>{esc(pair)}</dd></div>'
                    f'<div><dt>{esc(W("compare.index_runs"))}</dt><dd>{esc(runs)}</dd></div></dl></li>')
    return (f'<nav class="fx-idx" id="h-index" aria-label="{esc(W("toc.compare"))}">'
            f'<ol class="fx-idx__list fx-grid">{"".join(rows)}</ol></nav>')


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
            out.append(sayc("reruns.source_term", name=c.disp((ru.get("credit") or {}).get("name") or src), term=ru.get("source_term") or ""))
    return out


def comparison_html(c: Ctx) -> str:
    S = c.S
    alias = '<span class="fx-alias" id="h-lean"></span>'
    if not c.leans:
        # The first screen already says the release has no Lean here: one line.
        body = f'<p class="fx-none">{esc(W("compare.nolean"))}</p>'
        return (f'<section class="fx-sec" id="compare" aria-labelledby="compare-h">{alias}<span class="fx-alias" id="bench-lean"></span>'
                f'<h2 class="fx-h2 fx-vh" id="compare-h">{esc(W("toc.compare"))}</h2>{body}</section>')
    sel = c.doc.get("selection") or {}
    supporting = sel.get("scope_context") == "supporting-or-different"
    n = len(c.leans)
    heading = W("compare.heading")
    if n == 1:
        pair = pair_sentence(c, c.leans[0])
        l0 = c.leans[0]
        lname = l0["id"][2:]
        role = W("compare.lean_main") if l0.get("main_result") else W("compare.lean_support")
        intro = W("compare.selected_one", name=lname, role=role) + " " + (
            W("compare.intro_one", name=lname, pair=pair[:1].lower() + pair[1:]) if c.pairs[l0["id"]].get("target")
            else W("compare.intro_one_none", name=lname))
    else:
        intro = W("compare.selected_many", n=S.say(n)) + " " + W("compare.index_intro")
    if supporting:
        intro += " " + sayc("scope_context.supporting-or-different")
    idx = lean_index(c) if n > 1 else ""
    cmps = "".join(comparison_one(c, l, first=(i == 0)) for i, l in enumerate(c.leans))
    return (f'<section class="fx-sec" id="compare" aria-labelledby="compare-h" data-cmp-host>{alias}'
            f'<div class="fx-shead"><h2 class="fx-h2" id="compare-h">{esc(heading)}</h2><p class="fx-ans">{esc(intro)}</p>'
            f'<p class="fx-how">{S.ctext(W("compare.comparator_once"))}</p></div>'
            f'{idx}<div class="fx-cmps">{cmps}</div>{source_notes_html(c)}{formulations_html(c)}</section>')


def source_notes_html(c: Ctx) -> str:
    """Show attributed Atlas source observations beside the selected-check comparison.

    These are imported observations, not inferred extra checks or a theorem inventory.
    Retain the same dated text and pinned links printed with the original report.
    """
    notes, seen = [], set()
    for card in c.doc.get("independent_check_cards") or []:
        note = (card.get("value") or {}).get("atlas_source_note") or {}
        if not note.get("text"):
            continue
        key = json.dumps(note, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        links = " · ".join(f'<a class="ext" href="{esc(x["url"])}" rel="noopener">{esc(x["label"])}</a>'
                           for x in note.get("links") or [])
        notes.append(f'<p class="fx-prose"><strong>{esc(W("checks.atlas_source_note", date=note.get("inspected") or ""))}.</strong> '
                     f'{code_spans(note["text"])}</p>' + (f'<p class="fx-prose">{links}</p>' if links else ""))
    if not notes:
        return ""
    return (f'<div class="fx-c fx-forms-wrap" id="h-source-notes"><h3 class="fx-c__h">{esc(W("compare.source_notes_heading"))}</h3>'
            + "".join(notes) + '</div>')


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
    return (f'<div class="fx-c fx-forms-wrap" id="h-form"><h3 class="fx-c__h">{esc(S.C("family.formulations_heading"))}</h3>'
            f'<p class="fx-intro">{esc(S.C("family.formulations_intro"))}</p><ul class="fx-plain fx-forms">{"".join(items)}</ul>{thm_line}</div>')


# ---- who has checked it ----------------------------------------------------------------


def reading_says(rd, name: str = "") -> str:
    """One reader's finding as a sentence: their name, what they find the Lean states
    (from the backend's normalised state) and their own term."""
    state = rd.state or "none"
    return W("readings.says", name=name or rd.name, finds=W("readings.state").get(state, sayc("tone." + rd.tone)), term=rd.term or "")


READER_NOTE_KEYS = ("gap", "note", "definitions_to_check")


def reader_note_id(source: str, key: str) -> str:
    return f"rd-{slug_id(source)}-{key.replace('_', '-')}"


def reader_note_for(c: Ctx, text: str) -> str | None:
    """The id of the outside reader's note that the readers section already prints in
    full with this text, or None. A reader's request in "What is left to check" then
    links to it instead of printing it a second time."""
    t = " ".join(drop_file_refs(text or "").split())
    if not t:
        return None
    for src, rec in c.readings.items():
        sv = rec.get("source_value") or {}
        for key in READER_NOTE_KEYS:
            if sv.get(key) and " ".join(drop_file_refs(sv[key]).split()) == t:
                return reader_note_id(src, key)
    return None


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


def group_id(src: str) -> str:
    return f"grp-{slug_id(src)}"


def group_def_id(src: str) -> str:
    return f"rd-{slug_id(src)}-def"


def run_id(src: str, name: str) -> str:
    return f"run-{slug_id(src)}-{slug_id(name)}"


def group_order(c: Ctx) -> list:
    """Every outside group the page names, once: the groups that assessed the family's
    scope first (the backend's order), then any group that only reports Comparator runs."""
    order = [rd.source for rd in c.ev.readers]
    for l in c.leans:
        by_id = {ru["id"]: ru for ru in l.get("runs") or []}
        for g in l.get("run_groups") or []:
            for rid in g.get("run_ids") or []:
                ru = by_id.get(rid)
                src = (ru or {}).get("source") or g.get("source")
                if ru and src not in order:
                    order.append(src)
    return order


def group_runs(c: Ctx, src: str) -> list:
    """[(Lean statement, its run by this group or None)] for every Lean statement, in the
    page's order, so a card shows which statements the group ran and which it did not."""
    out = []
    for l in c.leans:
        by_id = {ru["id"]: ru for ru in l.get("runs") or []}
        mine = None
        for g in l.get("run_groups") or []:
            for rid in g.get("run_ids") or []:
                ru = by_id.get(rid)
                if ru and (ru.get("source") or g.get("source")) == src:
                    mine = ru
                    break
            if mine:
                break
        out.append((l, mine))
    return out


def group_scope_html(c: Ctx, src: str) -> str:
    """One group's assessment of whether the Lean states the advertised result: their term
    (with the map's colour dot), what that finding means, the notes they give, their term in
    their own words, their method in one line, and the links to their record."""
    S = c.S
    rd = next((x for x in c.ev.readers if x.source == src), None)
    rec = c.readings.get(src)
    k = f'<p class="fx-grp__k">{esc(W("groups.scope_k"))}</p>'
    if not rd:
        return f'<div class="fx-grp__part">{k}<p class="fx-muted">{esc(W("glance.no_scope"))}</p></div>'
    if not rec:
        return f'<div class="fx-grp__part">{k}<p class="fx-muted">{esc(W("readings.none_says", name=c.disp(rd.name)))}</p></div>'
    sv = rec.get("source_value") or {}
    credit = rec.get("credit") or {}
    tid = f"ins-rd-{slug_id(src)}"
    notes = []
    for key, lab in zip(READER_NOTE_KEYS, ("readings.gap", "readings.note", "readings.defs")):
        if sv.get(key):
            notes.append(f'<p class="fx-rd__note" id="{reader_note_id(src, key)}"><span class="fx-rd__k">{esc(W(lab))}:</span> <span class="md-math">{code_spans(drop_file_refs(sv[key]))}</span></p>')
    method = first_sentence(credit.get("method") or "")
    links = []
    if sv.get("url"):
        links.append(f'<a class="ext" href="{esc(sv["url"])}" rel="noopener">{esc(W("readings.record"))}</a>')
    if credit.get("url"):
        links.append(f'<a class="ext" href="{esc(credit["url"])}" rel="noopener">{esc(W("readings.method_link", name=c.disp(rd.name)))}</a>')
    version = (credit.get("pin") or "")[:7]
    c.tpls[tid] = record(W("inspect.kind_reading"), esc(reader_credit(S, rd.name)),
                         [(W("readings.term"), f"“{esc(rd.term or '')}”"), (W("readings.definition"), code_spans(sv.get("text") or "")),
                          (W("readings.method"), code_spans(S.short(credit.get("method") or "", 400))),
                          (W("inspect.version"), f'<code translate="no">{esc(version)}</code>' if version else ""),
                          (W("inspect.licence"), esc(credit.get("license") or ""))],
                         [(W("readings.record"), sv.get("url")), (W("readings.method"), credit.get("url"))])
    dot_tone = {"full": "all", "part": "part", "other": "other"}.get(rd.tone, "none")
    finds = W("readings.state").get(rd.state or "none", sayc("tone." + rd.tone))
    return (f'<div class="fx-grp__part">{k}'
            f'<p class="fx-grp__term"><span class="u-dot u-dot--{dot_tone}" aria-hidden="true"></span>“{esc(rd.term or "")}”</p>'
            f'<p class="fx-grp__says">{esc(W("groups.finds", finds=finds))}</p>'
            f'{"".join(notes)}'
            + (f'<p class="fx-rd__def" id="{group_def_id(src)}">{esc(W("readings.definition_of", term=rd.term or ""))} {code_spans(sv.get("text") or "")}</p>' if sv.get("text") else "")
            + (f'<p class="fx-rd__method">{esc(W("readings.method"))}: {code_spans(method)}</p>' if method else "")
            + f'<p class="fx-rd__links">{" ".join(links)} '
            f'{ins_button(tid, esc(W("readings.details")), name=W("readings.details_label", who=c.disp(rd.name) + "’s", num=c.num))}</p></div>')


def run_cell_html(c: Ctx, src: str, l, ru) -> tuple:
    """One group's Comparator run of one Lean statement, as a table cell: their word, their
    account, the date and version, and the original report; or that no run is recorded.
    Returns (html, whether the report gave fields)."""
    S = c.S
    name = l["id"][2:]
    if not ru:
        return f'<span class="fx-muted">{esc(W("glance.runs_none"))}</span>', False
    credit = ru.get("credit") or {}
    sv = ru.get("source_value") or {}
    who = c.disp(credit.get("name") or ru.get("source"))
    whose = possessive(S, who)
    when = S.date_words(ru.get("date"))
    pin = W("reruns.at_pin") if ru.get("pin_state") == "current" else W("reruns.other_pin")
    det = run_fields(ru)
    tid = "ins-run-" + slug_id(ru["id"][4:])
    c.tpls[tid] = record(W("inspect.kind_run"), f'{esc(who)}, <code translate="no">{esc(name)}</code>',
                         [(W("reruns.said"), f"“{esc(ru.get('source_term') or '')}”"),
                          (W("reruns.account"), esc(S.curly(sv.get("text") or ""))),
                          (W("inspect.date"), esc(when or W("reruns.undated"))), (W("inspect.version"), esc(pin)),
                          (W("readings.method"), code_spans(first_sentence(credit.get("method") or ""))),
                          (W("reruns.recorded"), esc(det))],
                         [(W("reruns.receipt"), ru.get("receipt"))])
    receipt = (f'<a class="ext" href="{esc(ru.get("receipt") or "")}" rel="noopener" '
               f'aria-label="{esc(W("reruns.receipt_label", who=whose, name=name))}">{esc(W("reruns.receipt"))}</a>' if ru.get("receipt") else "")
    details = ins_button(tid, esc(W("readings.details")), name=W("reruns.details_label", who=whose, name=name))
    return (f'<p class="fx-run__term">“{esc(ru.get("source_term") or "")}”</p>'
            f'<p class="fx-run__acc">{esc(S.curly(sv.get("text") or ""))}' + (f' <span class="fx-run__det">{esc(det)}</span>' if det else "") + '</p>'
            f'<p class="fx-run__meta">{esc(when or W("reruns.undated"))}, {esc(pin)}. {receipt} {details}</p>'), bool(det)


def runs_table_html(c: Ctx, srcs: list, names: dict) -> tuple:
    """Every reported Comparator run in one table: a row per Lean statement, a column per
    group, so which statements each group ran, and which it did not, reads across and down.
    A narrow screen stacks each statement's runs under it, labelled by group.
    Returns (html, whether any report gave fields)."""
    S = c.S
    if not c.leans or not srcs:
        return "", False
    runs = {src: dict((l["id"], ru) for l, ru in group_runs(c, src)) for src in srcs}
    head = "".join(f'<th scope="col">{esc(names[src])}</th>' for src in srcs)
    rows, any_detail = [], False
    for l in c.leans:
        name = l["id"][2:]
        title = l.get("name") or ""
        obj = ((f'<span class="fx-run__t md-math">{esc(curly_tex(title))}</span>' if title and title != name else "")
               + f'<code translate="no">{S.lean_breaks(">" + esc(name))[1:]}</code>')
        cells = []
        for src in srcs:
            ru = runs[src].get(l["id"])
            cell, det = run_cell_html(c, src, l, ru)
            any_detail = any_detail or det
            rid = f' id="{run_id(src, name)}"' if ru else ""
            cells.append(f'<td{rid} data-label="{esc(names[src])}"{" class=" + chr(34) + "fx-rt__none" + chr(34) if not ru else ""}>{cell}</td>')
        rows.append(f'<tr><th scope="row" class="fx-rt__obj">{obj}</th>{"".join(cells)}</tr>')
    k = f'<h4 class="fx-grp__k fx-rt__h">{S.ctext(W("groups.runs_table"))}</h4>'
    table = (f'<div class="fx-rt__wrap"><table class="fx-rt fx-rt--n{min(len(srcs), 4)}"><thead><tr><th scope="col">{esc(W("groups.runs_obj"))}</th>{head}</tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    return k + table, any_detail


def groups_html(c: Ctx) -> str:
    """What the groups found, in two comparisons: the coverage assessments side by side
    (a group that made none is named in one line, not given an empty card), then every
    Comparator run in one table of Lean statements by groups. Earlier addresses
    (#readings, #reruns, #reruns-<name>, #grp-<group>) land here."""
    S, ev = c.S, c.ev
    names_full = reader_full_names()
    aliases = ('<span class="fx-alias" id="h-readings"></span><span class="fx-alias" id="h-reruns"></span>'
               '<span class="fx-alias" id="reruns"></span>'
               + "".join(f'<span class="fx-alias" id="reruns-{esc(l["id"][2:])}"></span>' for l in c.leans))
    head = f'<h3 class="fx-h3" id="readings">{esc(W("groups.heading"))}</h3>'
    if not c.leans and not c.readings:
        return f'{aliases}{head}<p class="fx-none">{esc(W("readings.nolean"))}</p>'
    order = group_order(c)
    names, cards, silent = {}, [], []
    for src in order:
        rd = next((x for x in ev.readers if x.source == src), None)
        full = names_full.get(src) or (rd.name if rd else "") or c.source_name(src)
        name = c.disp(full) if full else c.source_name(src)
        names[src] = name
        if not rd:
            silent.append(f'<span class="fx-grp-none__n" id="{group_id(src)}">{esc(name)}</span>')
            continue
        credit = reader_credit(S, full) if full and full != name else ""
        cards.append(f'<article class="fx-c fx-grp" id="{group_id(src)}" aria-labelledby="{group_id(src)}-h">'
                     f'<header class="fx-grp__head"><h4 class="fx-c__h" id="{group_id(src)}-h">{esc(name)}</h4>'
                     + (f'<p class="fx-c__sub">{esc(credit)}</p>' if credit else "") + '</header>'
                     f'{group_scope_html(c, src)}</article>')
    run_srcs = [src for src in order if any(ru for _, ru in group_runs(c, src))]
    runs, any_detail = runs_table_html(c, run_srcs, names)
    lead = esc(ev.agreement_sentence()) if c.readings else ""
    note = "" if any_detail or not c.leans else f' {esc(W("reruns.details_none"))}'
    intro = W("groups.intro", names=join_and(S, [reader_credit(S, names_full.get(rd.source, rd.name)) for rd in ev.readers])) if ev.readers else ""
    none_line = (f'<p class="fx-grp-none">{W("groups.no_scope_line", names=join_and(S, silent))}</p>' if silent else "")
    return (f'{aliases}<div class="fx-grphead">{head}' + (f'<p class="fx-ans">{lead}</p>' if lead else "")
            + f'<p class="fx-how">{esc(intro)}{note}</p></div>'
            + (f'<div class="fx-grid fx-grid--groups">{"".join(cards)}</div>' if cards else "")
            + none_line + (f'<div class="fx-runs-all">{runs}</div>' if runs else ""))


def producer_drafts_html(c: Ctx) -> str:
    """OpenAI's own note on its Lean, as one card, and the AI agent's draft classifications
    as a quiet labelled card beside it, each draft naming the Lean statement it classifies."""
    S = c.S
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
                      f'<span class="md-math">{code_spans(drop_file_refs(val.get("note") or ""))}</span></p></li>')
    parts = []
    pv = (c.doc.get("producer_scope") or {}).get("value") or {}
    if pv.get("scope"):
        paras = [S.curly(p) for p in re.split(r"\n\s*\n", pv["scope"].strip()) if p.strip()]
        rest = S.md_paragraphs(chr(10) + chr(10).join(paras[1:])) if len(paras) > 1 else ""
        parts.append(f'<div class="fx-c fx-producer" id="h-producer"><h4 class="fx-c__h"><a class="ext" href="{esc(pv.get("url") or "")}" rel="noopener">{esc(W("readings.producer"))}</a></h4>'
                     f'<blockquote class="fx-producer__q md-math">{S.md_paragraphs(paras[0])}{rest}</blockquote></div>')
    if drafts:
        parts.append(f'<div class="fx-c fx-c--quiet fx-drafts" aria-labelledby="h-drafts"><h4 class="fx-c__h" id="h-drafts">{esc(W("readings.draft_heading"))}</h4>'
                     f'<ul class="fx-draft">{"".join(drafts)}</ul></div>')
    return f'<div class="fx-grid fx-grid--two">{"".join(parts)}</div>' if parts else ""


def other_checks_html(c: Ctx) -> str:
    """Other reports and calculations as one grid of cards: checks by another method (each
    leading with what it checked) and other people's accounts of running proof-verification
    software, each with its receipt."""
    S, doc = c.S, c.doc
    cards = doc.get("independent_check_cards") or []
    unav = doc.get("unavailable_check_reports") or []
    others = (c.cfind.get("replay-pass") or []) + (c.cfind.get("replay-fail") or [])
    if not cards and not unav and not others:
        return ""
    items = []
    if cards:
        idents = [check_identity(c, card) for card in cards]
        plain = [p for _, _, p in idents]
        for i, card in enumerate(cards):
            v = card.get("value") or {}
            credit = card.get("credit") or {}
            kind = sayc("check_kind." + card["field"]) if card.get("field") in evidence.WORDS["check_kind"] else card.get("field")
            state = W("checks.states").get(card.get("state"), card.get("state") or "")
            what = v.get("certifies") or v.get("text") or ""
            verdict = v.get("code") or v.get("verdict") or v.get("cold") or ""
            who = c.disp(credit.get("name") or card.get("source"))
            whose = possessive(S, who)
            tid = f"ins-card-{i}"
            covers, whole = card_covers(v)
            covers_html = (f"“{code_spans(covers)}”" if whole else code_spans(covers)) if covers else ""
            ident_html, sub, ident = idents[i]
            if plain.count(ident) > 1 and v.get("id"):
                sub = (sub + " " if sub else "") + esc(W("checks.report_id", id=v["id"]))
                ident = f"{ident} ({W('checks.report_id', id=v['id'])})"
            # Atlas observations stay outside the original report's attributed words.
            source_note = v.get("atlas_source_note") or {}
            source_note_html = code_spans(source_note.get("text") or "")
            if source_note_html:
                links = " · ".join(f'<a class="ext" href="{esc(x["url"])}" rel="noopener">{esc(x["label"])}</a>'
                                   for x in source_note.get("links") or [])
                source_note_html += (" " + links) if links else ""
            source_note_label = W("checks.atlas_source_note", date=source_note.get("inspected") or "")
            rows = [(W("checks.verdict"), f"“{esc(verdict)}”" if verdict else ""), (W("checks.certifies"), code_spans(what)),
                    (W("checks.relation"), covers_html),
                    (source_note_label, source_note_html),
                    (W("checks.detail"), "" if whole else code_spans(v.get("detail") or "")),
                    (W("inspect.version"), f'<code translate="no">{esc((credit.get("pin") or "")[:7])}</code>' if credit.get("pin") else "")]
            c.tpls[tid] = record(W("inspect.kind_card"), ident_html, rows, [(W("inspect.link"), v.get("url") or credit.get("url"))],
                                 sub=esc(f"{cap(kind)}, {who}"))
            gloss = v.get("text") if not v.get("certifies") and v.get("text") else cap(state)
            outcome = ((f"“{esc(verdict)}” " if verdict else "") + f'<span class="fx-fields__gloss">{esc(curly(gloss).rstrip(".") + ".")}</span>'
                       if gloss else (f"“{esc(verdict)}”" if verdict else ""))
            method = W("checks.method").get(card.get("field"), cap(kind or ""))
            report = (f'<a class="ext" href="{esc(v.get("url") or credit.get("url") or "")}" rel="noopener" '
                      f'aria-label="{esc(W("checks.report_label", who=whose, what=ident))}">{esc(W("checks.report"))}</a>')
            details = ins_button(tid, esc(W("readings.details")), name=W("checks.details_label", who=whose, what=ident))
            fields = [(W("checks.who"), esc(who), ""), (W("checks.verdict"), outcome, ""),
                      (W("checks.relation"), covers_html, "fx-fields__scope"),
                      (source_note_label, source_note_html, "fx-fields__scope"),
                      (W("checks.receipt"), f'{report} {details}', "")]
            dl = "".join(f'<div><dt>{esc(k)}</dt><dd{f" class={chr(34)}{cl}{chr(34)}" if cl else ""}>{val}</dd></div>' for k, val, cl in fields if val)
            items.append(f'<li class="fx-c fx-card"><p class="fx-c__kind">{esc(method)}</p><p class="fx-card__id">{ident_html}</p>'
                         + (f'<p class="fx-card__sub">{sub}</p>' if sub else "")
                         + f'<dl class="fx-fields">{dl}</dl></li>')
    for x in sorted(others, key=lambda x: x.get("date") or "", reverse=True):
        items.append(find_card(c, x, W("checks.kind_replay")))
    if unav:
        links = "".join(f'<li><a class="ext" href="{esc(u.get("url") or "")}" rel="noopener">{esc(u.get("name") or u.get("source") or u.get("url"))}</a></li>' for u in unav)
        items.append(f'<li class="fx-c fx-card"><p class="fx-c__kind">{esc(W("checks.unavailable_heading"))}</p><ul class="fx-plain">{links}</ul></li>')
    intro = checks_intro(c, cards) if cards else W("reruns.others_intro")
    return (f'<span class="fx-alias" id="h-hol"></span><span class="fx-alias" id="h-finite"></span><span class="fx-alias" id="h-reported"></span>'
            f'<h3 class="fx-h3" id="other-checks">{esc(W("checks.heading"))}</h3><p class="fx-how">{esc(intro)}</p>'
            f'<ul class="fx-cards {flow_class(len(items))}">{"".join(items)}</ul>')


def checked_html(c: Ctx) -> str:
    """What the groups found: one card per group, OpenAI's note and the AI drafts, other
    reports and calculations, problems reported by others and notes on the records."""
    probs = c.problems()
    finds = c.doc.get("findings") or []
    parts = [groups_html(c), producer_drafts_html(c), other_checks_html(c)]
    if probs:
        parts.append(f'<h3 class="fx-h3" id="problems"><span class="fx-alias" id="h-problems"></span>{esc(W("checks.problems_heading"))}</h3>'
                     f'<p class="fx-how">{esc(W("checks.problems_intro"))}</p>' + finds_list(c, probs).replace('class="fx-finds ', 'class="fx-finds fx-finds--problem ', 1))
    if finds:
        items = "".join(f'<li><code translate="no">{esc(x.get("row_id") or "")}</code>: {code_spans(x.get("message") or "")}</li>' for x in finds)
        parts.append(f'<h3 class="fx-h3" id="findings">{esc(W("checks.findings_heading"))}</h3>'
                     f'<div class="fx-c"><p class="fx-how">{esc(W("checks.findings_intro"))}</p><ul class="fx-plain fx-plain--cols">{items}</ul></div>')
    return (f'<section class="fx-sec" id="checks" aria-labelledby="checks-h"><span class="fx-alias" id="h-checks"></span>'
            f'<h2 class="fx-h2" id="checks-h">{esc(W("checked.heading_differ") if c.ev.agreement == "disagree" else W("checked.heading"))}</h2>{"".join(p for p in parts if p)}</section>')


def others_explain_html(c: Ctx) -> str:
    """Explanations others have published of this family's results: their own section,
    beside what people have said, rather than under the proof-check reports."""
    ex = c.cfind.get("explanation") or []
    if not ex:
        return ""
    return (f'<section class="fx-sec" id="others-explain" aria-labelledby="explanations">'
            f'<h2 class="fx-h2" id="explanations">{esc(W("said.question"))}</h2>'
            f'<p class="fx-how">{esc(W("claim.explanations_intro"))}</p>{finds_list(c, ex)}</section>')


# ---- what is left to check ----------------------------------------------------------------


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
    return (f'<article class="fx-c pp" id="{esc(m["id"])}">{aliases}'
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
        prev_html = f'<div class="fx-c fx-prevs"><h3 class="fx-c__h" id="previous">{esc(W("papers.previous"))}</h3><ul class="fx-pps">{"".join(items)}</ul></div>'
    rs = c.f.get("reasoning_summary")
    reasoning = (f'<p class="fx-prose small">{esc(S.C("family.reasoning_summary"))} '
                 f'<a class="ext" href="{esc(rs["url"])}" rel="noopener">{esc(rs["title"])}</a></p>') if rs else ""
    return (f'<section class="fx-sec" id="papers" aria-labelledby="papers-h"><span class="fx-alias" id="h-ms"></span>'
            f'<div class="fx-shead"><h2 class="fx-h2" id="papers-h">{esc(W("papers.heading"))}</h2><p class="fx-how">{S.ctext(W("papers.intro"))}</p></div>'
            f'<div class="pps fx-grid fx-grid--papers">{rows}{prev_html}</div>{reasoning}{S.withdrawn_from_family_html(c.num, root)}</section>')


def connections_html(c: Ctx) -> str:
    """What the family's papers cite in the release and what cites them, by one rule for both
    directions: a paper of this family citing another is said once, under "Within this
    family", and each outside row names the family paper on the other end of the citation."""
    S, f, root = c.S, c.f, c.root
    mss = [S.MS[s] for s in f["manuscripts"] if s in S.MS]
    own = set(f["manuscripts"])
    within: dict = {}          # citing family paper -> [cited family papers]
    cites: dict = {}           # outside paper -> [family papers citing it]
    cited: dict = {}           # outside paper -> [family papers it cites]
    for m in mss:
        for r in m.get("rests_on") or []:
            x = r["manuscript"]
            if x in own:
                within.setdefault(m["id"], [])
                if x not in within[m["id"]]:
                    within[m["id"]].append(x)
            else:
                cites.setdefault(x, [])
                if m["id"] not in cites[x]:
                    cites[x].append(m["id"])
        for x in m.get("cited_by_in_collection") or []:
            if x in own:
                within.setdefault(x, [])
                if m["id"] not in within[x]:
                    within[x].append(m["id"])
            else:
                cited.setdefault(x, [])
                if m["id"] not in cited[x]:
                    cited[x].append(m["id"])

    def paper_link(slug):
        return f'<a href="{root}papers/{esc(slug)}.html">{c.short_title_html(slug)}</a>'

    def rows(items: dict, row_key: str) -> str:
        out = []
        for slug, ours in items.items():
            m = S.MS.get(slug)
            if not m:
                continue
            fam = S.FAM.get(m.get("family") or "")
            fam_link = (f' <span class="rel__fam">{esc(S.C("words.result").capitalize())} <a href="{root}families/{fam["id"]}.html">{S.fam_title_html(fam)}</a></span>'
                        if fam and fam["id"] != c.num else "")
            lean = S.C("words.has_lean") if m.get("has_lean") else S.C("words.no_lean")
            whose = esc(W("cites." + row_key, papers="\x00")).replace("\x00", join_and(S, [paper_link(o) for o in ours]))
            out.append(f'<li><a class="rel__title" href="{root}papers/{esc(slug)}.html">{S.ms_title_html(m)}</a>'
                       f'<span class="rel__meta">{esc(S.C("family.cites_status", status=S.status_label(m.get("status", "current")), lean=lean))}</span>{fam_link}'
                       f'<span class="rel__by">{whose}</span></li>')
        return f'<ul class="rel">{"".join(out)}</ul>' if out else ""

    # One card per kind of connection that exists; the kinds with nothing to show are
    # said together in one line, never as empty columns.
    cards, nones = [], []
    if within:
        tpl = esc(W("cites.within_cites", citing="\x00", cited="\x01"))
        items = "".join("<li>" + tpl.replace("\x00", paper_link(a)).replace("\x01", join_and(S, [paper_link(b) for b in bs])) + "</li>"
                        for a, bs in within.items() if bs)
        cards.append(f'<div class="fx-c"><h3 class="fx-c__h">{esc(W("cites.within_heading"))}</h3><ul class="fx-plain fx-within">{items}</ul></div>')
    for items, row_key, head_key, none_key in ((cites, "cited_by_row", "cites_heading", "cites_none"), (cited, "cites_row", "cited_heading", "cited_none")):
        body = rows(items, row_key)
        if body:
            cards.append(f'<div class="fx-c"><h3 class="fx-c__h">{esc(W("cites." + head_key))}</h3>{body}</div>')
        else:
            nones.append(none_key)
    refs_html = []
    for m in mss:
        refs = m.get("references") or []
        if refs:
            anchor = "#pr-references" if m["id"] in S.PAPER_BIBLIOGRAPHY else ""
            refs_html.append(f'<li><a href="{root}papers/{esc(m["id"])}.html{anchor}">{esc(S.C("family.refs_summary", count=len(refs), title=S.tex_plain(m["title"])))}</a></li>')
        else:
            refs_html.append(f'<li class="fx-muted">{esc(S.C("family.refs_none_in", title=S.tex_plain(m["title"])))}</li>')
    cards.append(f'<div class="fx-c fx-refs" id="h-refs"><h3 class="fx-c__h">{esc(S.C("family.refs_heading"))}</h3><p class="fx-how">{esc(W("papers.refs_intro"))} <a href="{root}references-outside.html">{esc(S.C("references_outside.title"))}</a></p><ul class="fx-plain">{"".join(refs_html)}</ul></div>')
    none_line = ""
    if nones:
        none_line = f'<p class="fx-none">{esc(W("cites.none_both") if len(nones) == 2 else W("cites." + nones[0]))}</p>'
    fol = c.cfind.get("follow-up-result") or []
    fol_html = ""
    if fol:
        # Follow-up work is one more card of the same grid, its items as rows inside it.
        rows_ = "".join(find_card(c, x).replace('<li class="fx-c fx-find">', '<li class="fx-find fx-find--row">', 1)
                        for x in sorted(fol, key=lambda x: x.get("date") or "", reverse=True))
        fol_html = f'<div class="fx-c fx-followups" id="h-followups"><h3 class="fx-c__h">{esc(W("followups.heading"))}</h3><ul class="fx-finds">{rows_}</ul></div>'
    # Follow-up work is the principal reading; the citation and reference routes stack in a
    # narrower companion column beside it, each at its natural height.
    grid = (f'<div class="fx-cites2">{fol_html}<div class="fx-cites2__side">{"".join(cards)}</div></div>' if fol_html
            else f'<div class="fx-grid fx-grid--wide fx-grid--cites">{"".join(cards)}</div>')
    return (f'<section class="fx-sec" id="cites" aria-labelledby="cites-h"><span class="fx-alias" id="h-cites"></span>'
            f'<div class="fx-shead"><h2 class="fx-h2" id="cites-h">{esc(W("cites.heading"))}</h2><p class="fx-ans">{esc(W("cites.ans"))}</p><p class="fx-how">{esc(S.C("family.citations_intro"))}</p></div>'
            f'{none_line}{grid}</section>')


def explanations_html(c: Ctx) -> str:
    """Explanations written for the atlas: reviewed ones as reading routes, drafts as a
    visible list, an invitation when there are none."""
    S, fid, root = c.S, c.num, c.root
    ex = S.CONTRIB["explanations"].get(fid, [])
    parts = []
    for e in [e for e in ex if e["status"] == "reviewed"]:
        href = f'{root}{S.explanation_rel(e, fid)}'
        parts.append(f'<article class="exrec"><h3 class="fx-c__h md-math"><a href="{href}">{esc(e.get("title") or S.C("explanation.untitled"))}</a></h3>'
                     f'{S.explanation_meta_html(e, fid, root)}<p class="actions"><a class="btn btn--ghost" href="{href}">{esc(S.C("family.read_explanation"))}</a></p></article>')
    drafts = [e for e in ex if e["status"] != "reviewed"]
    if drafts:
        items = "".join(f'<li><span class="md-math">{esc(e.get("title") or S.C("explanation.untitled"))}</span>, {esc(S.people(e["names"]))} '
                        f'<span class="fx-muted small">({esc(S.C("family.explain_status_" + ("ready" if e["status"] == "ready-for-review" else "draft")))})</span> '
                        f'<a class="ext small" href="{esc(S.REPO + "/blob/main/" + e["path"])}" rel="noopener">{esc(S.C("family.explain_draft_source"))}</a></li>' for e in drafts)
        parts.append(f'<h3 class="fx-c__h fx-c__h--sub">{esc(S.C("family.explain_progress_heading"))}</h3><p class="fx-how">{esc(S.C("family.explain_progress_intro"))}</p><ul class="fx-plain">{items}</ul>')
    return "".join(parts)


def said_html(c: Ctx) -> str:
    S, f = c.S, c.f
    said = list(c.cfind.get("commentary") or [])
    lead = ""
    ty, tier = S.sourced(f, "type"), S.sourced(f, "tier")
    if ty and tier and tier.get("value") is not None:
        tsrc = S.SOURCES.get(tier["source"]) or {}
        tname = (tsrc.get("tier_names") or {}).get(str(tier["value"]))
        what = S.C("sources.type_words").get(ty["value"], ty["value"])
        if tname:
            lead = (f'<li class="fx-c fx-find"><p class="fx-find__who"><a class="ext fx-find__name" href="{esc(tsrc.get("url") or "")}" rel="noopener">{esc(S.C("family.tier_credit"))}</a></p>'
                    f'<p class="fx-find__what">{esc(S.C("family.tier_said", name=S.curly(tsrc.get("name") or ""), type=what, tier=S.curly(tname)))}</p></li>')
    if not said and not lead:
        return ""
    return (f'<section class="fx-sec fx-sec--quiet" id="said" aria-labelledby="said-h"><span class="fx-alias" id="h-said"></span>'
            f'<h2 class="fx-h2" id="said-h">{esc(W("said.heading") if c.cfind.get("explanation") else W("said.question"))}</h2><p class="fx-how">{esc(W("said.intro"))}</p>'
            + finds_list(c, said, unsigned=lead) + "</section>")


# ---- the page --------------------------------------------------------------------------------


def toc_html(c: Ctx, present: list) -> str:
    unresolved = not ((c.doc.get("claim") or {}).get("state") == "candidate" and (c.doc.get("claim") or {}).get("primary_candidate") in c.stmts) \
        or len(opening_statements(c)[0]) > 1
    label = lambda k: W("toc.claim_unresolved") if (k == "claim" and unresolved) else W("toc." + k)
    items = "".join(f'<li><a href="#{k}">{esc(label(k))}</a></li>' for k in present)
    return f'<nav class="fx-toc" aria-labelledby="toc-h"><p class="fx-toc__h" id="toc-h">{esc(W("toc.label"))}</p><ol>{items}</ol></nav>'


def rail_html() -> str:
    return (f'<section class="ins-rail" data-ins-rail hidden data-ins-hint="{esc(W("inspect.hint"))}" data-ins-close="{esc(W("inspect.close"))}" '
            f'data-ins-pinned="{esc(W("inspect.pinned"))}"><div class="ins-rail__bar"><p class="ins-rail__h" id="ins-rail-h" tabindex="-1">{esc(W("inspect.pinned"))}</p>'
            f'<button class="ins-rail__close" type="button">{esc(W("inspect.close"))}</button></div><div class="ins-rail__body"></div></section>')


# Before the first paint, show only the panel the address names (or the first), so a
# scripted page never flashes every panel and then collapses; family.js takes over.
TAB_PAINT_SCRIPT = ("<script>(function(){var d=document,a=d.querySelectorAll('[data-fx-panel]');if(a.length<2)return;"
                    "var h='';try{h=decodeURIComponent(location.hash.slice(1));}catch(x){}"
                    "var e=h&&d.getElementById(h),p=e&&(e.matches('[data-fx-panel]')?e:e.closest('[data-fx-panel]'))||a[0],i;"
                    "d.querySelector('.fx').classList.add('fx--tabbed');"
                    "for(i=0;i<a.length;i++)a[i].hidden=a[i]!==p;"
                    "var t=d.querySelectorAll('[data-fx-tab]');for(i=0;i<t.length;i++){var on=t[i].getAttribute('data-fx-tab')===p.id;"
                    "t[i].setAttribute('aria-selected',on?'true':'false');t[i].tabIndex=on?0:-1;}})();</script>")
TAB_GROUPS = (("overview", ("overview",)), ("result", ("claim", "papers")), ("lean", ("compare",)), ("checks", ("checks",)), ("cites", ("cites",)),
              ("said", ("others", "said")))


def build(S, f) -> None:
    """Write families/<id>.html."""
    c = Ctx(S, f)
    rel = f"families/{c.num}.html"
    head, overview = head_html(c)
    # The claim, then the papers it comes from, the Lean, the checks and the connections.
    # Atlas collects from public sources: it carries no contribution tab or forms (Will,
    # 19 October 2026). Reviewed explanations still get their own pages.
    for e in S.reviewed_explanations(c.num):
        S.build_explanation(c.f, e)
    sections = dict([("overview", overview), ("claim", theorem_html(c)), ("papers", papers_html(c)), ("compare", comparison_html(c)),
                     ("checks", checked_html(c)), ("cites", connections_html(c)),
                     ("said", said_html(c)), ("others", others_explain_html(c))])
    # One reading question per tab, so no answer sits eight screens down the page. Without
    # scripts every panel shows in turn and the tabs are links to them.
    groups = [(k, [x for x in keys if sections.get(x)]) for k, keys in TAB_GROUPS]
    groups = [(k, keys) for k, keys in groups if keys]
    panels = "\x01".join("".join(sections[x] for x in keys) for _, keys in groups)
    head, main = link_first_terms(head + "\x00" + panels).split("\x00", 1)
    parts = main.split("\x01")
    # A tab with nothing of its own (no Lean in the release) is set quietly.
    quiet = {"lean"} if not c.leans else set()
    if not c.leans and not c.readings and not c.problems() and not (c.doc.get("independent_check_cards") or c.doc.get("unavailable_check_reports")
                                                                  or c.cfind.get("replay-pass") or c.cfind.get("replay-fail")):
        quiet.add("checks")
    tabs = "".join(f'<li role="presentation"><a class="fx-tab{" fx-tab--quiet" if k in quiet else ""}" role="tab" id="t-{k}" href="#p-{k}" data-fx-tab="p-{k}" aria-controls="p-{k}">'
                   f'{esc(W("tabs." + k))}' + (f' <span class="fx-tab__none">{esc(W("tabs.none"))}</span>' if k in quiet else "") + '</a></li>' for k, _ in groups)
    body_panels = "".join(f'<div class="fx-panel" id="p-{k}" role="tabpanel" aria-labelledby="t-{k}" data-fx-panel>{html}</div>'
                          for (k, _), html in zip(groups, parts))
    body = f"""<div class="frame page fx">
{head}
<nav class="fx-tabs" aria-label="{esc(W('tabs.label'))}"><ul class="fx-tabs__list" role="tablist">{tabs}</ul>{help_q("tabs", W("help.tabs"))}</nav>
<div class="fx-body">
 <div class="fx-main">
{body_panels}{TAB_PAINT_SCRIPT if len(groups) > 1 else ""}
 </div>
 <aside class="fx-aside" aria-label="{esc(W('inspect.pinned'))}">{rail_html()}</aside>
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
    v = S.asset_v
    return (f'{fonts}<link rel="stylesheet" href="{root}assets/{v("inspect.css")}">\n'
            f'<link rel="stylesheet" href="{root}assets/{v("family.css")}">\n'
            f'<script defer src="{root}assets/{v("inspect.js")}"></script>\n<script defer src="{root}assets/{v("family.js")}"></script>')
