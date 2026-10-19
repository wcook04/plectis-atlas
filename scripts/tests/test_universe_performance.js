'use strict';
// Counts fitting work through the production paint call and production label fitter.
// Canvas is deliberately replaced with a deterministic width metric: this measures
// cache work, not browser frame time or typographic fidelity.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../../site/assets/universe.js'), 'utf8');
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

async function loads() {
  const begin = source.indexOf('        validate(both[0], both[1]);');
  const finish = source.indexOf('\n      })\n      .then(function ()', begin);
  assert.ok(begin >= 0 && finish > begin);
  const boot = source.slice(begin, finish);
  const waiting = new Promise(() => {});
  let validated = false;
  const requestedFonts = [];
  const fonts = vm.createContext({
    both: [{}, {}], validate: () => { validated = true; }, ingest() {}, readFonts() {},
    SERIF: 'serif', SANS: 'sans', Promise, setTimeout() {},
    document: { fonts: { load: font => { requestedFonts.push(font); return waiting; }, ready: waiting } }
  });
  let ready = false;
  const readiness = vm.runInContext('(function () {' + boot + '\n})()', fonts);
  Promise.resolve(readiness).then(() => { ready = true; });
  for (let i = 0; i < 4; i++) await Promise.resolve();
  assert.equal(validated, true, 'baseline generation validation remains on readiness path');
  assert.equal(ready, true, 'map readiness does not depend on unresolved fonts');
  assert.equal(requestedFonts.length, 4, 'only upright serif and sans chart faces are warmed');
  assert.ok(requestedFonts.every(font => !font.includes('italic')), 'unused italic faces stay off the startup network');

  // Execute the actual startup continuation and its idle work. The default
  // release must not fetch the parts index; direct family links still do.
  const readyStart = source.indexOf('        widthCache = {};', finish);
  const readyEnd = source.indexOf('        if (document.fonts && document.fonts.addEventListener)', readyStart);
  const startup = source.slice(readyStart, readyEnd);
  for (const initial of [null, 'd:test', 'f:test']) {
    let parts = 0;
    const noop = () => {};
    const state = vm.createContext({
      widthCache: {}, weights: noop, W: 0, H: 0, readHash: () => initial,
      window: { history: { state: null }, requestIdleCallback: fn => fn() },
      setTimeout: fn => fn(), restoreViewPositions: noop, showView: noop, pendingY: null,
      obj: () => ({ kind: 'f' }), discOf: () => 0, shards: {}, failedShards: {},
      loadShard: () => Promise.resolve(), loadParts: () => { parts++; return Promise.resolve(); },
      select: noop, openPage: noop, sel: null, renderPanel: noop, statusEl: { hidden: false },
      root: { classList: { add: noop } }, resize: noop, chartTo: noop, restoreSearch: noop,
      chart: {}, trail: [], paint: noop, lastPlan: null
    });
    vm.runInContext(startup, state);
    assert.equal(parts, initial === 'f:test' ? 1 : 0, `${initial}: parts load only for a requested family`);
  }

  // A fresh typed search must load the object index alongside its query, so
  // paper/result/Lean hits keep opening inside the map before any family visit.
  const searchStart = source.indexOf('    function runSearch(restoring)');
  const searchEnd = source.indexOf('    /* ---- Events', searchStart);
  const searchBody = source.slice(searchStart, searchEnd);
  for (const backend of [true, false]) {
    let resolveParts, queries = 0, parts = 0, settled = false;
    const pending = new Promise(resolve => { resolveParts = resolve; });
    const state = vm.createContext({
      searchIn: { value: 'ErdosReciprocal' }, query: '', searchFolded: false,
      searchShown: { q: null }, rememberSearch() {},
      resultsEl: { classList: { remove() {} }, querySelectorAll: () => [], innerHTML: '' },
      window: { AtlasSearch: backend ? { query: () => { queries++; return Promise.resolve([]); } } : null },
      loadSearch: () => { queries++; return Promise.resolve([]); },
      loadParts: () => { parts++; return pending; },
      Promise, T: key => key, fmtNum: String, escapeHtml: x => x, draw() {}
    });
    vm.runInContext(searchBody, state);
    const result = state.runSearch().then(() => { settled = true; });
    await Promise.resolve();
    assert.equal(queries, 1, 'search starts without waiting for the object index');
    assert.equal(parts, 1, 'typed search requests its object index');
    assert.equal(settled, false, 'search waits for object ids before classifying navigation');
    resolveParts(); await result;
    assert.equal(settled, true);
  }

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

// Repeated count substitutions retain British formatting without constructing
// a locale formatter for every count on every chart layout.
{
  const begin = source.indexOf('  var numberFormat =');
  const end = source.indexOf('  /* ---- Colour', begin);
  let constructions = 0;
  const state = vm.createContext({ Intl: { NumberFormat: function (locale) { constructions++; return new Intl.NumberFormat(locale); } } });
  vm.runInContext(source.slice(begin, end), state);
  for (const n of [0, 1, 372, 16077, 1234.5, -1000, Infinity, NaN]) {
    for (let i = 0; i < 100; i++) assert.equal(state.fmtNum(n), n.toLocaleString('en-GB'));
  }
  assert.equal(constructions, 1, 'all numeric labels share one formatter');
  assert.equal(state.fmtNum('Family'), 'Family');
  console.log('universe counts: one shared formatter preserves en-GB output');
}
