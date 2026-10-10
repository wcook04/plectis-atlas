# OpenAI Math Atlas

A reader's atlas to the mathematics OpenAI released on 6 October 2026 in [openai/math](https://github.com/openai/math). For each of the 372 result families it shows the paper's headline theorems beside the Lean statements that Comparator checks, what each manuscript cites inside the collection, and whose earlier work each argument uses. Every family is open for a human explanation, credited by name.

**[Open the atlas](https://wcook04.github.io/openai-math-atlas/)** · [Explain a result](https://wcook04.github.io/openai-math-atlas/explain.html) · [Check a statement](CONTRIBUTING.md) · [The numbers](https://wcook04.github.io/openai-math-atlas/numbers.html)

The atlas is independent of OpenAI. It is built from the public collection at a pinned commit, and every number on this page is computed by a script in this repository.

## The release in numbers

<!-- numbers:start -->
- **372 result families** in 17 disciplines, from **719 current manuscripts** (3 more were withdrawn and 27 earlier editions remain in the collection).
- **416 Lean statements** checked through Comparator challenge files, 189 of them main results. 339 manuscripts are accompanying papers of a family with at least one Lean statement.
- **10 Lean statements** are written in Mathlib's vocabulary alone. The median statement file introduces 13 definitions of its own, and the largest (EditApproximation) introduces 1,212. Comparator certifies a proof against exactly this file, so each definition is something a reader checks.
- **380 manuscripts** cite other manuscripts in the collection (578 citation links). 213 of them cite at least one manuscript with no accompanying Lean statement.
- **16,078 citations** of earlier work outside the collection, to 11,069 distinct works (matched by DOI, then arXiv identifier, then title).
- The TeX sources of the current manuscripts contain 2,255 theorems, 4,745 propositions, 1,267 corollaries and 12,397 lemmas.
- **What the Lean certifies.** Of 416 Lean statements, 307 certify a paper's headline theorem as stated, 21 part of one, 28 a consequence, 24 a weaker form and 35 a supporting result. In 14 families with Lean statements, none certifies the headline result. Classified by an AI agent from OpenAI's own Lean notes, quoting each note (`curated/scope_coverage.json`); no person has reviewed it yet.

Counted from [openai/math at `fd4aeeb2ee4f`](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb) by `scripts/build_data.py`. Exact definitions are in `data/summary.json`.
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

The Lean statement [`ErdosReciprocal`](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/ComparatorChallenges/ErdosReciprocal.lean) that Comparator checks against OpenAI's proof (3 definitions of its own; permitted axioms `propext`, `Quot.sound`, `Classical.choice`):

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

A Comparator challenge file leaves the proof as `sorry` by design. OpenAI's proof lives in the solution module `OAI.Combinatorics.Progressions.Main`, and Comparator accepts it only if it proves exactly the statement above using the permitted axioms.

OpenAI's scope note for this family:

> Erdős's reciprocal-sum conjecture asks whether every set of positive integers with divergent reciprocal sum contains arithmetic progressions of every finite length. The formalization proves this statement: for every requested length, such a set contains a progression with positive common difference. The selected theorem is the reciprocal-sum consequence. The paper's quantitative upper bound for the largest progression-free subset of $\{1,\ldots,N\}$ is outside this statement.
<!-- example:end -->

## Contribute in fifteen minutes

Each unit of work is small, credited by name on the site, and reviewed in the open.

| If you have | Do this | Guide |
|---|---|---|
| Ten minutes and some Lean or mathematics in one field | Check that one Lean statement says what the paper's theorem says | [`check-a-statement`](skills/check-a-statement/SKILL.md) |
| An evening and a result you understand | Write a motivated explanation of one family, one of 372 open exposition problems | [`explain-a-result`](skills/explain-a-result/SKILL.md) |
| Knowledge of a field's literature | Record where an idea in a manuscript first appeared | [`trace-a-credit`](skills/trace-a-credit/SKILL.md) |
| A large Linux machine | Replay a Comparator check and publish the receipt | [`replay-a-proof`](skills/replay-a-proof/SKILL.md) |
| A sharp eye | Report a mismatch, an error or a broken link | [`report-a-problem`](skills/report-a-problem/SKILL.md) |

**Bring your own agent.** The repository ships agent skills in [`skills/`](skills/), mirrored for Claude Code in `.claude/skills/` and for Codex and other agents in `.agents/skills/`, with instructions in [`AGENTS.md`](AGENTS.md). Open the repository in Claude Code, Codex or Cursor and ask it to begin with `start-here`. Agents may draft and check; every contribution names the person who stands behind it and says how AI was used. The full guide is [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Build it yourself

```sh
git clone https://github.com/wcook04/openai-math-atlas
cd openai-math-atlas
sh scripts/fetch_upstream.sh            # sparse checkout of openai/math at the pinned commit, without PDFs
python3 scripts/build_data.py           # writes data/*.json
python3 scripts/build_site.py           # writes site/_build/
python3 -m http.server -d site/_build   # then open http://localhost:8000
```

Python 3.10 or newer and git are the only requirements. The dataset in `data/` is plain JSON for your own analysis:

- `families.json`: the 372 families, their discipline, OpenAI's description, manuscripts and Lean statements;
- `manuscripts.json`: abstracts, headline statements with source file and line, references and where each is used;
- `statements.json`: every Comparator statement file, its imports and the definitions it introduces;
- `graph.json`: citations between manuscripts inside the collection;
- `works.json`: the outside works the collection cites;
- `summary.json`: every number above, with its definition.

## Licences and independence

The atlas is not affiliated with or endorsed by OpenAI. Material quoted from openai/math is copyright OpenAI under the Apache License 2.0 and is reproduced from the commit recorded in `upstream.json`, with links to source. Code, data and documentation in this repository are Apache-2.0; contributed explanations are CC BY 4.0. See [`NOTICE`](NOTICE).

## Author

Made by [Will Cook](https://wcook04.github.io/plectis/), who also maintains a Lean-checked research corpus on eight Erdős problems. To cite the atlas, use [`CITATION.cff`](CITATION.cff).
