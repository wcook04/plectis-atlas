"""Will Cook's websites: the header's ladder, film slots and the footer's sister sites.

The Atlas is one of several websites by Will Cook that share three things, rendered
here from site/family.json (DESIGN.md, "Will Cook's other websites"):

  the ladder        "Will Cook / Plectis Atlas" at the start of every header;
  a film slot       the Atlas walkthrough's still, play mark and running time, its
                    title the one link, opening YouTube in a new tab;
  the sister sites  every website by name in the footer, this one marked current.

site/family.json is an unchanged copy of sites.json in Will's home-page repository
(wcook04/wcook04.github.io), site/assets/websites/family.css an unchanged copy of its
assets/family/family.css, and site/assets/films/ holds the stills this site shows; that
repository's docs/family.md is the markup contract, and film_slot() follows its
scripts/build_hub.py. No page requests anything from another host: the still is served
from this site and YouTube opens only when a reader follows the link. To show a newer
edition of the film, copy the new sites.json here with its two stills and rebuild.
Standard library only.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE_ID = "atlas"
YOUTUBE = re.compile(r"https://www\.youtube\.com/watch\?v=[\w-]{11}")
WORDS = json.loads((SITE / "copy.json").read_text(encoding="utf-8"))["websites"]


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def problems(reg: dict, site_root: Path = SITE) -> list[str]:
    """What this site's pages rely on, said once, so a bad copy of the registry fails the build."""
    cfg = json.loads((site_root / "config.json").read_text(encoding="utf-8"))
    out = []
    if reg.get("schema") != "will_cook_site_family_v1":
        out.append(f"unknown schema {reg.get('schema')!r}")
    owner = reg.get("owner") or {}
    if owner.get("home") != cfg.get("author_url"):
        out.append(f"owner.home {owner.get('home')!r} differs from config.json author_url {cfg.get('author_url')!r}")
    if owner.get("name") != cfg.get("author"):
        out.append(f"owner.name {owner.get('name')!r} differs from config.json author {cfg.get('author')!r}")
    sites = [s for s in reg.get("sites", []) if s.get("id") == SITE_ID]
    if len(sites) != 1:
        return out + [f"exactly one site must have the id {SITE_ID!r}"]
    if sites[0].get("url") != cfg.get("base_url"):
        out.append(f"the {SITE_ID} site's url differs from config.json base_url")
    films = {f.get("id"): f for f in reg.get("films", [])}
    if not sites[0].get("films") or sites[0]["films"][0] not in films:
        return out + [f"the {SITE_ID} site names no film the registry holds"]
    film = films[sites[0]["films"][0]]
    if film.get("youtube"):
        if not YOUTUBE.fullmatch(film["youtube"]):
            out.append(f"{film['id']}: youtube must be https://www.youtube.com/watch?v=<id>")
        if not isinstance(film.get("duration_seconds"), int) or film["duration_seconds"] <= 0:
            out.append(f"{film['id']}: a released film needs its running time in seconds")
        for width in (640, 1280):
            if not film.get("still") or not (site_root / f"{film['still']}-{width}.webp").is_file():
                out.append(f"{film['id']}: copy its still to site/{film.get('still')}-{width}.webp")
    return out


def load(site_root: Path = SITE) -> dict:
    reg = json.loads((site_root / "family.json").read_text(encoding="utf-8"))
    found = problems(reg, site_root)
    if found:
        raise SystemExit("site/family.json:\n  " + "\n  ".join(found))
    return reg


REG = load()


def this_site() -> dict:
    return next(s for s in REG["sites"] if s["id"] == SITE_ID)


def film() -> dict:
    """The Atlas's own film: the first its registry entry names."""
    first = this_site()["films"][0]
    return next(f for f in REG["films"] if f["id"] == first)


def clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def spoken(seconds: int) -> str:
    minutes, rest = divmod(seconds, 60)
    parts = [f"{minutes} minute{'s' if minutes != 1 else ''}"] if minutes else []
    if rest:
        parts.append(f"{rest} second{'s' if rest != 1 else ''}")
    return " ".join(parts)


def film_slot(f: dict, *, root: str = "", size: str = "", sizes: str = "100vw", text: str | None = None) -> str:
    """The family's film slot (docs/family.md): a still that opens YouTube, or a held frame
    while the film is in preparation. root is the page's way back to the site root; text,
    when given, is the caption's sentence under the title (plain text)."""
    classes = "film-slot" + (f" film-slot--{size}" if size else "")
    title = esc(f["title"])
    para = f'<p class="film-slot__text">{esc(text)}</p>' if text else ""
    if f.get("youtube"):
        link, still, seconds = esc(f["youtube"]), esc(root + f["still"]), f["duration_seconds"]
        return (f'<figure class="{classes}">'
                f'<a class="film-slot__frame" href="{link}" target="_blank" rel="noopener noreferrer" aria-hidden="true" tabindex="-1">'
                f'<img src="{still}-640.webp" srcset="{still}-640.webp 640w, {still}-1280.webp 1280w" sizes="{esc(sizes)}" '
                f'alt="" width="1280" height="720" loading="lazy" decoding="async">'
                f'<span class="film-slot__play"></span><span class="film-slot__time">{clock(seconds)}</span></a>'
                f'<figcaption class="film-slot__caption">'
                f'<p class="film-slot__title"><a href="{link}" target="_blank" rel="noopener noreferrer">{title}'
                f'<span class="sr-only">{esc(WORDS["film_youtube"].format(duration=spoken(seconds)))}</span></a></p>'
                f'{para}</figcaption></figure>')
    return (f'<figure class="{classes} film-slot--pending">'
            f'<div class="film-slot__frame film-slot__frame--pending" aria-hidden="true">'
            f'<span class="film-slot__series">{esc(this_site()["name"])}</span>'
            f'<span class="film-slot__name">{esc(f["short"])}</span>'
            f'<span class="film-slot__status">{esc(WORDS["film_pending"])}</span></div>'
            f'<figcaption class="film-slot__caption">'
            f'<p class="film-slot__title">{title}</p>'
            f'<p class="film-slot__meta">{esc(WORDS["film_pending_meta"])}</p>'
            f'{para}</figcaption></figure>')


def ladder(wordmark: str) -> str:
    """The header's way up: "Will Cook / <wordmark>", the first rung his home page."""
    owner = REG["owner"]
    return (f'<span class="fam-ladder"><a class="fam-ladder__up" href="{esc(owner["home"])}" rel="author">{esc(owner["name"])}</a>'
            f'<span class="fam-ladder__sep" aria-hidden="true">/</span>{wordmark}</span>')


def sister_sites() -> str:
    """Every website in the registry's order, this one marked current, then the home page."""
    current = ' aria-current="page"'
    items = "".join(f'<li><a href="{esc(s["url"])}"{current if s["id"] == SITE_ID else ""}>{esc(s["short"])}</a></li>'
                    for s in REG["sites"])
    return (f'<nav class="fam-sites" aria-label="{esc(WORDS["sites_label"])}">'
            f'<p class="fam-sites__title">{esc(WORDS["sites_title"])}</p>'
            f'<ul class="fam-sites__list">{items}<li><a href="{esc(REG["owner"]["home"])}">{esc(WORDS["sites_all"])}</a></li></ul></nav>')
