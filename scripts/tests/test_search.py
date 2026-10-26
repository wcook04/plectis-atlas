#!/usr/bin/env python3
"""Check the site search's normaliser against Statement Map's own.

The search dialog (site/assets/atlas.js) must turn a query into exactly the tokens
Statement Map indexed, or a word that is in the release would find nothing. This
test runs the block of atlas.js between "search-normalise:start" and
"search-normalise:end" in Node over

  * every token in the vendored search shards (each must normalise to itself and
    land in the shard file that holds it),
  * every entry name in the vendored search entries,
  * a list of hard queries (sharp s, Erdős, ℝ, \\mathbb{R}, the fi ligature, the
    Turkish dotted I, hyphenated words, Greek final sigma, entities),

and compares the tokens and shards with search_tokens and search_shard, copied below
from Statement Map's web_projection.py (Will Cook, statement-map). It also checks
that the page each result links to is the backend's own reading_page for every
paper statement in the reader packets, in Python (build_site.search_url) and in
JavaScript (urlFor).
Exact Lean filename searches also run through the browser query code with generated
packets, checking canonical routes regardless of the query's capitalisation. The front
door's search words (scripts/build_universe.py) are generated too, and the query code is
checked to find a prefix of the last word, plural and singular forms, a hyphen either
way, a formula word (L^2), statements by printed number (Theorem 1.1), a marked line of
text per result and the nearest title words when nothing matches.

    python3 scripts/tests/test_search.py

Skips, with a message, when node is not installed. Standard library only.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


# --- copied from statement-map web_projection.py (credited above); keep in step -----
def search_tokens(text):
    """Deterministic lexical normalization, not mathematical equivalence."""
    text = unicodedata.normalize('NFKC', html.unescape(text)).casefold()
    text = re.sub(r'\\(?:mathbb|mathcal|mathrm|mathbf|text)\s*\{([^{}]*)\}', r' \1 ', text)
    return sorted(set(re.findall(r'[^\W_]+(?:-[^\W_]+)*', text, flags=re.UNICODE)))


def search_shard(token):
    return format(int(hashlib.sha256(token.encode()).hexdigest()[:2], 16) % 64, '02x')


def query_tokens(text):
    """search_tokens(text, query=True) at reader-projection/7: the folded words a query and
    the citation lookup use, NFKD with combining marks removed, split at non-word characters."""
    text = unicodedata.normalize('NFKC', html.unescape(text)).casefold()
    text = re.sub(r'\\(?:mathbb|mathcal|mathrm|mathbf|text)\s*\{([^{}]*)\}', r' \1 ', text)
    folded = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.category(c).startswith('M'))
    return sorted(set(re.findall(r'[^\W_]+', folded, flags=re.UNICODE)))
# --------------------------------------------------------------------------------------


HARD = [
    "ß", "Straße", "STRASSE", "ẞ", "Erdős", "ERDŐS", "erdos", "Erdős–Turán", "ℝ", "\\mathbb{R}", "\\mathbb {R}^n",
    "$\\mathcal{O}(n)$", "\\mathrm{CAT}(0)", "\\text{Hecke}", "ﬁnite ﬁeld", "ﬂow", "İstanbul", "ISTANBUL",
    "ıi", "Iİıi", "ΟΔΟΣ", "ὀδός", "Σίσυφος", "non-abelian", "Bi-Lipschitz", "k-server", "-x- -", "a--b",
    "x_1", "Hölder–Zygmund", "Ångström", "Å", "ﬀ", "µ-measure", "Ⅻ", "²", "½", "①", "𝔽_p", "𝐀", "Ǆ",
    "&amp; &lt;b&gt; &#233; &#x3C3;", "Tom &amp; Jerry", "Ꭰ ꭰ ᏸ", "ſ", "ﬆ", "ǰ", "ΐ", "ŉ", "ᾈ", "ᾳ",
    "Siegel zeros", "SiegelZeros", "quasi-Riemann", "7/8", "L-function", "Erdős reciprocal",
]


def normaliser_js() -> str:
    src = (ROOT / "site" / "assets" / "atlas.js").read_text(encoding="utf-8")
    m = re.search(r"/\* search-normalise:start.*?\*/(.*?)/\* search-normalise:end \*/", src, re.S)
    if not m:
        raise SystemExit("site/assets/atlas.js has no search-normalise block")
    return m.group(1)


RUNNER = r"""
var global = globalThis;
%s
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = { tokens: input.texts.map(t => searchTokens(t)), qtokens: input.texts.map(t => queryTokens(t)), shards: input.tokens.map(t => shardSync(t)),
              urls: input.entries.map(e => urlFor(e[0], e[1])) };
