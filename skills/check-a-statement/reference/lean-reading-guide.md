# Reading a Lean statement

A short guide for mathematicians who have not read Lean before. It covers what you meet in the release's challenge files. For anything else, see "Where to look things up" at the end.

## The parts of a challenge file

```lean
import Mathlib                       -- use Mathlib, Lean's main mathematics library

namespace OAI                        -- names below get the prefix OAI.
namespace Erdos3                     -- and then Erdos3., so HasAP is OAI.Erdos3.HasAP

def HasAP (A : Set ℕ) (k : ℕ) : Prop :=          -- a definition: name, arguments, type, body
  ∃ a d : ℕ, 0 < d ∧ ∀ i < k, a + i * d ∈ A

theorem t (A : Set ℕ) (h : A.Infinite) : HasAP A 3 := by   -- arguments before the colon are
  sorry                                                     -- hypotheses; the type after it is
                                                            -- the conclusion
end Erdos3
end OAI
```

| Keyword | What it does | What to check |
|---|---|---|
| `def`, `abbrev` | Defines a name. `abbrev` unfolds automatically; the meaning is the same. | Read the body. It is part of the statement. |
| `noncomputable` | Tells the compiler not to generate code. | Nothing; it does not change meaning. |
| `structure` | A record type. Each field is a piece of data or a property. | Every property field is an assumption about every object of that type. |
| `class`, `instance` | A structure that Lean finds automatically, and a declared member of it. | An `instance` in the file can change what `≤`, `+`, a norm or a topology means below it. |
| `theorem`, `lemma` | A statement with a proof (`sorry` in a challenge file). | Arguments before the colon are hypotheses, quantified over. |
| `variable`, `include` | Declares arguments that later declarations in the section receive when their statements mention them, or always after `include`. | These are hidden hypotheses of the theorems below them. |
| `axiom` | An assumption with no proof. | In a challenge file, a placeholder; see Step 3 of the skill. |
| `open`, `open scoped` | Makes short names and notation available. | Nothing, apart from which notation is in use. |
| `notation`, `local notation`, `macro` | New syntax. | Read what it expands to. |
| `set_option` | Settings for Lean's tools. | Nothing. |

Argument brackets: `(x : α)` is an explicit argument, `{x : α}` is implicit (Lean fills it in, but it is still quantified over), and `[Fintype α]` is an instance argument (an assumption about α that Lean finds automatically, here "α is finite"). All three kinds are part of the statement.

## Symbols

| Lean | Read as |
|---|---|
| `∀ x, P x` / `∃ x, P x` / `∃! x, P x` | for all x / there exists x / there exists exactly one x |
| `¬ P`, `P ∧ Q`, `P ∨ Q` | not P, P and Q, P or Q |
| `P → Q`, `P ↔ Q` | if P then Q, P if and only if Q |
| `∀ i < k, P i` | for every i with i < k |
| `x ∈ A`, `A ⊆ B`, `A ∩ B`, `A ∪ B`, `A \ B`, `Aᶜ` | membership, subset, intersection, union, difference, complement |
| `{x | P x}`, `{x // P x}` | the set of x with P x; the type of such x (a subtype) |
| `f '' A`, `f ⁻¹' B` | image of A under f; preimage of B |
| `(n : ℝ)`, `↑n` | n viewed as a real number (a cast) |
| `x⁻¹` | the inverse of x |
| `a ∣ b` | a divides b |
| `a % b`, `a / b` on ℕ or ℤ | remainder and quotient (see the next section) |
| `‖x‖`, `|x|` | norm, absolute value |
| `Finset.range n`, `Fin n` | {0, 1, …, n − 1} as a finite set; the type of numbers below n |
| `Set.Icc a b`, `Set.Ico a b`, `Set.Ioo a b`, `Set.Ici a`, `Set.Ioi a` | [a, b], [a, b), (a, b), [a, ∞), (a, ∞) |
| `∑ x ∈ s, f x`, `∏ x ∈ s, f x` | finite sum and product over the finite set s |
| `∑' n, f n` | infinite sum (0 when the series is not summable) |
| `Summable f` | the series of f converges unconditionally |
| `s.card`, `#s` | number of elements of a finite set |
| `A.Infinite`, `A.Finite` | A is infinite, finite |
| `Nat.Prime p`, `p.Prime` | p is prime (0 and 1 are not) |
| `Nat.Coprime a b` | gcd(a, b) = 1 |
| `Filter.Tendsto f Filter.atTop (𝓝 L)` | f(n) tends to L as n tends to infinity |
| `∀ᶠ n in Filter.atTop, P n` | P n for all sufficiently large n |
| `∃ᶠ n in Filter.atTop, P n` | P n for infinitely many n |
| `f =O[l] g`, `f =o[l] g`, `f ~[l] g` | big O, little o, asymptotic equivalence along l |
| `deriv f x`, `∫ x in a..b, f x` | derivative of f at x; integral from a to b |
| `Real.log`, `Real.exp`, `Real.sqrt` or `√`, `Real.pi` or `π` | natural logarithm, exponential, square root, π |
| `Irrational x` | x is not a rational number |

