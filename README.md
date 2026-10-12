# Plectis Atlas

An independent reading and inspection layer for [OpenAI's mathematics release](https://github.com/openai/math). The atlas brings papers, Lean challenge statements, citations and attributed outside findings together by result family: a group of related manuscripts and formal statements in OpenAI's catalogue. It helps you find a claim, inspect its formal scope, and see who checked what.

**[Open the atlas](https://wcook04.github.io/plectis-atlas/)**, a map of the whole release that opens into each family, its papers and its Lean statements. You can also go straight to [every family as a list](https://wcook04.github.io/plectis-atlas/explain.html), [the numbers and how each is counted](https://wcook04.github.io/plectis-atlas/numbers.html), or [how to contribute](CONTRIBUTING.md).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/map-dark.png">
  <img alt="The atlas's front page: every family of OpenAI's mathematics release drawn as one map by discipline, with a search, a key and four ways in" src="docs/map-light.png">
</picture>

The atlas is independent of OpenAI. It reads the public collection at a pinned commit. The counts below are generated from the backend's recorded counts and the atlas's rendering metadata, with their units and limits kept visible.

## What this adds

The release's papers, formal statements and outside assessments are spread across files and projects. The atlas gives them a shared reading interface: a map and searchable family list, full paper reading pages, formal statements, citation links and source-attributed findings. It includes families without Lean and keeps disagreements visible.

A reader can use those records to check a particular statement, explain one argument or correct a source link. The contribution workflow is available; the existence of a page does not mean its mathematics has been explained or reviewed. Paper-to-Lean candidates, AI scope drafts, reported proof replays and human reviews retain their separate labels and limits.

This repository builds the **website**. **Statement Map** is the separate backend that joins the evidence and exports the reader records. A checked-in export lets you rebuild the site without running the backend:

```text
Pinned research sources + outside reports + contribution records
                              |
                        Statement Map
                              |
                  backend/  (pinned export)
                              |
                    Atlas reader + builders  <--- paper sources + site assets
                              |
                  site/_build/  (static website)
```

The builders check record identity and rendering; they do not run Lean or Comparator. [Architecture and folder guide](docs/ARCHITECTURE.md) describes each source, generated output and build step.

## The release in numbers

<!-- numbers:start -->
- **372 result families** in 17 disciplines, from **719 current manuscripts** (3 more were withdrawn and 27 earlier editions remain in the collection).
- **416 Comparator challenge files**, 189 of them named in OpenAI's list of main results (200 declarations). 242 families have a Lean scope note linking at least one challenge file, and those notes name 339 current manuscripts as accompanying papers.
- **10 challenge files** import only Mathlib and add no local vocabulary. The median file adds 13 local vocabulary declarations (definitions, structures, instances, notation and similar), and the largest (EditApproximation) adds 1,212. Each one is part of what the statement means, so a reader checks it against the paper.
- **386 manuscripts** cite other manuscripts in the collection (586 citation links in the current extraction; the Atlas baseline inventory counts 579). 217 of them cite at least one manuscript without associated Lean.
- **16,077 resolved references** to work outside the collection, which group automatically into 11,019 works (by DOI, then arXiv identifier, then title; the grouping is unaudited).
- The TeX sources of the current manuscripts contain 2,255 theorem, 4,745 proposition, 1,267 corollary and 12,397 lemma environments, repeated statements included.
- **Draft scope reading.** Of 416 challenge files, an AI agent drafted 307 as stating a paper's headline theorem, 21 part of one, 28 a consequence, 24 a weaker form and 35 a supporting result; for 1 OpenAI's note leaves it unclear. The agent classified each file from OpenAI's scope note, quoting the note; no person has reviewed it.
- **Outside readers.** [MathVet](https://math.vet) and Carlos Toledo's [cert-machine](https://github.com/carlostoledo1891/cert-machine) each read every family's Lean against its headline, independently of OpenAI and of each other. Their findings, in their own terms, are on each family page and in the Families list.
- **Every paper in the browser.** 683 of the 719 current manuscripts have a full reading page made from their TeX, with every formula, cross-reference, citation and theorem anchor checked (figures are shown as placeholders); the other 36 have a reading page with a banner listing what did not convert. Formulas are checked with the KaTeX version the site loads. The PDF stays the reference (`data/paper_acceptance.json`).

Counted by Statement Map from [openai/math at `fd4aeeb2ee4f`](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb), generation `c2164a5394dc`. The unit, rule, state and credit behind each number, and its members, are on the site's Numbers page.
<!-- numbers:end -->

## One result, side by side

<!-- example:start -->
**Family 159: Erdős’s reciprocal-sum conjecture and quasipolynomial Szemerédi bounds.** The paper, [*Quasipolynomial Bounds for Arithmetic Progressions*](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026/paper.pdf), states:

> **Theorem** (label `ap:main`). For each fixed integer $k\ge3$ there are constants
> $C_k,c_k,\varepsilon_k>0$ such that, for every $N\ge2$,
> $$
>  r_k(N)\le C_kN\exp(-c_k(\log N)^{\varepsilon_k}).
> $$
> Equivalently, there is $A_k\ge1$ such that an $\alpha$-dense subset
> of $[N]$ contains a nonconstant $k$-term progression whenever
> $$
>  \log N\ge A_k(2+\log(1/\alpha))^{A_k},
>  \qquad 0<\alpha\le1.
> $$
>
> **Corollary** (label `ap:reciprocal`). Every set $A\subseteq\mathbb N$ with $\sum_{a\in A}a^{-1}=\infty$ contains nonconstant arithmetic progressions of every finite length.

The Lean statement [`ErdosReciprocal`](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/ComparatorChallenges/ErdosReciprocal.lean), the fixed statement Comparator checks OpenAI's proof against when it is run (3 local vocabulary declarations; allowed axioms `propext`, `Quot.sound`, `Classical.choice`; no definition holes):

```lean
def HasAP (A : Set ℕ) (k : ℕ) : Prop :=
  ∃ a d : ℕ, 0 < d ∧ ∀ i < k, a + i * d ∈ A
noncomputable def reciprocalTerm (A : Set ℕ) (n : ℕ) : ℝ := by
  classical
  exact if n ∈ A then (n : ℝ)⁻¹ else 0
def ReciprocalProgressionTheorem : Prop :=
  ∀ A : Set ℕ, ¬ Summable (reciprocalTerm A) → ∀ k : ℕ, HasAP A k
theorem manuscriptReciprocalProgressionTheorem : ReciprocalProgressionTheorem := by
  sorry
```

This challenge file leaves the proof as `sorry` by design. OpenAI's proof lives in the solution module `OAI.Combinatorics.Progressions.Main`, and if Comparator accepts a run, the proof establishes exactly the statement above using only the allowed axioms. MathVet and Neal McBurnett report re-running Comparator on it and accepting the proof.

OpenAI's scope note for this family:

> Erdős's reciprocal-sum conjecture asks whether every set of positive integers with divergent reciprocal sum contains arithmetic progressions of every finite length. The formalization proves this statement: for every requested length, such a set contains a progression with positive common difference. The selected theorem is the reciprocal-sum consequence. The paper's quantitative upper bound for the largest progression-free subset of $\{1,\ldots,N\}$ is outside this statement.
<!-- example:end -->

## Contribute

Start with one useful note on a passage you are reading: its location, your correction or question, and what you checked. Use the [note issue form](https://github.com/wcook04/plectis-atlas/issues/new?template=report-a-problem.yml) without installing anything. Accepted contributions are credited beside the work they improve. A first note can fit a fifteen-minute visit; review and publication follow afterwards.

| If you have | Do this | Guide |
|---|---|---|
| Time to read the relevant sources and compare the mathematics | Check one Lean challenge against its precisely located paper statements | [`check-a-statement`](skills/check-a-statement/SKILL.md) |
| A definition, example, lemma or argument you understand | Explain that part for a named reader | [`explain-a-result`](skills/explain-a-result/SKILL.md) |
| Knowledge of a field's literature | Record the earliest source you can find for an idea in a manuscript | [`trace-a-credit`](skills/trace-a-credit/SKILL.md) |
| A large Linux machine | Replay a Comparator check and publish the receipt | [`replay-a-proof`](skills/replay-a-proof/SKILL.md) |
| A sharp eye | Report a mismatch, an error or a broken link | [`report-a-problem`](skills/report-a-problem/SKILL.md) |
| Python or web development experience | Improve a parser, reader page, test or guide | [`improve-the-atlas`](skills/improve-the-atlas/SKILL.md) |

**Bring your own agent.** The repository ships agent skills in [`skills/`](skills/), mirrored for Claude Code in `.claude/skills/` and for Codex and other agents in `.agents/skills/`, with instructions in [`AGENTS.md`](AGENTS.md). Open the repository in Claude Code, Codex or Cursor and ask it to begin with `start-here`. Agents may draft and check; every contribution names the person who stands behind it and says how AI was used. The full guide is [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Build it yourself

Python 3.10 or newer and Git build the core site. Node is also needed to check formulas in the paper reading pages, using the vendored KaTeX version served by the site. Run this sequence to rebuild from the checked-in data and backend export:

```sh
git clone https://github.com/wcook04/plectis-atlas
cd plectis-atlas
python3 scripts/reader.py               # validates the pinned backend packets
sh scripts/fetch_upstream.sh            # sparse checkout of openai/math at the pinned commit, without PDFs
python3 scripts/build_site.py           # writes site/_build/
python3 scripts/build_papers.py         # writes each paper's full reading page into site/_build/papers/
python3 scripts/build_universe.py       # writes the map, site/_build/index.html, and its data
python3 scripts/check_paper_links.py site/_build
python3 -m http.server -d site/_build   # then open http://localhost:8000
```

`build_site.py` clears its output directory, so keep the order above. Without Node, the paper renderer marks pages partial and links to the reference PDF. Paper rendering also refreshes generated metadata in `data/`; if that metadata changes, follow the [metadata refresh sequence](docs/ARCHITECTURE.md#refreshing-paper-metadata) before treating the whole site as a consistent rebuild. Playwright and Chromium are optional, used only for share-card images.

`scripts/reader.py` checks exported file hashes, the release pin and generation before a page uses a packet. `scripts/backend.py` is its compatibility import. Source extraction and upstream updates are separate from rebuilding the site; see [the source and refresh boundaries](docs/ARCHITECTURE.md#refreshing-inputs).

The dataset in `data/` is plain JSON for your own analysis:

- `families.json`: result families, their discipline, OpenAI's description, manuscripts and Lean statements;
- `manuscripts.json`: abstracts, theorem-like statements with source file and line (those in the introduction flagged as candidate headline statements), and references with where each is cited;
- `statements.json`: every Comparator statement file, its imports and the definitions it introduces;
- `graph.json`: citations between manuscripts inside the collection;
- `works.json`: the outside works the collection cites;
- `review_queue.json`: every challenge file in order of where a careful reading is most useful, with the reasons, by a rule stated in `summary.json`;
- `statement_numbers.json`: what each extracted statement prints on its reading page ("Theorem 1.1"), bound to its source file, line and hash;
- `lean_xref.json`: each Lean declaration's counterpart in OpenAI's library and Mathlib at the pinned commits;
- `summary.json`: baseline extraction counts and definitions; current reader counts and their member records come from `backend/` and appear on the [Numbers page](https://wcook04.github.io/plectis-atlas/numbers.html).

## For producers of formal mathematics

If you release Lean alongside papers, [`ALIGNMENT.md`](ALIGNMENT.md) proposes four optional keys for the `alignment` block of `formalization.yaml` that link each printed claim to the Lean declaration stating it, and describes how checked work comes back to you.

## Sources, related work and motivation

| Project | Its work and the atlas's use of it |
| --- | --- |
| [OpenAI mathematics release](https://github.com/openai/math) | The papers, catalogue, scope notes, formal statements and release history being read. The atlas preserves the source pin and links back to it. |
| [MathVet](https://github.com/mathvet/mathvet), Carlos Toledo's [cert-machine](https://github.com/carlostoledo1891/cert-machine), and Neal McBurnett's [Lean tooling](https://github.com/nealmcb/openai-math-lean-tooling) | Outside statement readings and reported checks. Their findings remain attributed, with their scope and disagreements. |
| [Comparator](https://github.com/leanprover/comparator) | The challenge/solution checking tool used in reported proof replays. Building this website does not run it. |
| [formalization.yaml](https://github.com/mathlib-initiative/formalization.yaml) | The metadata standard on which the optional alignment proposal builds. |
| Patrick Massot's [leanblueprint](https://github.com/PatrickMassot/leanblueprint) | Related authoring infrastructure for navigating informal mathematics alongside Lean. Atlas instead assembles a reading view from a released collection and outside records. |
| [Cited by AGI](https://citedbyagi.com/) | Related work tracing bibliographic citations in the release. Atlas's reference records support reading and attribution; a citation count does not establish intellectual priority. |

The atlas's contribution is the combined reading interface and traceable integration of these sources. The source catalogue, statement comparisons and proof tools already exist; credit for them stays with their authors. [NOTICE](NOTICE) records imported material and licences. This is a selected collection with explicit provenance, not an exhaustive synthesis of online mathematics or a claim of priority over comparable projects.

Henry Cohn's [essay on mathematical technical debt](https://terrytao.wordpress.com/2026/09/15/the-technical-debt-of-ai-generated-mathematics/) motivates explanations that readers can reconstruct and use. Thomas Hales's [account of Lean's reliability](https://terrytao.wordpress.com/2026/10/09/what-mathematicians-should-know-about-the-lean-theorem-proverquestions-of-reliability-and-ai/) motivates keeping proof checking separate from the question of what a formal statement means. [Responsible Release of AI-Generated Mathematics](https://agmai.org/general-sep29/) calls for attribution, clear exposition and support for human understanding. These motivate the design; they are not endorsements or completed reviews of this atlas. The [About page](https://wcook04.github.io/plectis-atlas/about.html) gives the wider reading behind it.

## Licences and independence

The atlas is not affiliated with or endorsed by OpenAI. Material quoted from openai/math is copyright OpenAI under the Apache License 2.0 and is reproduced from the commit recorded in `upstream.json`, with links to source. Code, data and documentation in this repository are Apache-2.0; contributed explanations are CC BY 4.0. See [`NOTICE`](NOTICE).

## Author

Made by [Will Cook](https://wcook04.github.io/plectis/). The approach generalises the paper–Lean records and explanation workflow developed for [Plectis's research on eight Erdős problems](https://wcook04.github.io/plectis/maths/). The atlas applies that approach to a wider release; it does not claim authorship of the results it indexes. To cite it, use [`CITATION.cff`](CITATION.cff).
