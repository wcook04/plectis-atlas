# Architecture and repository guide

Plectis Atlas is a static website and a set of Python build tools. It consumes
a pinned export from **Statement Map**, the separate backend that joins source
records, contributions and reported evidence. No database or application server
is required. The [README](../README.md) is the public reading route; this guide owns development and build instructions.

The [documentation index](README.md) lists the reader, contributor and developer
guides. For file-level navigation, use [site source](../site/README.md) or
[build tools and checks](../scripts/README.md).

## Where responsibilities live

```text
upstream.json                 exact OpenAI source commit
backend/                      imported Statement Map reader packets and receipts
curated/                      attributed outside records and draft scope readings
contributions/                authored notes, checks, explanations and templates
data/                         generated source indexes and rendering metadata
scripts/                      ingestion, rendering and validation
scripts/tests/                Python and JavaScript regression suites
docs/images/                  README screenshots
site/                         authored copy, settings, styles, scripts and assets
site/_build/                  generated HTML and assets; ignored by Git
skills/                       canonical task instructions for agents
.agents/skills/                generated skill copies for Codex and other agents
.claude/skills/                generated skill copies for Claude Code
docs/                         repository explanation and README images
.github/                      contribution forms, checks and publishing workflows
```

The folders separate authored material, imported evidence and generated output.
The website is built by scripts; it needs no application server or installable
Python package. Tests live in `scripts/tests/`, import their script owners explicitly and are listed in
the [scripts guide](../scripts/README.md#check-a-change).

The root keeps documents GitHub and contributors expect to find there:
the README, contribution instructions, licences, citation metadata and agent
entry files. The [documentation index](README.md) also links the writing,
design and alignment guides at their existing addresses. Directory READMEs
explain the folder you have opened; build order and source ownership remain
in this guide. Runtime code does not depend on the agent skills.

[`.gitattributes`](../.gitattributes) identifies the imported backend, fonts
and KaTeX as vendored material, and the data JSON and skill mirrors as
generated. GitHub can exclude these from language statistics and collapse
generated diffs. The source records remain tracked and available for review;
these attributes do not change the build or its validation rules.

| Change | Owner |
| --- | --- |
| An exported reader record, paper–Lean candidate, evidence state or number's membership | Statement Map, followed by an accepted export through [`vendor_backend.py`](../scripts/vendor_backend.py). |
| Captured outside findings or draft scope readings | [`curated/`](../curated/README.md) and [`scripts/ingest/`](../scripts/ingest/); changes to consumed evidence also need a matching backend capture and export. |
| Export integrity and packet access | [`reader.py`](../scripts/reader.py), which validates hashes, schema, release, pin and generation. [`backend.py`](../scripts/backend.py) is a compatibility import. |
| Source extraction into the baseline JSON indexes | [`build_data.py`](../scripts/build_data.py); this does not rebuild Statement Map's export. |
| Family reading layout | [`family_page.py`](../scripts/family_page.py), orchestrated by [`build_site.py`](../scripts/build_site.py). |
| Other site pages, copy and settings | [`build_site.py`](../scripts/build_site.py), `copy*.json` and `config.json` in [`site/`](../site/), and [`site/assets/`](../site/assets/). |
| The header's lockup, film slots and footer's sister sites shared with Will Cook's other websites | [`websites.py`](../scripts/websites.py), from `site/family.json`, `site/assets/websites/family.css` and `site/assets/websites/plectis.svg`, unchanged copies from Will's home-page repository. |
| TeX reading pages and their acceptance metadata | [`build_papers.py`](../scripts/build_papers.py). |
| The release map and front page | [`build_universe.py`](../scripts/build_universe.py), run after the site build. |
| Lean source rendering and cross-references | [`lean_render.py`](../scripts/lean_render.py) and [`build_lean_xref.py`](../scripts/build_lean_xref.py). |
| Contribution formats and validation | [`contributions/README.md`](../contributions/README.md) and [`check_contributions.py`](../scripts/check_contributions.py). |
| Generated root README sections, data-folder guide and skill copies | [`sync_readme.py`](../scripts/sync_readme.py) and [`sync_skills.py`](../scripts/sync_skills.py). |

Statement Map owns the reader's evidence decisions. Atlas displays those
records and their limits; a page renderer must not silently substitute its own
judgement or rebuild a count from a different population. The separate
`data/` indexes support source browsing and rendering. They are not permission
to override the evidence packets.

Pairing follows the same rule. Every page, filter, card and the map read one
decision per Lean statement, Statement Map's `Reader.pairing_decision`, through
`build_site.lean_pairing`, which adapts it for the renderers and never re-ranks it.
In order of precedence the backend records a citation in the Lean source or a
binding in the release's manifest; an attributed source reading, in which a named
reader (so far an AI agent) read both sources and recorded which configured
declaration states which paper statement, the relation and its limits; or a
candidate from the Lean text's own words. Otherwise nothing is paired and the
backend's reason is shown. A source reading is displayed as such, with its author,
each link's relation and limits and its explanation on request; it is never
described as a word match, a review or a proof check. Reader v9 (26 October 2026)
replaced the site's own word matcher after a source review of every case where
the two had disagreed. Each Lean statement's source roles (its challenge file,
OpenAI's solution declarations and the Comparator configuration) come from the
backend's `lean-preview` packets (`reader.lean_preview`), so a page links the
actual proof rather than the challenge's `sorry`. A linked statement that the
Atlas's own extraction does not hold (a lemma, for example) is rendered from the
backend's statement-detail packet (`build_site.backend_only_statement`).

`LICENSES/manifest.json` owns the distributed component inventory.
`scripts/attribution.py` checks its bytes and source-licence coverage, then copies
licence notices into each website build. See [attribution](ATTRIBUTION.md).

## Source and output boundaries

[`backend/EXPORT.json`](../backend/EXPORT.json) records the Statement Map commit, acceptance receipt,
source pin, generation and file hashes. Packet manifests bind each packet to
that export. `reader.py` rejects altered bytes or mixed generations before a
page consumes them. The backend's source repository is not required for an
ordinary site rebuild. Its imported `NOTICE.md` retains the original notices
and source-relative references; do not rewrite hash-bound imported files here.

`data/` is also generated and tracked. Important indexes include families,
manuscripts, statements, citations and outside works. Paper rendering adds
`paper_acceptance.json`, `statement_numbers.json` and `paper_labels.json`.
`site/_build/` is disposable build output. Never hand-edit any of these to
repair a source or presentation problem.

The core builders use Python's standard library. Git supplies pinned source
bytes. Node runs formula checks with the KaTeX copy in `site/assets/vendor/`;
no npm install is needed. Without Node or usable KaTeX, the renderer reports
unchecked formulas and partial reading pages. Playwright and Chromium are
optional dependencies for `scripts/cards.py`, which renders share images.
None of these steps runs a Lean proof or establishes paper/statement fidelity.

## Rebuilding the website

Python 3.10 or newer and Git build the core site. Node is also needed to check formulas in the paper reading pages, using the vendored KaTeX version served by the site. Run this sequence to rebuild from the checked-in data and backend export:

```sh
git clone https://github.com/wcook04/plectis-atlas
cd plectis-atlas
python3 scripts/reader.py               # validates the pinned backend packets
sh scripts/fetch_upstream.sh            # sparse checkout of openai/math at the pinned commit, without PDFs
python3 scripts/build_site.py           # writes site/_build/
python3 scripts/build_papers.py --jobs 2 # writes each paper's full reading page into site/_build/papers/
python3 scripts/build_universe.py       # writes the map, site/_build/index.html, and its data
python3 scripts/check_paper_links.py site/_build
python3 -m http.server -d site/_build   # then open http://localhost:8000
```

`build_site.py` clears its output directory, so keep the order above. Without Node, the paper renderer marks pages partial and links to the reference PDF. Paper rendering also refreshes generated metadata in `data/`; if that metadata changes, follow the [metadata refresh sequence](#refreshing-paper-metadata) before treating the whole site as a consistent rebuild. Playwright and Chromium are optional, used only for share-card images.

After changing a shared renderer such as `lean_snippet_html()`, also run `build_universe.py`: the map stores those rendered excerpts in its detail files, so regenerating individual statement or family pages leaves the map's excerpts stale.

`scripts/reader.py` checks exported file hashes, the release pin and generation before a page uses a packet. `scripts/backend.py` is its compatibility import. Source extraction and upstream updates are separate from rebuilding the site; see [the source and refresh boundaries](#refreshing-inputs).

### Quick preview without paper sources

For layout and copy work, the checked-in inputs can build the family pages,
Lean pages and map without fetching upstream:

```sh
python3 scripts/reader.py
python3 scripts/build_site.py
python3 scripts/build_universe.py
python3 -m http.server -d site/_build
```

Open <http://localhost:8000>. This omits the full TeX reading pages; use the
complete sequence above when checking paper links or preparing a release.

### Refreshing paper metadata

Paper rendering writes metadata in `data/` even when given another `--out`
directory. A change to the renderer, its inputs or the formula-check environment
can therefore change counts and labels consumed by the other builders. In that
case, use a first paper pass to refresh metadata, then rebuild all consumers:

```sh
python3 scripts/build_papers.py
python3 scripts/sync_readme.py
python3 scripts/build_site.py
python3 scripts/build_papers.py
python3 scripts/build_universe.py
python3 scripts/check_paper_links.py site/_build
```

Review the generated diff. The second paper pass restores the pages removed
by `build_site.py`. With unchanged inputs and environment, the metadata should
be stable between the two passes. Rendering acceptance concerns conversion;
the PDF remains the reference for the paper.

## Use the data

The [published website is agent-navigable](https://wcook04.github.io/plectis-atlas/agents.md).
`scripts/build_universe.py::build_agent_navigation` generates the static `llms.txt`
entry and `agents.md` traversal guide alongside the existing map packets. The guide
describes `data/universe-data.json` and `data/universe-parts.json`, including stable
IDs, generation checks, all index relationships, directed citations, evidence limits
and a runnable fetch example. It uses `site/config.json` for the complete project URL.
Shared HTML links to the guide with an ordinary footer link and `rel=help`; no new
script, preload, prefetch or dependency is introduced. The complete build and deploy
run `python3 scripts/tests/test_agent_navigation.py --built site/_build` to check
graph connectivity, source identity, generated routes and their local destinations.

The files in [`data/`](../data/) are plain JSON. Baseline extraction and later
rendering have different producers; neither replaces Statement Map's evidence
records or number memberships in [`backend/`](../backend/).

| Files | Contents and producer |
|---|---|
| `summary.json`, `disciplines.json`, `history.json` | Baseline counts and definitions, the catalogue's subject order, and dated release history. Produced by `build_data.py`; `build_lean_claims.py` adds its own summary block. |
| `families.json` | Family IDs, disciplines, titles, OpenAI's descriptions, manuscripts, statements and per-family `lean_doc` scope notes. Produced by `build_data.py`. |
| `manuscripts.json` | Manuscript IDs, status, title, date, abstract, PDF URL, extracted statements, references, `rests_on`, `cited_by_in_collection` and `has_lean`. Produced by `build_data.py`. |
| `statements.json` | Comparator challenge IDs, full Lean source, hashes, imports, vocabulary, Comparator settings, solution module and associated families and papers. Produced by `build_data.py`. |
| `graph.json`, `works.json` | Citations within the collection, and outside works with their records and citing manuscripts. Produced by `build_data.py`. |
| `review_queue.json` | Challenge files ordered by a reading-priority rule, with reasons. The rule is recorded in `summary.json`; produced by `build_data.py`. |
| `paper_acceptance.json`, `statement_numbers.json`, `paper_labels.json` | Reading-page conversion results, printed statement numbers and label targets. Produced by `build_papers.py`. |
| `lean_claims.json` | Lean library declarations and their source locations, extracted textually by `build_lean_claims.py`. This is not a Lean build or proof check. |
| `lean_xref.json` | Declaration references into OpenAI's library and Mathlib at pinned commits, produced by `build_lean_xref.py`. |

#### How to read the extracted fields

- **Paper statements** in `manuscripts[].statements` are theorem-like TeX
  environments after `\input` expansion: theorems, propositions, corollaries,
  conjectures, questions and hypotheses. Each has a source `file` and `line`,
  `label`, TeX `text` and a `sha256` of its whitespace-normalised text.
  `headline` marks non-appendix theorems, corollaries, conjectures and
  propositions before the second section or with “main” in their display name.
  If none qualify, it marks the first three non-appendix theorems instead.
  This is an extraction heuristic. Lemmas are counted in `lemma_count`.
- **References** are bibliography entries actually cited in the manuscript,
  from `.bib` files or `thebibliography`. Their `uses` identify the source
  file, line, section and, where present, the containing statement or proof.
  `rests_on` follows citations to manuscripts in the collection through later
  editions, retaining their status and `has_lean` flag.
- **Statement vocabulary** lists the definitions, abbreviations, structures,
  classes, inductive types, instances, notation, macros and axioms introduced
  by the challenge file. These are part of what its statement means.
- **Lean coverage** of a manuscript (`has_lean`) means OpenAI's family scope
  note lists it as an accompanying paper and links at least one challenge.
  It is a different measure from OpenAI's reported share of formalised
  top-line results, quoted separately in `summary.json`.
- **Printed statement numbers**, such as “Theorem 1.1”, come from the paper
  renderer and are bound to the extracted statement's file, line and hash.
  They describe the reading page; the PDF remains the reference.

Family IDs are source identifiers, not a consecutive sequence. Outside works
are grouped by DOI, then arXiv identifier, then normalised title; that grouping
is unaudited and can count a work twice. Candidate paper-to-Lean matches come
from the backend export and remain subject to review. Source extraction alone
does not establish that a formal statement matches a paper's claim.

Use the [Numbers page](https://wcook04.github.io/plectis-atlas/numbers.html)
for the reader's current counts, definitions and member records. Quoted source
text retains its original copyright and licence; see [NOTICE](../NOTICE).

The directory's short [`README.md`](../data/README.md) is generated by
`sync_readme.py` and points here. To change that introduction, edit its
`data_guide()` function and regenerate; maintain the detailed reference here.


## Refreshing inputs

An ordinary rebuild does not update the OpenAI pin. `build_data.py` re-extracts
the baseline indexes from that pin, but does not refresh every derived artifact
or the backend export. Use it when changing extraction, then run the affected
downstream generators and review their diffs.

Moving `upstream.json` is a coordinated source refresh: obtain a matching,
accepted Statement Map generation, vendor it with `scripts/vendor_backend.py`,
rebuild the affected data and rendering metadata, and recheck contributions
against their recorded versions. The vendor tool's `--help` describes its
source checkout, data directory and acceptance receipt arguments. A pin change
alone cannot produce a valid site; the reader intentionally rejects a backend
export from another pin. An older contribution does not acquire a new review
merely because a filename still exists.

## Checks by change

For documentation or skill edits:

```sh
python3 scripts/sync_skills.py          # only when canonical skills changed
python3 scripts/sync_skills.py --check
python3 scripts/sync_readme.py --check
python3 scripts/attribution.py
git diff --check
```

For a reader, parser or contribution change, run its focused regression and
the relevant checks in [the CI workflow](../.github/workflows/check.yml).
It covers packet reading, search, extraction, paper conversion, contribution
validation, community records, generated entry surfaces and a site build.
For rendered page changes, also inspect the relevant pages and run
`scripts/tests/test_family_page.py` when family layouts change. The
[Pages workflow](../.github/workflows/pages.yml) shows the full publication
build, including optional share cards.

## Keeping the README useful

Lead with what a reader can do and one reliable action. Keep the website and
backend roles explicit, explain any diagram in prose, and link a folder to its
responsibility. Distinguish software capabilities from contributed content and
reviewed mathematics. Credit existing projects beside the capability being
compared; describe an implemented combination without unsupported priority
claims. Keep changing counts inside the generated README blocks. These rules
also apply to the canonical [`improve-the-atlas` skill](../skills/improve-the-atlas/SKILL.md).


### README preview images

The README opens with `docs/images/overview-light.png` and
`docs/images/overview-dark.png`: real browser captures of the entire release
map, with its discipline regions, family dots, release summary and colour key.
Both link to the public Atlas front page. The paper reader now sits beside the
“What you can do” feature table.

The overview pair was captured on 15 October 2026 from a local build of main
commit `96d9f05d8f1a5cf4fefbc47879b4dfbc1278ccc6`, using the documented quick
preview commands above. The map reads Statement Map generation
`sha256:e44fe048bf34d4e55b76af0e42f931ce1121c5c189edf0e8cd6061a5902b3e47`.
The native owners are `scripts/build_universe.py`, `site/assets/universe.js`
and `site/assets/universe.css`, with the shared `atlas.css`, fonts and theme
control. No map, labels, data or interface elements were reconstructed.

To reproduce the overview, open the locally served front page with no selection
or URL fragment, at a 1440 × 980 CSS pixel viewport and device scale 1. Wait for
the native map and fonts to load, and move the pointer off the map. The overview
fits all disciplines automatically; it has no zoom or pan controls. Capture each
theme through the site's own switch, keeping the viewport and scroll position.
These are full viewport PNG captures with no crop or pixel editing. Inspect both
at full size and in the GitHub README at desktop and phone widths. At phone
width the image is a linked thumbnail; its caption and text routes remain the
reading path.

The paper reader pair, `reader-light.jpg` and `reader-dark.jpg`, shows
*Quasipolynomial Bounds for Arithmetic Progressions*. It was captured on
15 October 2026 from the public deployment of Atlas commit
`4ac8e9f09057cd0a1c311df02bca0520839ae616`, verified against
[the successful Pages build](https://github.com/wcook04/plectis-atlas/actions/runs/38424773534).
It uses the actual output of `scripts/build_papers.py`, `site/assets/paper.css`
and the shared typography, fonts and theme control, at a 1440 × 900 CSS pixel
viewport. The PDF remains the reference. The family page pair,
`family-light.png` and `family-dark.png`, shows family 003's first screen: the
catalogue's claim beside what each group found, above the tabs. It was captured
on 19 October 2026 from a local build of the redesign branch at a 1440 × 900 CSS
pixel viewport.

The old map pair (`map-light.png` and `map-dark.png`) remains historical imagery.
It was captured on 12 October 2026 from the local `reader-v2` build at `d32c790`,
with a 1440 × 790 CSS pixel viewport at device scale 1 and Family 017 under the
pointer. At capture time that revision was not the public deployment. Do not
recolour a screenshot to manufacture another theme.