const subtle = globalThis.crypto && globalThis.crypto.subtle;
(subtle ? Promise.all(input.tokens.slice(0, 2000).map(t => subtle.digest('SHA-256', new TextEncoder().encode(t))
   .then(b => { const n = new Uint8Array(b)[0] %% 64; return (n < 16 ? '0' : '') + n.toString(16); })))
   : Promise.resolve(null)).then(s => { out.subtle = s; fs.writeFileSync(process.argv[3], JSON.stringify(out)); });
"""


def check_lean_filename_search(node, build_site, entries):
    """Run the browser query code against generated packets on a case-sensitive route map."""
    with tempfile.TemporaryDirectory() as tmp:
        previous_out = build_site.OUT
        try:
            build_site.OUT = Path(tmp)
            build_site.build_search_data()
        finally:
            build_site.OUT = previous_out
        labels = json.loads(Path(tmp, "data/search/labels.json").read_text())
        expected = {e["id"][2:]: [build_site.curly_prose(e["name"]), e.get("family_ids") or []]
                    for e in entries if e["kind"] == "lean"}
        assert labels["lean"] == expected, "Lean filenames must come from the search catalogue"
        assert len({key.lower() for key in expected}) == len(expected), "ambiguous Lean filename case"
        formula_name = build_site.search_statement_name({
            "kind": "statement",
            "id": "r:Global-Arthur-Enhancements-of-Cuspidal-Excursion-Parameters-October-5-2026:thm:parent",
            "name": r"$a<b>c$ \cite[Theorem~1.1]{Parent}",
        })
        assert "a<b>c" in formula_name.replace(" ", ""), "formula comparisons are not HTML tags"
        js = Path(tmp, "query.cjs")
        js.write_text(r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(process.argv[2], 'utf8');
const requested = [];
const context = {
  document: {body: {getAttribute: () => ''}, getElementById: () => null},
  fetch: async (url, options) => {
    requested.push(url);
    assert.ok(!options || options.method !== 'HEAD', 'search must not guess a filename');
    return {ok: true, json: async () => JSON.parse(fs.readFileSync(path.join(__dirname, url), 'utf8'))};
  }
};
vm.createContext(context);
vm.runInContext(src.slice(src.indexOf('(function (global) {')), context);
(async () => {
  for (const name of ['CoveringDensity', 'ElementaryPositivity', 'CartierChartCompactnessSupport']) {
    for (const spelling of [name, name.toLowerCase(), name.toUpperCase()]) {
      const hits = await context.AtlasSearch.query(spelling);
      const hit = hits.find(h => h.id === 'l:' + name);
      assert.ok(hit, 'missing Lean filename: ' + spelling);
      assert.equal(hit.url, 'statements/' + name + '.html');
      assert.ok(hit.family_ids.length, 'retain the catalogue family');
    }
  }
  assert.equal((await context.AtlasSearch.query('UnlistedLeanIdentifierForSearchTest')).length, 0);
  assert.ok((await context.AtlasSearch.query('014')).some(h => h.id === 'f:014'));
  const parentId = 'r:Global-Arthur-Enhancements-of-Cuspidal-Excursion-Parameters-October-5-2026:thm:parent';
  const parent = (await context.AtlasSearch.query('Ramanujan')).find(h => h.id === parentId);
  assert.ok(parent, 'citation-bearing title remains searchable');
  assert.ok(parent.name.startsWith('Theorem 1.1 (Finite-level Ramanujan–Arthur decomposition ['), parent.name);
  assert.ok(parent.name.includes('Theorem 1.1'), 'retain the cited locator');
  assert.ok(!parent.name.includes('\\'), 'render citation syntax in result labels');
  assert.equal(parent.url, 'papers/Global-Arthur-Enhancements-of-Cuspidal-Excursion-Parameters-October-5-2026.html#thm:parent');
  const citedOnly = (await context.AtlasSearch.query('ABKRT21')).find(h => / \(\[Aaronson et al\., 2021\]\)$/.test(h.name));
  assert.ok(citedOnly, 'a citation-only title keeps its attribution');
  const labels = JSON.parse(fs.readFileSync(path.join(__dirname, 'data/search/labels.json'), 'utf8'));
  const packetId = 'r:Diagonal-Fourier-extension-for-positively-curved-surfaces-in-three-dimensions-September-24-2026:thm:packet';
  assert.ok(/^\S+ [\d.]+ \(Packet propagation \[/.test(labels.statement_names[packetId]), labels.statement_names[packetId]);
  assert.ok(!labels.statement_names[packetId].includes('\\'), 'undefined source locator macros stay out of navigation labels');
  assert.ok(requested.every(url => url.endsWith('.json')), 'no guessed page request');
  console.log('test_search: canonical Lean filename searches pass in original, lower and upper case; unknown name stays empty.');
})().catch(err => { console.error(err); process.exitCode = 1; });
""", encoding="utf-8")
        subprocess.run([node, str(js), str(ROOT / "site/assets/atlas.js")], check=True)
        check_search_words(node, Path(tmp))


