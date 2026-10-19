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
const hit = range('    function hitAt(', '\n    /* ---- Selection, trail and address');
const load = range('    function loadParts()', '    function obj(');
const select = range('    function select(key, opts)', '    // A paper, theorem or Lean statement');
const click = range("    canvas.addEventListener('pointerdown',", "\n    document.addEventListener('click', function (e) {");
const shard = range('    function loadShard(di)', '    function detail(');
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
const chartNavigation = range('    function copyLayout(l)', '    // Advance the move;');
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
    sel: 'd:test', pendingViewSwitch: null,
    historyBackPending: null, historySelection: null,
    pendingY: null, pin: -1, hover: null, hoverVia: '',
    ring: null, ringWanted: null, reduceMotion: false, trail: [], liveEl: { textContent: '' },
    savedScrollPos: () => 0, viewPositions: () => ({}),
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
      sel: start, partsReady: true, searchFolded: false, phoneViewY: { map: 0, list: 0 },
      historyBackPending: null, historySelection: null,
      root: { getAttribute: () => 'map' },
      readHash: () => location.hash ? decodeURIComponent(location.hash.slice(3)) : null,
      parentKey: () => 'd:test',
      savedScrollPos: () => 27, viewPositions: () => ({ map: 27, list: 0 }),
      renderPanel: () => { rendered.push(state.sel); },
      showView() {}, restoreSearch() {}, restorePending() {},
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
      releaseLayout: () => layout('release'), discLayout: () => layout('disc'), famLayout: () => layout('fam')
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
    sel: 'f:a',
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
    hover: null, hoverVia: '',
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
      partsReady: true, shards: {}, shardLoading: {}, failedShards: {}, discOf: () => 0,
      fetchJson: (url, cache) => {
        detailCaches.push(cache);
        detailRequests++;
        if (detailRequests === 1) return failure === 'network' ?
          Promise.reject(new Error('offline detail')) : Promise.resolve({ generation_id: 'old' });
        return Promise.resolve({ generation_id: 'g' });
      }
    });
    vm.runInContext(shard + select, detailState);
    await assert.rejects(detailState.loadShard(0));
    assert.equal(detailState.failedShards[0], true, `${failure} is classified as failed detail`);
    assert.equal(detailState.shardLoading[0], null, 'rejected detail promise is released');
    detailState.select('f:a', { trail: true });
    await flush();
    assert.equal(detailRequests, 2, 'explicit selection admits exactly one detail retry');
    assert.deepEqual(detailCaches, ['default', 'reload'], 'failed detail retry bypasses browser cache');
    assert.equal(detailState.shards[0].generation_id, 'g');
  }
  console.log('universe interactions: moving hits, ground clicks, parts retry and latest-selection races pass');
}
main().catch(err => { console.error(err); process.exitCode = 1; });
