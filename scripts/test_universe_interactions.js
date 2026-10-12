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
const click = range("    canvas.addEventListener('click',", '\n    if (cardEl)');
const shard = range('    function loadShard(di)', '    function detail(');
// Isolate the production admission/retry prefix from board DOM rendering.
const syncAdmission = range('    function syncBoard()', '      // The neighbours\' titles') + '\n    }';
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
  const c = context();
  vm.runInContext(hit, c);
  assert.equal(c.hitAt(20, 20, true), 'f:a', 'click can hit the visible moving family');
  let handler;
  c.canvas = { addEventListener: (name, fn) => { handler = fn; } };
  const selected = [];
  c.select = key => selected.push(key);
  vm.runInContext(click, c);
  handler({ x: 20, y: 20 });
  assert.deepEqual(selected, ['f:a'], 'moving-dot click selects its displayed family');
  handler({ x: 200, y: 200 });
  assert.equal(c.backCalls, 0, 'moving empty ground must not accidentally navigate back');
  c.chart.start = 0;
  handler({ x: 200, y: 200 });
  assert.equal(c.backCalls, 1, 'settled empty ground still navigates back');

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
