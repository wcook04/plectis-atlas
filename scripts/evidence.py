"""One vocabulary for the evidence a reader sees: recorded state, tone, words and mark.

Statement Map decides every state (scripts/reader.py): which outside reader found
what, which pairing a Lean statement has and by what evidence, which re-runs are
accepted at the release's pin. This module only gives each state its name, groups
an outside reader's recorded finding into the three tones the family mark can
draw, and hands every page the same words from site/copy_evidence.json. It never
combines two readers into one verdict, never chooses a theorem, and never turns
an unknown into a zero. scripts/glyphs.py draws what this module describes.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = json.loads((ROOT / "site" / "copy_evidence.json").read_text(encoding="utf-8"))

# An outside reader's finding on whether the release's Lean states the family's
# headline, as Statement Map normalises it (readings[].state), grouped into the
# tones the mark draws. Each source's own term (readings[].source_term) is kept
# beside it and shown in words.
TONE = {"all": "full", "part": "part", "narrower": "part", "weaker": "part",
        "supporting": "other", "different": "other"}
TONES = ("full", "part", "other", "none")
PAIRINGS = ("candidate-pairing", "producer-cited-association", "producer-declared-binding", "unavailable")


def join_names(names) -> str:
    """Credited names joined for a sentence. Each credited name may contain a comma
    ("Carlos Toledo, cert-machine"), so groups are separated by semicolons."""
    names = [n for n in names if n]
    return WORDS["reruns"]["names_joiner"].join(names)


def say(key: str, **kw) -> str:
    """A string from copy_evidence.json by dotted key, formatted with kw."""
    node = WORDS
    for part in key.split("."):
        node = node[part]
    return node.format(**kw) if kw else node


@dataclass(frozen=True)
class Reading:
    source: str            # the reader's source id, e.g. "mathvet"
    name: str              # the credited name, e.g. "Carlos Toledo, cert-machine"
    url: str | None        # where the reader publishes its findings
    state: str | None      # Statement Map's normalised state ("all", "narrower", ...) or None
    tone: str              # full | part | other | none
    term: str | None       # the reader's own word for it ("MATCHES", "partial", ...)


@dataclass(frozen=True)
class LeanMark:
    id: str                # "l:SiegelZeros"
    name: str
    main_result: bool | None
    accepted: tuple        # outside sources whose re-run is accepted at the current pin
    holes: int | None      # definition holes, None when unavailable


@dataclass(frozen=True)
class FamilyEvidence:
    id: str                # "f:003"
    num: str               # "003"
    name: str
    discipline: str | None
    papers: int            # current papers
    editions: int          # previous editions
    withdrawn: int
    lean: tuple            # LeanMark, in the reader's order
    readers: tuple         # Reading, in READER_ORDER; tone "none" when that reader has no finding
    agreement: str         # agree | disagree | unknown (the backend's headline_coverage)
    claim: str             # candidate | unresolved
    pairing: str           # selection.pairing_state
    scope_context: str | None
    checks: tuple = field(default=())   # kinds of outside checks by another method ("hol_checks", ...)
    findings: int = 0
    community_findings: int = 0
    contributions: int = 0
    comparison: str = "unavailable"   # the backend's finer reader_comparison.state
    community: tuple = ()             # (kind, count) of attributed community findings, e.g. ("explanation", 2)

    def community_count(self, kind: str) -> int:
        """How many attributed community findings of this kind the family has
        ("explanation", "error-reported", "correction", "replay-pass", "replay-fail",
        "follow-up-result", "commentary")."""
        return dict(self.community).get(kind, 0)

    def agreement_sentence(self) -> str:
        """The backend's comparison of the two readings, in one sentence."""
        key = f"{self.comparison}:{self.agreement}"
        table = WORDS["comparison"]
        return table.get(key) or say("agreement." + self.agreement)

    @property
    def has_lean(self) -> bool:
        return bool(self.lean)

    @property
    def tones(self) -> tuple:
        return tuple(r.tone for r in self.readers)

    @property
    def key(self) -> str:
        """A stable class for filtering the map: "nolean", or "lean-<left tone>-<right tone>"."""
        return "nolean" if not self.lean else "lean-" + "-".join(self.tones)

    def sentence(self) -> str:
        """One plain sentence a screen reader can say for the family's mark."""
        n = self.papers
        parts = [say("sentence.papers_one") if n == 1 else say("sentence.papers_many", n=n)]
        k = len(self.lean)
        parts.append(say("sentence.lean_none") if k == 0 else say("sentence.lean_one") if k == 1
                     else say("sentence.lean_many", n=k))
        text = f"{self.name}: " + ", ".join(parts) + "."
        if self.lean:
            found = [f"{r.name} {say('tone_short.' + r.tone) if r.tone == 'none' else 'finds ' + say('tone_short.' + r.tone)}"
                     for r in self.readers]
            text += " " + "; ".join(found) + "."
        if self.checks:
            text += " " + say("other_checks", kinds=", ".join(say("check_kind." + c) for c in self.checks
                                                         if c in WORDS["check_kind"]))
        return text


