'use strict';
// Counts fitting work through the production paint call and production label fitter.
// Canvas is deliberately replaced with a deterministic width metric: this measures
// cache work, not browser frame time or typographic fidelity.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../site/assets/universe.js'), 'utf8');
const start = source.indexOf('    function labelTokens(');
const end = source.indexOf('    function drawText(', start);
assert.ok(start >= 0 && end > start);
const paintCall = source.match(/var t = famLabel\(fj, ([^;]+?)\), f2 = fams\[fj\]\.data;/);
assert.ok(paintCall, 'production family label paint call is present');
let widths = 0;
const titles = ['Log abundance for compact Kähler spaces under logarithmic Iitaka subadditivity',
  'Function-field reconstruction from Milnor K-theory and Galois data',
  'Restricted geometric Langlands, global Arthur enhancements, and generic Ramanujan'];
const c = vm.createContext({
  D: { families: titles.map(title => ({ title })) }, labelCache: {}, SERIF: 'serif',
  clamp: (x, a, b) => Math.max(a, Math.min(b, x)),
  textWidth: (text, font) => { widths++; return text.length * parseFloat(font.split(' ')[1]) * 0.5; },
  chart: { start: 1, to: { nodes: titles.map(() => ({ r: 70 })) } }, moving: true,
  fams: titles.map(() => ({ data: {} })), n: {}, fj: 0
});
vm.runInContext(source.slice(start, end), c);
const call = `famLabel(fj, ${paintCall[1]})`;
let firstFrameWidths;
for (let frame = 0; frame < 30; frame++) {
  for (let i = 0; i < titles.length; i++) {
    c.fj = i; c.n = { r: 40 + frame * 1.01 };
    vm.runInContext(call, c);
  }
  if (frame === 0) firstFrameWidths = widths;
  else assert.equal(widths, firstFrameWidths, 'later animation frames perform no fresh fitting work');
}
assert.equal(Object.keys(c.labelCache).length, titles.length,
  'animation fits each family once at its stable target radius');
const warm = widths;
c.chart.start = 0; c.moving = false; c.n = { r: 70 };
for (let i = 0; i < titles.length; i++) { c.fj = i; vm.runInContext(call, c); }
assert.equal(widths, warm, 'settled paint reuses animation target fits');
// A tiny radius cannot fit even one glyph plus a discretionary hyphen. The real
// tokenizer must still consume input, rather than spinning on a negative limit.
const tiny = vm.runInContext("labelTokens('UnbreakableWord', 1)", c, { timeout: 1000 });
assert.ok(tiny.length > 0 && tiny.length <= 'UnbreakableWord'.length);
console.log(`universe performance: 30 frames, ${titles.length} cached family fits, ${widths} width calls`);

