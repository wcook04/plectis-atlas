#!/usr/bin/env node
// Check that every formula of a reading page typesets with KaTeX.
//
// Used by scripts/build_papers.py. Reads a JSON list on stdin:
//
//   [{"paper": slug, "tex": "...", "display": true|false, "macros": {...}}, ...]
//
// An item without "macros" reuses the macros of the previous item for the same
// paper, so a batch carries each paper's macros once. Every formula is rendered
// with the options the reading page uses (site/assets/paper.js): throwOnError,
// strict "ignore", trust false, maxExpand 2000, a fresh copy of the macros each
// time. Writes one JSON object to stdout:
//
//   {"katex": "<version>", "checked": n, "failures": [{"index": i, "paper": slug, "error": "..."}]}
//
// KaTeX is loaded from the path in the KATEX_JS environment variable: the
// package directory or its dist/katex.js (or katex.mjs). Nothing is downloaded.

import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);

async function loadKatex(spec) {
  let p = path.resolve(spec);
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) {
    const dist = path.join(p, 'dist', 'katex.js');
    p = fs.existsSync(dist) ? dist : p;
  }
  if (p.endsWith('.mjs')) {
    const mod = await import(pathToFileURL(p).href);
    return mod.default || mod;
  }
  const mod = require(p);
  return mod.default || mod;
}

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    process.stdin.on('error', reject);
  });
}

async function main() {
  const spec = process.env.KATEX_JS;
  if (!spec) {
    process.stderr.write('KATEX_JS is not set\n');
    process.exit(2);
  }
  let katex;
  try {
    katex = await loadKatex(spec);
  } catch (err) {
    process.stderr.write(`cannot load KaTeX from ${spec}: ${err && err.message}\n`);
    process.exit(2);
  }
  if (process.argv.includes('--version')) {
    process.stdout.write(JSON.stringify({ katex: katex.version }) + '\n');
    return;
  }
  const items = JSON.parse(await readStdin() || '[]');
  const lastMacros = new Map();
  const failures = [];
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    let macros = it.macros;
    if (macros) lastMacros.set(it.paper, macros);
    else macros = lastMacros.get(it.paper) || {};
    try {
      katex.renderToString(String(it.tex), {
        displayMode: !!it.display,
        macros: Object.assign({}, macros),
        throwOnError: true,
        strict: 'ignore',
        trust: false,
        maxExpand: 2000,
        leqno: !!it.leqno,
        fleqn: !!it.fleqn,
      });
    } catch (err) {
      const msg = String((err && err.message) || err).replace(/\s+/g, ' ').slice(0, 300);
      failures.push({ index: i, paper: it.paper, error: msg });
    }
  }
  process.stdout.write(JSON.stringify({ katex: katex.version, checked: items.length, failures }) + '\n');
}

main().catch((err) => {
  process.stderr.write(String((err && err.stack) || err) + '\n');
  process.exit(1);
});
