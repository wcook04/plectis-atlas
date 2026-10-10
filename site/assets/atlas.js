/* OpenAI Math Atlas: shared page behaviour.
   Theme switch, mathematics (KaTeX, with the TeX source kept where it cannot be
   typeset), copy buttons, site search, sortable and filterable tables, and the
   receipt card's fitting. No frameworks. */
(function () {
  'use strict';
  var doc = document;
  var root = (doc.body && doc.body.getAttribute('data-root')) || '';
  var STR = { copied: 'Copied' };

  /* ---- Theme ---------------------------------------------------------- */
  function systemDark() { return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function effectiveTheme() {
    var t = doc.documentElement.getAttribute('data-theme');
    return t || (systemDark() ? 'dark' : 'light');
  }
  function syncToggle() {
    var b = doc.querySelector('.theme-toggle');
    if (!b) return;
    var dark = effectiveTheme() === 'dark';
    b.setAttribute('aria-label', dark ? b.getAttribute('data-label-light') : b.getAttribute('data-label-dark'));
    b.setAttribute('aria-pressed', dark ? 'true' : 'false');
  }
  function setTheme(next) {
    var html = doc.documentElement;
    html.classList.add('no-transitions');
    var sys = systemDark() ? 'dark' : 'light';
    try {
      if (next === sys) { localStorage.removeItem('atlas-theme'); html.removeAttribute('data-theme'); }
      else { localStorage.setItem('atlas-theme', next); html.setAttribute('data-theme', next); }
    } catch (e) { html.setAttribute('data-theme', next); }
    if (next === sys) html.removeAttribute('data-theme');
    syncToggle();
    window.dispatchEvent(new CustomEvent('atlas-theme'));
    requestAnimationFrame(function () { requestAnimationFrame(function () { html.classList.remove('no-transitions'); }); });
  }
  var toggle = doc.querySelector('.theme-toggle');
  if (toggle) {
    syncToggle();
    toggle.addEventListener('click', function () { setTheme(effectiveTheme() === 'dark' ? 'light' : 'dark'); });
  }

  /* ---- Mathematics ---------------------------------------------------- */
  var GLOBAL_MACROS = {
    '\\ensuremath': '#1', '\\xspace': '', '\\bm': '\\boldsymbol{#1}', '\\mathbbm': '\\mathbb{#1}',
    '\\textup': '\\textrm{#1}', '\\textsc': '\\textrm{#1}', '\\upshape': '', '\\eqref': '\\text{(#1)}',
    '\\label': '', '\\nobreak': '', '\\allowbreak': '', '\\hbox': '\\text{#1}', '\\mbox': '\\text{#1}',
    '\\dfrac': '\\frac{#1}{#2}', '\\RR': '\\mathbb{R}', '\\NN': '\\mathbb{N}', '\\ZZ': '\\mathbb{Z}',
    '\\QQ': '\\mathbb{Q}', '\\CC': '\\mathbb{C}',
    /* Paired delimiters declared with \\DeclarePairedDelimiter, which the data
       extractor does not read; these are their standard meanings. */
    '\\norm': '\\left\\lVert #1\\right\\rVert', '\\abs': '\\left\\lvert #1\\right\\rvert',
    '\\ip': '\\left\\langle #1\\right\\rangle', '\\floor': '\\left\\lfloor #1\\right\\rfloor',
    '\\ceil': '\\left\\lceil #1\\right\\rceil', '\\set': '\\left\\{ #1\\right\\}'
  };
  var macroSets = {};
  var macrosEl = doc.getElementById('tex-macros');
  if (macrosEl) { try { macroSets = JSON.parse(macrosEl.textContent); } catch (e) { macroSets = {}; } }
  function macrosFor(el) {
    var host = el.closest('[data-macros]');
    var key = host ? host.getAttribute('data-macros') : '';
    var m = {};
    var k;
    for (k in GLOBAL_MACROS) m[k] = GLOBAL_MACROS[k];
    var own = macroSets[key] || {};
    for (k in own) {
      var v = own[k];
      if (typeof v === 'string' && !/\\(?:newcommand|def|let|ifx|ifmmode|csname|expandafter)/.test(v)) m[k] = v;
    }
    return m;
  }
  var stats = window.__atlasMath = { ok: 0, failed: 0, errors: [] };
  function renderSpans(scope) {
    if (!window.katex) return;
    var spans = (scope || doc).querySelectorAll('span.m:not([data-done])');
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      el.setAttribute('data-done', '1');
      var tex = el.textContent;
      try {
        window.katex.render(tex, el, { displayMode: el.getAttribute('data-d') === '1', macros: macrosFor(el), throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
        stats.ok++;
      } catch (err) {
        el.textContent = tex;
        el.classList.add('m-fail');
        el.title = doc.body.getAttribute('data-tex-failed') || '';
        stats.failed++;
        if (stats.errors.length < 200) stats.errors.push(String(err && err.message || err).slice(0, 160));
      }
    }
  }
  function renderAuto(scope) {
    if (!window.renderMathInElement) return;
    var opts = function (dollars) {
      var d = [{ left: '\\(', right: '\\)', display: false }, { left: '\\[', right: '\\]', display: true }];
      if (dollars) { d.unshift({ left: '$$', right: '$$', display: true }); d.push({ left: '$', right: '$', display: false }); }
      return { delimiters: d, throwOnError: true, strict: 'ignore', errorCallback: function () { stats.failed++; }, ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'] };
    };
    var a = (scope || doc).querySelectorAll('.tex-auto:not([data-done])');
    for (var i = 0; i < a.length; i++) { a[i].setAttribute('data-done', '1'); try { window.renderMathInElement(a[i], opts(false)); } catch (e) { stats.failed++; } }
    var b = (scope || doc).querySelectorAll('.md-math:not([data-done])');
    for (var j = 0; j < b.length; j++) { b[j].setAttribute('data-done', '1'); try { window.renderMathInElement(b[j], opts(true)); } catch (e) { stats.failed++; } }
  }
  window.atlasRenderMath = function (scope) { renderSpans(scope); renderAuto(scope); };

  /* ---- Copy ------------------------------------------------------------ */
  doc.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-copy-next],[data-copy-text]');
    if (!b) return;
    var text = b.hasAttribute('data-copy-text') ? b.getAttribute('data-copy-text') : (b.nextElementSibling ? b.nextElementSibling.textContent : '');
    var done = function () {
      var old = b.textContent;
      b.textContent = b.getAttribute('data-copied') || doc.body.getAttribute('data-copied') || STR.copied;
      setTimeout(function () { b.textContent = old; }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, done);
    else done();
  });

  /* ---- Site search ------------------------------------------------------ */
  var dlg = doc.getElementById('search-dialog');
  var index = null;
  var sel = -1;
  function norm(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function loadIndex(cb) {
    if (index) return cb();
    fetch(root + 'data/search.json').then(function (r) { return r.json(); }).then(function (j) {
      index = j.map(function (e) { e.n = norm(e.t + ' ' + e.k + ' ' + e.s); return e; });
      cb();
    }).catch(function () { index = []; cb(); });
  }
  function runSearch() {
    var input = dlg.querySelector('.search__input');
    var list = dlg.querySelector('.search__results');
    var empty = dlg.querySelector('.search__empty');
    var q = norm(input.value).trim();
    list.innerHTML = '';
    sel = -1;
    if (!q) { empty.hidden = true; return; }
    var terms = q.split(/\s+/);
    var hits = [];
    for (var i = 0; i < index.length && hits.length < 400; i++) {
      var e = index[i];
      var ok = true;
      for (var t = 0; t < terms.length; t++) if (e.n.indexOf(terms[t]) < 0) { ok = false; break; }
      if (ok) hits.push(e);
    }
    hits.sort(function (a, b) { return (norm(a.t).indexOf(terms[0]) === 0 ? 0 : 1) - (norm(b.t).indexOf(terms[0]) === 0 ? 0 : 1); });
    hits = hits.slice(0, 40);
    empty.hidden = hits.length > 0;
    hits.forEach(function (e, k) {
      var li = doc.createElement('li');
      var a = doc.createElement('a');
      a.href = root + e.u;
      a.setAttribute('role', 'option');
      a.id = 'sr-' + k;
      a.textContent = e.t;
      var s = doc.createElement('span');
      s.className = 'k';
      s.textContent = e.k + (e.s ? ', ' + e.s : '');
      a.appendChild(s);
      li.appendChild(a);
      list.appendChild(li);
    });
  }
  function moveSel(d) {
    var items = dlg.querySelectorAll('.search__results a');
    if (!items.length) return;
    if (sel >= 0 && items[sel]) items[sel].removeAttribute('aria-selected');
    sel = (sel + d + items.length) % items.length;
    items[sel].setAttribute('aria-selected', 'true');
    items[sel].scrollIntoView({ block: 'nearest' });
  }
  function openSearch() {
    if (!dlg || dlg.open) return;
    loadIndex(function () { runSearch(); });
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    dlg.querySelector('.search__input').focus();
  }
  if (dlg) {
    var ob = doc.querySelector('.search-open');
    if (ob) ob.addEventListener('click', openSearch);
    dlg.querySelector('.search__input').addEventListener('input', function () { loadIndex(runSearch); });
    dlg.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); moveSel(1); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); moveSel(-1); }
      else if (ev.key === 'Enter') {
        var items = dlg.querySelectorAll('.search__results a');
        var pick = items[sel >= 0 ? sel : 0];
        if (pick) { ev.preventDefault(); location.href = pick.href; }
      }
    });
    dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); });
    doc.addEventListener('keydown', function (ev) {
      if (ev.key === '/' && !ev.metaKey && !ev.ctrlKey && !/^(INPUT|TEXTAREA|SELECT)$/.test((doc.activeElement || {}).tagName || '') && !(doc.activeElement && doc.activeElement.isContentEditable)) {
        ev.preventDefault();
        openSearch();
      }
    });
  }

  /* ---- Tables ----------------------------------------------------------- */
  function shownCount(container, n) {
    var p = container && container.querySelector('[data-shown-template]');
    if (p) p.textContent = p.getAttribute('data-shown-template').replace('{n}', n.toLocaleString('en-GB'));
  }
  Array.prototype.forEach.call(doc.querySelectorAll('.tbl--sortable'), function (table) {
    var body = table.tBodies[0];
    table.querySelectorAll('button.sort').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var th = btn.closest('th');
        var idx = +btn.getAttribute('data-sort');
        var numeric = btn.getAttribute('data-type') === 'n';
        var dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
        if (th.getAttribute('aria-sort') === 'none' && numeric) dir = 'descending';
        table.querySelectorAll('th').forEach(function (h) { h.setAttribute('aria-sort', 'none'); });
        th.setAttribute('aria-sort', dir);
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var x = a.cells[idx].getAttribute('data-v'), y = b.cells[idx].getAttribute('data-v');
          var c = numeric ? (+x - +y) : x.localeCompare(y, 'en-GB');
          return dir === 'ascending' ? c : -c;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });
  Array.prototype.forEach.call(doc.querySelectorAll('[data-filter-rows]'), function (input) {
    var table = doc.getElementById(input.getAttribute('data-filter-rows'));
    var wrap = input.closest('.filters');
    var apply = function () {
      var terms = norm(input.value).trim().split(/\s+/).filter(Boolean);
      var n = 0;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
        var q = norm(r.getAttribute('data-q'));
        var ok = terms.every(function (t) { return q.indexOf(t) >= 0; });
        r.hidden = !ok;
        if (ok) n++;
      });
      shownCount(wrap, n);
    };
    input.addEventListener('input', apply);
    apply();
  });
  Array.prototype.forEach.call(doc.querySelectorAll('[data-filter-table]'), function (wrap) {
    var table = doc.getElementById(wrap.getAttribute('data-filter-table'));
    var state = { d: '', s: '' };
    var apply = function () {
      var n = 0;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
        var ok = (!state.d || r.getAttribute('data-d') === state.d) && (!state.s || r.getAttribute('data-s') === state.s);
        r.hidden = !ok;
        if (ok) n++;
      });
      shownCount(wrap, n);
    };
    wrap.addEventListener('click', function (ev) {
      var b = ev.target.closest('.chip');
      if (!b) return;
      var key = b.hasAttribute('data-filter-d') ? 'd' : 's';
      state[key] = b.getAttribute(key === 'd' ? 'data-filter-d' : 'data-filter-s');
      b.parentNode.querySelectorAll('.chip').forEach(function (c) { c.setAttribute('aria-pressed', c === b ? 'true' : 'false'); });
      apply();
    });
    var params = new URLSearchParams(location.search);
    if (params.get('d')) { var cb = wrap.querySelector('[data-filter-d="' + params.get('d') + '"]'); if (cb) cb.click(); }
    apply();
  });

  /* ---- Receipt card fitting ---------------------------------------------- */
  function fitCards() {
    doc.querySelectorAll('.rc__fit').forEach(function (box) {
      var inner = box.firstElementChild;
      if (!inner) return;
      var f = box.closest('.rc__lean') ? 1.3 : 1.45;
      inner.style.setProperty('--fit', f);
      box.classList.remove('is-clipped');
      var guard = 0;
      var over = function () {
        if (inner.scrollHeight > box.clientHeight + 1) return true;
        var wide = inner.querySelectorAll('.m-d, pre');
        for (var i = 0; i < wide.length; i++) if (wide[i].scrollWidth > wide[i].clientWidth + 1) return true;
        return false;
      };
      while (over() && f > 0.6 && guard++ < 30) {
        f -= 0.04;
        inner.style.setProperty('--fit', f.toFixed(2));
      }
      if (over()) box.classList.add('is-clipped');
    });
  }

  /* ---- Start ----------------------------------------------------------- */
  function start() {
    window.atlasRenderMath(doc);
    if (doc.querySelector('.rc')) {
      fitCards();
      if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(fitCards);
      var t;
      window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(fitCards, 150); });
    }
    doc.documentElement.setAttribute('data-math', window.katex ? 'ready' : 'unavailable');
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start); else start();
})();
