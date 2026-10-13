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

// Every paper column shows: the board wraps columns instead of paging them, and
// a width change only re-packs the columns. Layout never rebuilds the board:
// that rebuild used to toggle the scrollbar and call syncBoard indefinitely.
function boardLayout() {
  const layoutStart = source.indexOf('    function layoutBoard()');
  const layoutEnd = source.indexOf('    function drawWires()', layoutStart);
  assert.ok(layoutStart >= 0 && layoutEnd > layoutStart);
  const cols = Array.from({ length: 14 }, (_, i) => ({ hidden: i % 3 === 0, classList: { contains: () => false } }));
  let width = 740, wireCalls = 0, repositionCalls = 0, rebuilds = 0;
  const papersEl = { children: cols, style: {}, get clientWidth() { return width; } };
  const boardEl = { querySelector: key => key === '[data-u-papers]' ? papersEl : null };
  const board = { on: true, pending: false, fi: 33, per: 2, sig: 'family-034' };
  const state = vm.createContext({
    board, boardEl, narrow: () => false, getComputedStyle: () => ({ fontSize: '16.8px' }),
    drawWires: () => { wireCalls++; },
    repositionBoardCard: () => { repositionCalls++; },
    syncBoard: () => { rebuilds++; throw new Error('layout re-entered syncBoard'); }
  });
  vm.runInContext(source.slice(layoutStart, layoutEnd), state);
  const shown = () => cols.filter(c => !c.hidden).length;
  vm.runInContext('layoutBoard()', state, { timeout: 1000 });
  assert.equal(board.per, 2);
  assert.equal(shown(), 14, 'every paper column shows');
  assert.equal(papersEl.style.columnCount, '2');
  for (let i = 0; i < 100; i++) {
    width = i % 2 === 0 ? 755 : 740;
    vm.runInContext('layoutBoard()', state, { timeout: 1000 });
    assert.equal(board.per, i % 2 === 0 ? 3 : 2);
    assert.equal(shown(), 14, 'a resize hides no column');
  }
  assert.equal(wireCalls, 101, 'wire placement follows each layout');
  assert.equal(repositionCalls, 101, 'every board layout repositions a visible preview');
  assert.equal(rebuilds, 0, 'layout never rebuilds or re-enters syncBoard');
  assert.equal(board.sig, 'family-034', 'width does not invalidate the board');
  console.log('universe board layout: every column shows, width only re-packs, no rebuild');
}
boardLayout();

// Dense boards generate many nested pointerover events for the same card. The
// visible preview should retain its placement until its source, mode, packet,
// or geometry changes; each full placement reads every nearby card's bounds.
function boardPreviewPlacement() {
  const begin = source.indexOf('    function hideBoardCard(dismiss)');
  const end = source.indexOf('    var boardClick = null,', begin);
  assert.ok(begin >= 0 && end > begin, 'production board-card handlers are present');
  let rectReads = 0, timerClears = 0, wireDraws = 0, htmlWrites = 0;
  const stageSize = { width: 1100, height: 760 };
  const bounds = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, width, height });
  const sourceCard = (left, key = 'f:near') => ({
    getAttribute: attr => attr === 'data-bk' ? key : null,
    getBoundingClientRect: () => { rectReads++; return bounds(left, 320, 130, 90); },
    closest: () => null,
    classList: { contains: () => false }
  });
  const first = sourceCard(930), second = sourceCard(580);
  const neighbours = Array.from({ length: 35 }, (_, i) => sourceCard(60 + i * 20, `f:other-${i}`));
  const classes = new Set();
  const cardEl = {
    offsetWidth: 300, offsetHeight: 200, style: {},
    classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
    querySelector: () => null,
    set innerHTML(html) { htmlWrites++; this.html = html; }, get innerHTML() { return this.html; }
  };
  const board = { on: true, hoverKey: null, hoverVia: '', hoverEl: null, dismissedKey: null, hideT: null };
  const state = vm.createContext({
    Math, Array, board, boardEl: {
      querySelectorAll: () => [first, second, ...neighbours],
      contains: el => el === first || el === second || neighbours.includes(el)
    }, cardEl,
    stage: { getBoundingClientRect: () => { rectReads++; return bounds(0, 0, stageSize.width, stageSize.height); } },
    hoverMQ: { matches: true }, narrow: () => false,
    shards: {}, obj: key => ({ key }), discOf: () => 0,
    cardKey: '', cardOn: false, cardBox: null,
    clearTimeout: () => { timerClears++; }, hideCard: () => { state.cardOn = false; },
    drawWires: () => { wireDraws++; }, boardCardHtml: key => `${key}:${state.shards[0]?.version || 'loading'}`,
    katexIn() {}, overlap: () => 0,
    clamp: (value, lo, hi) => Math.max(lo, Math.min(hi, value))
  });
  vm.runInContext(source.slice(begin, end), state);
  state.showBoardCard(first, 'pointer');
  const initialReads = rectReads;
  assert.ok(initialReads > 35, 'first placement measures the dense board');
  board.hideT = 123;
  for (let i = 0; i < 50; i++) state.showBoardCard(first, 'pointer');
  assert.equal(rectReads, initialReads, 'unchanged visible card avoids repeated full-board measurements');
  assert.ok(timerClears >= 51, 're-entry still cancels a pending hide');
  assert.equal(htmlWrites, 1, 'unchanged card retains its typeset preview');

  const firstBox = state.cardBox;
  state.showBoardCard(second, 'pointer');
  assert.ok(rectReads > initialReads, 'a distinct DOM card with the same key gets a new placement');
  assert.notEqual(state.cardBox.x0, firstBox.x0, 'placement follows the actual source card');
  const afterSecond = rectReads;
  state.showBoardCard(second, 'focus');
  assert.ok(rectReads > afterSecond, 'focus mode gets its own placement');
  const beforePacket = htmlWrites;
  state.shards[0] = { version: 'ready-a' };
  state.showBoardCard(second, 'focus');
  assert.equal(htmlWrites, beforePacket + 1, 'new detail packet refreshes preview content');

  stageSize.width = 780;
  state.repositionBoardCard();
  assert.ok(state.cardBox.x0 >= 8 && state.cardBox.x1 <= stageSize.width - 8,
    'forced layout placement keeps the preview inside the narrowed stage');
  state.hideBoardCard();
  assert.equal(board.hoverEl, null, 'hide releases the preview source element');
  board.dismissedKey = 'f:near';
  const beforeDismissedReads = rectReads;
  state.showBoardCard(second, 'pointer');
  assert.equal(rectReads, beforeDismissedReads, 'dismissed card does not resurrect under stationary pointer');
  assert.equal(board.hoverKey, null);
  assert.ok(wireDraws >= 1);
  console.log('universe board preview: nested hover re-entry is cached; invalidations and bounds are respected');
}
boardPreviewPlacement();


