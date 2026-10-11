"""The family mark: one small, exact drawing of a family's recorded evidence.

The same drawing appears wherever a family does: on the map's plate, in lists,
on the family page, in search results. Every stroke encodes a recorded state
from scripts/evidence.py; nothing is decoration.

    papers   short lines on the left, one per current paper (at most four drawn)
    ring     a brick ring around those lines when an outside group has checked the
             paper's result by another method (HOL Light cards, exact computation)
    thread   a steel line from the papers to the diamond when a paper theorem is
             paired with the Lean: dashed for a candidate pairing found by shared
             words, solid when the Lean source cites the theorem or the release
             declares the link
    diamond  present when the release has a Lean statement for the family, with a
             second outline behind it when it has more than one. Each half is one
             outside reader's finding (left and right in copy_evidence.json order):
             filled for all of the headline, pale for part of it or a narrower or
             weaker statement, open for a supporting or different result, dotted
             when that reader has not read the family

Colours come from CSS classes in site/assets/evidence.css, so the mark follows
the page's light or dark scheme. Every mark carries a text alternative.
"""
from __future__ import annotations

from html import escape as _esc

from evidence import FamilyEvidence, say

# Geometry, in viewBox units. The mark is 44 wide and 28 high.
W, H = 44, 28
CY = 14
PX0, PX1 = 3.5, 13.0          # the paper lines
DX, DR = 30.5, 8.6             # the diamond's centre and half-diagonal
RING_C, RING_R = 8.25, 9.4     # the brick ring around the papers


