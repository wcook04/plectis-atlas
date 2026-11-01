"""Checks for the parts the Atlas shares with Will Cook's other websites (scripts/websites.py,
from site/family.json; DESIGN.md "Will Cook's other websites"): every header starts with the
lockup (the Plectis plait to his home page, served from this site, then the Atlas's tiles
and name) and has no other way off the Atlas; every footer lists the sister
sites in the list's order with the Atlas marked current; the map's panel and the help page
show the Atlas film as the family's film slot, its title the one link and its still served
from this site; every page links the shared stylesheet; and a copy of the list that no longer
fits the Atlas stops the build. Standard library only:
python3 scripts/tests/test_websites.py
"""
from __future__ import annotations

import copy
import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_site as S  # noqa: E402
import build_universe as U  # noqa: E402
import websites as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class Tags(HTMLParser):
    """Start tags with their attributes, and the text of the whole fragment."""

    def __init__(self, text: str):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.text: list[str] = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def links(fragment: str) -> list[dict]:
    return [a for t, a in Tags(fragment).tags if t == "a"]


class Registry(unittest.TestCase):
    def test_the_list_names_this_site_and_its_film(self):
        self.assertEqual(W.problems(W.REG), [])
        self.assertEqual(W.this_site()["url"], S.CFG["base_url"])
        self.assertEqual(W.REG["owner"]["home"], S.CFG["author_url"])
        f = W.film()
        for width in (640, 1280):
            self.assertTrue((ROOT / "site" / f"{f['still']}-{width}.webp").is_file(), width)

    def test_a_copy_that_no_longer_fits_stops_the_build(self):
        broken = copy.deepcopy(W.REG)
        film = next(x for x in broken["films"] if x["id"] == W.this_site()["films"][0])
        film["still"] = "assets/films/missing"
        film["duration_seconds"] = None
        broken["owner"]["home"] = "https://example.org/"
        found = " ".join(W.problems(broken))
        self.assertIn("missing-640.webp", found)
        self.assertIn("running time", found)
        self.assertIn("author_url", found)
        gone = copy.deepcopy(W.REG)
        gone["sites"] = [s for s in gone["sites"] if s["id"] != W.SITE_ID]
        self.assertTrue(W.problems(gone))

    def test_running_time_in_figures_and_words(self):
        self.assertEqual((W.clock(327), W.spoken(327)), ("5:27", "5 minutes 27 seconds"))
        self.assertEqual((W.clock(60), W.spoken(60)), ("1:00", "1 minute"))
        self.assertEqual(W.spoken(1801), "30 minutes 1 second")


class Header(unittest.TestCase):
    def test_header_starts_with_the_lockup_and_has_one_way_off_the_atlas(self):
        home = W.REG["owner"]["home"]
        for rel in ("index.html", "families/017.html", "explanations/017/x/index.html"):
            root = "../" * rel.count("/")
            h = S.header(rel, None)
            top = h[h.index('<header class="top">'):h.index("</header>")]
            a = links(top)
            self.assertEqual(a[0], {"class": "fam-lockup__home", "href": home, "rel": "author",
                                    "title": "All of Will Cook's projects and videos"}, rel)
            self.assertEqual((a[1]["class"], a[1]["href"]), ("fam-lockup__site", f"{root}index.html"), rel)
            lockup = top[top.index('<span class="fam-lockup">'):top.index('<nav class="nav"')].rstrip()
            img = [x for t, x in Tags(lockup).tags if t == "img"]
            self.assertEqual(img, [{"src": f"{root}assets/websites/plectis.svg", "alt": "Will Cook: all projects and videos",
                                    "width": "26", "height": "26"}], rel)
            self.assertRegex(lockup, r'</a><span class="fam-lockup__rule" aria-hidden="true"></span><a class="fam-lockup__site"')
            self.assertRegex(lockup, r'<svg class="mark"[^>]*aria-hidden="true".*<span class="fam-lockup__name" translate="no">Plectis Atlas</span></a></span>$')
            off_site = [x["href"] for x in a if x["href"].startswith("http")]
            self.assertEqual(off_site, [home], rel)

    def test_the_plait_is_served_from_the_atlas(self):
        svg = (ROOT / "site/assets/websites/plectis.svg").read_text(encoding="utf-8")
        self.assertTrue(svg.lstrip().startswith("<svg"))
        self.assertNotRegex(svg, r'(href|src)\s*=\s*"(https?:)?//')
        self.assertNotIn("@import", svg)
        self.assertNotIn("url(http", svg)

    def test_every_page_links_the_shared_stylesheet_after_the_atlas_one(self):
        for rel in ("index.html", "families/159.html", "papers/x.html"):
            head = S.head(rel, "Title", "Description")
            sheets = [a["href"] for t, a in Tags(head).tags if t == "link" and a.get("rel") == "stylesheet"]
            root = "../" * rel.count("/")
            names = [s.split("?")[0] for s in sheets]
            self.assertIn(f"{root}assets/websites/family.css", names)
            self.assertLess(names.index(f"{root}assets/atlas.css"), names.index(f"{root}assets/websites/family.css"))
        css = (ROOT / "site/assets/websites/family.css").read_text(encoding="utf-8")
        for cls in (".fam-lockup", ".fam-lockup__home", ".fam-lockup__rule", ".film-slot__frame", ".film-slot__play", ".film-slot__time", ".fam-sites__list"):
            self.assertIn(cls, css)
        atlas = (ROOT / "site/assets/atlas.css").read_text(encoding="utf-8")
        for name in ("page", "surface", "ink", "ink-soft", "muted", "faint", "rule", "rule-strong", "accent", "serif", "sans", "mark-warm", "mark-cool"):
            self.assertRegex(atlas, rf"--fam-{name}: var\(--")
        self.assertIn(".sr-only", atlas)


