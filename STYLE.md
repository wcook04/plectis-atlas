# How to write an explanation

The atlas treats every result family as an open exposition problem. The mathematics is written down in the manuscripts, but nobody has yet explained it so that a reader outside the specialty can follow why it is true. This guide says what a good explanation on the atlas looks like.

The procedure for writing one is in `skills/explain-a-result/SKILL.md`. The file to start from is `contributions/_templates/explanation.md`.

## The test

Choose a reader and name them at the top of your explanation, for example "a second-year undergraduate who has taken a first course in analysis". For every paragraph, that reader should be able to say:

1. what is being done;
2. why it is being done now;
3. how it follows from what came before;
4. what it achieves towards the result.

If any answer needs knowledge you have not given, the paragraph is unfinished.

## 1. Fix what is true before you write

Before you write a sentence of explanation, know exactly:

- the statement of the result, with every hypothesis and quantifier;
- which parts the manuscript proves, which are checked in Lean, which are quoted from earlier work, which are computed, and which are open;
- what the Lean statement certifies, and whether anyone has checked that it matches the paper (look for statement checks on the atlas).

An explanation is never stronger or weaker than its source. Keep a proof, a computation, a heuristic and an open question visibly separate. If you find that a manuscript and its Lean statement disagree, report it (`skills/report-a-problem/SKILL.md`) and explain the difference in your text.

## 2. The problem comes first

Open with the problem as its author posed it, quoted, with the source and the year. Then:

- go through every symbol with actual numbers ("2^n is 2 multiplied by itself n times, so 2^3 = 8");
- restate the problem in plain words;
- give an example where the condition holds and one where it fails, and say what failing means.

Never open on a list of numbers or a formula without saying where it comes from.

## 3. State the result and give it time

State the theorem with every hypothesis inside the statement. Then, before any proof:

- say for each hypothesis whether it is natural or restrictive: which familiar objects satisfy it, which it excludes, and why a reader should care;
- give examples the theorem covers and examples it does not;
- say why the result is not obvious: show the first approach a reader would try and where it fails.

Lead with the result at its full strength. State the limits once, after it.

## 4. Show the plan before the proof

Before the proof, list its stages as a short numbered plan, one sentence each, and use the same numbering in the proof. A reader who knows where the argument is going can build intuition as it goes.

## 5. Show every step, and end each stage with a checkpoint

- Leave no claim unexplained, however obvious it feels to you. If something holds "clearly", show why in one line.
- Show the intermediate arithmetic: 15/7 = 2 + 1/7, because 15 = 2 × 7 + 1.
- Before an operation, say why it is done and what it is for. Answer the "why not" questions a reader will ask: why this choice, why not a simpler one, what happens in the edge case.
- End each stage with a checkpoint: what is now known, and what is still needed.
- Connect every new idea to the goal. Say why it appears now and which step it serves.
- Give the hard step the most space. Routine steps can be brief.

## 6. Use examples that expose the mechanism

- Use examples throughout, and choose them to show the mechanism. Prefer the example that shows every possible outcome at once over one that shows only the easy case.
- Carry one example all the way through the argument when one exists, then say what the general case needs beyond it.
- Say where an example stops being representative.
- Contrast with a known case when that makes a test concrete.

## 7. Definitions, notation and names

- Define every term at its first use.
- Introduce a symbol only when it is used more than once and makes the text easier to read. Write out a symbol that would be used once.
- Use the field's standard words. Do not invent names for ordinary objects. Keep private nicknames, labels from a manuscript's internal structure and names of Lean declarations out of the prose. If a reader would have to ask what a term means, replace it with the mathematics it stands for.
- A standard tool keeps its standard name: "by the Chinese remainder theorem", "by the Cauchy–Schwarz inequality".
- Give each symbol one meaning, and remind the reader of notation after a long gap.

## 8. Precise language

- For values, use "is", "equals" or "has". A value does not "become" or "turn into" another value; those verbs describe processes.
- Define a process exactly: what goes in, what is done, what comes out.
- Name the object you are talking about. Avoid a pronoun whose object is more than a clause away.
- Use an analogy only if it maps onto the mechanism. Otherwise state the plain fact.
- Use "clearly", "obviously" and "it is easy to see" only when the next clause shows it.
- Punctuate with commas, colons and full stops. Avoid dashes as punctuation.
- Use one spelling convention throughout.

## 9. Displays and figures

- Introduce every display, table or figure in a sentence before it appears, and say what it shows.
- Label every axis and number line with what it measures.
- End a list or picture that continues with "…". Without it, the picture says the list stops.
- Draw the mathematics itself: a number line, a graph, a table of values, a diagram of the construction. Leave out decorative props that stand for nothing in the argument.
- Describe every figure in the text, so that a reader who cannot see it loses nothing.

## 10. Credit each idea where it is used

When an idea comes from earlier work, say so where it is used: who introduced it, where (with a theorem or page number), and how the argument here relates to it. Say which credits the manuscript gives and which you traced yourself. Assert that an idea first appeared somewhere only when you can cite the source. "The earliest appearance I found is …" is the honest form when you searched and remain unsure. Record each credit you trace as a credit file as well (`skills/trace-a-credit/SKILL.md`).

## 11. Say exactly what the Lean statement checks

If the family has Lean statements, include a section that:

- links the challenge file at the pinned commit;
- reads its statement line by line in words;
- says what Comparator certifies: the proof in OpenAI's library proves exactly this statement, uses only the permitted axioms, and is accepted by the Lean kernel;
- says what neither Lean nor Comparator checks: that the formal statement means what the paper's sentence means. Link any statement check on the atlas, or say that none exists yet;
- says which parts of the paper the Lean statement does not cover (the scope note `lean/docs/<family>.md` upstream lists them).

If the family has no Lean statement, say so in one sentence.

## 12. Name what stays open

Close the mathematics by stating the exact stronger statement that remains open, and why the method stops short of it.

## 13. AI assistance and responsibility

You may use AI tools to help you read, draft, check arithmetic or find references. Say what you used and for what in `ai_assistance`, in one plain sentence. Every named author must understand every sentence and be able to answer a question about any step. Open every reference an AI tool suggests before you cite it: such tools invent citations, theorem numbers and quotations.

## 14. Format

- One file, `explanation.md`, in `contributions/explanations/<family>/<github-handle>/`, started from the template.
- Write mathematics in LaTeX, between `$...$` inline and `$$...$$` for displays. GitHub renders this notation, so you can preview the file on your fork.
- Put figures in the same folder and link them with a relative path: `![What the figure shows](figure-1.svg)`. Prefer SVG or PNG and keep each file under 5 MB. If a script drew the figure, put the script beside it.
- Quote OpenAI's text briefly and exactly, with its location. OpenAI publishes it under the Apache License 2.0.
- Let the argument set the length.

## 15. Self-check before you ask for review

- The first section names the reader and says what the explanation shows.
- The problem appears as its author posed it, with the source, before any result.
- Every symbol is unpacked with numbers at its first use.
- Each hypothesis is called natural or restrictive, with examples.
- The plan comes before the proof, and the proof follows the plan.
- Every stage ends with a checkpoint.
- The examples expose the mechanism, and one is carried through.
- The prose has no private nicknames, no one-use notation and no Lean names.
- Every idea from earlier work is credited where it is used, with a source you have opened.
- The Lean section says what is checked and what is not.
- The open question is stated exactly.
- No sentence is stronger or weaker than its source.
- `ai_assistance` is accurate, and every author can defend every sentence.
- `python3 scripts/check_contributions.py <your file>` reports no errors and no style warnings.