// A 15 px scrollbar can move the family board across its two/three-column
// threshold. The card width then changes the excerpt budget from 170 to 100.
// Layout must refresh the visible excerpt without rebuilding the whole board:
// that rebuild used to toggle the scrollbar and call syncBoard indefinitely.
function boardLayout() {
  const layoutStart = source.indexOf('    function layoutBoard()');
  const layoutEnd = source.indexOf('    function drawWires()', layoutStart);
  assert.ok(layoutStart >= 0 && layoutEnd > layoutStart);
  const cols = Array.from({ length: 14 }, () => ({ hidden: false, classList: { contains: () => false } }));
  const pagerControls = {
    '[data-u-page-n]': { textContent: '' },
    '[data-u-page="-1"]': { setAttribute() {}, disabled: false },
    '[data-u-page="1"]': { setAttribute() {}, disabled: false }
  };
  const pager = { hidden: false, querySelector: key => pagerControls[key] };
  let width = 740, excerptCalls = 0, katexCalls = 0, wireCalls = 0, rebuilds = 0;
  const resultCard = { getAttribute: key => key === 'data-bk' ? 'r:test' : 'p:test' };
  const x = {
    innerHTML: 'initial excerpt', clientWidth: 365, offsetHeight: 0, scrollWidth: 0,
    attrs: { 'data-u-budget': '170' },
    getAttribute(key) { return this.attrs[key]; },
    setAttribute(key, value) { this.attrs[key] = String(value); },
    closest: () => resultCard
  };
  const rc = { get clientWidth() { return width === 740 ? 365 : 231; } };
  const papersEl = {
    children: cols, style: {}, get clientWidth() { return width; },
    querySelector: () => rc
  };
  const boardEl = {
    querySelector: key => key === '[data-u-papers]' ? papersEl : key === '[data-u-pager]' ? pager : null,
    querySelectorAll: () => [x]
  };
  const board = { on: true, pending: false, fi: 33, per: 2, page: 2, cols: 14, budget: 170, sig: 'family-034' };
  const state = vm.createContext({
    board, boardEl, fams: Object.assign(Array(34).fill(null), { 33: { d: 1 } }),
    shards: { 1: { results: { 'r:test': { html: 'source statement' } } } },
    narrow: () => false, getComputedStyle: () => ({ fontSize: '16.8px' }),
    clamp: (v, lo, hi) => Math.max(lo, Math.min(hi, v)), T: key => key,
    excerpt: (html, budget) => { excerptCalls++; return { html: `${html}:${budget}`, cut: false }; },
    katexIn: () => { katexCalls++; }, drawWires: () => { wireCalls++; }, boardFontVersion: 0,
    syncBoard: () => { rebuilds++; throw new Error('layout re-entered syncBoard'); }
  });
  vm.runInContext(source.slice(layoutStart, layoutEnd), state);
  vm.runInContext('layoutBoard()', state, { timeout: 1000 });
  assert.equal(board.per, 2);
  assert.equal(board.page, 2);
  assert.deepEqual(cols.map((c, i) => c.hidden ? -1 : i).filter(i => i >= 0), [4, 5]);
  assert.equal(excerptCalls, 0, 'unchanged budget keeps the existing excerpt');
  width = 755;
  vm.runInContext('layoutBoard()', state, { timeout: 1000 });
  assert.equal(board.per, 3);
  assert.equal(board.page, 1, 'resize keeps the first previously visible column');
  assert.deepEqual(cols.map((c, i) => c.hidden ? -1 : i).filter(i => i >= 0), [3, 4, 5]);
  assert.equal(board.budget, 100);
  assert.equal(x.innerHTML, 'source statement:100');
  assert.equal(x.getAttribute('data-u-budget'), '100');
  width = 740;
  vm.runInContext('layoutBoard()', state, { timeout: 1000 });
  assert.equal(board.per, 2);
  assert.equal(board.budget, 170);
  assert.equal(x.innerHTML, 'source statement:170');
  assert.equal(excerptCalls, 2, 'each width change refreshes the visible excerpt once');
  assert.equal(katexCalls, 2);
  vm.runInContext('layoutBoard()', state, { timeout: 1000 });
  assert.equal(excerptCalls, 2, 'stable width does no extra excerpt work');
  board.page = 4;
  x.setAttribute('data-u-budget', 100); // a newly visible page still has its old budget
  delete x.attrs['data-u-fit'];
  vm.runInContext('layoutBoard()', state, { timeout: 1000 });
  assert.deepEqual(cols.map((c, i) => c.hidden ? -1 : i).filter(i => i >= 0), [8, 9]);
  assert.equal(x.innerHTML, 'source statement:170', 'pagination refreshes a stale visible excerpt');
  assert.equal(excerptCalls, 3);
  assert.equal(wireCalls, 5, 'wire placement follows each bounded layout');
  for (let i = 0; i < 100; i++) {
    width = i % 2 === 0 ? 755 : 740;
    vm.runInContext('layoutBoard()', state, { timeout: 1000 });
    assert.equal(board.budget, i % 2 === 0 ? 100 : 170);
  }
  assert.equal(excerptCalls, 103, '100 width flips perform 100 bounded excerpt refreshes');
  assert.equal(katexCalls, 103);
  assert.equal(wireCalls, 105);
  assert.equal(rebuilds, 0, 'layout never rebuilds or re-enters syncBoard');
  assert.equal(board.sig, 'family-034', 'excerpt width does not invalidate the board');
  console.log('universe board layout: 15 px width toggle, bounded excerpt refresh, no rebuild');
}
boardLayout();

// An excerpt that still overflows after six shortening attempts must not repeat
// those six KaTeX renders on every unrelated board refresh. A width or font
// change is a new fit and may try again.
function excerptFitMemo() {
  const begin = source.indexOf('    function fitExcerpts()');
  const end = source.indexOf('    function drawWires()', begin);
  assert.ok(begin >= 0 && end > begin);
  let width = 180, fontSize = '16px', excerptCalls = 0, katexCalls = 0;
  const card = { getAttribute: key => key === 'data-bk' ? 'r:test' : 'p:test' };
  const x = {
    innerHTML: 'initial', attrs: { 'data-u-budget': '170' },
    get clientWidth() { return width; }, offsetHeight: 999, scrollWidth: 999,
    getAttribute(key) { return this.attrs[key]; },
    setAttribute(key, value) { this.attrs[key] = String(value); },
    closest: () => card
  };
  const state = vm.createContext({
    board: { fi: 0, budget: 170 }, boardFontVersion: 0, fams: [{ d: 0 }],
    shards: { 0: { results: { 'r:test': { html: 'long source statement' } } } },
    boardEl: { querySelectorAll: () => [x] },
    getComputedStyle: () => ({ fontSize }),
    excerpt: (html, budget) => { excerptCalls++; return { html: `${html}:${budget}`, cut: true }; },
    katexIn: () => { katexCalls++; }
  });
  vm.runInContext(source.slice(begin, end), state);
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(excerptCalls, 6, 'first overflowing fit has a six-attempt ceiling');
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(excerptCalls, 6, 'identical geometry reuses the exhausted fit');
  width = 150;
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(excerptCalls, 13, 'changed width restores source, then permits six fit attempts');
  fontSize = '17px';
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(excerptCalls, 20, 'changed font restores source, then permits six fit attempts');
  state.boardFontVersion++;
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(excerptCalls, 27, 'font-load version restores source before refitting');
  assert.equal(katexCalls, excerptCalls);
  console.log('universe excerpts: exhausted fits are cached by width and font');
}
excerptFitMemo();

