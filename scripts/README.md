# Build tools and checks

Run these commands from the repository root. The core Python scripts need
Python 3.10 or newer and its standard library. Git fetches upstream sources;
Node checks formulas and search behaviour. Share-card rendering optionally
uses Playwright and Chromium.

For a first build, follow the [quick preview](../docs/ARCHITECTURE.md#quick-preview-without-paper-sources)
or [complete website build](../docs/ARCHITECTURE.md#rebuilding-the-website).
That guide owns the order of the commands and the paper-metadata refresh rule.
The [published site is agent-navigable](https://wcook04.github.io/plectis-atlas/agents.md)
through the same static map packets built here.

## Build and render

| Tool | Responsibility |
|---|---|
| [reader.py](reader.py) | Validates and reads the pinned Statement Map export. `python3 scripts/reader.py` checks its packets. |
| [build_site.py](build_site.py) | Builds family and Lean pages, lists, search and shared assets. Clears its output directory first. |
| [family_page.py](family_page.py) | Renders family pages for the site builder. |
| [build_papers.py](build_papers.py) | Converts the paper sources into full reading pages and writes their rendering metadata. |
| [build_universe.py](build_universe.py) | Builds the release map, its existing JSON exports and agent navigation (`llms.txt`, `agents.md`); replaces the front page after the site build. |
| [lean_render.py](lean_render.py) | Renders Lean source for the page builders. |
| [cards.py](cards.py) | Renders share images. |
| [sync_readme.py](sync_readme.py) | Refreshes the root README's computed blocks and the data folder's generated guide. |
| [attribution.py](attribution.py) | Checks distributed asset credits and source licence copies; includes notices in the website build. |
| [sync_skills.py](sync_skills.py) | Copies canonical `skills/` into the generated agent skill folders. |

`backend.py` is a compatibility import for the reader. New code should use
[`reader.py`](reader.py).

## Fetch and refresh inputs

| Tool | Responsibility |
|---|---|
| [fetch_upstream.sh](fetch_upstream.sh) | Fetches the OpenAI commit recorded in `upstream.json`. |
| [build_data.py](build_data.py) | Extracts baseline JSON indexes from the pinned sources. |
| [build_lean_claims.py](build_lean_claims.py), [build_lean_xref.py](build_lean_xref.py) | Extract Lean declaration records and cross-references. |
| [ingest/](ingest/) | Imports source-specific outside findings. |
| [vendor_backend.py](vendor_backend.py) | Imports an accepted Statement Map export and records its identity and hashes. |

An ordinary site build uses the included data and export. Changing the source
pin requires a matching backend export and refreshed dependent data; follow
[Refreshing inputs](../docs/ARCHITECTURE.md#refreshing-inputs).

## Check a change

Regression suites live in `tests/`; builders and shared modules remain above.
Run `python3 scripts/check_repository_structure.py` to check placement, and
`python3 scripts/tests/test_repository_structure.py` for its negative fixtures.
The checker uses Git candidates, including staged files and nonignored new files.

Choose the check for the code you changed. Each `test_*.py` runs directly with
Python from the repository root, for example:

```sh
python3 scripts/tests/test_family_page.py
```

| Change | Check |
|---|---|
| Packet reading, hashes or evidence records | [test_reader.py](tests/test_reader.py) |
| Search normalisation and result links | [test_search.py](tests/test_search.py), with Node installed |
| Agent entry, map relationships and project-path URLs | [test_agent_navigation.py](tests/test_agent_navigation.py); add `--built site/_build` after the complete build |
| Source extraction | [test_build_data.py](tests/test_build_data.py) |
| Paper rendering | [test_build_papers.py](tests/test_build_papers.py) |
| Family layouts and statement snippets | [test_family_page.py](tests/test_family_page.py) |
| Previous and next links between families, Lean statements and papers | [test_sibling_nav.py](tests/test_sibling_nav.py) |
| A contribution file or its validation | [check_contributions.py](check_contributions.py); see [Contributing](../CONTRIBUTING.md) |
| Links between built paper and Lean pages | [test_check_paper_links.py](tests/test_check_paper_links.py); [check_paper_links.py](check_paper_links.py), after the complete build |

For documentation and skill changes:

```sh
python3 scripts/attribution.py
python3 scripts/sync_readme.py --check
python3 scripts/sync_skills.py --check
git diff --check
```

Run `python3 scripts/sync_skills.py` first if you edited a canonical skill.
The [CI workflow](../.github/workflows/check.yml) lists the checks run for pull
requests; the [Pages workflow](../.github/workflows/pages.yml) owns the publication
build. None of these website checks runs a Lean proof or Comparator replay.

[All documentation](../docs/README.md) · [Repository introduction](../README.md)
