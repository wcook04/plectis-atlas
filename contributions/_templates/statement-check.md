---
kind: statement-check
# The Comparator challenge name, as in lean/ComparatorChallenges/<name>.lean upstream.
statement: ErdosReciprocal
# The family the statement belongs to, in double quotes.
family: "159"
# The manuscript you compared against: its folder name under preprints/ upstream.
manuscript: Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026
# Where the paper states the result: number, title if any, label, section.
paper_statement: "[replace: for example Corollary 1.2 (Divergent reciprocal sums), label ap:reciprocal, Section 1]"
# One of: matches, stronger-than-paper, weaker-than-paper, different, cannot-tell.
verdict: cannot-tell
# You: the person who read both sources and signs this verdict.
reviewer:
  name: "[replace: your full name, as it should appear on the site]"
  github: your-github-handle
  background: "[replace: one line, for example PhD student in additive combinatorics; first time reading Lean]"
# "none", or one plain sentence saying which tool did what.
ai_assistance: none
# YYYY-MM-DD
date: 2026-10-10
---

## What the paper says

[replace: quote the paper's statement exactly, with its number, label and section. Then say in your own words what every symbol ranges over, including any convention the paper fixes elsewhere, such as whether its natural numbers start at 0 or 1.]

## What the Lean statement says

[replace: list every definition in the challenge file and say in words what it means. Then translate the theorem into one plain sentence with its quantifiers in order. Note anything in the .json configuration that matters, such as definition_names.]

## Differences

[replace: every difference you found, however small, and whether it matters. Cover the domain of each variable, edge cases such as 0, empty sets and short lengths, hypotheses added or dropped, quantifier order, and anything the Lean statement leaves out. List the checks that found no difference too.]

## Why this verdict

[replace: argue the verdict. For matches, show that each statement implies the other. For stronger-than-paper or weaker-than-paper, show the implication that holds and say why the other fails. For different or cannot-tell, say exactly what stops the comparison.]
