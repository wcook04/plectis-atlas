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

    python3 scripts/test_search.py

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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# --- copied from statement-map web_projection.py (credited above); keep in step -----
def search_tokens(text):
    """Deterministic lexical normalization, not mathematical equivalence."""
    text = unicodedata.normalize('NFKC', html.unescape(text)).casefold()
    text = re.sub(r'\\(?:mathbb|mathcal|mathrm|mathbf|text)\s*\{([^{}]*)\}', r' \1 ', text)
    return sorted(set(re.findall(r'[^\W_]+(?:-[^\W_]+)*', text, flags=re.UNICODE)))


def search_shard(token):
    return format(int(hashlib.sha256(token.encode()).hexdigest()[:2], 16) % 64, '02x')
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
const out = { tokens: input.texts.map(t => searchTokens(t)), shards: input.tokens.map(t => shardSync(t)),
              urls: input.entries.map(e => urlFor(e[0], e[1])) };
const subtle = globalThis.crypto && globalThis.crypto.subtle;
(subtle ? Promise.all(input.tokens.slice(0, 2000).map(t => subtle.digest('SHA-256', new TextEncoder().encode(t))
   .then(b => { const n = new Uint8Array(b)[0] %% 64; return (n < 16 ? '0' : '') + n.toString(16); })))
   : Promise.resolve(null)).then(s => { out.subtle = s; fs.writeFileSync(process.argv[3], JSON.stringify(out)); });
"""


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
          f"the backend's reading pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
