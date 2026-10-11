# Plectis Atlas

OpenAI's mathematics release, read and checked. The atlas sets out every paper of [openai/math](https://github.com/openai/math) by result family, puts each main theorem beside the Lean statement that formalises it, and records what outside groups have checked, each credited where it appears. Every paper has a reading page, and every family is open for a human explanation, credited by name.

**[Open the atlas](https://wcook04.github.io/plectis-atlas/)**, a map of the whole release that opens into each family, its papers and its Lean statements. You can also go straight to [every family as a list](https://wcook04.github.io/plectis-atlas/explain.html), [the numbers and how each is counted](https://wcook04.github.io/plectis-atlas/numbers.html), or [how to contribute](CONTRIBUTING.md).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/map-dark.png">
  <img alt="The atlas's front page: every family of OpenAI's mathematics release drawn as one map by discipline, with a search, a key and four ways in" src="docs/map-light.png">
</picture>

The atlas is independent of OpenAI. It is built from the public collection at a pinned commit, and every number on this page is computed by a script in this repository.

## The release in numbers

<!-- numbers:start -->
- **372 result families** in 17 disciplines, from **719 current manuscripts** (3 more were withdrawn and 27 earlier editions remain in the collection).
- **416 Comparator challenge files**, 189 of them named in OpenAI's list of main results (200 declarations). 242 families have a Lean scope note linking at least one challenge file, and those notes name 339 current manuscripts as accompanying papers.
- **10 challenge files** import only Mathlib and add no local vocabulary. The median file adds 13 local vocabulary declarations (definitions, structures, instances, notation and similar), and the largest (EditApproximation) adds 1,212. Each one is part of what the statement means, so a reader checks it against the paper.
- **381 manuscripts** cite other manuscripts in the collection (579 citation links). 214 of them cite at least one manuscript with no accompanying Lean statement.
- **16,077 resolved references** to work outside the collection, which group automatically into 11,019 works (by DOI, then arXiv identifier, then title; the grouping is unaudited).
- The TeX sources of the current manuscripts contain 2,255 theorem, 4,745 proposition, 1,267 corollary and 12,397 lemma environments, repeated statements included.
- **Draft scope reading.** Of 416 challenge files, 307 state a paper's headline theorem as stated, 21 part of one, 28 a consequence, 24 a weaker form and 35 a supporting result; for 1 the note leaves it unclear. In 14 families with Lean statements, no statement covers the headline result or part of it, and in 10 more only part of it is covered. An AI agent classified each file from OpenAI's scope note, quoting the note (`curated/scope_coverage.json`); no person has reviewed it.
- **Two independent readers.** [MathVet](https://math.vet) and Carlos Toledo's [cert-machine](https://github.com/carlostoledo1891/cert-machine), reading each family's Lean against its headline independently of OpenAI and of each other, agree that 127 families' Lean states the headline and 93 states less; they disagree on 22. Their verdicts sit on each family page, credited.
- **Every paper in the browser.** 683 of the 719 current manuscripts have a full reading page made from their TeX, with every formula, cross-reference, citation and theorem anchor checked (figures are shown as placeholders); the other 36 have a reading page with a banner listing what did not convert. Formulas are checked with the KaTeX version the site loads. The PDF stays the reference (`data/paper_acceptance.json`).

Counted from [openai/math at `fd4aeeb2ee4f`](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb) by `scripts/build_data.py`. The unit, universe and rule behind each number are in `data/summary.json` under `metric_receipts`.
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

Start with one useful note on a passage you are reading: its location, your correction or question, and what you checked. Use the note issue form without installing anything. Accepted contributions are credited beside the work they improve. A first note can fit a fifteen-minute visit; review and publication follow afterwards.

| If you have | Do this | Guide |
|---|---|---|
| Time to read the relevant sources and compare the mathematics | Check one Lean challenge against its precisely located paper statements | [`check-a-statement`](skills/check-a-statement/SKILL.md) |
| A definition, example, lemma or argument you understand | Explain that part for a named reader | [`explain-a-result`](skills/explain-a-result/SKILL.md) |
| Knowledge of a field's literature | Record the earliest source you can find for an idea in a manuscript | [`trace-a-credit`](skills/trace-a-credit/SKILL.md) |
| A large Linux machine | Replay a Comparator check and publish the receipt | [`replay-a-proof`](skills/replay-a-proof/SKILL.md) |
| A sharp eye | Report a mismatch, an error or a broken link | [`report-a-problem`](skills/report-a-problem/SKILL.md) |

**Bring your own agent.** The repository ships agent skills in [`skills/`](skills/), mirrored for Claude Code in `.claude/skills/` and for Codex and other agents in `.agents/skills/`, with instructions in [`AGENTS.md`](AGENTS.md). Open the repository in Claude Code, Codex or Cursor and ask it to begin with `start-here`. Agents may draft and check; every contribution names the person who stands behind it and says how AI was used. The full guide is [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Build it yourself

```sh
git clone https://github.com/wcook04/plectis-atlas
cd plectis-atlas
sh scripts/fetch_upstream.sh            # sparse checkout of openai/math at the pinned commit, without PDFs
python3 scripts/build_data.py           # writes data/*.json
python3 scripts/build_site.py           # writes site/_build/
python3 scripts/build_papers.py         # writes each paper's full reading page into site/_build/papers/
python3 scripts/build_universe.py       # writes the map, site/_build/index.html, and its data
python3 -m http.server -d site/_build   # then open http://localhost:8000
```

Each step writes into `site/_build/`, and `build_site.py` clears it first, so run them in this order. Python 3.10 or newer and git are the only requirements. With Node installed, the reading pages check every formula with the KaTeX build the site itself serves (`site/assets/vendor/`); without Node every page is marked partial and links the PDF.

`backend/` holds a pinned export of Statement Map, the backend that joins the release's statements, Lean challenges, outside readings and contributions into records with a receipt behind every count. The site takes its evidence counts and contribution targets from it, and `scripts/backend.py` checks every file's hash, the release pin and the generation before a page uses it.

The dataset in `data/` is plain JSON for your own analysis:

- `families.json`: the 372 families, their discipline, OpenAI's description, manuscripts and Lean statements;
- `manuscripts.json`: abstracts, theorem-like statements with source file and line (those in the introduction flagged as candidate headline statements), and references with where each is cited;
- `statements.json`: every Comparator statement file, its imports and the definitions it introduces;
- `graph.json`: citations between manuscripts inside the collection;
- `works.json`: the outside works the collection cites;
- `review_queue.json`: every challenge file in order of where a careful reading is most useful, with the reasons, by a rule stated in `summary.json`;
- `statement_numbers.json`: what each extracted statement prints on its reading page ("Theorem 1.1"), bound to its source file, line and hash;
- `lean_xref.json`: each Lean declaration's counterpart in OpenAI's library and Mathlib at the pinned commits;
- `summary.json`: every number above, with its unit, universe and rule.

## For producers of formal mathematics

If you release Lean alongside papers, [`ALIGNMENT.md`](ALIGNMENT.md) proposes four optional keys for the `alignment` block of `formalization.yaml` that link each printed claim to the Lean declaration stating it, and describes how checked work comes back to you.

## Licences and independence

The atlas is not affiliated with or endorsed by OpenAI. Material quoted from openai/math is copyright OpenAI under the Apache License 2.0 and is reproduced from the commit recorded in `upstream.json`, with links to source. Code, data and documentation in this repository are Apache-2.0; contributed explanations are CC BY 4.0. See [`NOTICE`](NOTICE).

## Author

Made by [Will Cook](https://wcook04.github.io/plectis/), who also maintains a Lean-checked research corpus on eight Erdős problems. To cite the atlas, use [`CITATION.cff`](CITATION.cff).
