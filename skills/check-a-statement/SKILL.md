---
name: check-a-statement
description: Use when comparing one Lean statement from OpenAI's mathematics release (a Comparator challenge file) with the paper theorem it formalises, to write a statement check in contributions/checks/<statement-id>/<github-handle>.md. Gives the reading procedure, a checklist of the conventions that make a Lean statement say something other than the paper, the five verdicts, and a worked example (ErdosReciprocal). A named person signs every verdict; an agent may only draft.
---

# Check a statement

A statement check answers one question: does this Lean statement say what the paper's theorem says? You read both, compare them line by line, choose one of five verdicts and explain it. A first check of a short statement takes about fifteen minutes once you know the steps; a long statement can take an evening.

## What Comparator certifies, and what it leaves to you

Each Lean statement on the atlas is a challenge file in the release, `lean/ComparatorChallenges/<Name>.lean`. It states the theorem with its proof left as `sorry`, together with every definition the statement needs. A configuration file `<Name>.json` beside it names the theorem, the module of OpenAI's library that contains the proof, and the axioms the proof may use.

Comparator, a checking tool published by the Lean FRO (the organisation that develops Lean), compares the proof in the library with the challenge file. When it accepts, three things hold:

1. the proof proves exactly the statement in the challenge file, with exactly the definitions in that file (Comparator compares their bodies too, with one exception, the definition holes described in Step 3);
2. the proof uses no axioms beyond the `permitted_axioms` in the `.json` file;
3. the Lean kernel, the small program at the core of Lean that checks every inference, accepts the proof.

Comparator does not check that the challenge file means what the paper means. A statement can be proved perfectly and still be weaker than the paper, or about a slightly different object, because of one definition or one convention. That comparison is the statement check.

## Who signs

The verdict belongs to a named person. You must have read the challenge file and the paper statement yourself, and you must agree with every sentence in the file, because your name, GitHub handle and background appear on the atlas beside the verdict.

An AI agent may help you read, may draft every section and may run the checklist. If you are an agent: never write the reviewer's name, handle or background yourself, never choose the verdict on the person's behalf, and say in `ai_assistance` what you drafted. Put your draft in front of the person, point out each step you could not verify, and let them decide.

## Before you start

1. Choose a statement. This lists statements nobody has checked yet, those with the fewest custom definitions first:

   ```sh
   python3 skills/start-here/find_work.py --kind check --discipline "number theory"
   ```

2. Open these files at the commit in `upstream.json`. The atlas page for the statement links the Lean file, the scope note and the paper's statements in its TeX source.
   - the challenge file `lean/ComparatorChallenges/<Name>.lean` and its `<Name>.json`;
   - the scope note `lean/docs/<family>.md`, which says which paper result the statement formalises and what it leaves out;
   - the paper, `preprints/<manuscript>/` upstream (the TeX source is in its `build/` folder, useful for labels).

3. Copy the template:

   ```sh
   mkdir -p contributions/checks/<Name>
   cp contributions/_templates/statement-check.md contributions/checks/<Name>/<your-github-handle>.md
   ```

## The procedure

### Step 1. Pin down the paper statement

Find the result that the scope note names. Record its number, its label (visible in the TeX source as `\label{...}`) and its section; this goes in `paper_statement`. Quote it exactly in "What the paper says".

Then read backwards from it to every definition and convention it relies on: what the paper's ℕ is, what its words such as "progression", "graph" or "measure" mean, and any standing assumption announced at the start of a section. Write down what each symbol ranges over.

Your check covers the whole challenge file. If its `.json` lists several `theorem_names`, find the paper result for each, and treat each theorem under the same four headings. If the Lean statement matches no single displayed result, quote the closest ones and say so.

### Step 2. Read the whole challenge file

Read from the first line to the last. Comparator compares every definition the statement uses, so each `def`, `abbrev`, `structure`, `class`, `instance`, `notation`, `variable` and `axiom` in the file can change what the theorem says. For each one, write down:

- what it means, in words;
- the paper's corresponding notion;
- any difference.

Definitions from Mathlib, Lean's main mathematics library, are not in the file. `skills/check-a-statement/reference/lean-reading-guide.md` decodes the common notation, lists the conventions Mathlib uses for undefined expressions, and says where to look a definition up.

### Step 3. Read the configuration

Open `<Name>.json`.