function excerptExpandsAtSameBudget() {
  const begin = source.indexOf('    function fitExcerpts()');
  const end = source.indexOf('    function drawWires()', begin);
  let width = 120, renders = 0;
  const card = { getAttribute: key => key === 'data-bk' ? 'r:test' : 'p:test' };
  const x = {
    innerHTML: 'source:170', attrs: { 'data-u-budget': '170' }, scrollWidth: 0,
    get clientWidth() { return width; },
    get offsetHeight() {
      const shown = Number(this.innerHTML.split(':')[1]);
      return width < 200 && shown > 80 ? 999 : 20;
    },
    getAttribute(key) { return this.attrs[key]; },
    setAttribute(key, value) { this.attrs[key] = String(value); },
    closest: () => card
  };
  const state = vm.createContext({
    board: { fi: 0, budget: 170 }, boardFontVersion: 0, fams: [{ d: 0 }],
    shards: { 0: { results: { 'r:test': { html: 'source' } } } },
    boardEl: { querySelectorAll: () => [x] },
    getComputedStyle: () => ({ fontSize: '16px', lineHeight: '24px' }),
    excerpt: (html, budget) => { renders++; return { html: `${html}:${budget}`, cut: budget < 170 }; },
    katexIn() {}
  });
  vm.runInContext(source.slice(begin, end), state);
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  const shortened = Number(x.innerHTML.match(/source:(\d+)/)[1]);
  assert.ok(shortened < 170, 'narrow card shortens the excerpt');
  assert.equal(state.board.budget, 170, 'fitting a card does not change the board budget');
  const narrowRenders = renders;
  width = 300;
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(x.innerHTML, 'source:170', 'wider card restores the full source at the same board budget');
  assert.equal(renders, narrowRenders + 1, 'expansion needs one source render');
  vm.runInContext('fitExcerpts()', state, { timeout: 1000 });
  assert.equal(renders, narrowRenders + 1, 'stable expanded geometry is cached');
  console.log('universe excerpts: narrow-to-wide card restores text at unchanged budget');
}
excerptExpandsAtSameBudget();

async function loads() {
  const begin = source.indexOf('        validate(both[0], both[1]);');
  const finish = source.indexOf('\n      })\n      .then(function ()', begin);
  assert.ok(begin >= 0 && finish > begin);
  const boot = source.slice(begin, finish);
  const waiting = new Promise(() => {});
  let validated = false;
  const fonts = vm.createContext({
    both: [{}, {}], validate: () => { validated = true; }, ingest() {}, readFonts() {},
    SERIF: 'serif', SANS: 'sans', Promise, setTimeout() {},
    document: { fonts: { load: () => waiting, ready: waiting } }
  });
  let ready = false;
  const readiness = vm.runInContext('(function () {' + boot + '\n})()', fonts);
  Promise.resolve(readiness).then(() => { ready = true; });
  for (let i = 0; i < 4; i++) await Promise.resolve();
  assert.equal(validated, true, 'baseline generation validation remains on readiness path');
  assert.equal(ready, true, 'map readiness does not depend on unresolved fonts');

  const selectStart = source.indexOf('    function select(key, opts)');
  const selectEnd = source.indexOf('      var o = key ? obj(key) : null;', selectStart);
  const clickPrefix = source.slice(selectStart, selectEnd) + '\n    }';
  const directStart = source.indexOf('          var initialFamily = obj(start);');
  const directEnd = source.indexOf('          loadParts().then(', directStart);
  assert.ok(directStart >= 0 && directEnd > directStart);
  for (const kind of ['clicked', 'direct']) {
    const events = [];
    const state = vm.createContext({
      selectionRequest: 0, historyBackPending: null, historySelection: null,
      partsReady: false, shards: {}, failedShards: {},
      statusEl: null, T: x => x, start: 'f:033',
      obj: () => ({ kind: 'f' }), discOf: () => 1,
      loadShard: () => { events.push('detail-start'); return waiting; },
      loadParts: () => { events.push('parts-start'); return waiting; }
    });
    if (kind === 'clicked') {
      vm.runInContext(clickPrefix, state); state.select('f:033', {});
    } else vm.runInContext(source.slice(directStart, directEnd) + 'loadParts();', state);
    assert.deepEqual(events, ['detail-start', 'parts-start'], `${kind}: both requests start before either resolves`);
  }
  console.log('universe loading: unresolved fonts do not block; clicked and direct families start detail + parts together');
}
loads().catch(error => { console.error(error); process.exitCode = 1; });
