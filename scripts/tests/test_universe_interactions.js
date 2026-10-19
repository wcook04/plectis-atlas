/* Exercise production map handlers with deterministic state and deferred network replies. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../site/assets/universe.js'), 'utf8');
function range(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `production range missing: ${start}`);
  return source.slice(a, b);
}
const hit = range('    function hitAt(', '\n    /* ---- The card:');
const previewGuard = range('    function guardPreviewClicks(el)', '    if (stage) {');
const wires = range('    function drawWires()', '    function markBoard()');
const load = range('    function loadParts()', '    function obj(');
const select = range('    function select(key, opts)', '    // A paper, theorem or Lean statement');
const click = range("    canvas.addEventListener('pointerdown',", '\n    if (cardEl)');
const shard = range('    function loadShard(di)', '    function detail(');
// Isolate the production admission/retry prefix from board DOM rendering.
const syncAdmission = range('    var boardShardWaiting = {};', '      // The neighbours\' titles') + '\n    }';
const boardVisibility = range('    function showBoard()', '    // The chosen card gets');
const boardPages = range('    function layoutPages()', '    function showBoard()');
const boardSync = range('    function refreshBoardNeighbours()', '    function showBoard()');
const boardPointer = range("    if (boardEl) {\n      boardEl.addEventListener('pointerdown'", "      boardEl.addEventListener('pointerover'") + '    }';
const boardRepeat = range('    var boardClick = null, boardRepeatPress = null, boardDoubleOpened = false;', '    function selectFromBoard(key)');
const documentKeys = range("    document.addEventListener('keydown', function (e) {", "    window.addEventListener('hashchange'");
const stepperRender = range('    function renderStepper(o)', '    function scopeName(o)');
const listPreview = range("    root.addEventListener('pointerover', function (e) {", '    function showView(v, restoring)');
const detailAgain = range('          var again = function () {', '          watchPanelShard(di, again);');
const panelWatch = range('    function watchPanelShard(di, again)', '    function renderPanel(quiet)');
const hashState = range('    function updateHash(', '    function panelScroller()');
const backSteps = range('    function stepBack()', '    function selectAncestor(');
const ancestorStep = range('    function selectAncestor(', '    function openPage(');
const popstate = range("    window.addEventListener('popstate'", '    // Leaving for a paper or a family page');
const pagehide = range("    window.addEventListener('pagehide'", '    function readHash()');
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
    shards: {}, loadShard: () => Promise.resolve({}),
    mapPress: null, lastPointerType: '',
    D: { generation_id: 'g', families, papers: [], results: [], lean: [] },
    L: { results: [], lean: [], papers: [] }, fams: families,
    chart: { start: 1, shown: { level: 'disc', nodes: [
      { x: 20, y: 20, r: 10, a: 1 }, { x: 60, y: 20, r: 10, a: 1 }
    ], regions: [] } },
    root: { getAttribute: () => 'map' }, window: { scrollTo() {} }, obj: key => objects.get(key),
    sel: 'd:test', board: {}, pendingBoard: null, pendingViewSwitch: null,
    historyBackPending: null, historySelection: null,
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
  function historyFixture(start = 'd:test') {
    const listeners = {}, location = { pathname: '/atlas', search: '', hash: '#o=' + encodeURIComponent(start) };
    const entries = [{ hash: location.hash, state: { o: start, uPrev: null, v: 'map', y: 8 } }];
    let index = 0, backCalls = 0, pendingBack = false, focused = 0;
    const history = {
      get state() { return entries[index].state; },
      replaceState(state, _unused, url) {
        entries[index] = { hash: url ? url.slice(url.indexOf('#')) : entries[index].hash, state };
        location.hash = entries[index].hash;
      },
      pushState(state, _unused, url) {
        entries.splice(index + 1);
        entries.push({ hash: url.slice(url.indexOf('#')), state });
        index++; location.hash = entries[index].hash;
      },
      back() { backCalls++; pendingBack = true; }
    };
    const rendered = [];
    const state = context({
      window: { history, location, addEventListener: (type, fn) => { listeners[type] = fn; }, scrollTo() {} },
      sel: start, partsReady: true, board: {}, searchFolded: false, phoneViewY: { map: 0, list: 0 },
      historyBackPending: null, historySelection: null,
      root: { getAttribute: () => 'map' },
      readHash: () => location.hash ? decodeURIComponent(location.hash.slice(3)) : null,
      parentKey: () => 'd:test',
      savedScrollPos: () => 27, viewPositions: () => ({ map: 27, list: 0 }),
      boardPosition: () => null,
      renderPanel: () => { rendered.push(state.sel); },
      showView() {}, restoreSearch() {}, restorePending() {}, restoreBoardPosition() {},
      focusArrival: () => { focused++; }
    });
    vm.runInContext(hashState + select + backSteps + ancestorStep + popstate + pagehide, state);
    return {
      state, history, entries, location, rendered, listeners,
      get backCalls() { return backCalls; }, get focused() { return focused; },
      deliverBack() {
        assert.equal(pendingBack, true, 'a browser traversal was requested');
        pendingBack = false; index--;
        location.hash = entries[index].hash;
        listeners.popstate({ state: history.state });
      }
    };
  }
  const historyWalk = historyFixture();
  historyWalk.state.select('f:a', { trail: true });
  assert.equal(historyWalk.entries[1].state.uPrev, 'd:test', 'first map visit records its predecessor');
  historyWalk.state.select('f:b', { trail: true });
  assert.equal(historyWalk.entries[2].state.uPrev, 'f:a', 'nested map visit records its predecessor');
  historyWalk.listeners.pagehide();
  assert.equal(historyWalk.history.state.uPrev, 'f:a', 'pagehide scroll receipt preserves predecessor');
  assert.equal(historyWalk.history.state.y, 27);
  historyWalk.state.stepBack();
  historyWalk.state.stepBack();
  assert.equal(historyWalk.backCalls, 1, 'repeated back while popstate is pending is ignored');
  assert.equal(historyWalk.state.sel, 'f:b', 'selection waits for browser history traversal');
  historyWalk.state.select('d:test', { trail: true });
  historyWalk.state.select('f:b', { trail: true });
  assert.equal(historyWalk.history.state.o, 'f:b', 'selection during pending back does not race the URL');
  historyWalk.deliverBack();
  assert.deepEqual(historyWalk.rendered.slice(-2), ['f:a', 'f:b'], 'popstate settles before latest queued selection');
  assert.equal(historyWalk.state.sel, 'f:b');
  assert.equal(historyWalk.state.trail.length, 2, 'expected popstate keeps the in-map trail');
  assert.equal(historyWalk.focused, 1, 'back traversal restores focus');
  historyWalk.history.replaceState({ ...historyWalk.history.state, uPrev: 'external' }, '');
  const pushesBeforeAncestor = historyWalk.entries.length;
  historyWalk.state.stepBack();
  assert.equal(historyWalk.backCalls, 1, 'nonmatching predecessor does not leave the site');
  assert.equal(historyWalk.state.sel, 'f:a', 'nonmatching predecessor opens the map ancestor');
  assert.equal(historyWalk.history.state.uPrev, 'f:b');
  assert.equal(historyWalk.entries.length, pushesBeforeAncestor + 1, 'ancestor is a new browser entry');

  const replacedVisit = historyFixture();
  replacedVisit.state.select('f:a', { trail: true });
  replacedVisit.state.select('f:b', {});
  assert.equal(replacedVisit.history.state.uPrev, 'd:test', 'nonpush hash update preserves predecessor');
  assert.equal(replacedVisit.entries.length, 2, 'nonpush update replaces the current visit');

  const queuedAncestor = historyFixture();
  queuedAncestor.state.select('f:a', { trail: true });
  queuedAncestor.state.select('f:b', { trail: true });
  queuedAncestor.state.stepBack();
  queuedAncestor.state.selectAncestor('d:test');
  queuedAncestor.deliverBack();
  assert.equal(queuedAncestor.state.sel, 'd:test', 'breadcrumb click during pending back is replayed');
  assert.equal(queuedAncestor.location.hash, '#o=d%3Atest');
  const deepLink = historyFixture('f:a');
  deepLink.state.stepBack();
  assert.equal(deepLink.backCalls, 0, 'direct deep link does not traverse to a previous website');
  assert.equal(deepLink.state.sel, 'd:test', 'direct deep link steps to its map parent');
  assert.equal(deepLink.history.state.uPrev, 'f:a');

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
  // Async detail replies can ask the board to lay out again; every column already
  // shows, so a layout only records the selection it was drawn for.
  let pageLayouts = 0;
  const chosenPage = context({
    board: { on: false, pending: true, fi: 0, per: 2, revealKey: null, selectionKey: 'd:test' },
    layoutBoard: () => { pageLayouts++; }
  });
  vm.runInContext(boardPages, chosenPage);
  chosenPage.sel = 'f:a';
  chosenPage.layoutPages();
  assert.ok(pageLayouts > 0, 'board layout still runs for asynchronous updates');
  assert.equal(chosenPage.board.on, false, 'temporary layout visibility is restored');
  assert.equal(chosenPage.board.selectionKey, 'f:a');

  // A neighbour packet enriches only its side card. The whole board and its
  // focused controls stay in place; the own-family packet may rebuild but
  // restores the same card after replacement.
  let rebuilds = 0, enriched = 0;
  const title = { innerHTML: 'old title' };
  const sideAttrs = { 'data-g': '1', 'data-bk': 'f:b' };
  const sideCard = {
    getAttribute: key => sideAttrs[key] || null,
    setAttribute: (key, value) => { sideAttrs[key] = String(value); },
    querySelector: key => key === '.u-bc__ft' ? title : null
  };
  const doc = { activeElement: null };
  const replacement = {
    getAttribute: key => key === 'data-bk' ? 'r:chosen' : null,
    querySelectorAll: () => [], closest: () => null,
    focus: () => { doc.activeElement = replacement; }
  };
  const oldCard = {
    getAttribute: key => key === 'data-bk' ? 'r:chosen' : null,
    closest: key => key === '[data-bk]' ? oldCard : null
  };
  const boardEl = {
    scrollTop: 75,
    set innerHTML(value) { rebuilds++; doc.activeElement = null; this.html = value; },
    get innerHTML() { return this.html; },
    contains: el => el === sideCard || el === oldCard,
    querySelectorAll: key => key === '.u-bc--f' ? [sideCard] : key === '[data-bk]' ? [replacement] : []
  };
  const boardState2 = context({
    D: { families: [{ id: 'f:a', cites: [[1, 1]], citedBy: [] }, { id: 'f:b', cites: [], citedBy: [] }] },
    fams: [{ d: 0 }, { d: 1 }], sel: 'f:a', boardEl, document: doc,
    board: { fi: 0, sig: '0|1', on: true, pending: false, per: 2,
      selectionKey: 'f:a', ringKey: null },
    shards: { 0: {} }, failedShards: { 1: true },
    boardFamily: () => 0, boardHtml: () => '<replacement board>',
    typesetBoard() {}, hideBoardCard() {}, markBoard() {}, layoutBoard() {},
    ringBoard() {}, restoreBoardPosition() {}, revealBoardSelection() {},
    katexIn: () => { enriched++; }, loadShard: () => Promise.resolve({})
  });
  vm.runInContext(boardSync, boardState2);
  doc.activeElement = sideCard;
  boardState2.syncBoard();
  boardState2.shards[1] = { families: { 'f:b': { titleHtml: 'ready title' } } };
  boardState2.syncBoard();
  assert.equal(rebuilds, 0, 'neighbour readiness does not rebuild papers');
  assert.equal(title.innerHTML, 'ready title');
  assert.equal(sideAttrs['data-u-detail'], 'ready');
  assert.equal(enriched, 1, 'new side title is typeset once');
  assert.equal(doc.activeElement, sideCard, 'neighbour refresh retains card focus');
  boardState2.board.sig = '0|0';
  doc.activeElement = oldCard;
  boardState2.syncBoard();
  assert.equal(rebuilds, 1, 'own-family readiness refreshes board content');
  assert.equal(doc.activeElement, replacement, 'own-family rebuild restores card focus');

  // A detail packet replaces the sidebar HTML after focus has already reached
  // a row. The callback must return focus to the matching new row, including the
  // second occurrence of a repeated key, without stealing unrelated focus.
  function detailFocus(oldKeys, activeIndex) {
    const doc = { body: { id: 'body' }, activeElement: null };
    let replaced = false, focusCalls = 0;
    // Give every row an independent focus method so the selected occurrence
    // can be checked after the callback has swapped the list.
    const oldRows = oldKeys.map(key => ({ id: '', getAttribute: name => name === 'data-go' ? key : null }));
    const newRows = oldKeys.map(key => ({
      id: '', getAttribute: name => name === 'data-go' ? key : null,
      focus(opts) { assert.equal(opts.preventScroll, true); focusCalls++; doc.activeElement = this; }
    }));
    const view = {
      contains: el => oldRows.includes(el),
      querySelectorAll: () => replaced ? newRows : oldRows,
      querySelector: () => null,
      set innerHTML(html) {
        replaced = true;
        if (oldRows.includes(doc.activeElement)) doc.activeElement = doc.body;
        this.html = html;
      }
    };
    const scroller = { scrollTop: 0, getBoundingClientRect: () => ({ top: 0, bottom: 500 }) };
    const state = vm.createContext({
      sel: 'f:104', o: { key: 'f:104' }, visit: 1, panelDetailVisit: 1, document: doc, viewEl: view,
      scrollPos: () => 40, panelScroller: () => scroller,
      rerender: () => '<new sidebar>', typeset() {}, restorePending() {}, syncActive() {},
      showPanelSection() { throw new Error('row focus should not use section reveal'); }
    });
    vm.runInContext(detailAgain, state);
    doc.activeElement = activeIndex == null ? { id: 'outside' } : oldRows[activeIndex];
    const prior = doc.activeElement;
    state.again();
    return { doc, newRows, prior, focusCalls, scroller, view };
  }
  const rowFocus = detailFocus(['f:104'], 0);
  assert.equal(rowFocus.doc.activeElement, rowFocus.newRows[0], 'detail readiness restores focused row');
  assert.equal(rowFocus.focusCalls, 1);
  assert.equal(rowFocus.scroller.scrollTop, 40, 'restored focus keeps reading position');
  const duplicateFocus = detailFocus(['f:104', 'f:104'], 1);
  assert.equal(duplicateFocus.doc.activeElement, duplicateFocus.newRows[1],
    'detail readiness restores the second row with the same data-go key');
  const outsideFocus = detailFocus(['f:104'], null);
  assert.equal(outsideFocus.doc.activeElement, outsideFocus.prior, 'external focus is not stolen');
  assert.equal(outsideFocus.focusCalls, 0);
  const oldHeading = {
    id: 'u-section-papers',
    getAttribute: key => key === 'data-u-section' ? 'papers' : null,
    getBoundingClientRect: () => ({ top: 100, bottom: 120 })
  };
  const newHeading = { id: 'u-section-papers' };
  const sectionDoc = { activeElement: oldHeading };
  let shownSection = null;
  const sectionView = {
    contains: el => el === oldHeading,
    querySelectorAll: () => [],
    querySelector: key => key === '#u-section-papers' ? newHeading : null,
    set innerHTML(html) { this.html = html; sectionDoc.activeElement = null; }
  };
  const sectionScroller = { scrollTop: 0, getBoundingClientRect: () => ({ top: 0, bottom: 500 }) };
  const sectionState = vm.createContext({
    sel: 'f:104', o: { key: 'f:104' }, visit: 1, panelDetailVisit: 1, document: sectionDoc, viewEl: sectionView,
    scrollPos: () => 40, panelScroller: () => sectionScroller,
    rerender: () => '<new sidebar>', typeset() {}, restorePending() {}, syncActive() {},
    showPanelSection: target => { shownSection = target; }
  });
  vm.runInContext(detailAgain, sectionState);
  sectionState.again();
  assert.equal(shownSection, newHeading, 'visible section heading retains section-follow behaviour');
  for (const leaveBeforeReply of [false, true]) {
    const reply = deferred();
    let requests = 0, replacements = 0, renders = 0;
    const view = {
      contains: () => false, querySelector: () => null,
      set innerHTML(html) { replacements++; this.html = html; }
    };
    const pendingPanel = vm.createContext({
      Promise, panelShardWaiting: {}, panelDetailVisit: 0, sel: 'f:same',
      document: { activeElement: {} }, viewEl: view,
      loadShard: () => { requests++; return reply.promise; },
      scrollPos: () => 40, panelScroller: () => ({ scrollTop: 0, getBoundingClientRect: () => ({ top: 0, bottom: 500 }) }),
      rerender: () => '<latest sidebar>', typeset: () => { renders++; },
      restorePending() {}, syncActive() {}
    });
    vm.runInContext(panelWatch + 'function callbackFor(visit) { var o = { key: "f:same" };' + detailAgain + 'return again; }', pendingPanel);
    for (let i = 1; i <= 50; i++) {
      pendingPanel.panelDetailVisit = i;
      pendingPanel.watchPanelShard(0, pendingPanel.callbackFor(i));
    }
    assert.equal(requests, 1, 'revisits retain one pending sidebar subscription');
    if (leaveBeforeReply) pendingPanel.panelDetailVisit++;
    reply.resolve({});
    await flush();
    assert.equal(replacements, leaveBeforeReply ? 0 : 1, 'only the latest still-current visit replaces the sidebar');
    assert.equal(renders, replacements, 'sidebar typesetting is bounded to that replacement');
    assert.equal(Object.keys(pendingPanel.panelShardWaiting).length, 0, 'settled sidebar callback is released');
  }
  // renderPanel replaces the sibling nav on every selection and detail update.
  // Preserve focus by direction, with an end-of-list and no-sibling fallback.
  const stepDoc = { activeElement: null };
  const stepButton = way => ({
    classList: { contains: name => name === `u-step__go--${way}` },
    focus(options) { assert.equal(options.preventScroll, true); stepDoc.activeElement = this; }
  });
  const stepHeading = { focus(options) { assert.equal(options.preventScroll, true); stepDoc.activeElement = this; } };
  const stepEl = {
    buttons: [], hidden: false,
    contains(el) { return this.buttons.includes(el); },
    querySelector(selector) {
      if (selector === 'button') return this.buttons[0] || null;
      const way = selector.endsWith('--prev') ? 'prev' : 'next';
      return this.buttons.find(b => b.classList.contains(`u-step__go--${way}`)) || null;
    },
    set innerHTML(html) {
      this.buttons = ['prev', 'next'].filter(way => html.includes(way)).map(stepButton);
      this.html = html;
    }
  };
  const stepState = vm.createContext({ stepEl, titleEl: stepHeading, document: stepDoc, stepperHtml: o => o.buttons });
  vm.runInContext(stepperRender, stepState);
  stepEl.innerHTML = 'prev next';
  stepDoc.activeElement = stepEl.buttons[0];
  stepState.renderStepper({ buttons: 'prev next' });
  assert.equal(stepDoc.activeElement, stepEl.buttons[0], 'Previous focus follows its replacement button');
  stepDoc.activeElement = stepEl.buttons[1];
  stepState.renderStepper({ buttons: 'prev next' });
  assert.equal(stepDoc.activeElement, stepEl.buttons[1], 'Next focus follows its replacement button');
  stepDoc.activeElement = stepEl.buttons[1];
  stepState.renderStepper({ buttons: 'prev' });
  assert.equal(stepDoc.activeElement, stepEl.buttons[0], 'at the end, focus moves to remaining sibling button');
  stepDoc.activeElement = stepEl.buttons[0];
  stepState.renderStepper({ buttons: '' });
  assert.equal(stepDoc.activeElement, stepHeading, 'without a sibling button, focus moves to heading');
  const elsewhere = {};
  stepEl.innerHTML = 'prev next';
  stepDoc.activeElement = elsewhere;
  stepState.renderStepper({ buttons: 'prev next' });
  assert.equal(stepDoc.activeElement, elsewhere, 'async nav replacement does not steal external focus');

  let arrowDocumentKey, focusedArrivals = 0;
  const arrowSelections = [];
  let dialogOpen = false;
  const arrowState = context({
    sel: 'f:a', boardClick: null, boardRepeatPress: null,
    document: {
      addEventListener(type, fn, capture) { assert.equal(type, 'keydown'); assert.equal(capture, true); arrowDocumentKey = fn; },
      querySelector: () => dialogOpen ? {} : null
    },
    siblingKey: (_o, way) => way < 0 ? 'f:prev' : 'f:next',
    // A focused field or a box that scrolls sideways keeps its own arrow keys.
    arrowsBelongTo: t => !!t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || '') || !!t.isContentEditable || !!t.scrollsSideways),
    select: key => { arrowSelections.push(key); arrowState.sel = key; },
    focusArrival: () => { focusedArrivals++; }
  });
  vm.runInContext(documentKeys, arrowState);
  const arrowEvent = (key, target = { tagName: 'DIV' }, more = {}) => ({
    key, target, defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; },
    stopImmediatePropagation() {}, ...more
  });
  assert.equal(arrowDocumentKey(arrowEvent('ArrowLeft')), undefined);
  assert.deepEqual(arrowSelections, ['f:prev']);
  assert.equal(focusedArrivals, 1, 'left arrow focuses the newly selected sibling');
  const right = arrowEvent('ArrowRight'); arrowDocumentKey(right);
  assert.equal(right.defaultPrevented, true);
  assert.deepEqual(arrowSelections, ['f:prev', 'f:next']);
  assert.equal(focusedArrivals, 2, 'right arrow focuses the newly selected sibling');
  for (const blocked of [
    arrowEvent('ArrowLeft', { tagName: 'INPUT' }),
    arrowEvent('ArrowRight', { tagName: 'TEXTAREA' }),
    arrowEvent('ArrowLeft', { tagName: 'DIV', isContentEditable: true }),
    arrowEvent('ArrowRight', { tagName: 'DIV' }, { metaKey: true }),
    arrowEvent('ArrowLeft', { tagName: 'DIV' }, { ctrlKey: true }),
    arrowEvent('ArrowRight', { tagName: 'DIV' }, { altKey: true }),
    arrowEvent('ArrowLeft', { tagName: 'DIV' }, { shiftKey: true }),
    arrowEvent('ArrowRight', { tagName: 'DIV', scrollsSideways: true })
  ]) {
    arrowDocumentKey(blocked);
    assert.equal(blocked.defaultPrevented, false, 'typing and modified arrows keep their normal action');
  }
  dialogOpen = true;
  const dialogArrow = arrowEvent('ArrowRight'); arrowDocumentKey(dialogArrow);
  assert.equal(dialogArrow.defaultPrevented, false, 'open dialog blocks sibling shortcut');
  assert.deepEqual(arrowSelections, ['f:prev', 'f:next'], 'blocked arrows never select a sibling');
  assert.equal(focusedArrivals, 2, 'blocked arrows never move arrival focus');

  const listHandlers = {};
  let listDraws = 0, listSyncs = 0, listReveals = 0;
  const focusSequence = [];
  const makeRow = key => {
    const element = {
      getAttribute: attr => attr === 'data-go' ? key : null,
      matches: selector => selector === ':focus-visible',
      closest: selector => selector === '[data-go]' ? element : null,
      contains: child => child === element || child.owner === element
    };
    return element;
  };
  const row = makeRow('f:a'), otherRow = makeRow('f:b');
  const listChild = owner => ({ owner, closest: selector => selector === '[data-go]' ? owner : null });
  const titlePart = listChild(row), statusPart = listChild(row), synopsisPart = listChild(row), nextPart = listChild(otherRow);
  const outsideRow = { closest: () => null };
  const listState = context({
    root: { addEventListener: (type, fn) => { listHandlers[type] = fn; } },
    panelBody: { contains: element => element === row || element === otherRow },
    hover: null, hoverVia: '', cardPtr: { x: 1 },
    syncActive: () => { listSyncs++; focusSequence.push('sync'); }, draw: () => { listDraws++; },
    revealEntry: () => { listReveals++; focusSequence.push('reveal'); }
  });
  vm.runInContext(listPreview, listState);
  listHandlers.pointerover({ target: titlePart, pointerType: 'mouse', relatedTarget: outsideRow });
  assert.equal(listState.hover, 'f:a', 'entering a row previews its map object');
  assert.equal(listState.hoverVia, 'list');
  assert.equal(listSyncs, 0, 'pointer preview keeps compact sidebar rows unchanged');
  assert.equal(listDraws, 1);
  listHandlers.pointerout({ target: titlePart, relatedTarget: statusPart });
  listHandlers.pointerover({ target: statusPart, relatedTarget: titlePart, pointerType: 'mouse' });
  listHandlers.pointerout({ target: statusPart, relatedTarget: synopsisPart });
  assert.equal(listState.hover, 'f:a', 'moving within title, status and synopsis keeps the preview');
  assert.equal(listDraws, 1, 'within-row transitions do not redraw the map');
  assert.equal(listSyncs, 0, 'within-row transitions do not expand active state');
  listHandlers.pointerout({ target: synopsisPart, relatedTarget: outsideRow });
  assert.equal(listState.hover, null, 'leaving the row clears pointer preview');
  assert.equal(listSyncs, 0, 'pointer departure leaves compact sidebar layout unchanged');

  listHandlers.pointerover({ target: titlePart, pointerType: 'mouse', relatedTarget: outsideRow });
  const beforeHandoffDraws = listDraws, beforeHandoffSyncs = listSyncs;
  listHandlers.pointerout({ target: titlePart, relatedTarget: nextPart });
  assert.equal(listState.hover, 'f:a', 'row-to-row pointerout waits for the incoming row');
  assert.equal(listDraws, beforeHandoffDraws, 'row-to-row pointerout does not redraw an empty preview');
  listHandlers.pointerover({ target: nextPart, pointerType: 'mouse', relatedTarget: titlePart });
  assert.equal(listState.hover, 'f:b', 'incoming row replaces the preview directly');
  assert.equal(listDraws, beforeHandoffDraws + 1, 'row handoff draws only the new preview');
  assert.equal(listSyncs, beforeHandoffSyncs, 'row handoff keeps compact sidebar layout');
  listHandlers.pointerout({ target: nextPart, relatedTarget: outsideRow });

  listState.hover = 'f:a'; listState.hoverVia = 'map';
  const beforeMapHandoffDraws = listDraws, beforeMapHandoffSyncs = listSyncs;
  listHandlers.pointerover({ target: titlePart, relatedTarget: outsideRow, pointerType: 'mouse' });
  assert.equal(listState.hoverVia, 'list', 'same-key map hover transfers ownership to the sidebar row');
  assert.equal(listDraws, beforeMapHandoffDraws + 1);
  assert.equal(listSyncs, beforeMapHandoffSyncs, 'map-to-list handoff does not expand synopsis');
  listHandlers.pointerover({ target: statusPart, relatedTarget: titlePart, pointerType: 'mouse' });
  assert.equal(listDraws, beforeMapHandoffDraws + 1, 'repeated over within transferred row does not redraw');
  listHandlers.pointerout({ target: statusPart, relatedTarget: outsideRow });

  listHandlers.focusin({ target: titlePart, relatedTarget: outsideRow });
  assert.equal(listState.hover, 'f:a', 'keyboard focus previews the row');
  assert.equal(listState.hoverVia, 'focus');
  assert.equal(listReveals, 1);
  assert.deepEqual(focusSequence, ['sync', 'reveal'], 'keyboard arrival expands before revealing the focused row');
  const focusedDraws = listDraws, focusedSyncs = listSyncs;
  listHandlers.focusout({ target: titlePart, relatedTarget: statusPart });
  listHandlers.focusin({ target: statusPart, relatedTarget: titlePart });
  listHandlers.pointerout({ target: statusPart, relatedTarget: outsideRow });
  assert.equal(listState.hover, 'f:a', 'within-row focus and pointer departure preserve keyboard preview');
  assert.equal(listState.hoverVia, 'focus');
  assert.equal(listDraws, focusedDraws, 'stable focused row does not redraw');
  assert.equal(listSyncs, focusedSyncs, 'stable focused row does not resynchronize');
  listHandlers.focusout({ target: statusPart, relatedTarget: outsideRow });
  assert.equal(listState.hover, null, 'actual keyboard departure clears preview');
  assert.equal(listSyncs, focusedSyncs + 1, 'focus departure clears active state');
  const c = context();
  vm.runInContext(hit, c);
  assert.equal(c.hitAt(20, 20, true), 'f:a', 'click can hit the visible moving family');
  const handlers = {};
  c.canvas = { addEventListener: (name, fn) => { handlers[name] = fn; } };
  const selected = [];
  c.select = key => selected.push(key);
  // A family dot opens the family's page; the press still decides which family.
  c.openPage = o => selected.push(o.key);
  vm.runInContext(click, c);
  const event = (x, y) => ({ x, y, button: 0, isPrimary: true, pointerType: 'mouse' });
  const handler = (e) => handlers.click(e);
  handler(event(20, 20));
  assert.deepEqual(selected, ['f:a'], 'moving-dot click opens its displayed family');
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

  const boardHandlers = {}, boardSelected = [];
  let boardBacks = 0, boardOpens = 0;
  const card = { getAttribute: key => key === 'data-bk' ? 'r:chosen' : null };
  const cardText = {
    closest: key => key === '[data-bk]' ? card : null,
    matches: () => false
  };
  const ground = { closest: () => null, matches: () => true };
  const boardPointerState = context({
    boardPress: null, boardClick: null, boardRepeatPress: null, boardDoubleOpened: false,
    board: { page: 0 }, sel: 'r:old',
    boardEl: { addEventListener: (type, fn) => { boardHandlers[type] = fn; }, contains: () => true },
    selectFromBoard: key => boardSelected.push(key),
    stepBack: () => { boardBacks++; }, openFromBoard: () => { boardOpens++; },
    hideBoardCard() {}, layoutBoard() {}
  });
  vm.runInContext(boardPointer, boardPointerState);
  const boardEvent = (target, x, y) => ({
    target, clientX: x, clientY: y, button: 0, isPrimary: true, detail: 1,
    defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }
  });
  boardHandlers.pointerdown(boardEvent(cardText, 10, 10));
  const textDrag = boardEvent(cardText, 40, 10);
  boardHandlers.click(textDrag);
  assert.equal(textDrag.defaultPrevented, true, 'dragged theorem text suppresses click');
  assert.deepEqual(boardSelected, [], 'dragged theorem text does not select its card');
  assert.equal(boardPointerState.boardPress, null, 'dragged press is consumed');
  boardHandlers.pointerdown(boardEvent(ground, 10, 10));
  const groundDrag = boardEvent(ground, 40, 10);
  boardHandlers.click(groundDrag);
  assert.equal(groundDrag.defaultPrevented, true);
  assert.equal(boardBacks, 0, 'dragging empty board space does not step back');
  boardHandlers.pointerdown(boardEvent(cardText, 10, 10));
  boardHandlers.click(boardEvent(cardText, 12, 10));
  assert.deepEqual(boardSelected, ['r:chosen'], 'short press still selects card');
  boardHandlers.pointerdown(boardEvent(cardText, 10, 10));
  boardHandlers.pointercancel();
  boardHandlers.click(boardEvent(cardText, 40, 10));
  assert.equal(boardSelected.length, 2, 'pointer cancel clears stale drag start');
  boardHandlers.pointerdown(boardEvent(cardText, 10, 10));
  const keyboard = boardEvent(card, 0, 0);
  keyboard.key = 'Enter';
  boardHandlers.keydown(keyboard);
  assert.equal(keyboard.defaultPrevented, true);
  assert.equal(boardPointerState.boardPress, null, 'keyboard activation clears stale drag start');
  boardHandlers.click(boardEvent(cardText, 40, 10));
  assert.equal(boardSelected.length, 4, 'keyboard activation and later click both select');
  assert.equal(boardOpens, 0, 'none of these gestures double-open a result');

  function shiftedBoardFixture() {
    const rootHandlers = {}, boardHandlers = {}, selected = [], opened = [];
    const card = key => ({ getAttribute: attr => attr === 'data-bk' ? key : null });
    const target = key => ({
      getAttribute: () => null,
      closest: selector => selector === '[data-bk]' ? card(key) : null,
      matches: () => false
    });
    const outside = { getAttribute: () => null, closest: () => null, matches: () => false };
    const state = context({
      root: { addEventListener: (type, fn, capture) => { assert.equal(capture, true); rootHandlers[type] = fn; } },
      boardEl: { addEventListener: (type, fn) => { boardHandlers[type] = fn; }, contains: () => true },
      board: { on: true, fi: 0, page: 0 }, boardPress: null, sel: 'r:old',
      selectFromBoard: key => { selected.push(key); state.sel = key; },
      openFromBoard: key => opened.push(key),
      hideBoardCard() {}, layoutBoard() {}, stepBack() {}
    });
    vm.runInContext(boardRepeat + boardPointer, state);
    const event = (which, x, y, time, more = {}) => ({
      target: which, clientX: x, clientY: y, timeStamp: time,
      button: 0, isPrimary: true, pointerType: 'mouse', detail: 1,
      defaultPrevented: false, stopped: false,
      preventDefault() { this.defaultPrevented = true; },
      stopImmediatePropagation() { this.stopped = true; }, ...more
    });
    const dispatch = (type, e, withinBoard) => {
      if (rootHandlers[type]) rootHandlers[type](e);
      if (!e.stopped && withinBoard && boardHandlers[type]) boardHandlers[type](e);
      return e;
    };
    const first = () => {
      const a = target('r:first');
      dispatch('pointerdown', event(a, 30, 40, 100), true);
      dispatch('click', event(a, 30, 40, 110), true);
      assert.deepEqual(selected, ['r:first'], 'first card click selects but does not open');
      assert.deepEqual(opened, []);
      return a;
    };
    return { state, selected, opened, target, outside, event, dispatch, first };
  }
  const shifted = shiftedBoardFixture();
  shifted.first();
  shifted.dispatch('pointerdown', shifted.event(shifted.outside, 31, 40, 230), false);
  const shiftedSecond = shifted.dispatch('click', shifted.event(shifted.outside, 31, 40, 240, { detail: 2 }), false);
  assert.deepEqual(shifted.opened, ['r:first'], 'second click over displaced sidebar opens the original card');
  assert.deepEqual(shifted.selected, ['r:first'], 'capture handles the second click before sidebar handlers');
  assert.equal(shiftedSecond.defaultPrevented, true);
  assert.equal(shiftedSecond.stopped, true);

  const otherCard = shiftedBoardFixture();
  otherCard.first();
  const secondTarget = otherCard.target('r:other');
  otherCard.dispatch('pointerdown', otherCard.event(secondTarget, 30, 40, 230), true);
  otherCard.dispatch('click', otherCard.event(secondTarget, 30, 40, 240, { detail: 2 }), true);
  assert.deepEqual(otherCard.opened, ['r:first'], 'shifted hit over another card opens original key');
  assert.deepEqual(otherCard.selected, ['r:first'], 'second card does not steal the double click');
  otherCard.dispatch('dblclick', otherCard.event(secondTarget, 30, 40, 245, { detail: 2 }), true);
  assert.deepEqual(otherCard.opened, ['r:first'], 'native dblclick cannot duplicate the capture open');

  for (const [name, pointer, clickEvent] of [
    ['drag', { x: 30, y: 40, time: 230 }, { x: 50, y: 40, time: 240 }],
    ['modifier', { x: 30, y: 40, time: 230, metaKey: true }, { x: 30, y: 40, time: 240, metaKey: true }],
    ['touch', { x: 30, y: 40, time: 230, pointerType: 'touch' }, { x: 30, y: 40, time: 240 }],
    ['expiry', { x: 30, y: 40, time: 700 }, { x: 30, y: 40, time: 710 }]
  ]) {
    const rejected = shiftedBoardFixture();
    rejected.first();
    rejected.dispatch('pointerdown', rejected.event(rejected.outside, pointer.x, pointer.y, pointer.time, pointer), false);
    rejected.dispatch('click', rejected.event(rejected.outside, clickEvent.x, clickEvent.y, clickEvent.time,
      { detail: 2, ...clickEvent }), false);
    assert.deepEqual(rejected.opened, [], `${name} cannot open a displaced board card`);
  }
  const changed = shiftedBoardFixture();
  changed.first(); changed.state.sel = 'r:unrelated';
  changed.dispatch('pointerdown', changed.event(changed.outside, 30, 40, 230), false);
  changed.dispatch('click', changed.event(changed.outside, 30, 40, 240, { detail: 2 }), false);
  assert.deepEqual(changed.opened, [], 'changed selection invalidates the old double-click target');
  const cancelled = shiftedBoardFixture();
  cancelled.first();
  cancelled.dispatch('pointerdown', cancelled.event(cancelled.outside, 30, 40, 230), false);
  cancelled.dispatch('pointercancel', cancelled.event(cancelled.outside, 30, 40, 235), false);
  cancelled.dispatch('click', cancelled.event(cancelled.outside, 30, 40, 240, { detail: 2 }), false);
  assert.deepEqual(cancelled.opened, [], 'cancelled second press cannot open a card');
  const keyboardInterruption = shiftedBoardFixture();
  const keyTarget = keyboardInterruption.first();
  keyboardInterruption.dispatch('keydown', keyboardInterruption.event(keyTarget, 30, 40, 220, { key: 'Escape' }), true);
  keyboardInterruption.dispatch('pointerdown', keyboardInterruption.event(keyboardInterruption.outside, 30, 40, 230), false);
  keyboardInterruption.dispatch('click', keyboardInterruption.event(keyboardInterruption.outside, 30, 40, 240, { detail: 2 }), false);
  assert.deepEqual(keyboardInterruption.opened, [], 'keyboard interaction clears stale first-click latch');
  const shortcutInterruption = shiftedBoardFixture();
  const shortcutTarget = shortcutInterruption.first();
  let documentKey;
  shortcutInterruption.state.document = { addEventListener: (_type, fn) => { documentKey = fn; }, querySelector: () => null };
  shortcutInterruption.state.searchIn = { focus() {}, select() {} };
  vm.runInContext(documentKeys, shortcutInterruption.state);
  documentKey(shortcutInterruption.event(shortcutTarget, 30, 40, 220, { key: '/' }));
  shortcutInterruption.dispatch('pointerdown', shortcutInterruption.event(shortcutInterruption.outside, 30, 40, 230), false);
  shortcutInterruption.dispatch('click', shortcutInterruption.event(shortcutInterruption.outside, 30, 40, 240, { detail: 2 }), false);
  assert.deepEqual(shortcutInterruption.opened, [], 'search shortcut cancels the gesture before board key handlers run');

  // The preview guard is registered before both map and board click handlers.
  // A text drag must stop their selection handler, then release the next click.
  const previewListeners = {};
  const previewCard = {
    addEventListener(type, fn) { (previewListeners[type] ||= []).push(fn); }
  };
  const preview = vm.createContext({ Math });
  vm.runInContext(previewGuard, preview);
  preview.guardPreviewClicks(previewCard);
  const previewSelections = [];
  previewCard.addEventListener('click', () => previewSelections.push('selected'));
  const previewEvent = (x, y, extra = {}) => ({
    clientX: x, clientY: y, button: 0, isPrimary: true, detail: 1,
    defaultPrevented: false, stopped: false,
    preventDefault() { this.defaultPrevented = true; },
    stopImmediatePropagation() { this.stopped = true; }, ...extra
  });
  const dispatchPreview = (type, event) => {
    for (const listener of previewListeners[type] || []) {
      listener(event);
      if (event.stopped) break;
    }
    return event;
  };
  dispatchPreview('pointerdown', previewEvent(10, 10));
  const previewDrag = dispatchPreview('click', previewEvent(30, 10));
  assert.equal(previewDrag.defaultPrevented, true, 'dragged preview text suppresses default click');
  assert.deepEqual(previewSelections, [], 'drag never reaches downstream preview selection');
  dispatchPreview('pointerdown', previewEvent(10, 10));
  dispatchPreview('click', previewEvent(12, 10));
  assert.deepEqual(previewSelections, ['selected'], 'ordinary click reaches preview selection');
  dispatchPreview('pointerdown', previewEvent(10, 10));
  dispatchPreview('pointercancel', previewEvent(10, 10));
  assert.equal(dispatchPreview('click', previewEvent(10, 10)).defaultPrevented, true,
    'cancelled gesture never reaches preview selection');
  dispatchPreview('pointerdown', previewEvent(10, 10));
  dispatchPreview('click', previewEvent(10, 10));
  assert.deepEqual(previewSelections, ['selected', 'selected'], 'next clean click works after cancellation');
  assert.equal(dispatchPreview('click', previewEvent(10, 10, { metaKey: true })).defaultPrevented, true,
    'modified preview click stays with the browser');
  assert.equal(dispatchPreview('click', previewEvent(10, 10, { button: 2 })).defaultPrevented, true,
    'secondary preview click does not navigate');
  dispatchPreview('pointerdown', previewEvent(10, 10));
  dispatchPreview('click', previewEvent(10, 10, { detail: 0 }));
  assert.equal(previewSelections.length, 3, 'keyboard click clears any older pointer gesture');

  const dimensions = { width: 1280, height: 900 };
  const wireAttrs = {};
  const wireSvg = { setAttribute(name, value) { wireAttrs[name] = value; }, innerHTML: '' };
  const wireInner = {
    get clientWidth() { return dimensions.width; }, get clientHeight() { return dimensions.height; },
    scrollWidth: 1280, scrollHeight: 900,
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
    querySelector: selector => selector === '[data-u-wires]' ? wireSvg : null,
    querySelectorAll: () => []
  };
  const wireState = vm.createContext({
    boardEl: { querySelector: () => wireInner }, board: { on: true },
    getComputedStyle: () => ({ fontSize: '16px' }), Math
  });
  vm.runInContext(wires, wireState);
  wireState.drawWires();
  assert.deepEqual(wireAttrs, { width: 1280, height: 900 });
  dimensions.width = 963; dimensions.height = 768;
  wireState.drawWires();
  assert.deepEqual(wireAttrs, { width: 963, height: 768 },
    'old SVG overflow cannot hold wires at its stale scroll dimensions');
  dimensions.width = 810; dimensions.height = 600;
  wireState.drawWires();
  assert.deepEqual(wireAttrs, { width: 810, height: 600 }, 'wires follow a further board resize');

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