- `theorem_names` lists the theorems Comparator certifies. The rest of the file supports them.
- `definition_names` lists **definition holes**. For these, Comparator checks only the name and the type; the body comes from OpenAI's library and may differ from the body in the challenge file. If this list is not empty, find each of these definitions in OpenAI's library and read it: start from the file for `solution_module` (the module `OAI.Geometry.PlaneColoring.Five` is the file `lean/OAI/Geometry/PlaneColoring/Five.lean`) and search the library for the definition's name. Check that each says the same as the challenge's version, or what the paper means. A hole filled with something trivial can make the theorem trivial, and Comparator would still accept it.
- `permitted_axioms` is normally `propext`, `Quot.sound` and `Classical.choice`, Lean's three standard axioms. Anything else deserves a sentence in your check.
- If the challenge file declares an `axiom` and proves the theorem from it, that axiom stands in for the missing proof. Comparator rejects any proof in the library that uses an axiom outside `permitted_axioms`, so the placeholder cannot leak into the certified result.

### Step 4. Write the theorem as one sentence

Translate the theorem into a plain sentence, keeping the quantifiers in their Lean order. Unfold each custom definition into the sentence once, so the sentence uses only standard mathematics. If a theorem is stated as `theorem foo : SomeTheorem` where `SomeTheorem` is a `def ... : Prop`, unfold `SomeTheorem` and treat its body as the statement.

### Step 5. Run the checklist

Go through every item of the checklist below. Write down each item that applies, including those where you found no difference, so a reader can see what you checked.

### Step 6. Compare in both directions

Answer two questions, each with a short argument:

- Does the Lean statement imply the paper's statement?
- Does the paper's statement imply the Lean statement?

When an implication needs a small translation (removing 0 from a set, shifting an index, rescaling a constant), write the translation out.

### Step 7. Choose the verdict

| Verdict | Lean implies paper | Paper implies Lean | What it tells a reader |
|---|---|---|---|
| `matches` | yes | yes | The proof certifies the paper's statement. |
| `stronger-than-paper` | yes | no | The proof certifies the paper's statement and more. |
| `weaker-than-paper` | no | yes | The proof certifies part of what the paper claims. |
| `different` | no | no | The two say different things; the proof does not certify the paper's statement. |
| `cannot-tell` | ? | ? | You could not decide. Say exactly what stopped you. |

"Yes" means you can show the implication. "No" means it fails and you can say why, with an example where possible. If you can show one direction and cannot decide the other, choose `cannot-tell` and say which direction is open. A Lean statement whose hypotheses can never all hold is true for an empty reason; it is `weaker-than-paper`, and the Differences section must say so plainly.

### Step 8. Write it up and submit

Fill the four sections of the template: "What the paper says", "What the Lean statement says", "Differences", "Why this verdict". Quote Lean code in fenced code blocks. Keep what you verified separate from what you believe. Then run:

```sh
python3 scripts/check_contributions.py contributions/checks/<Name>/<your-github-handle>.md
```

Fix every error, then open a pull request with this one file. If you prefer not to use git, the "Check a statement" issue form takes the same content, and a maintainer turns it into a file credited to you.

## The checklist

