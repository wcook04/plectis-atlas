# Website source

This folder holds the page copy, settings, styles and browser code for
[Plectis Atlas](https://wcook04.github.io/plectis-atlas/). Python builders in
[`scripts/`](../scripts/README.md) combine them with the checked data to produce
the static website in `_build/`.

The [published website is agent-navigable](https://wcook04.github.io/plectis-atlas/agents.md).
`build_universe.py` generates `llms.txt` and `agents.md` beside the map from the
configured site URL and current packet generation. They document the existing
map JSON, which remains available without running the browser interface.

Read the [design contract](../DESIGN.md) and the
[first-time-reader writing rule](../STYLE.md#write-the-website-for-a-first-time-reader)
before changing a page. Explain what was compared, verified or rendered, by
whom, and what the reported result establishes.
[Quick preview](../docs/ARCHITECTURE.md#quick-preview-without-paper-sources)
gives the local build commands.

## Find the page you want to change

| Page or feature | Copy | Styles and browser behaviour | Python renderer |
|---|---|---|---|
| Map and front page | [copy_universe.json](copy_universe.json) | [universe.css](assets/universe.css), [universe.js](assets/universe.js) | [build_universe.py](../scripts/build_universe.py) |
| Agent entry and map traversal | `build_agent_navigation()` in [build_universe.py](../scripts/build_universe.py) | Static text; no browser code | [build_universe.py](../scripts/build_universe.py) |
| Family pages | [copy_family.json](copy_family.json) | [family.css](assets/family.css), [family.js](assets/family.js) | [family_page.py](../scripts/family_page.py) |
| Lean pages | [copy_lean.json](copy_lean.json) | [lean.css](assets/lean.css), [lean.js](assets/lean.js) | [build_site.py](../scripts/build_site.py), [lean_render.py](../scripts/lean_render.py) |
| Full paper reading pages | `TXT` in [build_papers.py](../scripts/build_papers.py), plus shared [copy.json](copy.json) | [paper.css](assets/paper.css), [paper.js](assets/paper.js) | [build_papers.py](../scripts/build_papers.py) |
| Shared navigation, search and other pages | [copy.json](copy.json), [copy_evidence.json](copy_evidence.json) | [atlas.css](assets/atlas.css), [atlas.js](assets/atlas.js), [inspect.css](assets/inspect.css), [inspect.js](assets/inspect.js) | [build_site.py](../scripts/build_site.py) |

[config.json](config.json) holds site URLs, the upstream checkout location,
issue-form settings and the KaTeX version. Local fonts and KaTeX are in
[`assets/fonts/`](assets/fonts/) and [`assets/vendor/`](assets/vendor/).

[copy_evidence.json](copy_evidence.json) supplies evidence wording across the
map, family and Lean pages through [`evidence.py`](../scripts/evidence.py).
The paper reader's `TXT` dictionary holds its conversion banners, figure
placeholders and reader-specific notes.

## Keep source and output separate

Edit the source files above. `_build/` is generated, ignored by Git and
replaced by the site builder. The [complete build sequence](../docs/ARCHITECTURE.md#rebuilding-the-website)
adds the full paper pages and then the map.

Evidence records, paper-to-Lean candidates and counts come from Statement
Map's export through [`reader.py`](../scripts/reader.py). A presentation change
must preserve their meaning and attribution. To change an evidence record,
follow the [source ownership guide](../docs/ARCHITECTURE.md#where-responsibilities-live).

After a page change, inspect it in both colour schemes at laptop and phone
widths, including keyboard use and any affected interactions. The design
contract defines the visual checks; the [scripts guide](../scripts/README.md#check-a-change)
points to the relevant regressions.

[All documentation](../docs/README.md) · [Repository introduction](../README.md)