class Footer(unittest.TestCase):
    def test_footer_lists_every_sister_site_with_the_atlas_current(self):
        f = S.footer("families/017.html")
        nav = f[f.index('<nav class="fam-sites"'):]
        nav = nav[:nav.index("</nav>")]
        self.assertIn('aria-label="Will Cook&#x27;s websites"', nav)
        got = [(x["href"], x.get("aria-current")) for x in links(nav)]
        want = [(s["url"], "page" if s["id"] == W.SITE_ID else None) for s in W.REG["sites"]]
        self.assertEqual(got, want + [(W.REG["owner"]["home"], None)])
        family_line = re.search(r'<p class="foot__family">(.*?)</p>', f, re.S).group(1)
        self.assertEqual([x["href"] for x in links(family_line)], [S.CFG["author_url"]])
        self.assertNotIn('href="https://wcook04.github.io/practical-formal-verification/"', f)


class FilmSlot(unittest.TestCase):
    def check_released(self, fragment: str, root: str, size: str):
        f = W.film()
        tags = Tags(fragment).tags
        self.assertNotIn("iframe", [t for t, _ in tags])
        fig = [a for t, a in tags if t == "figure"]
        self.assertEqual(fig, [{"class": f"film-slot film-slot--{size}"}])
        frame, title = links(fragment)
        self.assertEqual(frame, {"class": "film-slot__frame", "href": f["youtube"], "target": "_blank",
                                 "rel": "noopener noreferrer", "aria-hidden": "true", "tabindex": "-1"})
        self.assertEqual(title, {"href": f["youtube"], "target": "_blank", "rel": "noopener noreferrer"})
        img = next(a for t, a in tags if t == "img")
        self.assertEqual(img["src"], f"{root}{f['still']}-640.webp")
        self.assertEqual(img["srcset"], f"{root}{f['still']}-640.webp 640w, {root}{f['still']}-1280.webp 1280w")
        self.assertEqual((img["alt"], img["width"], img["height"]), ("", "1280", "720"))
        for t, a in tags:
            for attr in ("src", "srcset"):
                self.assertFalse(a.get(attr, "").startswith(("http:", "https:", "//")), (t, a))
        self.assertIn(f'<span class="film-slot__time">{W.clock(f["duration_seconds"])}</span>', fragment)
        self.assertIn(f'{S.esc(f["title"])}<span class="sr-only">, video on YouTube, {W.spoken(f["duration_seconds"])}</span></a></p>',
                      fragment)

    def test_map_panel_offers_the_small_slot_and_hides_it_with_the_ground_text(self):
        U.import_site()
        h = U.film_html()
        self.assertTrue(h.startswith('<div class="u-film" data-u-ground>'))
        self.check_released(h, "", "inline")
        self.assertIn(f'<p class="film-slot__text">{S.esc(U.U("page.film.text"))}</p>', h)
        self.assertNotIn("youtube.com", (ROOT / "site/copy_universe.json").read_text(encoding="utf-8"))

    def test_help_page_shows_the_slot_after_its_opening(self):
        S.OUT = Path(tempfile.mkdtemp(prefix="atlas-websites-"))
        S.build_help()
        h = (S.OUT / "help.html").read_text(encoding="utf-8")
        head = h[h.index('<header class="phead phead--film">'):]
        head = head[:head.index("</header>")]
        self.check_released(head[head.index("<figure"):], "", "inline")
        self.assertLess(head.index('class="phead__facts"'), head.index("<figure"))
        self.assertNotIn("film-slot", S.help_dialog(""))

    def test_a_film_in_preparation_holds_its_place_without_a_link(self):
        pending = dict(W.film(), youtube=None, duration_seconds=None, still=None)
        h = W.film_slot(pending, size="small")
        self.assertEqual(links(h), [])
        self.assertIn('class="film-slot film-slot--small film-slot--pending"', h)
        self.assertIn('<p class="film-slot__meta">Video in preparation</p>', h)


if __name__ == "__main__":
    unittest.main()