def reader_order(readings_seen: set[str]) -> list[str]:
    """The two sides of the diamond: the configured order, then any other source alphabetically."""
    order = list(WORDS["readers"]["order"])
    return order + sorted(s for s in readings_seen if s not in order)


def family_evidence(r, family_id: str, discipline: str | None = None) -> FamilyEvidence:
    """Describe one family's recorded evidence for the mark and the page. Reads only the
    backend's reader packet and overview record; decides nothing."""
    fam = r.overview_family(family_id)
    doc = r.family(family_id)
    history = doc.get("paper_history") or []
    by_source = {rd["source"]: rd for rd in doc.get("readings") or []}
    readings = []
    for src in reader_order(set(by_source))[:2]:
        rd = by_source.get(src)
        credit = (rd or {}).get("credit") or {}
        state = (rd or {}).get("state")
        if rd is not None and state not in TONE:
            raise SystemExit(f"family {family_id}: {src} reading has state {state!r}, which "
                             "scripts/evidence.py does not know; add it to TONE and copy_evidence.json")
        readings.append(Reading(source=src, name=credit.get("name") or src, url=credit.get("url"),
                                state=state, tone=TONE[state] if rd is not None else "none",
                                term=(rd or {}).get("source_term")))
    lean = tuple(LeanMark(id=l["id"], name=l.get("name") or l["id"][2:], main_result=l.get("main_result"),
                          accepted=tuple(l.get("accepted_current_sources") or ()),
                          holes=len(l["definition_holes"]) if isinstance(l.get("definition_holes"), list) else None)
                 for l in doc.get("lean") or [])
    kinds = []
    for card in doc.get("independent_check_cards") or []:
        if card.get("field") and card["field"] not in kinds:
            kinds.append(card["field"])
    cmp = doc.get("reader_comparison") or {}
    sel = doc.get("selection") or {}
    comm = doc.get("community") or {}
    return FamilyEvidence(
        id=doc["id"], num=doc["id"][2:], name=doc.get("name") or fam.get("name") or doc["id"],
        discipline=discipline,
        papers=sum(1 for p in history if p.get("status") == "current"),
        editions=sum(1 for p in history if p.get("status") == "previous-edition"),
        withdrawn=sum(1 for p in history if p.get("status") == "withdrawn"),
        lean=lean, readers=tuple(readings),
        agreement=cmp.get("headline_coverage") or cmp.get("state") or "unknown",
        claim=(doc.get("claim") or {}).get("state") or "unresolved",
        pairing=sel.get("pairing_state") or "unavailable",
        scope_context=sel.get("scope_context"),
        checks=tuple(kinds),
        findings=len(doc.get("findings") or []),
        community_findings=len(comm.get("findings") or []),
        contributions=len(doc.get("contributions") or []),
        comparison=cmp.get("state") or "unavailable",
        community=tuple(sorted(Counter(f.get("kind") for f in comm.get("findings") or [] if f.get("kind")).items())),
    )


@lru_cache(maxsize=None)
def _discipline_of(r) -> dict:
    out = {}
    for d in r.universe.get("disciplines") or []:
        for fid in d.get("family_ids") or []:
            out[fid] = d["id"]
    return out


_ALL: dict = {}


def all_families(r) -> list[FamilyEvidence]:
    """Every family's evidence, in the release's source order (cached per reader)."""
    key = id(r)
    if key not in _ALL:
        disc = _discipline_of(r)
        _ALL[key] = [family_evidence(r, fid, disc.get(fid)) for fid in r.family_ids()]
    return _ALL[key]


def legend_counts(families) -> dict:
    """How many families each mark class covers, for a legend that is also a filter.
    These are counts of what the map draws, made from the same records."""
    out = {"families": len(families), "nolean": 0, "lean": 0, "ring": 0, "disagree": 0,
           "thread_candidate": 0, "thread_cited": 0}
    for t in TONES:
        out["left_" + t] = out["right_" + t] = 0
    for ev in families:
        if not ev.has_lean:
            out["nolean"] += 1
        else:
            out["lean"] += 1
            out["left_" + ev.readers[0].tone] += 1
            out["right_" + ev.readers[1].tone] += 1
            if ev.agreement == "disagree":
                out["disagree"] += 1
            if ev.pairing == "candidate-pairing":
                out["thread_candidate"] += 1
            elif ev.pairing in ("producer-cited-association", "producer-declared-binding"):
                out["thread_cited"] += 1
        if ev.checks:
            out["ring"] += 1
        if ev.community_count("explanation"):
            out["explained_by_others"] = out.get("explained_by_others", 0) + 1
        if ev.community_count("error-reported") or ev.community_count("correction"):
            out["problems_reported"] = out.get("problems_reported", 0) + 1
    return out
