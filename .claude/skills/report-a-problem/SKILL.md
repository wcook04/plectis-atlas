---
name: report-a-problem
description: Use when someone has found something wrong or doubtful in the atlas or the release it reads, such as a mismatch between a paper and its Lean statement, an error in a manuscript, a Comparator failure, a wrong number or broken link on the atlas, or a mistake in a contribution. Explains how to make the report precise and constructive (the commit, the file and lines, the exact text quoted, what was expected and what was found, a minimal example) and where to send it.
---

# Report a problem

A good report lets a reader confirm the problem in two minutes without asking you anything.

## Where to send it

- **The atlas first.** Open the Issues tab, choose New issue, then "Report a problem". The report stays on public record in the atlas's issue tracker, where maintainers and other readers can confirm it and act on it.
- **OpenAI's files.** The atlas is independent of OpenAI and cannot change the manuscripts or the Lean files. For an error in one of them, you may also tell OpenAI through whatever channel their repository describes, and link that report in yours.
- **A contribution.** For a problem in an explanation, a check or a credit, you may also comment on the pull request that added it. If you disagree with a statement check, you can file your own check with a different verdict.

## What to include

1. **Where.** The upstream commit (the atlas reads the commit in `upstream.json`), the file path and line numbers, or the URL of the atlas page. For a manuscript, the theorem number, its label and the page.
2. **The exact text.** Copy the relevant lines into a code block. Keep the quotation short and copy it; retyped text drifts.
3. **What you expected and what you found**, one or two sentences each.
4. **Why it matters.** Say what the problem changes. For a claimed mismatch between a paper and its Lean statement, give the smallest example you can: a number, set or function on which the two statements disagree.
5. **How sure you are.** Certain, fairly sure, or unsure and asking for a second look. Say what you checked.
6. **AI assistance.** If an AI tool helped you find or describe the problem, say which and how.

A report shaped like this works well:

```text
Kind: mismatch between paper and Lean statement
Where: lean/ComparatorChallenges/<Name>.lean, lines <a> to <b>, at commit <commit>;
       paper <manuscript>, Theorem <n>, label <label>, page <p>
Quoted lines: <the exact lines>
Expected: <what the paper says, in one sentence>
Found: <what the Lean statement says, in one sentence>
Example: <the smallest case where they disagree>
Confidence: fairly sure; I checked <what>
AI assistance: none
```

## Keep it constructive

- Describe the mathematics or the file. Leave out speculation about how it was produced and about anyone's motives.
- Keep what you verified separate from what you suspect.
- Report one problem per issue, and link related issues.
- If you have a fix for the atlas itself, a pull request is welcome; mention the issue in it.

## For agents

An agent may find a problem and draft the report. Before anything is posted, the person must open the file at the stated commit and confirm every quoted line and every line number, because agents misquote line numbers and paraphrase when they mean to quote. Never open an issue or post a comment without the person's explicit go-ahead.