def _f(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s if s != "-0" else "0"


def _poly(points) -> str:
    return " ".join(f"{_f(x)},{_f(y)}" for x, y in points)


def specimen_parts(ev: FamilyEvidence) -> str:
    """The mark's drawing, without the outer <svg> (for embedding in larger figures)."""
    out = []
    k = min(ev.papers, 4) or 1
    gap = 4.4 if k > 1 else 0
    y0 = CY - gap * (k - 1) / 2
    if ev.checks:
        out.append(f'<circle class="sp-ring" cx="{_f(RING_C)}" cy="{CY}" r="{_f(RING_R)}"/>')
    for i in range(k):
        y = y0 + i * gap
        out.append(f'<line class="sp-paper" x1="{_f(PX0)}" y1="{_f(y)}" x2="{_f(PX1)}" y2="{_f(y)}"/>')
    if ev.has_lean:
        left, top, right, bottom = (DX - DR, CY), (DX, CY - DR), (DX + DR, CY), (DX, CY + DR)
        if ev.pairing in ("candidate-pairing", "producer-cited-association", "producer-declared-binding"):
            dash = " sp-thread--candidate" if ev.pairing == "candidate-pairing" else ""
            x_start = (RING_C + RING_R + 0.6) if ev.checks else PX1 + 1.4
            out.append(f'<line class="sp-thread{dash}" x1="{_f(x_start)}" y1="{CY}" x2="{_f(left[0] - 0.4)}" y2="{CY}"/>')
        if len(ev.lean) > 1:
            off = 2.2
            out.append(f'<polygon class="sp-back" points="{_poly([(x + off, y - off) for x, y in (left, top, right, bottom)])}"/>')
        tl, tr = (ev.tones + ("none", "none"))[:2]
        out.append(f'<polygon class="sp-half sp-half--{tl}" points="{_poly([left, top, bottom])}"/>')
        out.append(f'<polygon class="sp-half sp-half--{tr}" points="{_poly([top, right, bottom])}"/>')
        dia = "sp-dia" + (" sp-dia--none" if "none" in (tl, tr) else "")
        out.append(f'<polygon class="{dia}" points="{_poly([left, top, right, bottom])}"/>')
        out.append(f'<line class="sp-split" x1="{_f(DX)}" y1="{_f(top[1] + 0.9)}" x2="{_f(DX)}" y2="{_f(bottom[1] - 0.9)}"/>')
    return "".join(out)


def specimen(ev: FamilyEvidence, size: float = 44, *, label: str | None = None, cls: str = "",
             decorative: bool = False) -> str:
    """The family mark as inline SVG, `size` CSS pixels wide.

    The text alternative defaults to ev.sentence(). Pass decorative=True only where
    the same sentence is already written beside the mark."""
    h = size * H / W
    classes = "sp" + (f" {cls}" if cls else "") + f" sp--{ev.key}"
    if decorative:
        a11y = 'aria-hidden="true" focusable="false"'
    else:
        a11y = f'role="img" aria-label="{_esc(label or ev.sentence())}"'
    return (f'<svg class="{classes}" viewBox="0 0 {W} {H}" width="{_f(size)}" height="{_f(h)}" {a11y}>'
            f'{specimen_parts(ev)}</svg>')


def tone_swatch(tone: str, side: str = "both", size: float = 18) -> str:
    """A small diamond showing one tone, for legends and reader headings.
    side: "left", "right" or "both"."""
    s = size
    c, r = s / 2, s / 2 - 1.2
    left, top, right, bottom = (c - r, c), (c, c - r), (c + r, c), (c, c + r)
    parts = []
    if side in ("left", "both"):
        parts.append(f'<polygon class="sp-half sp-half--{tone}" points="{_poly([left, top, bottom])}"/>')
    if side in ("right", "both"):
        parts.append(f'<polygon class="sp-half sp-half--{tone}" points="{_poly([top, right, bottom])}"/>')
    parts.append(f'<polygon class="sp-dia" points="{_poly([left, top, right, bottom])}"/>')
    if side != "both":
        parts.append(f'<line class="sp-split" x1="{_f(c)}" y1="{_f(c - r + 0.9)}" x2="{_f(c)}" y2="{_f(c + r - 0.9)}"/>')
    return (f'<svg class="sp sp-swatch" viewBox="0 0 {_f(s)} {_f(s)}" width="{_f(s)}" height="{_f(s)}" '
            f'aria-hidden="true" focusable="false">{"".join(parts)}</svg>')


def thread_swatch(kind: str = "candidate", width: float = 28) -> str:
    """A short thread for legends: kind "candidate" (dashed) or "cited" (solid)."""
    dash = " sp-thread--candidate" if kind == "candidate" else ""
    return (f'<svg class="sp sp-swatch" viewBox="0 0 {_f(width)} 10" width="{_f(width)}" height="10" '
            f'aria-hidden="true" focusable="false"><line class="sp-thread{dash}" x1="1" y1="5" '
            f'x2="{_f(width - 1)}" y2="5"/></svg>')


def legend_items(left_name: str, right_name: str) -> list[tuple[str, str]]:
    """(swatch svg, words) for every element of the mark, in reading order."""
    return [
        ('<svg class="sp sp-swatch" viewBox="0 0 16 12" width="16" height="12" aria-hidden="true" focusable="false">'
         '<line class="sp-paper" x1="2" y1="3" x2="14" y2="3"/><line class="sp-paper" x1="2" y1="7.4" x2="14" y2="7.4"/>'
         '</svg>', say("legend.papers")),
        (tone_swatch("full"), say("legend.diamond")),
        (tone_swatch("full", "left"), say("legend.halves", left=left_name, right=right_name)),
        (tone_swatch("full"), say("legend.full")),
        (tone_swatch("part"), say("legend.part")),
        (tone_swatch("other"), say("legend.other")),
        (thread_swatch("candidate"), say("legend.thread_candidate")),
        (thread_swatch("cited"), say("legend.thread_cited")),
        ('<svg class="sp sp-swatch" viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">'
         '<circle class="sp-ring" cx="10" cy="10" r="8"/><line class="sp-paper" x1="5" y1="8" x2="15" y2="8"/>'
         '<line class="sp-paper" x1="5" y1="12" x2="15" y2="12"/></svg>', say("legend.ring")),
    ]
