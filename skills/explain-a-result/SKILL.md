---
name: explain-a-result
description: Use when writing, revising or reviewing an explanation of one result family for the atlas (contributions/explanations/<family>/<github-handle>/explanation.md). Gives the procedure for a motivated first-principles account (the problem as posed, every symbol unpacked with numbers, the plan before the proof, a checkpoint after each stage, credit where each idea is used, exactly what the Lean statement checks, what stays open), the section template, and a self-check list. A named person authors and stands behind every sentence; an agent may draft.
---

# Explain a result

Every result family in the release is an open exposition problem: the manuscripts state and prove the results, and the atlas invites people to explain them so that a reader outside the specialty can follow why they are true. An explanation names its reader, starts from the problem as it was first posed, and takes that reader to the result one checked step at a time.

The full style guide is `STYLE.md` at the repository root. This skill is the procedure.

## Before you write

1. **Claim the family.** Open an issue with the "Claim an explanation" form. A claim tells others you are working on the family. It does not stop anyone else: several explanations of one family can coexist, written for different readers.
2. **Choose your reader.** Write one line naming them, for example "undergraduates who have taken a first course in group theory". Every later decision follows from it.
3. **Read the sources.** On the atlas family page, open:
   - the family summary and each manuscript's introduction and main statements;
   - the scope note `lean/docs/<family>.md` upstream, if the family has Lean statements;
   - each Lean challenge file, and any statement checks and credits already on the atlas.
4. **Fix what is true.** Write, for yourself, five short lines:
   1. the exact statement, with every hypothesis;
   2. which parts the manuscript proves, and which it quotes from earlier work;
   3. what the Lean statement checks, and whether a statement check confirms it matches the paper;
   4. what remains open;
   5. who did what before.

   If you cannot write these lines yet, keep reading before you draft. If the sources disagree, report the problem (`skills/report-a-problem/SKILL.md`) and say so in your explanation.
5. **Copy the template.**

   ```sh
   mkdir -p contributions/explanations/<family>/<your-github-handle>
   cp contributions/_templates/explanation.md contributions/explanations/<family>/<your-github-handle>/explanation.md
   ```

## The section template

The template has these sections, in this order. Rename a section when the mathematics calls for it, but keep its job.

| Section | Its job |
|---|---|
| Title and "Written for" line | Name the result in plain words, and name the reader. |
| What this explains | The result in one sentence, the reader, and what they will be able to follow by the end. |
| The problem as it was first posed | The original question, quoted with its source and year; every symbol unpacked with numbers; a plain restatement; one example where the condition holds and one where it fails. |
| The result | The theorem with every hypothesis inside it; each hypothesis called natural or restrictive, with examples it includes and excludes. |
| Why it is not obvious | The first approach a reader would try, and where it fails. |
| The plan of the proof | A short numbered list of stages, one sentence each. |
| The proof | One subsection per stage. Each says why the stage is needed, shows every step, and ends with a **Checkpoint**: what is now known, and what is still needed. |
| Where the ideas come from | Credit for each idea from earlier work, with sources you have opened. |
| What the Lean statement checks | The challenge file, read in words; what Comparator certifies; what neither Lean nor Comparator checks; what the statement does not cover. |
| What stays open | The exact stronger statement that is not proved, and why the method stops short of it. |
| References | Every work cited. |

Exercises with answers are a welcome final section when they help the reader check their understanding.

## The rules that matter most

1. State the problem as originally posed before any result.
2. Unpack every symbol with actual numbers.
3. Show the plan of the proof before the proof.
4. End each stage with a checkpoint saying what is now known and what is still needed.
5. Choose examples that expose the mechanism, and carry one through the whole argument.
6. Define every term at its first use. Use no private nicknames and no notation that appears only once.
7. Say whether each hypothesis is natural or restrictive.
8. Credit each idea where it is used.
9. Say exactly what the Lean statement checks and what it does not.
10. Name what stays open.

`STYLE.md` explains each rule with examples, along with the rules on precise language (use "is" and "equals" for values, and keep "becomes" for processes), figures and format.

## Working with an AI agent

An agent can draft sections, compute and check examples, propose figures, and suggest references. The named authors stay responsible for every sentence.

- The authors read and understand every sentence, and can answer a question about any step.
- Every reference an agent suggests is opened and checked before it is cited. Agents invent plausible citations, theorem numbers and quotations.
- `ai_assistance` says plainly which tool did what, for example "Claude drafted Stages 2 and 3 and computed the table in Section 2; I rewrote both stages and checked every step."

If you are an agent: ask the person for their name, GitHub handle and reader; never fill these in yourself. Mark every step you could not verify, for example with a comment `<!-- unverified: ... -->`, and list those steps when you hand the draft over. Never set `status: ready-for-review` or `status: reviewed` on your own.

## Self-check

Before you set `status: ready-for-review`, check each item:

- [ ] The first section names the reader and says what the explanation shows.
- [ ] The problem appears as its author posed it, with the source, before any result.
- [ ] Every symbol is unpacked with numbers at its first use.
- [ ] Each hypothesis is called natural or restrictive, with examples.
- [ ] The plan comes before the proof, and the proof follows it.
- [ ] Every stage ends with a checkpoint.
- [ ] One example is carried through, and the examples expose the mechanism.
- [ ] There are no private nicknames, no one-use notation and no Lean names in the prose.
- [ ] Every idea from earlier work is credited where it is used, with a source you have opened.
- [ ] The Lean section says what is checked and what is not.
- [ ] The open question is stated exactly.
- [ ] No sentence is stronger or weaker than its source.
- [ ] `ai_assistance` is accurate, and every author can defend every sentence.
- [ ] `python3 scripts/check_contributions.py <your file>` reports no errors and no style warnings.

## Status and review

- `draft`: work in progress. A draft pull request is welcome; it shows others the family is being worked on.
- `ready-for-review`: the authors have done the self-check and want a reviewer. Say so in the pull request.
- `reviewed`: a named reviewer, who is not an author, has read the whole explanation and checked its mathematics. The reviewer adds themselves under `reviewers` and sets this status in a pull request; the checker refuses `reviewed` without a reviewer.

A reviewer checks the mathematics against the manuscript and the Lean statement, works through the examples, and reads the explanation as the named reader would. Disagreements go in the pull request; the authors decide what to change.

To improve someone else's explanation, open an issue or a pull request with suggested changes. If you contribute substantial text, ask the authors to add you to `authors`. To write for a different reader, write your own explanation in your own folder.
