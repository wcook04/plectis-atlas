# Architecture and repository guide

Plectis Atlas is a static website and a set of Python build tools. It consumes
a pinned export from **Statement Map**, the separate backend that joins source
records, contributions and reported evidence. No database or application server
is required. The [README](../README.md) is the first reading and build route.

## Where responsibilities live

```text
upstream.json                 exact OpenAI source commit
backend/                      imported Statement Map reader packets and receipts
curated/                      attributed outside records and draft scope readings
contributions/                authored notes, checks, explanations and templates
data/                         generated source indexes and rendering metadata
scripts/                      ingestion, rendering, validation and regression tests
site/                         authored copy, settings, styles, scripts and assets
site/_build/                  generated HTML and assets; ignored by Git
skills/                       canonical task instructions for agents
.agents/skills/                generated skill copies for Codex and other agents
.claude/skills/                generated skill copies for Claude Code
docs/                         repository explanation and README images
.github/                      contribution forms, checks and publishing workflows
```

The folders distinguish authored material, imported material and generated
output. Tests remain beside the scripts they exercise; their `test_` names make
them discoverable. `DESIGN.md` owns the website's reader experience, `STYLE.md`
owns explanations, and `CONTRIBUTING.md` owns submission and review. Runtime
code does not depend on the agent skills.

| Change | Owner |
| --- | --- |
| An exported reader record, paper–Lean candidate, evidence state or number's membership | Statement Map, followed by an accepted export through [`vendor_backend.py`](../scripts/vendor_backend.py). |
| Captured outside findings or draft scope readings | [`curated/`](../curated/README.md) and [`scripts/ingest/`](../scripts/ingest/); changes to consumed evidence also need a matching backend capture and export. |
| Export integrity and packet access | [`reader.py`](../scripts/reader.py), which validates hashes, schema, release, pin and generation. [`backend.py`](../scripts/backend.py) is a compatibility import. |
| Source extraction into the baseline JSON indexes | [`build_data.py`](../scripts/build_data.py); this does not rebuild Statement Map's export. |
| Family reading layout | [`family_page.py`](../scripts/family_page.py), orchestrated by [`build_site.py`](../scripts/build_site.py). |
| Other site pages, copy and settings | [`build_site.py`](../scripts/build_site.py), `copy*.json` and `config.json` in [`site/`](../site/), and [`site/assets/`](../site/assets/). |
| TeX reading pages and their acceptance metadata | [`build_papers.py`](../scripts/build_papers.py). |
| The release map and front page | [`build_universe.py`](../scripts/build_universe.py), run after the site build. |
| Lean source rendering and cross-references | [`lean_render.py`](../scripts/lean_render.py) and [`build_lean_xref.py`](../scripts/build_lean_xref.py). |
| Contribution formats and validation | [`contributions/README.md`](../contributions/README.md) and [`check_contributions.py`](../scripts/check_contributions.py). |
| Generated README sections and skill copies | [`sync_readme.py`](../scripts/sync_readme.py) and [`sync_skills.py`](../scripts/sync_skills.py). |

Statement Map owns the reader's evidence decisions. Atlas displays those
records and their limits; a page renderer must not silently substitute its own
judgement or rebuild a count from a different population. The separate
`data/` indexes support source browsing and rendering. They are not permission
to override the evidence packets.

## Source and output boundaries

`backend/EXPORT.json` records the Statement Map commit, acceptance receipt,
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

Follow [the README's ordered commands](../README.md#build-it-yourself) to use
the checked-in inputs. `build_site.py` removes its output directory before
writing it. `build_papers.py` then adds the paper pages, and `build_universe.py`
replaces the front page with the map. `check_paper_links.py` checks links between
the built statement and paper pages.

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
git diff --check
```

For a reader, parser or contribution change, run its focused regression and
the relevant checks in [the CI workflow](../.github/workflows/check.yml).
It covers packet reading, search, extraction, paper conversion, contribution
validation, community records, generated entry surfaces and a site build.
For rendered page changes, also inspect the relevant pages and run
`scripts/test_family_page.py` when family layouts change. The
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