// Repeated pointer/selection work must share one completion watcher per pending
// shard. The former syncBoard registered 50 own callbacks and then 100 neighbour
// callbacks after only 50 calls while both shards were pending.
async function boardShardCallbacks() {
  const syncStart = source.indexOf('    function syncBoard()');
  const syncEnd = source.indexOf('      var sig = fi +', syncStart);
  assert.ok(syncStart >= 0 && syncEnd > syncStart);
  const watchStart = source.lastIndexOf('    var boardShardWaiting = {};', syncStart);
  const admission = (watchStart >= 0 ? source.slice(watchStart, syncStart) : '') +
    source.slice(syncStart, syncEnd) + '\n    }';
  const deferred = () => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
  };
  const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  function fixture() {
    const packets = [deferred(), deferred()];
    const calls = { sync: 0, loads: [0, 0], hides: 0 };
    let family = 0;
    const state = vm.createContext({
      Promise, boardEl: {}, board: { fi: 0, on: true },
      D: { families: [{ cites: [[1]], citedBy: [] }] },
      fams: [{ d: 0 }, { d: 1 }], shards: {}, failedShards: {}, shardLoading: {},
      boardFamily: () => family,
      hideBoard: () => { calls.hides++; state.board.on = false; },
      loadShard: di => { calls.loads[di]++; return packets[di].promise; }
    });
    vm.runInContext(admission, state);
    const original = state.syncBoard;
    state.syncBoard = () => { calls.sync++; return original(); };
    return { state, calls, packets, navigateOut: () => { family = -1; state.syncBoard(); } };
  }
  const active = fixture();
  for (let i = 0; i < 50; i++) active.state.syncBoard();
  assert.equal(active.calls.sync, 50);
  assert.deepEqual(active.calls.loads, [1, 1], '50 interactions share each pending shard request');
  active.state.shards[0] = {};
  active.packets[0].resolve({});
  await flush();
  assert.equal(active.calls.sync, 51, 'own completion schedules only one current-family board sync');
  assert.deepEqual(active.calls.loads, [1, 1], 'own completion does not add neighbour watchers');
  active.state.shards[1] = {};
  active.packets[1].resolve({});
  await flush();
  assert.equal(active.calls.sync, 52, 'neighbour completion schedules only one board sync');

  const stale = fixture();
  for (let i = 0; i < 50; i++) stale.state.syncBoard();
  stale.navigateOut();
  const beforeStale = stale.calls.sync;
  stale.state.shards[0] = {};
  stale.packets[0].resolve({});
  stale.state.shards[1] = {};
  stale.packets[1].resolve({});
  await flush();
  assert.equal(stale.state.board.on, false, 'departing the family hides its board');
  assert.equal(stale.calls.sync, beforeStale, 'stale shard completions cannot reopen or redraw the departed board');

  const retry = fixture();
  for (let i = 0; i < 50; i++) retry.state.syncBoard();
  retry.state.failedShards[0] = true;
  retry.packets[0].reject(new Error('temporary detail failure'));
  await flush();
  assert.equal(retry.calls.sync, 51, 'one failed own shard causes one failed-state board sync');
  for (let i = 0; i < 50; i++) retry.state.syncBoard();
  assert.equal(retry.calls.loads[0], 1, 'failed detail is not automatically retried');
  retry.packets[0] = deferred();
  delete retry.state.failedShards[0]; // explicit selection admits another attempt
  for (let i = 0; i < 50; i++) retry.state.syncBoard();
  assert.equal(retry.calls.loads[0], 2, 'explicit retry starts one replacement request');
  retry.state.shards[0] = {};
  retry.packets[0].resolve({});
  await flush();
  assert.equal(retry.calls.sync, 152, 'retry completion also schedules one bounded board sync');
  console.log('universe board shards: pending callbacks coalesce; stale and failed completions stay bounded');
}

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
Promise.all([loads(), boardShardCallbacks()]).catch(error => { console.error(error); process.exitCode = 1; });
