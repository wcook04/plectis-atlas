# How the Plectis Atlas looks and reads

The design contract for the site. Read it before changing a page; record here
what a page teaches, so the next pass starts from it.

## The read

A public reading room for OpenAI's mathematics release, for mathematicians
first and AI researchers second. It is set in a publication register and kept
as quiet as a good journal. It takes one risk: the front door is the whole
release, drawn as one map that opens into every family. Everything else stays
calm so that the map, and the mathematics, are what a visitor remembers.

The release arrives as 719 papers, 416 Lean files and a catalogue. A
mathematician wants something smaller and sharper: what exactly is claimed,
whether the Lean says the same thing, and who has checked what. The site exists
to answer those questions for any result in under a minute, and to make the
size of the release feel like something a person can walk through.

## What a reader can do for any result

Every family page answers these, in this order. The home page promises them.

1. **The claim.** Read the main theorem exactly as printed, with its number, its hypotheses and its place in the paper.
2. **The formal statement.** See the Lean statement beside it, and whether outside readers judge that it states all of the theorem, part of it or less.
3. **The checks.** See who has re-run what, with what result, and what is left for a reader to check by hand.
4. **The reading.** Open the paper as a page, at the passage.
5. **The connections.** Follow what it cites inside the release, and what cites it.
6. **The problems.** See findings, corrections, disagreements and withdrawn papers.
7. **The next step.** Explain it, check it or correct it, credited by name, with or without an AI account.

This list is grounded in mathematicians' own writing about AI-generated
mathematics. The About page paraphrases those essays and links them.

## The thread

The site's one recurring drawing is **the thread**: a line from a paper's
theorem to the Lean statement that formalises it. It is the thing the release
does not give its readers, so it carries the design.

- Steel ink. Dashed while the pairing was found automatically and nobody has reviewed it; solid once a person has.
- It appears everywhere the pairing does:
  - on the map, between a result's dot and its Lean diamond;
  - on the family page, from the theorem card to the Lean card;
  - in the reading pages' margins;
  - on the Lean page, back to the paper.
- It never decorates. Where there is no pairing there is no thread, and the page says so in words.
- Its ends sit on the cards' borders, marked as the map marks them: a dot on the paper card, a diamond on the Lean card.
  - Side by side, it runs from border to border at the height of the card headings.
  - Stacked, it is a short vertical connector in the gap.
  - It never crosses text.
- When one card is much shorter than the other and fits the window, it can travel beside the longer one as the reader scrolls, taking the thread with it.

## Inks, type and ground

**Ground and inks.**
- One flat ground: cream in the light scheme, violet-black in the dark, with no gradients, glow or texture.
- Steel is for Lean and formal checks: Comparator re-runs and Lean statements.
- Brick is for every other machine check (HOL Light, exact computation) and for outward citations.
- Structure stays in low-chroma greys.
- Colour always comes with a word or a shape, never alone.

**Type.**
- Plectis Serif (STIX Two Text) for reading and theorem text.
- KaTeX for formulas.
- Plectis Sans (Source Sans 3) for the interface.
- Lean in the `--lean-mono` stack.
- Sentence case throughout.
- No tracked capitals, and no monospace outside code.

**Measure.**
- 60 to 72 characters for reading text.
- Wide formulas scroll inside their own box, never the page.
- Reading containers are capped in `ch`. KaTeX's hidden text inflates the audit's character counts, so judge formula-heavy lines by eye.

## The scale, made human

**Numbers.**
- A number is a sentence a person could say aloud, with what it counts.
- It links to the rows behind it.
- No big-number heroes.

**Entering the release.**
- Start from one thing a person can hold: one family, one theorem, one Lean statement.
- The map shows the whole release. The plate speaks for what is under the pointer, and the panel beside it for what is selected; rewriting the panel on every hover made it flicker.
- A short digest of the key sits on the map's first screen, so the marks can be read before scrolling.

**Disclosure.**
- Release, then discipline, then family, then result.
- At most four choices at any decision point.
- Lists filter and never dump.

**Teaching by example.** The home page teaches the site with one family read
in full, before it shows any totals.

## Words

- Plain and exact. A statement "states" a theorem, a check "checked" a run, a paper "cites" another.
  - "Certified" appears only as a named source's own verdict, attributed to it.
  - A pairing found automatically is a "candidate", and says so.
- No em dashes. No "not X, Y" framing. No taglines. No middle-dot strings of facts; write a sentence.
- People whose pronouns no source states are "they".
- Ways into the release are chosen by how widely the problem is known, never by anything that implies a ranking of the results, and each says in one line why to read it.
- The atlas shows and does not argue.
  - It never implies that OpenAI or any credited group endorses it.
  - It never characterises anyone's work.
  - What the release lacks is never said. It is simply there on the page, done well.

## Evidence states stay distinct

Each of these states has its own wording. Unknown is neither red nor green.

| Recorded state | What the reader sees |
|---|---|
| Candidate pairing | A proposed correspondence, its method, and that nobody has reviewed it |
| Reported re-run | A named outside group reports this result; the atlas did not re-run it |
| Name linked from the source text | A link found by reading the Lean source, with no claim that Lean elaborated it |
| Paper rendered in full | The reading page passed its rendering checks; this says nothing about the mathematics |
| Unnumbered, or number unavailable | Two different states; neither is replaced by a section number |
| No card, or zero cards | Missing coverage differs from an observed empty set |
| An AI agent's draft classification | A quiet line after the outside readings, never styled as a verdict |
| The two outside readers disagree | One sentence naming both readings leads the section |
| An exact check that was not decided | Says nothing against the result; drawn in neutral grey |

## Motion

Motion only answers an action:
- the camera flight when you open a family;
- the thread brightening when you point at a pairing;
- the theme cross-fade.

There are no entrance animations and nothing moves on its own. Reduced motion
jumps instead of flying.

## The pages and their one job

| Page | Its job |
|---|---|
| `index.html`, the map | Find a way into the release |
| `families/<id>.html` | What is claimed, what states it formally, what has been checked |
| `papers/<slug>.html` | Read the paper, with evidence at each theorem |
| `statements/<id>.html` | Read the Lean statement whole, and what you must check |
| `explain.html` | Every family as a list, with who has explained it |
| `sources.html`, `glossary.html`, `numbers.html`, `contribute.html`, `about.html` | Credit, terms, counts with receipts, how to help, why it is built this way |

## Quality floor

Judge every page at four sizes, in both schemes:
- laptop, 1440×790;
- small laptop, 1280×690;
- monitor, 1920×953;
- phone, 390×664.

Every page must also:
- have a skip link first, visible focus and full keyboard use;
- reflow at 320px;
- make no requests to other hosts;
- show no layout shift;
- keep a working route when JavaScript is off.

Read the screenshots in order before calling anything done, and have fresh eyes
read them too.
