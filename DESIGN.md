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

## The family mark

Every family has one small drawing of its recorded evidence, made by
`scripts/glyphs.py` from the states in `scripts/evidence.py`. It appears
wherever the family does: on the plate, in lists and search results, in the
desk, at the head of the family page. Every stroke encodes a recorded state;
nothing is decoration, and every mark carries a sentence for screen readers.

- **Papers**: short ink lines on the left, one per current paper, at most four.
- **Ring**: a brick ring around those lines when an outside group checked the
  paper's result by another method (HOL Light cards, exact computation).
- **Thread**: a steel line from the papers to the diamond when a paper theorem
  is paired with the Lean. Dashed for a candidate pairing found by shared
  words; solid when the Lean source cites the theorem or the release declares
  the link.
- **Diamond**: the release has a Lean statement for the family; a second
  outline behind it, more than one. Each half is one outside reader's finding
  on whether that Lean states the family's headline result: left half MathVet,
  right half cert-machine (order in `site/copy_evidence.json`). Filled, all of
  it; pale, part of it or a narrower or weaker statement; open, a supporting
  or different result; dotted, not read.

The two halves are never merged into one verdict. Agreement is visible as a
symmetric diamond and stated in words from the backend's own comparison.

## The plate: the front door

The whole release on one screen, as a plate of specimens: the seventeen
disciplines in the release's order, each a titled group of its families' marks
in catalogue order. Seen from across a room it shows where the release has Lean
and what the outside readers found; up close, every mark is a family.

- Each group's title says, in one sentence, how many families it has and how
  many have Lean statements.
- Groups flow in columns on wide screens and stack on phones. Geometry is
  stable: filtering dims marks, never moves them.
- Every mark is a link to its family page, so the plate works without
  JavaScript, and has a text alternative.
- Pointing at a mark previews it (name, the catalogue's first sentence, its
  evidence in words). Selecting it opens the desk beside the plate and rings
  the mark; its citations inside the release are drawn to the marks they
  connect, with direction and counts. Hover never replaces the selection.
- A discipline's title opens it as a sheet: each family as a card with its
  mark at reading size, name, first sentence of its claim and its evidence in
  words. The trail leads back to the whole release.
- The key is also the filter: each line has its count and highlights the marks
  it describes.
- Search sits above the plate. Its results light up marks and list families,
  papers, theorems and Lean names.
- Selection lives in the URL (`#o=f%3A003`, `#o=d%3Anumber-theory`); Back and
  Forward restore it. The older `#d=...&f=...` links still land.
- Keyboard: Tab reaches the plate, arrow keys move between marks in reading
  order, Enter opens the desk, Escape closes it. Nothing needs dragging.

## The thread

The line from a paper's theorem to the Lean statement paired with it. Wherever
two statements sit side by side, the qualification sits at the join, because
adjacency itself makes a claim.

| Recorded pairing | Line | Words at the join |
|---|---|---|
| Candidate pairing (shared words) | dashed steel | Found by the words the two share; nobody has reviewed whether they state the same thing. |
| Cited in the Lean source | solid steel | The Lean source cites this theorem by its label; nobody has reviewed the match. |
| Declared by the release's manifest | solid steel | The release binds them; nobody has reviewed the match. |
| Unresolved, or several targets | none | No theorem is paired; the alternatives are listed with their reasons. |
| Reviewed by a named person | solid, heavier | Their recorded relation, their name, the version they reviewed. |

A reported re-run is evidence about the Lean statement it ran, never about the
paper theorem beside it. Outside readings concern the family's headline as a
whole and sit under a heading that says so.

## Reading a family

The family page is the beginning of mathematical work, not of an audit.

- **Head**: the trail; the family's name; OpenAI's catalogue description as a
  credited quotation; the family's figure, a small map of its papers, their
  main statements and the Lean statements with their threads; one sentence of
  evidence beside the mark.
- **Two lines kept apart**: the formal status (what the Lean states, who re-ran
  it) and the readable argument (the paper at the passage, any explanation).
  Neither stands in for the other.
- **The claim**: when the backend names a candidate theorem for the headline,
  it is shown exactly as printed, with its number and paper, and the candidate
  state in words. When the headline is unresolved, the catalogue's claim leads
  and the candidates follow with their reasons; no convenient theorem fills the
  gap.
- **The comparison**: the paper theorem and the Lean statement side by side on
  wide screens, stacked on narrow ones, joined by the thread and its words.
  Either can be expanded without resetting the other. No scroll syncing.
- **Then**: what the outside readers found (each in their own term, notes
  beside verdicts, disagreement first), who re-ran the Lean, what is left to
  check, the papers (current, previous editions, withdrawn), connections, and
  how to explain, check or correct it.

## Inspection

One pattern for every supporting record: an outside reading, a re-run, a
candidate theorem, a number, a Lean name, a citation.

- Pointing or focusing shows a light preview that can itself be pointed at and
  dismissed with Escape. Hover is never the only way in.
- Selecting pins the record in the inspection rail beside the reading column
  (a sheet from the bottom on phones). Focus moves to it; closing returns focus
  and the reading position.
- The rail shows the record's source, credit, date, version and a real link to
  the source. Long commands and full inventories live here, not in the reading
  column.
- A qualification that changes the meaning of a claim stays beside the claim,
  never only in the rail.

## Identity and links

Every object keeps one identity across the plate, the lists, the family page,
the paper and the Lean page: the backend's ids, never rebuilt from TeX.

- Pages have stable addresses: `families/003.html`, `papers/<slug>.html#<anchor>`,
  `statements/<id>.html`. The plate's selection is `index.html#o=<id>`.
- A copied link opens the same object, with JavaScript off too, and the page
  says which release pin it shows.
- A shared family page carries its own title, description and preview, so the
  link stands alone.

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
- The plate shows the whole release. A preview speaks for what is under the pointer, and the desk beside it for what is selected; rewriting the desk on every hover made it flicker.
- The key sits on the plate's first screen, so the marks can be read before scrolling.

**Disclosure.**
- Release, then discipline, then family, then result.
- At most four primary actions at any decision point; an expert's contents can show more.
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
| Headline unresolved | The catalogue's claim leads; candidate theorems follow with their reasons |
| Cited in the Lean source, or declared by the release | A source link between the two, not a review of their match |
| A number whose inputs are incomplete | Its known part and what is missing; never a zero |

## Motion

Motion only answers an action:
- the desk sliding in when you select a family, and a discipline opening into its sheet;
- the thread brightening when you point at a pairing;
- the theme cross-fade.

There are no entrance animations and nothing moves on its own. Reduced motion
jumps instead of flying.

## The pages and their one job

| Page | Its job |
|---|---|
| `index.html`, the plate | See the whole release's evidence and find a way in |
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
