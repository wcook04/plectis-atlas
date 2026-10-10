---
name: start-here
description: Use when someone wants to contribute to the OpenAI Math Atlas and has not chosen a task, or asks how they can help. Asks about their mathematics, their time and their computer, then hands them one concrete unit of work (a statement to check, a family to explain, a credit to trace, a proof to replay or a problem to report) with the links to open, the template to copy and the next skill to follow.
---

# Start here

Aim: within a few minutes, the person has one specific task that fits the time they have, the right files open, and the template copied to the right place. Ask, choose, hand over.

## 1. Ask three questions

Ask them in one message, and skip any the person has already answered:

1. Which mathematics do you know well? A field, a level such as "undergraduate analysis", or "none in particular" are all good answers.
2. How much time do you have: fifteen minutes, an evening, or a few evenings over several weeks?
3. Have you read any Lean before? Do you have a Linux computer with plenty of memory and disk that you can leave running for hours?

## 2. Choose the kind of work

| If they have | Suggest | Next skill |
|---|---|---|
| A field they know, and fifteen minutes or more | Check one Lean statement in that field, starting with a short one | `check-a-statement` |
| An evening or more, and they like explaining | Explain one result family, after claiming it | `explain-a-result` |
| Knowledge of the literature in a field | Trace where an idea in a manuscript first appeared | `trace-a-credit` |
| A Linux machine they can leave running | Replay a Comparator check and record the receipt | `replay-a-proof` |
| Something that looks wrong | Report it | `report-a-problem` |
| An interest in the atlas's code | Improve the scripts, data or skills | `improve-the-atlas` |

A first statement check needs no Lean experience: the checklist and the reading guide in `check-a-statement` cover what a short statement uses. Someone without a particular field can check a short statement in a subject they studied, trace a credit, or report problems.

## 3. Find one concrete item

Run from the repository root:

```sh
python3 skills/start-here/find_work.py --disciplines
python3 skills/start-here/find_work.py --kind check --discipline "<their field>"
python3 skills/start-here/find_work.py --kind explanation --discipline "<their field>"
python3 skills/start-here/find_work.py --kind credit --discipline "<their field>"
python3 skills/start-here/find_work.py --kind replay --main-results
```

The script lists items nobody has done yet, easiest first, with the links to open. Show the person the top two or three, one line each, and let them choose.

- For a first check in fifteen minutes, prefer a statement with three or fewer custom definitions, few lines of Lean, and no definition holes.
- Before suggesting an explanation, look at the open claims: issues labelled `claim`. With the GitHub command-line tool, run `gh issue list --repo wcook04/openai-math-atlas --label claim --state open`; otherwise open the Issues tab and filter by the `claim` label. A claimed family can still take an explanation for a different reader; suggest the person comments on the claim first.

## 4. Hand over

Give the person, in one message:

1. the item, and one sentence on why it fits them;
2. the links to open (the script prints them);
3. the commands that copy the template to the right path, with their GitHub handle filled in once they have told you what it is;
4. the skill to follow next;
5. the command that checks their file: `python3 scripts/check_contributions.py <path>`.

Then work through the next skill with them.

## If they do not use git

Every kind of contribution has an issue form (Issues, then New issue): claim an explanation, check a statement, suggest a credit, share a replay, report a problem. A maintainer turns a submitted form into a file credited to its author. An explanation is a long document and needs a pull request; GitHub's web editor can create the file on a fork without installing anything (on the fork, Add file, then Create new file).

## Say this once

The person's name appears on the atlas beside what they submit. They disclose any AI help in `ai_assistance`, and they sign only what they have read and understood. If you are an agent, you draft; they decide and sign.
