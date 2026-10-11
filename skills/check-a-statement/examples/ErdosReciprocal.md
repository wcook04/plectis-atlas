---
kind: statement-check
upstream_commit: "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
statement: ErdosReciprocal
family: "159"
manuscript: Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026
paper_statement: "Corollary 1.2 (Divergent reciprocal sums), label ap:reciprocal, Section 1"
verdict: matches
reviewer:
  name: "[replace: the name of the person who has read both sources and signs this verdict]"
  github: your-github-handle
  background: "[replace: one line about the reviewer]"
ai_assistance: "This example was drafted by an AI agent to teach the method. A reviewer who submits a check must read both sources, rewrite this field and sign the verdict."
date: 2026-10-10
---

<!-- Teaching example for skills/check-a-statement/SKILL.md. It is not a signed check. -->

## What the paper says

Corollary 1.2 (Divergent reciprocal sums), label `ap:reciprocal`, in Section 1 of *Quasipolynomial Bounds for Arithmetic Progressions*:

> Every set A ⊆ ℕ with ∑_{a∈A} a^{-1} = ∞ contains nonconstant arithmetic progressions of every finite length.

The paper does not define ℕ separately. Its introduction poses Erdős's question for "every set A of positive integers", and the sum of a^{-1} over A makes sense only when 0 ∉ A, so here ℕ is {1, 2, 3, …}. The introduction defines a k-term progression as a, a + d, …, a + (k − 1)d with d > 0, and "nonconstant" refers to d > 0. "Every finite length" means every k ≥ 1; the proof remarks that divergence forces A to be infinite, which gives lengths one and two.

The scope note `lean/docs/159.md` says the Lean statement is this reciprocal-sum consequence, and that the quantitative bound of Theorem 1.1 is outside it.

## What the Lean statement says

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

- `HasAP A k`: there are natural numbers a and d with d > 0 such that a + i·d ∈ A for every i < k. The first term a may be 0.
- `reciprocalTerm A n`: 1/n as a real number when n ∈ A, and 0 otherwise. Mathlib sets `(0 : ℝ)⁻¹ = 0`, so the term at n = 0 is 0 in every case.
- `ReciprocalProgressionTheorem`: for every set A of natural numbers, if n ↦ reciprocalTerm A n is not summable, then `HasAP A k` holds for every natural number k.

In one sentence: for every set A of natural numbers whose reciprocals do not have a finite sum, and every k, A contains k terms a, a + d, …, a + (k − 1)d with d > 0.

Configuration (`ErdosReciprocal.json`): the certified theorem is `OAI.Erdos3.manuscriptReciprocalProgressionTheorem`; `definition_names` is empty, so Comparator compares all three definitions in full; `permitted_axioms` are `propext`, `Quot.sound` and `Classical.choice`.

## Differences

1. **Sets containing 0.** Lean quantifies over every A ⊆ ℕ, including sets that contain 0; the paper's sets are sets of positive integers. Because the term at 0 is 0, removing 0 from A changes nothing in the hypothesis. This difference does not matter (see the next section).
2. **First term 0.** `HasAP` allows a = 0. For a set without 0 this cannot happen once k ≥ 1, because taking i = 0 puts a in the set.
3. **Lengths 0 and 1.** `HasAP A 0` holds for every A (a = 0, d = 1, and no i < 0), and `HasAP A 1` says A is nonempty. Both agree with the paper's "every finite length".
4. **Summability.** Every term of reciprocalTerm A is at least 0, so `¬ Summable` says exactly that the sum of 1/n over A diverges to infinity (Mathlib: `summable_iff_not_tendsto_nat_atTop_of_nonneg`).
5. **No other differences found.** I checked: the reciprocal is computed in ℝ (in ℕ, `1 / n` would be 0 for n ≥ 2); `0 < d` matches "nonconstant"; a and d are chosen after A and k, as in the paper; the theorem is packaged as a `def ... : Prop` whose body is read above; there are no `variable`, `instance` or `axiom` lines.
6. **Not covered.** Theorem 1.1, the bound r_k(N) ≤ C_k N exp(−c_k (log N)^{ε_k}), is not part of this statement.

## Why this verdict

**Lean implies the paper.** Let B be a set of positive integers with ∑_{b∈B} 1/b = ∞. As a set of natural numbers B does not contain 0, reciprocalTerm B has nonnegative terms with infinite sum, and so it is not summable. For each k ≥ 1 the Lean theorem gives a and d > 0 with a + i·d ∈ B for every i < k. Taking i = 0 shows a ∈ B, so all k terms are positive integers in B, and they form a nonconstant progression.

**The paper implies Lean.** Let A ⊆ ℕ with reciprocalTerm A not summable, and let B = A \ {0}. The terms at 0 are 0 for both sets, so reciprocalTerm B = reciprocalTerm A and ∑_{b∈B} 1/b = ∞. B is a set of positive integers, so the paper gives, for each k ≥ 1, a nonconstant k-term progression in B ⊆ A; listed in increasing order it has the form a + i·d with d > 0, which is `HasAP A k`. The case k = 0 holds for every set.

The two statements are equivalent, so the verdict is `matches`. Allowing 0 makes the Lean statement cover more sets at no cost: specialised to sets without 0 it is exactly the paper's corollary.
