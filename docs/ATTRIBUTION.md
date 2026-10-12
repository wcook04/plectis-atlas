# Sources, credit and citation

Plectis Atlas assembles a reading interface from other people's mathematics,
source code and assessments. Credit belongs beside the material being used.
A citation to the Atlas does not replace a citation to a paper, a proof tool
or an outside report.

## Cite the work you rely on

- **A mathematical claim:** cite the original paper and its exact theorem,
  version and location. The Atlas's paper page is a route to that source.
- **A formal statement or proof check:** identify the challenge or declaration,
  source commit, configuration and the group reporting the run. Cite the
  group's record, rather than describing the Atlas as having run Comparator.
- **An outside reading or correction:** cite its author and original report.
  Preserve whether it is a draft, a reported result, a disagreement or an
  independently reviewed contribution.
- **The Atlas itself:** use [`CITATION.cff`](../CITATION.cff), include the Atlas
  revision or access date, and give the page URL. For a source-dependent claim,
  also record the OpenAI pin in [`upstream.json`](../upstream.json) and, where
  relevant, the backend generation in [`backend/EXPORT.json`](../backend/EXPORT.json).

The machine-readable references in `CITATION.cff` name direct source projects,
components and an implemented algorithm. The complete source-record catalogues
remain in the locations below; an Atlas citation does not transfer their
results or authorship to Will Cook.

## Where the attribution lives

| Material | Record and point of use |
|---|---|
| OpenAI papers, catalogue, Lean files and scope notes | [`upstream.json`](../upstream.json), source locators in `data/`, and pinned source links on paper, family and Lean pages |
| MathVet, cert-machine, Neal McBurnett's tooling and Ben Knill's HOL cards | [`curated/sources/`](../curated/sources/) records credit, snapshot, licence, method and imported fields; family and Lean pages retain report attribution |
| Erdős problem links and the public tier list | Their records in `curated/sources/` describe what was captured; no general reuse licence is asserted |
| Other public reports and discussions | [`curated/community.json`](../curated/community.json) records each effort, its contributors, URL and reuse description, and associates findings with a family or statement |
| Statement Map's generated evidence export | [`backend/EXPORT.json`](../backend/EXPORT.json) records its version and hashes; [`backend/NOTICE.md`](../backend/NOTICE.md) retains its original notice |
| Fonts and KaTeX | [`LICENSES/manifest.json`](../LICENSES/manifest.json) lists all distributed files, hashes, component versions, credits, source links and modifications; full licence texts are beside it |
| Contributed explanations, checks and credits | Each contribution records authors, assistance, sources and review state under the [contribution rules](../CONTRIBUTING.md) |
| Motivation and related work | The README and website's About page link the essays beside the claims they inform; a motivating essay is not an endorsement of the Atlas |

The [Sources page](https://wcook04.github.io/plectis-atlas/sources.html) collects
the records and component credits. [`NOTICE`](../NOTICE) explains the licence
boundaries. Original Atlas code and documentation are Apache-2.0; imported
material retains its own terms. A generated JSON file can contain material
from several sources and is not a blanket relicensing of those sources.

## Algorithms, design and tools

The `squarify()` routine in [`build_site.py`](../scripts/build_site.py) implements
Mark Bruls, Kees Huizing and Jarke J. van Wijk's *Squarified Treemaps* (2000),
[DOI 10.1007/978-3-7091-6783-0_4](https://doi.org/10.1007/978-3-7091-6783-0_4).
It is used by the older treemap and generic share-card renderer, not the current
disc map. The authors' [paper](https://vanwijk.win.tue.nl/stm.pdf) describes the
row-selection method. The Atlas does not claim to have invented it.

The current map adapts Will Cook's earlier Plectis map code. Its source comments
record the originating revision and functions. The [README design notes](../DESIGN.md#the-repository-front-page)
credit Observable Plot, Datasette and Lean Blueprint as references for the
repository's presentation and navigation. They are references for design
choices, not bundled dependencies. Lean Blueprint is also related mathematical
authoring infrastructure; the Atlas does not run it.

Python and Git build the site; Node runs formula and search checks. Optional
Playwright/Chromium render share cards. These tools are not bundled in the
website. KaTeX and the font subsets are bundled and carry their licence copies.
KaTeX's JavaScript and CSS use MIT; its bundled fonts use OFL-1.1 and retain
Design Science and Khan Academy's notices. A package's root licence does not
necessarily cover every file it distributes; check embedded font metadata too.
Codex and Claude Code have assisted with repository implementation and editing;
that assistance is not mathematical authorship or an independent review.
Contribution-specific assistance is recorded on the contribution itself.

## Adding or correcting a source

Open the original source before recording its author, title, date, identifier
or quotation. Use a commit or archived version where available. Describe what
was used: copied text or code, transformed data, a reported assessment, an idea,
or a reference for comparison. Do not label an Atlas survey as the work of the
person whose pages it surveyed. Do not infer a licence from public visibility,
a repository badge, or a citation alone.

For reproduced material, retain the applicable notices and licence text, and
state the changes. For a cited source without a stated licence, link it and
keep the captured material and reuse description precise. Avoid turning a
source's claim into the Atlas's own finding. New mathematical-priority claims
need the [trace-a-credit](../skills/trace-a-credit/SKILL.md) process; a reference
list alone cannot establish priority.

Update the source owner, then regenerate its consumers. In particular, an
attribution correction in `curated/community.json` must reach a fresh Statement
Map capture and accepted export before backend-driven pages can show it.
Never patch a hash-bound backend packet in place.

Run `python3 scripts/attribution.py` after a source or asset change, and
`python3 scripts/attribution.py --built site/_build` after building the website.
The check detects unlisted assets, changed component bytes, missing source
metadata and missing distributed notices. It does not establish permission,
validate every scholarly citation, or certify mathematical priority. Review
those questions against the original source.
