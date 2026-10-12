# How the Plectis Atlas looks and reads

The design contract for the site. Read it before changing a page; record here
what a page teaches, so the next pass starts from it.

## The read

A public reading room for OpenAI's mathematics release, for mathematicians
first and AI researchers second. It is set in a publication register and kept
as quiet as a good journal. It takes one risk: the front door is the whole
release, drawn as one map that opens into every family, with a list beside it
that reads the map in words. Everything else stays
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

## No symbol codes

Every drawn thing is one concrete object (a family, a paper, a theorem, a Lean
statement), labelled in words on the drawing. Colour means one thing in a
drawing, said in one line. A state is a sentence beside the object it
qualifies. Never a composite mark that packs several facts into one symbol, never
a key the reader must learn before the page makes sense, never treemap or
stock-market tile grids. (12 October 2026: a "family mark" with papers, a
reader-split diamond, tones and rings was rejected as a code to crack, and the
old tile map as just as bad. The Plectis maths site is the model: a problem is
introduced in words with its mathematics typeset, its status is a sentence, and
its map labels every problem with plain counts.)

## The front door: the map and the list

The release on one screen as our map, with a readable list beside it, the way
a good maps app pairs a map with its results. 700-plus results need both: the
map for where things are, the list for reading them.

- **The map** (the existing map engine): the seventeen disciplines labelled in
  words on the drawing with plain counts ("Number theory, 31 families, 24 with
  Lean"). Family nodes are coloured by one meaning (what the outside readers
  find the release's Lean states), each colour named in one line. Citations
  are drawn only for the selected family, and called citations.
- **The list** (the left panel): the release in sentences, search, then the
  disciplines. Choosing one zooms the map to it and lists its families as plain
  entries: title, the claim's first sentence with its mathematics typeset
  (credited to OpenAI's catalogue), and one sentence saying what the Lean
  states and who checked it. Pointing at an entry lights its node; clicking
  opens the family.
- **A family**: the map shows its papers (short title, date), their results
  labelled by printed number ("Theorem 1.1") and its Lean statements by name.
  Selecting a result shows the theorem typeset as printed, the Lean statement
  paired with it if any, and the routes on: read it in the paper, compare with
  Lean, open the family page. A click always leads to mathematics, never to a
  status page.
- Hover to read, click to open. Selection lives in the URL (`#o=f%3A003`,
  `#o=d%3Anumber-theory`, `#o=r:...`, `#o=l:...`); Back and Forward restore it;
  older `#d=...&f=...` links still land. Keyboard: Tab, arrows, Enter, Escape.

## What each view shows first

From the outside review of the first rebuild screenshots (12 October 2026):
give space and emphasis to what the current task needs, at each depth.

| View | First read | Second read | Third read |
|---|---|---|---|
| Release | Disciplines and the size of the corpus | Families and what their Lean states | A route into a chosen object |
| Discipline | Readable family titles | Where they sit and how they connect | The selected family's claim |
| Family or theorem | The selected statement, typeset | Its paper and its Lean counterpart | The mathematical neighbourhood |
| Families list | Comparable rows | How their evidence differs | Filters that refine the question |
| Lean statement | The formal statement and its hypotheses | The paper passage and the pairing's state | Sources, runs, further inspection |

- Labels are horizontal and collision-managed, never rotated. The selection
  always keeps its full label.
- Level of detail follows scale: a family is a plain disc until it is large
  enough for its inner map to be read.
- At theorem focus the reading pane widens (about 40 to 45 per cent of the
  workspace) and the map refits. The mathematics never shrinks to fit.
- A list beside the map is an index: a title and one status line per row, and
  the active row expanded.

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

A heading that pairs two statements carries the pairing's state where the
pairing is asserted ("Possible Lean match: suggested from shared wording;
correspondence not reviewed"). A reported re-run is evidence about the Lean
statement it ran, never about the paper theorem beside it, and never upgrades
an unreviewed pairing. Outside readings concern the family's headline as a
whole and sit under a heading that says so.

## Reading a family

The family page is the beginning of mathematical work, not of an audit.

- **Head**: the trail; the family's name; OpenAI's catalogue description as a
  credited quotation, with its mathematics typeset.
- **The theorem**: the page's centrepiece, set large as printed (number, paper,
  date), with "Read it in the paper" and "Compare with Lean". Its place in the
  family is one click away on the map ("Show on the map").
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

Every object keeps one identity across the map, the lists, the family page,
the paper and the Lean page: the backend's ids, never rebuilt from TeX.

- Pages have stable addresses: `families/003.html`, `papers/<slug>.html#<anchor>`,
  `statements/<id>.html`. The map's selection is `index.html#o=<id>`.
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
- The map shows the whole release. A preview speaks for what is under the pointer, and the panel for what is selected; rewriting the panel on every hover made it flicker.
- The one-line colour key sits on the map's first screen.

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
- the camera moving to a discipline or a family when you select it;
- the thread brightening when you point at a pairing;
- the theme cross-fade.

There are no entrance animations and nothing moves on its own. Reduced motion
jumps instead of flying.

## The pages and their one job

| Page | Its job |
|---|---|
| `index.html`, the map and the list | See the whole release and find a way in |
| `families/<id>.html` | What is claimed, what states it formally, what has been checked |
| `papers/<slug>.html` | Read the paper, with evidence at each theorem |
| `statements/<id>.html` | Read the Lean statement whole, and what you must check |
| `explain.html` | Every family as a list, with who has explained it |
| `sources.html`, `glossary.html`, `numbers.html`, `contribute.html`, `about.html` | Credit, terms, counts with receipts, how to help, why it is built this way |

## What the October rebuild taught

- **Say what was checked, by whom, in their words.** A re-run sentence names
  the operation and its object ("Comparator accepts OpenAI's proof of this Lean
  statement, as three outside groups report"). Each group then gets its own
  line in its own term. Credited names contain commas, so groups are separated
  by semicolons.
- **Bring the cited passage to the theorem.** A number a theorem cites, such
  as (1.5), opens the actual passage from that paper's reading page under the
  theorem, labelled with the paper and its date. If it cannot be found, the
  link goes to the passage instead of a guess.
- **Retrieval stays behind the mathematics.** How a passage was found (the
  shared words, the method) sits behind "Why this passage is shown". The
  passage's state, unreviewed and found by wording, stays visible.
- **No folds.** Content is shown, or opened in the rail on request.
- **A paper's word macros are words.** `\newcommand{\KN}{Kerr--Newman}` is
  typeset as text, never sent to the formula renderer.
- **One owner for each decision.** The pairing heuristics, headline choice,
  re-run tallies and reader grades that the frontend used to compute have been
  deleted. The backend decides them; the pages say what it decided.

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