## Arithmetic in ℕ and ℤ

- ℕ is {0, 1, 2, …}. `ℕ+` is {1, 2, 3, …}.
- In ℕ, subtraction stops at 0: `3 - 5 = 0`.
- In ℕ, `a / b` is the quotient rounded down, and `a / 0 = 0`.
- In ℤ, `/` and `%` are chosen so that the remainder is at least 0 when the divisor is not 0: `-7 / 2 = -4` and `-7 % 2 = 1`. Also `a / 0 = 0` and `a % 0 = a`.
- Casts happen exactly where they are written. `((a - b : ℕ) : ℤ)` truncates and then casts; `(a : ℤ) - (b : ℤ)` casts and then subtracts. `Int.toNat` sends negative integers to 0; `Int.natAbs` takes the absolute value.

## Values of undefined expressions

Lean gives every expression a value. These are the conventions you meet most often. The lemma names are those in the Mathlib version the release pins; search for them if a name has changed.

| Expression | Value in Lean | Mathlib lemma |
|---|---|---|
| `x / 0` | 0 | `div_zero` |
| `(0 : ℝ)⁻¹` | 0 | `inv_zero` |
| `Real.log 0`, `Real.log x` for x < 0 | 0, and log of the absolute value | `Real.log_zero`, `Real.log_abs` |
| `Real.sqrt x` for x ≤ 0 | 0 | `Real.sqrt_eq_zero_of_nonpos` |
| `∑' n, f n` when f is not summable | 0 | `tsum_eq_zero_of_not_summable` |
| `deriv f x` when f is not differentiable at x | 0 | `deriv_zero_of_not_differentiableAt` |
| `∫ x, f x ∂μ` when f is not integrable | 0 | `MeasureTheory.integral_undef` |
| `Nat.card α` for an infinite type | 0 | `Nat.card_eq_zero_of_infinite` |
| `Set.ncard s` for an infinite set | 0 | `Set.Infinite.ncard` |
| `sSup s` for an empty or unbounded set of reals | 0 | `Real.sSup_empty`, `Real.sSup_of_not_bddAbove` |

When a statement uses one of these expressions, ask whether a hypothesis rules out the undefined case. If none does, test the statement on that case.

## Sums and summability

- `Summable f` for `f : ℕ → ℝ` means unconditional convergence. For f ≥ 0 it is the same as bounded partial sums (`summable_iff_not_tendsto_nat_atTop_of_nonneg`). For real f of both signs it is absolute convergence (`summable_abs_iff`), so a conditionally convergent series is not `Summable`.
- The harmonic series is not summable: `Real.not_summable_natCast_inv`.
- `HasSum f a` says the series of f converges unconditionally to a.

## Where to look things up

- **[Mathlib documentation](https://leanprover-community.github.io/mathlib4_docs/)**. Search a name to see its definition and its lemmas. The site shows the latest Mathlib, which can differ slightly from the version the release uses.
- **The exact Mathlib version**: `lean/lake-manifest.json` upstream gives the Mathlib commit in the `rev` field of the `mathlib` entry. To read a definition exactly as the release uses it, open the Mathlib source at that commit: `https://github.com/leanprover-community/mathlib4/tree/<rev>/Mathlib`.
- **[Loogle](https://loogle.lean-lang.org/)** finds Mathlib lemmas by name or by the shape of their statement.
- **[The Lean Zulip chat](https://leanprover.zulipchat.com/)**. The "new members" channel welcomes questions about reading Lean.
- **In an editor**: with Lean installed and the upstream `lean/` folder open in VS Code with the Lean 4 extension, hovering over a name shows its type and documentation; `#print Name` shows a definition, and `#check` shows a type.
