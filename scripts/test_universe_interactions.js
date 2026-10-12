/* Exercise production map handlers with deterministic state and deferred network replies. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../site/assets/universe.js'), 'utf8');
function range(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `production range missing: ${start}`);
  return source.slice(a, b);
}
const hit = range('    function hitAt(', '\n    /* ---- The card:');
const load = range('    function loadParts()', '    function obj(');
const select = range('    function select(key, opts)', '    // A paper, theorem or Lean statement');
const click = range("    canvas.addEventListener('pointerdown',", '\n    if (cardEl)');
const shard = range('    function loadShard(di)', '    function detail(');
// Isolate the production admission/retry prefix from board DOM rendering.
const syncAdmission = range('    function syncBoard()', '      // The neighbours\' titles') + '\n    }';
const boardVisibility = range('    function showBoard()', '    // The chosen card gets');
const chartNavigation = range('    function copyLayout(l)', '    function chartAnimating()');
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
function context(extra = {}) {
  const families = [{ id: 'f:a' }, { id: 'f:b' }];
  const objects = new Map(families.map((f, i) => [f.id, { key: f.id, kind: 'f', i }]));
  objects.set('d:test', { key: 'd:test', kind: 'd', i: 0 });
  const c = vm.createContext({
    Promise, Math, console, partsPromise: null, partsReady: false, partsFailed: false, selectionRequest: 0,
    statusEl: { textContent: '', hidden: true }, T: key => key,
    failedShards: {}, discOf: () => 0,
    mapPress: null, lastPointerType: '',
    D: { generation_id: 'g', families, papers: [], results: [], lean: [] },
    L: { results: [], lean: [], papers: [] }, fams: families,
    chart: { start: 1, shown: { level: 'disc', nodes: [
      { x: 20, y: 20, r: 10, a: 1 }, { x: 60, y: 20, r: 10, a: 1 }
    ], regions: [] } },
    root: { getAttribute: () => 'map' }, obj: key => objects.get(key),
    sel: 'd:test', board: {}, pendingBoard: null, pendingViewSwitch: null,
    pendingY: null, pin: -1, hover: null, hoverVia: '', cardDismissed: null,
    ring: null, ringWanted: null, reduceMotion: false, trail: [], liveEl: { textContent: '' },
    savedScrollPos: () => 0, boardPosition: () => null, viewPositions: () => ({}),
    restoreViewPositions() {}, setReading() {}, renderPanel() {}, updateHash() {},
    chartTo() {}, narrow: () => false, nameOf: o => o.key, draw() {}, addObj() {},
    localXY: e => [e.x, e.y], backCalls: 0,
    ...extra
  });
  c.stepBack = () => { c.backCalls++; };
  return c;
}
const packet = () => ({ generation_id: 'g', papers: [], results: [], lean: [] });
async function flush() { for (let i = 0; i < 6; i++) await Promise.resolve(); }
async function main() {
  for (const [from, to, moving] of [
    ['fam', 'disc', false], ['fam', 'release', false],
    ['release', 'disc', true], ['disc', 'fam', false]
  ]) {
    const layout = level => ({ level, nodes: [{ x: level === 'fam' ? 50 : 100, y: 20, r: 10, a: 1 }], regions: [] });
    const target = { level: to, di: to === 'disc' ? 0 : -1, fi: to === 'fam' ? 0 : -1 };
    const nav = context({
      W: 200, H: 100, stage: null, chrome: [], CHART_MS: 280, nowMs: () => 100,
      chart: { level: from, di: -1, fi: -1, start: 0, shown: layout(from) },
      chartTarget: () => target, chromeBoxes: () => [],
      releaseLayout: () => layout('release'), discLayout: () => layout('disc'), famLayout: () => layout('fam'),
      board: { pending: false }, showBoard() {}
    });
    vm.runInContext(chartNavigation, nav);
    nav.chartTo(true);
    assert.equal(!!nav.chart.start, moving, `${from} to ${to}: intended animation policy`);
    assert.equal(nav.chart.to.level, to);
    if (!moving) {
      assert.equal(nav.chart.shown.level, to, 'snap publishes target hit geometry immediately');
      assert.notEqual(nav.chart.shown.nodes, nav.chart.to.nodes, 'shown geometry is copied');
    }
  }
  const attributes = new Map(), classes = new Set(['is-on']);
  const boardState = context({
    board: { on: true, pending: true, fi: 0, sig: 'old' },
    boardEl: {
      setAttribute: (k, v) => attributes.set(k, v), removeAttribute: k => attributes.delete(k),
      classList: { add: k => classes.add(k), remove: k => classes.delete(k) }
    },
    root: { setAttribute() {}, removeAttribute() {} },
    hideCard() {}, hideBoardCard() {}, layoutBoard() {}, ringBoard() {},
    restoreBoardPosition() {}, revealBoardSelection() {}
  });
  vm.runInContext(boardVisibility, boardState);
  boardState.hideBoard();
  assert.equal(attributes.has('inert'), true, 'outgoing board immediately disables interaction');
  assert.equal(classes.has('is-on'), false);
  assert.equal(boardState.board.pending, false, 'hide cancels pending display');
  boardState.showBoard();
  assert.equal(attributes.has('inert'), true, 'canceled pending board cannot reopen');
  boardState.board.pending = true;
  boardState.showBoard();
  assert.equal(attributes.has('inert'), false, 'fresh visible board regains interaction');
  assert.equal(classes.has('is-on'), true);
  boardState.board.on = false; boardState.board.pending = true;
  boardState.hideBoard();
  assert.equal(attributes.has('inert'), true, 'even not-yet-visible board becomes inert');
  assert.equal(boardState.board.pending, false);
  const c = context();
  vm.runInContext(hit, c);
  assert.equal(c.hitAt(20, 20, true), 'f:a', 'click can hit the visible moving family');
  const handlers = {};
  c.canvas = { addEventListener: (name, fn) => { handlers[name] = fn; } };
  const selected = [];
  c.select = key => selected.push(key);
  vm.runInContext(click, c);
  const event = (x, y) => ({ x, y, button: 0, isPrimary: true, pointerType: 'mouse' });
  const handler = (e) => handlers.click(e);
  handler(event(20, 20));
  assert.deepEqual(selected, ['f:a'], 'moving-dot click selects its displayed family');
  handler({ x: 200, y: 200 });
  assert.equal(c.backCalls, 0, 'moving empty ground must not accidentally navigate back');
  c.chart.start = 0;
  handler({ x: 200, y: 200 });
  assert.equal(c.backCalls, 1, 'settled empty ground still navigates back');

  c.chart.start = 1;
  handlers.pointerdown(event(20, 20));
  c.chart.shown.nodes[0].x = 100;
  c.chart.shown.nodes[1].x = 20;
  handler(event(20, 20));
  assert.equal(selected.at(-1), 'f:a', 'moving press retains the family pressed, not the new family underneath');
  assert.equal(c.mapPress, null, 'press is consumed');
  handlers.pointerdown(event(200, 200));
  c.chart.shown.nodes[1] = { x: 200, y: 200, r: 10, a: 1 };
  const beforeGround = selected.length;
  c.chart.start = 0;
  handler(event(200, 200));
  assert.equal(selected.length, beforeGround, 'moving ground press does not select a newly arrived target');
  assert.equal(c.backCalls, 1, 'moving ground press does not back out after motion ends');
  c.chart.shown.nodes[0] = { x: 20, y: 20, r: 10, a: 1 };
  handlers.pointerdown(event(20, 20));
  const beforeDrag = selected.length;
  handler(event(40, 20));
  assert.equal(selected.length, beforeDrag, 'drag beyond click tolerance does not navigate');
  assert.equal(c.backCalls, 1, 'drag to ground does not navigate back');
  handlers.pointerdown(event(20, 20));
  assert.equal(typeof handlers.pointercancel, 'function', 'cancel handler registered');
  handlers.pointercancel(event(20, 20));
  assert.equal(c.mapPress, null, 'canceled press is not retained');
  handler(event(200, 200));
  assert.equal(selected.at(-1), 'f:b', 'next independent click does not reuse canceled family press');
  handlers.pointerdown(event(20, 20));
  c.sel = 'f:b';
  const beforeChangedSelection = selected.length;
  handler(event(20, 20));
  assert.equal(selected.length, beforeChangedSelection, 'selection changes invalidate an outstanding press');
  c.chart.shown.nodes[0].a = 0.01;
  assert.equal(c.hitAt(20, 20, true), 'f:a', 'faint but painted circle remains clickable');
  c.chart.shown.nodes[0].a = 0.009;
  assert.equal(c.hitAt(20, 20, true), null, 'invisible circle is excluded');

  let requests = 0;
  const caches = [];
  const retry = context({ fetchJson: (url, cache) => {
    caches.push(cache);
    requests++;
    return requests === 1 ? Promise.reject(new Error('temporary failure')) : Promise.resolve(packet());
  } });
  vm.runInContext(load, retry);
  await assert.rejects(retry.loadParts(), /temporary failure/);
  await retry.loadParts();
  assert.equal(requests, 2, 'failed parts request is retried');
  assert.deepEqual(caches, ['default', 'reload'], 'network retry bypasses cached packets');
  assert.equal(retry.partsReady, true);

  const mismatchCaches = [];
  const mismatch = context({ fetchJson: (url, cache) => {
    mismatchCaches.push(cache);
    return Promise.resolve(mismatchCaches.length === 1 ? { ...packet(), generation_id: 'old' } : packet());
  } });
  vm.runInContext(load, mismatch);
  await assert.rejects(mismatch.loadParts(), /another build/);
  assert.equal(mismatch.partsPromise, null, 'validation rejection also releases cached promise');
  await mismatch.loadParts();
  assert.deepEqual(mismatchCaches, ['default', 'reload'], 'generation retry bypasses cached packets');
  assert.equal(mismatch.partsReady, true);

  let attempts = 0;
  const feedback = context({ fetchJson: () => ++attempts === 1 ?
    Promise.reject(new Error('offline')) : Promise.resolve(packet()) });
  vm.runInContext(load + select, feedback);
  feedback.select('f:a');
  assert.equal(feedback.statusEl.textContent, 'status.parts_loading');
  assert.equal(feedback.statusEl.hidden, false);
  await flush();
  assert.equal(feedback.statusEl.textContent, 'status.parts_failed');
  feedback.select('f:a');
  await flush();
  assert.equal(feedback.sel, 'f:a');
  assert.equal(feedback.statusEl.hidden, true, 'successful retry clears failure status');

  for (const latest of ['f:b', 'd:test', null]) {
    const reply = deferred();
    const race = context({ fetchJson: () => reply.promise });
    vm.runInContext(load + select, race);
    race.select('f:a', { trail: true });
    race.select(latest, { trail: true });
    reply.resolve(packet());
    await flush();
    assert.equal(race.sel, latest, `latest selection wins over deferred family: ${latest}`);
    assert.ok(!race.trail.some(t => t.key === 'f:a'), 'superseded selection leaves no trail entry');
  }
  for (const failure of ['network', 'generation']) {
    let detailRequests = 0;
    const detailCaches = [];
    const detailState = context({
      partsReady: true, shards: {}, shardLoading: {}, failedShards: {},
      boardEl: {}, boardFamily: () => 0, hideBoard() {}, discOf: () => 0,
      fetchJson: (url, cache) => {
        detailCaches.push(cache);
        detailRequests++;
        // Bound a broken recursive retry so this regression cannot itself hang Node.
        if (detailRequests > 5) return new Promise(() => {});
        if (detailRequests === 1) return failure === 'network' ?
          Promise.reject(new Error('offline detail')) : Promise.resolve({ generation_id: 'old' });
        return Promise.resolve({ generation_id: 'g' });
      }
    });
    detailState.fams[0].d = 0;
    vm.runInContext(shard + syncAdmission + select, detailState);
    await assert.rejects(detailState.loadShard(0));
    assert.equal(detailState.failedShards[0], true, `${failure} is classified as failed detail`);
    assert.equal(detailState.shardLoading[0], null, 'rejected detail promise is released');
    detailState.syncBoard();
    detailState.syncBoard();
    detailState.syncBoard();
    await flush();
    assert.equal(detailRequests, 1, 'board redraw does not automatically retry failed detail');
    detailState.renderPanel = () => detailState.syncBoard();
    detailState.select('f:a', { trail: true });
    await flush();
    assert.equal(detailRequests, 2, 'explicit selection admits exactly one detail retry');
    assert.deepEqual(detailCaches, ['default', 'reload'], 'failed detail retry bypasses browser cache');
    assert.equal(detailState.shards[0].generation_id, 'g');
  }
  console.log('universe interactions: moving hits, ground clicks, parts retry and latest-selection races pass');
}
main().catch(err => { console.error(err); process.exitCode = 1; });
