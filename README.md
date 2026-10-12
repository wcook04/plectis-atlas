# Plectis Atlas

An independent reading room for [OpenAI’s mathematics release](https://github.com/openai/math). Explore the papers by subject, compare their claims with the linked Lean statements, and see what outside readers have checked.

**[Explore the website ↗](https://wcook04.github.io/plectis-atlas/)** &nbsp; [Browse families](https://wcook04.github.io/plectis-atlas/explain.html) &nbsp; [Contribute](CONTRIBUTING.md) &nbsp; [Developer guide](docs/ARCHITECTURE.md)

<a href="https://wcook04.github.io/plectis-atlas/">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/map-dark.png">
    <img src="docs/map-light.png" width="1440" height="790" alt="Open Plectis Atlas: a map of result families arranged by mathematical discipline, coloured by outside readers’ assessments of their Lean coverage.">
  </picture>
</a>

*Explore the release by discipline, then open a family to read its papers and evidence.*

## What this adds

OpenAI groups related papers into **result families**. The atlas brings each family’s papers, formal statements, references and attributed outside findings into one reading interface. It includes families without Lean and keeps disagreements visible. You can read the website without installing anything.

| Start with | What you can do |
|---|---|
| [The map](https://wcook04.github.io/plectis-atlas/) | Explore by discipline, search for a theorem, or follow connections between families. |
| [A result family](https://wcook04.github.io/plectis-atlas/families/159.html) | Read a paper’s claim beside its linked Lean statement, then follow the sources. |
| [The Lean catalogue](https://wcook04.github.io/plectis-atlas/statements.html) | Inspect a challenge file, its definitions and the checks reported for it. |
| [Sources and outside readings](https://wcook04.github.io/plectis-atlas/sources.html) | See who checked what, with credit and links to their own records. |

## The release in numbers

<!-- overview:start -->
| In the pinned release | Explore |
|---|---|
| **372 result families** across 17 disciplines | [Browse by subject](https://wcook04.github.io/plectis-atlas/explain.html) |
| **719 current manuscripts** | [Read the papers through their families](https://wcook04.github.io/plectis-atlas/explain.html) |
| **416 Lean challenge files** | [Inspect the formal statements](https://wcook04.github.io/plectis-atlas/statements.html) |
| **16,077 resolved references** to work outside the collection | [Follow the citations](https://wcook04.github.io/plectis-atlas/references-outside.html) |
<!-- overview:end -->

These describe the collection at the commit in [`upstream.json`](upstream.json). [How each number is counted](https://wcook04.github.io/plectis-atlas/numbers.html) gives the definitions and the records behind them.

<details>
<summary>Full counts, coverage and reading-page checks</summary>

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

</details>

## One result, side by side

[Open the reciprocal-sum family](https://wcook04.github.io/plectis-atlas/families/159.html) to see how a paper, its formal statement and outside readings fit together. The comparison is also available below, with the source links and Lean text.

<details>
<summary>Read the paper’s statement, the Lean challenge and OpenAI’s scope note</summary>

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

</details>

The atlas keeps separate what a paper claims, what its Lean statement says, and what a recorded check establishes. Outside re-runs are attributed to the people who report them. Automatically proposed pairings and AI draft classifications are labelled; they still need review. The paper’s PDF remains the reference for its browser reading page.

## Contribute

Choose a passage you are reading. Give its location, your correction or question, and what you checked. You can [open a note](https://github.com/wcook04/plectis-atlas/issues/new?template=report-a-problem.yml) without installing anything. Accepted contributions are credited beside the work they improve.

For a larger contribution, [explain a result](skills/explain-a-result/SKILL.md), [compare a statement](skills/check-a-statement/SKILL.md), [trace an earlier source](skills/trace-a-credit/SKILL.md), or [replay a proof check](skills/replay-a-proof/SKILL.md). The [contributor guide](CONTRIBUTING.md) covers formats, credit and review. An available contribution route does not mean a family already has a reviewed explanation.

**Working with an agent?** Open this repository in Codex, Claude Code or Cursor and ask it to start with [`start-here`](skills/start-here/SKILL.md). The [agent instructions](AGENTS.md) route each task to its skill. Agents can help draft and check; a named person stands behind each contribution and discloses how AI was used.

## Build it yourself

This repository builds the **website**. **Statement Map** is the separate backend that joins the evidence and exports its reader records. The checked-in export lets you rebuild the site without running the backend. The site builders validate records and rendering; they do not run Lean or Comparator.

The [developer guide](docs/ARCHITECTURE.md#rebuilding-the-website) has the complete build sequence, a quick preview and validation commands. Python builds a static site; Node checks paper formulas with the included KaTeX.

| Looking for | Start here |
|---|---|
| Data for your own analysis | [`data/`](data/) and the [dataset guide](docs/ARCHITECTURE.md#use-the-data) |
| Site code, build order and source ownership | [Architecture and repository guide](docs/ARCHITECTURE.md) |
| Editorial and visual conventions | [Writing guide](STYLE.md) and [design contract](DESIGN.md) |
| Agent task instructions | [Canonical skills](skills/) |

## For producers of formal mathematics

If you release Lean alongside papers, [the alignment proposal](ALIGNMENT.md) links printed claims to the Lean declarations stating them using optional keys in `formalization.yaml`. It also describes how checked work comes back to you.

## Sources, related work and motivation

The atlas brings together [OpenAI’s release](https://github.com/openai/math), [MathVet](https://math.vet), Carlos Toledo’s [cert-machine](https://github.com/carlostoledo1891/cert-machine) and Neal McBurnett’s [Lean tooling](https://github.com/nealmcb/openai-math-lean-tooling). Credit stays with each source, beside the finding it supports. The [Sources page](https://wcook04.github.io/plectis-atlas/sources.html) lets you follow those records.

<details>
<summary>Related projects and the writing behind the design</summary>

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


</details>

## Licences and independence

Plectis Atlas is independent of OpenAI and is not affiliated with or endorsed by it. Quoted release material is copyright OpenAI, reproduced under Apache-2.0 from the pinned source. Atlas code, data and documentation are Apache-2.0; contributed explanations are CC BY 4.0. See [the licence](LICENSE) and [attribution notice](NOTICE).

## Author

Made by [Will Cook](https://wcook04.github.io/plectis/). The approach generalises the paper–Lean records and explanation workflow developed for [Plectis's research on eight Erdős problems](https://wcook04.github.io/plectis/maths/). The atlas applies that approach to a wider release; it does not claim authorship of the results it indexes. To cite it, use [`CITATION.cff`](CITATION.cff).