def check_search_words(node, tmp: Path):
    """The front door's search words (scripts/build_universe.py): a prefix of the last word,
    plural and singular, a hyphen either way, a formula word, a printed statement number,
    a line of text with the words marked, and the title words offered when nothing matches."""
    from types import SimpleNamespace
    import build_universe as BU
    import reader
    BU.import_site()
    r = reader.load()
    words, blocks, vocab_files = BU.build_search_words(SimpleNamespace(r=r, gen=r.generation))
    wdir = tmp / "data" / "universe-search"
    wdir.mkdir(parents=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False)
    for part in ("names", "atoms"):
        (wdir / f"{part}.json").write_text(dump(words.pop(part)), encoding="utf-8")
    (wdir / "words.json").write_text(dump(words), encoding="utf-8")
    for k, v in vocab_files.items():
        (wdir / f"vocab-{k}.json").write_text(dump(v), encoding="utf-8")
    for b in blocks:
        (wdir / f"text-{b['start'] // BU.TEXT_BLOCK:04d}.json").write_text(dump(b), encoding="utf-8")
    assert BU.list_label_template(r"label=\textup{(G\arabic*)},ref=G\arabic*") == r"\textup{(G\arabic*)}"
    assert BU.list_label_template("(a)") is None
    js = tmp / "words.cjs"
    js.write_text(r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(process.argv[2], 'utf8');
const context = {
  document: {body: {getAttribute: () => ''}, getElementById: () => null},
  fetch: async url => ({ok: true, json: async () => JSON.parse(fs.readFileSync(path.join(__dirname, url), 'utf8'))})
};
vm.createContext(context);
vm.runInContext(src.slice(src.indexOf('(function (global) {')), context);
const AS = context.AtlasSearch;
const total = r => Object.values(r.counts).reduce((a, b) => a + b, 0);
(async () => {
  const hy = await AS.query('log-concave'), flat = await AS.query('logconcave');
  assert.ok(total(hy) > 0 && total(flat) === total(hy), 'logconcave finds what log-concave finds');
  const sob = await AS.query('Sob'), sobolev = await AS.query('Sobolev');
  assert.ok(total(sob) >= total(sobolev), 'a prefix of the last word finds the word');
  const rm = await AS.query('random matrix');
  assert.ok(rm.some(h => /random sign matrices/.test(h.name)), 'matrix finds matrices');
  const l2 = await AS.query('L^2', {statements: 100000});
  assert.ok(total(l2) > 0 && total(l2) < 400, 'L^2 is one formula word, not the letters L and 2');
  const thm = await AS.query('Theorem 1.1', {statements: 100000});
  const names = await AS.names();
  const st = thm.filter(h => h.kind === 'statement');
  assert.ok(st.length > 100 && st.every(h => names[h.idx] === 'Theorem 1.1'), 'Theorem 1.1 finds the statements printed so');
  assert.equal(AS.displayName(st[0], names).indexOf('Theorem 1.1'), 0, 'statements are named by their printed number');
  const sn = await AS.snippet(rm.find(h => /random sign matrices/.test(h.name)), rm);
  assert.ok(sn && /<mark>random<\/mark>/i.test(sn.html), 'a result line marks the matched words');
  const none = await AS.query('hypergraf');
  assert.equal(total(none), 0);
  assert.ok((await AS.suggest(none.missing)).some(w => /^hypergraph/i.test(w)), 'nearest title words are offered');
  const ids = thm.map(h => h.id);
  assert.equal(new Set(ids).size, ids.length, 'one row per entry');
  console.log('test_search: prefixes, plurals, hyphens, formula words, printed numbers, marked lines and suggestions pass.');
})().catch(err => { console.error(err); process.exitCode = 1; });
""", encoding="utf-8")
    subprocess.run([node, str(js), str(ROOT / "site/assets/atlas.js")], check=True)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("test_search: skipped, node is not installed (the normaliser runs in the browser).")
        return 0
    import reader
    import build_site

    r = reader.load()
    idx = r.search_index
    tokens, where = [], {}
    for shard, path in sorted(idx["shards"].items()):
        for tok in r.packet(path)["terms"]:
            tokens.append(tok)
            where[tok] = shard
    entries = []
    for chunk in idx["entry_chunks"]:
        entries.extend(r.packet(chunk)["entries"])
    check_lean_filename_search(node, build_site, entries)
    texts = tokens + [e["name"] for e in entries] + HARD
    with tempfile.TemporaryDirectory() as tmp:
        inp, outp, js = Path(tmp, "in.json"), Path(tmp, "out.json"), Path(tmp, "run.js")
        inp.write_text(json.dumps({"texts": texts, "tokens": tokens, "entries": [[e["id"], e["kind"]] for e in entries]},
                                  ensure_ascii=False), encoding="utf-8")
        js.write_text(RUNNER % normaliser_js(), encoding="utf-8")
        subprocess.run([node, str(js), str(inp), str(outp)], check=True)
        got = json.loads(outp.read_text(encoding="utf-8"))

    fails = []
    for text, toks in zip(texts, got["tokens"]):
        want = search_tokens(text)
        if sorted(toks) != want:
            fails.append(f"tokens of {text!r}: atlas.js {sorted(toks)}, Statement Map {want}")
    for text, toks in zip(texts, got["qtokens"]):
        want = query_tokens(text)
        if sorted(toks) != want:
            fails.append(f"query words of {text!r}: atlas.js {sorted(toks)}, Statement Map {want}")
    # Every author and text word the citation shards index is a query word of itself, so
    # the citation lookup (cite.js) can reach it.
    cite_words = 0
    for name, path in r.packet("citations-index.json")["shards"].items():
        if name.startswith("work-"):
            continue
        for key in r.packet(path)["terms"]:
            word = key.split(":", 1)[1]
            cite_words += 1
            if query_tokens(word) != [word]:
                fails.append(f"citation key {key!r} is not reachable by a query")
    for tok in tokens:
        if search_tokens(tok) != [tok]:
            fails.append(f"vendored token {tok!r} does not normalise to itself in Statement Map's function")
    for tok, sh in zip(tokens, got["shards"]):
        if sh != where[tok] or sh != search_shard(tok):
            fails.append(f"shard of {tok!r}: atlas.js {sh}, file {where[tok]}, Statement Map {search_shard(tok)}")
    if got.get("subtle") is not None:
        for tok, sh in zip(tokens, got["subtle"]):
            if sh != where[tok]:
                fails.append(f"crypto.subtle shard of {tok!r}: {sh}, file {where[tok]}")
    for e, url in zip(entries, got["urls"]):
        py = build_site.search_url(e["id"], e["kind"])
        if url != py:
            fails.append(f"url of {e['id']}: atlas.js {url}, build_site {py}")
    # The backend's own reading routes for paper statements.
    by_id = {e["id"]: (e, u) for e, u in zip(entries, got["urls"])}
    checked = 0
    for fid in r.family_ids():
        for st in r.family(fid).get("statements") or []:
            page = st.get("reading_page")
            if not page or st["id"] not in by_id:
                continue
            checked += 1
            if by_id[st["id"]][1] != page:
                fails.append(f"{st['id']}: search links {by_id[st['id']][1]}, the backend reads it at {page}")
    if fails:
        print(f"test_search: {len(fails)} failures")
        for f in fails[:40]:
            print("  " + f)
        return 1
    print(f"test_search: {len(tokens)} vendored tokens, {len(entries)} entry names and {len(HARD)} hard queries "
          f"normalise as Statement Map does; every token's shard matches; {checked} statement links match "
          f"the backend's reading pages; query words match too, and all {cite_words} citation words are reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