1. **Natural numbers start at 0.** Lean's ℕ contains 0. Many papers start at 1, often without saying so. Check every variable of type ℕ: does the Lean statement include a case the paper excludes, or index from 0 where the paper indexes from 1?
2. **Subtraction and division in ℕ and ℤ.** In ℕ, `a - b = 0` whenever `b ≥ a`, and `a / b` rounds down, with `a / 0 = 0`. So `n - 1` at `n = 0` is 0, and `(n + 1) / 2` is a floor. Check every formula at its smallest values.
3. **Undefined expressions have values.** Lean assigns every expression a value, including those a paper would call undefined: `x / 0 = 0`, `(0 : ℝ)⁻¹ = 0`, `Real.log 0 = 0`, `Real.sqrt x = 0` for `x < 0`, the infinite sum `∑'` of a non-summable sequence is 0, `deriv` of a non-differentiable function is 0, the integral of a non-integrable function is 0, `Nat.card` and `Set.ncard` of an infinite set are 0, and `sSup` of an empty or unbounded set of reals is 0. A statement that uses one of these without a hypothesis excluding the bad case can be true for a meaningless reason.
4. **Coercions.** Casts such as `(n : ℝ)` or the arrow `↑` move a number between ℕ, ℤ, ℚ, ℝ and ℂ. `((a - b : ℕ) : ℤ)` subtracts in ℕ (truncating) and then casts; `(a : ℤ) - b` casts first. `(n : ℝ)⁻¹` is the real number 1/n; `1 / n` computed in ℕ is 0 for every `n ≥ 2`. Find where each cast happens.
5. **Quantifier order.** `∀ ε, ∃ N, ...` differs from `∃ N, ∀ ε, ...`. For each `∃`, say what the witness may depend on, and check the paper allows the same. A constant the paper calls uniform must be chosen before the variables it is uniform in.
6. **Hypotheses added or dropped.** Put the Lean hypotheses and the paper's hypotheses side by side. An extra hypothesis in Lean makes the Lean statement weaker; a missing one makes it stronger, or false if the hypothesis was needed. Hypotheses also hide in `variable` lines, in square-bracket arguments such as `[Fintype α]` or `[Fact p.Prime]`, in the fields of a `structure`, and in types such as `Fin n`, `ℕ+` or a subtype `{x // P x}`.
7. **Special and edge cases.** Try the smallest values: 0, 1, the empty set, length 0 or 1, the trivial group, the zero function. Check what the Lean statement says there and what the paper says.
8. **Empty hypotheses and trivial witnesses.** Can all the hypotheses hold at once? Write down one object that satisfies them. If no object does, the theorem says nothing. For an existence statement, check that the witness cannot be something trivial (the empty set, 0, a constant) because a definition is too loose.
9. **`Summable` and divergence.** Mathlib's `Summable f` means the series converges unconditionally. For terms that are all at least 0, this is the same as bounded partial sums, so `¬ Summable f` means the series diverges to infinity. For real terms of both signs, `Summable` means absolute convergence: the alternating harmonic series 1 − 1/2 + 1/3 − … converges and is not `Summable`. Check the signs of the terms before you read `Summable` as "converges". If an extra argument names a summation method, as in `Summable f L` or `∑'[L]`, look that method up.
10. **`Set`, `Finset` and intervals.** A `Finset` is finite by construction; a `Set` may be infinite. `Finset.range n` and `Fin n` both stand for {0, 1, …, n − 1}. `Set.Icc a b` contains both endpoints, `Set.Ico a b` contains `a` and excludes `b`, and so on for `Ioc`, `Ioo`, `Ici`, `Ioi`. Check every endpoint.
11. **Eventual and asymptotic statements.** `∀ᶠ n in Filter.atTop, P n` means "P n holds for every sufficiently large n"; `∃ᶠ n in Filter.atTop, P n` means "P n holds for infinitely many n". `f =O[atTop] g`, `f =o[atTop] g` and `f ~[atTop] g` are big O, little o and asymptotic equivalence. Check that each implied constant and threshold may depend on exactly what the paper allows.
12. **A theorem packaged inside a definition.** Challenge files often define `def SomeTheorem : Prop := ...` and then state `theorem foo : SomeTheorem`. Comparator compares the body of `SomeTheorem`, so this is safe, but the body is the statement: unfold it and read it.
13. **Structures, classes and instances.** Each field of a `structure` is an assumption about every object of that type. A `class` or `instance` declared in the file can change what familiar notation means further down, such as `≤`, `+`, a norm or a topology.
14. **What the statement leaves out.** A paper theorem often has several parts, explicit constants or rates. The scope note says which part the Lean statement covers. Record what is not covered. It belongs in an honest check, though it is a limit of coverage and does not make the covered part wrong.

## Worked example: ErdosReciprocal

This example was written to teach the method. It is not a signed check: the atlas shows a verdict only when a named reviewer submits one. The same example, in the exact file format, is in `skills/check-a-statement/examples/ErdosReciprocal.md`.

**The paper.** Family 159, manuscript `Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026`. The scope note `lean/docs/159.md` says the formalised result is the reciprocal-sum consequence, and that the paper's quantitative bound on progression-free subsets of {1, …, N} is outside the statement. The paper states it as Corollary 1.2 (label `ap:reciprocal`, Section 1):

> Every set A ⊆ ℕ with ∑_{a∈A} a^{-1} = ∞ contains nonconstant arithmetic progressions of every finite length.

The introduction poses Erdős's question for "every set A of positive integers", and the sum of a^{-1} over A makes sense only when 0 ∉ A, so the paper's ℕ is {1, 2, 3, …}. The introduction defines a k-term progression as a, a + d, …, a + (k − 1)d with d > 0.

**The challenge file**, without its namespace lines:

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

**The definitions in words.**

- `HasAP A k`: there are natural numbers a and d with d > 0 such that a + i·d lies in A for every natural number i < k. So A contains the k numbers a, a + d, …, a + (k − 1)d. The first term a may be 0.
- `reciprocalTerm A n`: the real number 1/n when n ∈ A, and 0 otherwise. Lean writes 1/n as `(n : ℝ)⁻¹`, the inverse of n viewed as a real number, and Mathlib sets `(0 : ℝ)⁻¹ = 0`. So the term at n = 0 is 0 whether or not 0 ∈ A. The `classical` line only lets Lean decide membership in an arbitrary set; it does not change the meaning.
- `ReciprocalProgressionTheorem`: for every set A of natural numbers, if the function n ↦ reciprocalTerm A n is not summable, then HasAP A k holds for every natural number k.

**The configuration.** `theorem_names` is `OAI.Erdos3.manuscriptReciprocalProgressionTheorem`, `definition_names` is empty (no holes, so all three definitions are compared in full), and `permitted_axioms` are the standard three.

**The checklist, item by item.**

- Natural numbers (item 1): the Lean statement covers every A ⊆ ℕ, including sets that contain 0. The paper covers sets of positive integers. This is the one difference, settled below.
- Undefined expressions (item 3): the only one is `(0 : ℝ)⁻¹ = 0`, which makes 0 contribute nothing to the sum.
- Coercions (item 4): the reciprocal is computed in ℝ, as it should be. Had the file used `1 / n` in ℕ, every term with n ≥ 2 would be 0, every set would give a summable function, and the theorem would say nothing.
- `Summable` (item 9): every term is at least 0, so `¬ Summable (reciprocalTerm A)` says exactly that ∑_{n∈A} 1/n diverges to infinity. Mathlib proves this equivalence for nonnegative terms (`summable_iff_not_tendsto_nat_atTop_of_nonneg`).
- Progressions (items 6 and 8): `0 < d` matches "nonconstant". Had the file allowed `0 ≤ d`, the constant progression a, a, a, … would satisfy `HasAP A k` for every nonempty A, and the conclusion would be empty.
- Edge cases (item 7): `HasAP A 0` holds for every A (take a = 0, d = 1; there is no i < 0), and `HasAP A 1` says only that A is nonempty. The paper's "every finite length" includes these short lengths; its proof notes that divergence forces A to be infinite, which supplies lengths one and two.
- Quantifier order (item 5): a and d are chosen after A and k, as in the paper.
- Packaging (item 12): the theorem's type is `ReciprocalProgressionTheorem`, a `def ... : Prop`. Its body is unfolded above.
- What is left out (item 14): the paper's Theorem 1.1, the bound r_k(N) ≤ C_k N exp(−c_k (log N)^{ε_k}), is not part of this statement.

**Lean implies the paper.** Let B be a set of positive integers with ∑_{b∈B} 1/b = ∞. Regard B as a set of natural numbers; it does not contain 0. Then reciprocalTerm B n is 1/n for n ∈ B and 0 otherwise, its terms are at least 0, and their sum is infinite, so the function is not summable. The Lean theorem gives, for each k ≥ 1, natural numbers a and d with d > 0 and a + i·d ∈ B for every i < k. Taking i = 0 shows a ∈ B, so a ≥ 1, and every term a + i·d is an element of B. So B contains a nonconstant progression of length k. Allowing a = 0 in `HasAP` costs nothing here, because the first term must itself lie in B.

**The paper implies Lean.** Let A be any set of natural numbers whose reciprocalTerm function is not summable, and let B = A \ {0}. The term at 0 is 0 for both sets, so reciprocalTerm B equals reciprocalTerm A, and ∑_{b∈B} 1/b = ∞. B is a set of positive integers, so the paper gives, for each k, a nonconstant progression of length k in B. Listing it in increasing order gives a and d > 0 with a + i·d ∈ B ⊆ A for every i < k, which is `HasAP A k`. For k = 0 there is nothing to prove.

**Verdict: `matches`.** The two statements are equivalent. The Lean statement quantifies over more sets, those containing 0, and the convention `(0 : ℝ)⁻¹ = 0` makes 0 contribute nothing, so specialising the Lean statement to sets without 0 gives exactly Erdős's version, and the paper's version implies the general one.

## Writing a good check

- One point per paragraph. Quote the exact Lean lines you discuss.
- Give an example whenever you claim a difference matters: a set, a number or a function where the two statements disagree.
- Say what you checked and found no difference in, so the next reader does not repeat the work.
- If you disagree with an existing check, write your own; the atlas shows every signed verdict. Say in your Differences section where and why you differ.
- If you find a real mismatch, also open a "Report a problem" issue so it reaches the people maintaining the atlas (see `skills/report-a-problem/SKILL.md`).
