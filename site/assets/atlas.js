/* Plectis Atlas: shared page behaviour.
   Theme switch, mathematics (KaTeX, with the TeX source kept where it cannot be
   typeset), copy buttons, sortable and filterable tables, and the
   receipt card's fitting. No frameworks. */
(function () {
  'use strict';
  var doc = document;
  var root = (doc.body && doc.body.getAttribute('data-root')) || '';
  var STR = { copied: 'Copied', failed: 'Copy failed' };

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

  /* ---- Site menu (phones) ------------------------------------------------ */
  /* Below 760px the navigation folds behind one Menu button so the header stays one
     row; without JavaScript the links simply wrap. Escape or a click outside closes it. */
  var navBtn = doc.querySelector('.nav-toggle');
  var nav = doc.getElementById('site-nav');
  if (navBtn && nav) {
    var setNav = function (open) {
      navBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      nav.classList.toggle('nav--open', open);
    };
    navBtn.addEventListener('click', function () { setNav(navBtn.getAttribute('aria-expanded') !== 'true'); });
    doc.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && navBtn.getAttribute('aria-expanded') === 'true') { setNav(false); navBtn.focus(); }
    });
    doc.addEventListener('click', function (ev) {
      if (navBtn.getAttribute('aria-expanded') === 'true' && !nav.contains(ev.target) && !navBtn.contains(ev.target)) setNav(false);
    });
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
  /* KaTeX lets a line break after a relation or an operator, as TeX does, so a short
     formula such as "Re s > 11/12" could end a line on its relation. A brace pair makes
     a short formula one unit; a long one keeps its breaks. 32 TeX characters is about
     the width of "T_1 + HT_2 + HT_3 = 96H^{2/3}U", which fits a phone's line. */
  function keepShort(tex) {
    var t = String(tex == null ? '' : tex);
    if (t.replace(/\s+/g, '').length > 32 || /\\\\|\\begin|\\tag|&|(^|[^\\])%/.test(t)) return t;
    return '{' + t + '}';
  }
  window.atlasKeepShortMath = keepShort;
  function renderSpans(scope) {
    if (!window.katex) return;
    var spans = (scope || doc).querySelectorAll('span.m:not([data-done])');
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      el.setAttribute('data-done', '1');
      var tex = el.textContent;
      try {
        var display = el.getAttribute('data-d') === '1';
        window.katex.render(display ? tex : keepShort(tex), el, { displayMode: display, macros: macrosFor(el), throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
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
      return { delimiters: d, throwOnError: true, strict: 'ignore', preProcess: keepShort, errorCallback: function () { stats.failed++; }, ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'] };
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
    if (b._label == null) b._label = b.textContent;
    var flash = function (msg) {
      b.textContent = msg;
      clearTimeout(b._t);
      b._t = setTimeout(function () { b.textContent = b._label; }, 1600);
    };
    /* "Copied" only after the browser confirms the write. Otherwise say so, and put
       the text in a selected field beside the button so it can be copied by hand. */
    var ok = function () {
      var f = b.parentNode && b.parentNode.querySelector('.copy-fallback');
      if (f) f.remove();
      flash(b.getAttribute('data-copied') || doc.body.getAttribute('data-copied') || STR.copied);
    };
    var failed = function () {
      flash(doc.body.getAttribute('data-copy-failed') || STR.failed);
      var f = b.parentNode && b.parentNode.querySelector('.copy-fallback');
      if (!f) {
        f = doc.createElement('input');
        f.type = 'text';
        f.readOnly = true;
        f.className = 'copy-fallback';
        f.setAttribute('aria-label', doc.body.getAttribute('data-copy-failed') || STR.failed);
        b.insertAdjacentElement('afterend', f);
      }
      f.value = text;
      f.focus();
      f.select();
    };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, failed);
      else failed();
    } catch (e) { failed(); }
  });

  /* Loose matching for the tables' own filters (site search is the separate block below). */
  function norm(s) { return (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[\u2018\u2019]/g, "'").toLowerCase(); }

  /* ---- Tables ----------------------------------------------------------- */
  function shownCount(container, n) {
    var p = container && container.querySelector('[data-shown-template]');
    if (p) p.textContent = p.getAttribute('data-shown-template').replace('{n}', n.toLocaleString('en-GB'));
  }
  function sortTable(table, idx, numeric, dir, remember) {
    var body = table.tBodies[0];
    table.querySelectorAll('th').forEach(function (h) { h.setAttribute('aria-sort', 'none'); });
    var btn = table.querySelector('button.sort[data-sort="' + idx + '"]');
    if (btn) btn.closest('th').setAttribute('aria-sort', dir);
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(function (a, b) {
      var x = a.cells[idx].getAttribute('data-v'), y = b.cells[idx].getAttribute('data-v');
      var c = numeric ? (+x - +y) : x.localeCompare(y, 'en-GB');
      return dir === 'ascending' ? c : -c;
    });
    rows.forEach(function (r) { body.appendChild(r); });
    doc.querySelectorAll('select[data-sort-table]').forEach(function (sel) {
      if (sel.getAttribute('data-sort-table') !== table.id) return;
      var value = idx + ':' + (numeric ? 'n' : 's') + ':' + dir;
      if (Array.prototype.some.call(sel.options, function (opt) { return opt.value === value; })) sel.value = value;
    });
    if (remember !== false && window.history && history.replaceState) {
      var params = new URLSearchParams(location.search);
      params.set('sort', idx + ':' + dir);
      history.replaceState(history.state, '', location.pathname + '?' + params.toString() + location.hash);
    }
  }
  Array.prototype.forEach.call(doc.querySelectorAll('.tbl--sortable'), function (table) {
    table.querySelectorAll('button.sort').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var th = btn.closest('th');
        var numeric = btn.getAttribute('data-type') === 'n';
        var dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
        if (th.getAttribute('aria-sort') === 'none' && numeric) dir = 'descending';
        sortTable(table, +btn.getAttribute('data-sort'), numeric, dir);
      });
    });
    // Reconstruct the chosen order when Back reloads the list instead of restoring
    // its DOM from the browser's page cache. Only accept an existing sort column.
    var saved = /^(\d+):(ascending|descending)$/.exec(new URLSearchParams(location.search).get('sort') || '');
    var savedButton = saved && table.querySelector('button.sort[data-sort="' + saved[1] + '"]');
    if (savedButton) sortTable(table, +saved[1], savedButton.getAttribute('data-type') === 'n', saved[2], false);
  });
  /* On a phone the column heads are hidden: a menu sorts the list instead
     (value "column:n|s:ascending|descending"). */
  Array.prototype.forEach.call(doc.querySelectorAll('select[data-sort-table]'), function (sel) {
    var table = doc.getElementById(sel.getAttribute('data-sort-table'));
    if (!table) return;
    sel.addEventListener('change', function () {
      var v = sel.value.split(':');
      sortTable(table, +v[0], v[1] === 'n', v[2]);
    });
  });
  Array.prototype.forEach.call(doc.querySelectorAll('[data-filter-rows]'), function (input) {
    var table = doc.getElementById(input.getAttribute('data-filter-rows'));
    var wrap = input.closest('.filters');
    var apply = function (remember) {
      var terms = norm(input.value).trim().split(/\s+/).filter(Boolean);
      var n = 0;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
        var q = norm(r.getAttribute('data-q'));
        var ok = terms.every(function (t) { return q.indexOf(t) >= 0; });
        r.hidden = !ok;
        if (ok) n++;
      });
      shownCount(wrap, n);
      if (remember !== false && window.history && history.replaceState) {
        var params = new URLSearchParams(location.search);
        if (input.value) params.set('q', input.value); else params.delete('q');
        history.replaceState(history.state, '', location.pathname + (params.toString() ? '?' + params.toString() : '') + location.hash);
      }
    };
    input.addEventListener('input', apply);
    input.value = new URLSearchParams(location.search).get('q') || '';
    apply(false);
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

  /* The Families list: filters by discipline, evidence, each outside reader's finding
     and words, combined, and by the map's colour (t, the key's links); the state lives
     in the address (?d=&c=&t=&l=&r=&q=) so a
     filtered list can be shared. Without JavaScript the whole list shows and the
     filters stay hidden. */
  Array.prototype.forEach.call(doc.querySelectorAll('[data-filter-families]'), function (wrap) {
    var table = doc.getElementById(wrap.getAttribute('data-filter-families'));
    if (!table) return;
    var empty = doc.querySelector('.filters__empty');
    var reset = wrap.querySelector('.filters__reset');
    var KEYS = ['d', 'c', 't', 'l', 'r', 'g', 'p', 'q'];
    var state = { d: '', c: '', t: '', l: '', r: '', g: '', p: '', q: '' };
    /* "Search all text": the site search, opened with the same words. */
    var searchAll = wrap.querySelector('[data-search-all]');
    function syncSearchAll() {
      if (!searchAll) return;
      var w = (state.q || '').trim();
      searchAll.href = searchAll.getAttribute('data-search-all') + (w ? '?q=' + encodeURIComponent(w) : '');
    }
    var controls = {};
    wrap.querySelectorAll('[data-filter]').forEach(function (el) { controls[el.getAttribute('data-filter')] = el; });
    wrap.hidden = false;
    var toggle = wrap.querySelector('.filters__toggle');
    if (toggle) toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      wrap.classList.toggle('is-open', open);
    });
    function sync() { KEYS.forEach(function (k) { if (controls[k]) controls[k].value = state[k]; }); }
    function apply(push) {
      var n = 0;
      var words = norm(state.q).trim().split(/\s+/).filter(Boolean);
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        var q = row.getAttribute('data-q') || '';
        var ok = (!state.d || row.getAttribute('data-d') === state.d) &&
          (!state.c || (' ' + row.getAttribute('data-c') + ' ').indexOf(' ' + state.c + ' ') >= 0) &&
          (!state.t || row.getAttribute('data-t') === state.t) &&
          (!state.l || row.getAttribute('data-l') === state.l) &&
          (!state.r || row.getAttribute('data-r') === state.r) &&
          (!state.g || row.getAttribute('data-g') === state.g) &&
          (!state.p || row.getAttribute('data-p') === state.p) &&
          words.every(function (w) { return norm(q).indexOf(w) >= 0; });
        row.hidden = !ok;
        if (ok) n++;
      });
      shownCount(wrap, n);
      syncSearchAll();
      /* The active criteria in words, after the count. */
      var parts = [];
      KEYS.forEach(function (k) {
        var el = controls[k];
        if (!state[k] || !el) return;
        if (el.tagName === 'SELECT') {
          var opt = el.options[el.selectedIndex];
          var txt = opt ? opt.textContent.replace(/\s*\([\d,]+\)$/, '') : state[k];
          var lab = wrap.querySelector('label[for="' + el.id + '"]');
          parts.push((k === 'l' || k === 'r') && lab ? lab.textContent + ': ' + txt.toLowerCase() : k === 'c' ? txt.charAt(0).toLowerCase() + txt.slice(1) : txt);
        } else {
          parts.push('\u201c' + state[k] + '\u201d');
        }
      });
      var nEl = wrap.querySelector('.filters__n');
      if (nEl && parts.length) {
        var tot = table.tBodies[0].rows.length;
        nEl.textContent = nEl.getAttribute('data-criteria-lead').replace('{n}', n.toLocaleString('en-GB')).replace('{total}', tot.toLocaleString('en-GB')) + ' ' + parts.join('; ') + '.';
      }
      if (empty) empty.hidden = n > 0;
      if (reset) reset.hidden = !KEYS.some(function (k) { return state[k]; });
      if (push !== false && window.history && history.replaceState) {
        var u = new URLSearchParams(location.search);
        KEYS.forEach(function (k) { if (state[k]) u.set(k, state[k]); else u.delete(k); });
        history.replaceState(null, '', location.pathname + (u.toString() ? '?' + u.toString() : '') + location.hash);
      }
    }
    var t = 0;
    wrap.addEventListener('input', function (ev) {
      var el = ev.target.closest('[data-filter]');
      if (!el) return;
      state[el.getAttribute('data-filter')] = el.value;
      clearTimeout(t);
      t = setTimeout(apply, el.tagName === 'INPUT' ? 120 : 0);
    });
    if (reset) reset.addEventListener('click', function () { KEYS.forEach(function (k) { state[k] = ''; }); sync(); apply(); });
    var params = new URLSearchParams(location.search);
    /* Disagreement used to be offered twice on the Families list; an old ?c=disagree link
       now selects the one remaining control, the colour "The groups disagree". */
    if (params.get('c') === 'disagree' && controls.t && controls.t.querySelector('option[value="split"]')) { params.delete('c'); params.set('t', 'split'); }
    KEYS.forEach(function (k) {
      var v = params.get(k) || '';
      var el = controls[k];
      if (!v || !el) return;
      if (el.tagName === 'SELECT' && !el.querySelector('option[value="' + v.replace(/"/g, '') + '"]')) return;
      state[k] = v;
    });
    sync();
    apply(false);
  });

  /* ---- Number receipts (numbers.html) ---------------------------------------
     "The records behind this number": the receipt header, then its member pages in
     order, as Statement Map's WEB.md describes. Each packet must carry this page's
     generation; each page must start where the last ended; the total must match
     the header. The build has already reconstructed every receipt and checked its
     digest; the page shows the members a reader asks for, a page at a time. */
  var numWords = {};
  try { numWords = JSON.parse((doc.getElementById('number-words') || {}).textContent || '{}'); } catch (e) { numWords = {}; }
  var NW = function (k, o) { var t = numWords[k] || ''; return t.replace(/\{(\w+)\}/g, function (m, x) { return o && o[x] != null ? o[x] : m; }); };
  var GEN_PAGE = (doc.body && doc.body.getAttribute('data-generation')) || '';
  var numCache = {};
  function getNum(path) {
    if (!numCache[path]) {
      numCache[path] = fetch(root + 'data/' + path).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (j) {
        if (GEN_PAGE && j.generation_id !== GEN_PAGE) { var e = new Error('generation'); e.generation = true; throw e; }
        return j;
      });
      numCache[path].catch(function () { delete numCache[path]; });
    }
    return numCache[path];
  }
  function memberLabel(item) {
    if (typeof item === 'string') return { id: item, text: item };
    var id = item.id || '';
    var ident = item.identity;
    var text = item.name || (Array.isArray(ident) ? ident.join(', ') : (ident != null ? String(ident) : id));
    if (item.value != null) text += ': ' + item.value;
    return { id: id, text: text };
  }
  var LAB = null;   /* family names and paper titles, from the search's labels.json */
  function named(id) {
    if (!LAB) return null;
    if (id.slice(0, 2) === 'f:' && LAB.families[id]) return id.slice(2) + ' ' + LAB.families[id].n;
    if (id.slice(0, 2) === 'p:' && LAB.papers[id]) return LAB.papers[id];
    if (id.slice(0, 2) === 'r:') { var rest = id.slice(2), j = rest.indexOf(':'); var t = LAB.papers['p:' + rest.slice(0, j)]; return rest.slice(j + 1) + (t ? ', ' + t : ''); }
    if (id.slice(0, 2) === 'l:') return id.slice(2);
    return null;
  }
  function memberLi(item) {
    var li = doc.createElement('li');
    var m = memberLabel(item);
    var url = /^[fplrd]:/.test(m.id) && window.AtlasSearch ? window.AtlasSearch.url(m.id) : null;
    if (url) {
      var a = doc.createElement('a');
      a.href = root + url;
      a.textContent = m.text === m.id ? (named(m.id) || m.id.replace(/^[fplrd]:/, '')) : m.text;
      li.appendChild(a);
    } else {
      li.textContent = m.text;
    }
    return li;
  }
  function loadCollection(header, name, upto) {
    var coll = (header.collections || {})[name];
    if (!coll || !coll.pages || !coll.pages.length) return Promise.resolve([]);
    var pages = coll.pages.slice(0, upto == null ? coll.pages.length : upto);
    return Promise.all(pages.map(getNum)).then(function (docs) {
      var items = [], expect = 0;
      docs.forEach(function (d) {
        if (d.start !== expect) throw new Error('page out of order');
        items = items.concat(d.items);
        expect += d.items.length;
      });
      if (pages.length === coll.pages.length && expect !== coll.count) throw new Error('count');
      return items;
    });
  }
  function renderReceipt(det) {
    var row = det.closest('.numrow');
    var body = det.querySelector('.receipt__body');
    var path = row && row.getAttribute('data-receipt');
    if (!path || det.getAttribute('data-loaded')) return;
    det.setAttribute('data-loaded', '1');
    var keep = body.innerHTML;
    var status = doc.createElement('p');
    status.className = 'small muted';
    status.setAttribute('role', 'status');
    status.textContent = NW('loading');
    body.insertBefore(status, body.firstChild);
    getNum(path).then(function (header) {
      var number = header.number || {};
      var colls = header.collections || {};
      var show = colls.observations && colls.observations.count ? 'observations' : 'members';
      var frag = doc.createDocumentFragment();
      var facts = doc.createElement('p');
      facts.className = 'receipt__facts';
      ['members', 'universe', 'observations'].forEach(function (n) {
        if (colls[n]) { var sp = doc.createElement('span'); sp.textContent = NW(n, { n: colls[n].count.toLocaleString('en-GB') }); facts.appendChild(sp); }
      });
      frag.appendChild(facts);
      if (number.membership === 'unavailable' || !(colls[show] && colls[show].count)) {
        var p = doc.createElement('p'); p.textContent = number.state === 'reported' ? NW('none_listed') : NW('empty'); frag.appendChild(p);
      }
      if (number.issues && number.issues.length) {
        var ih = doc.createElement('p'); ih.textContent = NW('issues'); frag.appendChild(ih);
        var il = doc.createElement('ul');
        number.issues.forEach(function (x) { var li = doc.createElement('li'); li.textContent = typeof x === 'string' ? x : JSON.stringify(x); il.appendChild(li); });
        frag.appendChild(il);
      }
      var ul = doc.createElement('ul');
      ul.className = 'receipt__members';
      frag.appendChild(ul);
      var total = colls[show] ? colls[show].count : 0;
      var more = null;
      function fill(items, limit) {
        ul.innerHTML = '';
        items.slice(0, limit).forEach(function (it) { ul.appendChild(memberLi(it)); });
      }
      if (total) {
        var labelsReady = window.AtlasSearch ? window.AtlasSearch.labels().then(function (l) { LAB = l; }, function () {}) : Promise.resolve();
        Promise.all([loadCollection(header, show, 1), labelsReady]).then(function (r2) { var items = r2[0];
          fill(items, 50);
          if (total > 50) {
            more = doc.createElement('button');
            more.type = 'button';
            more.className = 'btn btn--small';
            more.textContent = NW('more', { n: total.toLocaleString('en-GB') });
            more.addEventListener('click', function () {
              more.disabled = true;
              loadCollection(header, show).then(function (all) { fill(all, all.length); more.remove(); })
                .catch(function () { more.disabled = false; status.textContent = NW('failed'); });
            });
            ul.insertAdjacentElement('afterend', more);
          }
        }).catch(function () { status.textContent = NW('failed'); });
      }
      if (number.sha256) {
        var dg = doc.createElement('p'); dg.className = 'small muted receipt__digest';
        dg.textContent = NW('digest', { sha: number.sha256.replace('sha256:', '').slice(0, 16) });
        frag.appendChild(dg);
      }
      status.textContent = '';
      body.innerHTML = '';
      body.appendChild(frag);
      body.insertAdjacentHTML('beforeend', keep);
    }).catch(function (e) {
      status.textContent = e && e.generation ? NW('generation') : NW('failed');
      det.removeAttribute('data-loaded');
    });
  }
  doc.addEventListener('toggle', function (ev) {
    var det = ev.target;
    if (det && det.matches && det.matches('details.receipt[data-key]') && det.open) renderReceipt(det);
  }, true);
  /* A link to numbers.html#n-<key> opens that number's records. */
  function openNumberFromHash() {
    var m = /^#n-(.+)$/.exec(location.hash);
    if (!m) return;
    var row = doc.getElementById('n-' + decodeURIComponent(m[1]));
    var det = row && row.querySelector('details.receipt');
    if (det && !det.open) det.open = true;
  }
  window.addEventListener('hashchange', openNumberFromHash);
  openNumberFromHash();

  /* ---- Receipt card fitting ---------------------------------------------- */
  /* On a narrow screen the inline comparison reflows into stacked, readable text
     (atlas.css), so it is never shrunk or clipped; only the fixed 16:9 frames are. */
  var stackedMQ = window.matchMedia ? window.matchMedia('(max-width: 760px)') : null;
  function fitCards() {
    doc.querySelectorAll('.rc__fit').forEach(function (box) {
      var inner = box.firstElementChild;
      if (!inner) return;
      if (stackedMQ && stackedMQ.matches && !box.closest('.rc-wrap--solo')) {
        inner.style.removeProperty('--fit');
        box.classList.remove('is-clipped');
        return;
      }
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

  /* ---- Anchors inside collapsed sections ----------------------------------- */
  /* A link to a line of the full file, or to a section folded into <details>,
     opens the enclosing sections before the browser scrolls to it. */
  function revealTarget() {
    var id = decodeURIComponent(location.hash.replace(/^#/, ''));
    if (!id) return;
    var el = doc.getElementById(id);
    if (!el) return;
    var opened = false;
    for (var p = el.parentElement; p; p = p.parentElement) {
      if (p.tagName === 'DETAILS' && !p.open) { p.open = true; opened = true; }
    }
    if (opened) el.scrollIntoView({ block: 'start' });
  }
  window.addEventListener('hashchange', revealTarget);

  /* ---- Start ----------------------------------------------------------- */
  function start() {
    revealTarget();
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

/* Glossary previews, after the Plectis term previews: a marked word ([[id|text]] in the
   copy, rendered as a.term) shows its short definition after a 140 ms dwell, beside the
   word, and clears 260 ms after the pointer leaves. Focus shows it too; Escape closes it.
   The definitions load once, on first use, from assets/glossary.json; without them the
   word is a plain link to the glossary page. A term's example, when it has one, follows
   its definition. Any element with data-tip (a list's column head or filter, written by
   build_site.tip_attr) shows its own explanation the same way, above it when it says
   data-tip-place="above"; inside such an element its explanation wins over a term's. */
(function () {
  var doc = document, root = (doc.body && doc.body.getAttribute('data-root')) || '';
  var data = null, loading = null, pop = null, current = null, showTimer = 0, hideTimer = 0;
  function load() {
    if (data || loading) return loading;
    loading = fetch(root + 'assets/glossary.json').then(function (r) { return r.ok ? r.json() : { terms: [] }; })
      .then(function (j) { data = {}; (j.terms || []).forEach(function (t) { data[t.id] = t; }); return data; })
      .catch(function () { data = {}; return data; });
    return loading;
  }
  function ensurePop() {
    if (pop) return pop;
    pop = doc.createElement('div');
    pop.className = 'term-pop'; pop.id = 'term-pop'; pop.setAttribute('role', 'tooltip'); pop.hidden = true;
    pop.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
    pop.addEventListener('mouseleave', scheduleHide);
    doc.body.appendChild(pop);
    return pop;
  }
  function place(a) {
    var r = a.getBoundingClientRect(), p = ensurePop(), vw = doc.documentElement.clientWidth;
    p.style.maxWidth = Math.min(340, vw - 24) + 'px';
    var w = p.offsetWidth, h = p.offsetHeight;
    var left = Math.max(12, Math.min(r.left + window.scrollX, window.scrollX + vw - w - 12));
    var below = r.bottom + 8 + h < window.innerHeight;
    if (a.getAttribute('data-tip-place') === 'above' && r.top - h - 8 > 0) below = false;
    var top = below ? r.bottom + window.scrollY + 8 : r.top + window.scrollY - h - 8;
    p.style.left = left + 'px'; p.style.top = top + 'px';
  }
  function described(a) {
    var f = doc.activeElement;
    return f && f !== doc.body && a.contains(f) ? f : a;
  }
  function fill(p, head, body, example) {
    p.innerHTML = '';
    var h = doc.createElement('p'); h.className = 'term-pop__h'; h.textContent = head;
    var b = doc.createElement('p'); b.className = 'term-pop__b'; b.textContent = body;
    p.appendChild(h); p.appendChild(b);
    if (example) { var x = doc.createElement('p'); x.className = 'term-pop__x'; x.textContent = example; p.appendChild(x); }
  }
  function show(a) {
    if (a.hasAttribute('data-tip')) {
      if (current !== a) return;
      var p0 = ensurePop(), lab = a.querySelector('label, .sort, a.term, .th-tip') || a;
      fill(p0, (lab.textContent || '').trim(), a.getAttribute('data-tip'));
      p0.hidden = false; described(a).setAttribute('aria-describedby', 'term-pop');
      place(a);
      return;
    }
    load().then(function (d) {
      var t = d && d[a.getAttribute('data-term')];
      if (!t || current !== a) return;
      var p = ensurePop(), ex = (doc.body && doc.body.getAttribute('data-example-word')) || 'Example';
      fill(p, t.term, t.short, t.example ? ex + ': ' + t.example : '');
      p.hidden = false; a.setAttribute('aria-describedby', 'term-pop');
      place(a);
    });
  }
  function hide() {
    if (pop) pop.hidden = true;
    if (current) {
      current.removeAttribute('aria-describedby');
      var f = current.querySelector && current.querySelector('[aria-describedby="term-pop"]');
      if (f) f.removeAttribute('aria-describedby');
    }
    current = null;
  }
  function owner(e) {
    if (!e.target.closest) return null;
    return e.target.closest('[data-tip]') || e.target.closest('a.term');
  }
  function scheduleHide() { clearTimeout(showTimer); clearTimeout(hideTimer); hideTimer = setTimeout(hide, 260); }
  function onEnter(e) {
    var a = owner(e);
    if (!a) return;
    if (a === current && pop && !pop.hidden) { clearTimeout(hideTimer); return; }
    clearTimeout(hideTimer); clearTimeout(showTimer);
    current = a;
    showTimer = setTimeout(function () { show(a); }, e.type === 'focusin' ? 0 : 140);
  }
  function onLeave(e) {
    var a = owner(e);
    if (a && a === current && !(e.relatedTarget && a.contains(e.relatedTarget))) scheduleHide();
  }
  doc.addEventListener('mouseover', onEnter);
  doc.addEventListener('mouseout', onLeave);
  doc.addEventListener('focusin', onEnter);
  doc.addEventListener('focusout', onLeave);
  doc.addEventListener('keydown', function (e) { if (e.key === 'Escape' && pop && !pop.hidden) hide(); });
  window.addEventListener('scroll', function () { if (current && pop && !pop.hidden) place(current); }, { passive: true });
})();

/* Site search over Statement Map's compact search (statement-map-web/2).
   The backend's search-index.json names the algorithm and this follows it exactly:
   unescape HTML, Unicode NFKC, Python's casefold, unwrap \mathbb \mathcal \mathrm
   \mathbf \text, then the tokens [^\W_]+(?:-[^\W_]+)*. Each token lives in one of 64
   shards, chosen by the first byte of SHA-256 of its UTF-8 bytes. A query matches an
   entry only when every one of its words is among that entry's exact tokens; the
   search fetches only the shards and entry chunks it needs, and every packet must
   carry this page's generation. Exact words, never meanings.
   window.AtlasSearch = { query(q, opts) -> Promise<[{id, kind, name, family_ids, url}]>,
   tokens(q), url(id, kind) }. The front door's plate reads it too. */
(function (global) {
  'use strict';

  /* search-normalise:start (scripts/tests/test_search.py runs this block in Node) */
  /* Python's str.casefold() where it differs from str.lower(), by code point; the
     Cherokee ranges are folded in foldChar. Generated from Python 3.12. */
  var FOLD = {"181":"\u03bc","223":"ss","329":"\u02bcn","383":"s","496":"j\u030c","837":"\u03b9","912":"\u03b9\u0308\u0301","944":"\u03c5\u0308\u0301","962":"\u03c3","976":"\u03b2","977":"\u03b8","981":"\u03c6","982":"\u03c0","1008":"\u03ba","1009":"\u03c1","1013":"\u03b5","1415":"\u0565\u0582","7296":"\u0432","7297":"\u0434","7298":"\u043e","7299":"\u0441","7300":"\u0442","7301":"\u0442","7302":"\u044a","7303":"\u0463","7304":"\ua64b","7830":"h\u0331","7831":"t\u0308","7832":"w\u030a","7833":"y\u030a","7834":"a\u02be","7835":"\u1e61","7838":"ss","8016":"\u03c5\u0313","8018":"\u03c5\u0313\u0300","8020":"\u03c5\u0313\u0301","8022":"\u03c5\u0313\u0342","8064":"\u1f00\u03b9","8065":"\u1f01\u03b9","8066":"\u1f02\u03b9","8067":"\u1f03\u03b9","8068":"\u1f04\u03b9","8069":"\u1f05\u03b9","8070":"\u1f06\u03b9","8071":"\u1f07\u03b9","8072":"\u1f00\u03b9","8073":"\u1f01\u03b9","8074":"\u1f02\u03b9","8075":"\u1f03\u03b9","8076":"\u1f04\u03b9","8077":"\u1f05\u03b9","8078":"\u1f06\u03b9","8079":"\u1f07\u03b9","8080":"\u1f20\u03b9","8081":"\u1f21\u03b9","8082":"\u1f22\u03b9","8083":"\u1f23\u03b9","8084":"\u1f24\u03b9","8085":"\u1f25\u03b9","8086":"\u1f26\u03b9","8087":"\u1f27\u03b9","8088":"\u1f20\u03b9","8089":"\u1f21\u03b9","8090":"\u1f22\u03b9","8091":"\u1f23\u03b9","8092":"\u1f24\u03b9","8093":"\u1f25\u03b9","8094":"\u1f26\u03b9","8095":"\u1f27\u03b9","8096":"\u1f60\u03b9","8097":"\u1f61\u03b9","8098":"\u1f62\u03b9","8099":"\u1f63\u03b9","8100":"\u1f64\u03b9","8101":"\u1f65\u03b9","8102":"\u1f66\u03b9","8103":"\u1f67\u03b9","8104":"\u1f60\u03b9","8105":"\u1f61\u03b9","8106":"\u1f62\u03b9","8107":"\u1f63\u03b9","8108":"\u1f64\u03b9","8109":"\u1f65\u03b9","8110":"\u1f66\u03b9","8111":"\u1f67\u03b9","8114":"\u1f70\u03b9","8115":"\u03b1\u03b9","8116":"\u03ac\u03b9","8118":"\u03b1\u0342","8119":"\u03b1\u0342\u03b9","8124":"\u03b1\u03b9","8126":"\u03b9","8130":"\u1f74\u03b9","8131":"\u03b7\u03b9","8132":"\u03ae\u03b9","8134":"\u03b7\u0342","8135":"\u03b7\u0342\u03b9","8140":"\u03b7\u03b9","8146":"\u03b9\u0308\u0300","8147":"\u03b9\u0308\u0301","8150":"\u03b9\u0342","8151":"\u03b9\u0308\u0342","8162":"\u03c5\u0308\u0300","8163":"\u03c5\u0308\u0301","8164":"\u03c1\u0313","8166":"\u03c5\u0342","8167":"\u03c5\u0308\u0342","8178":"\u1f7c\u03b9","8179":"\u03c9\u03b9","8180":"\u03ce\u03b9","8182":"\u03c9\u0342","8183":"\u03c9\u0342\u03b9","8188":"\u03c9\u03b9","64256":"ff","64257":"fi","64258":"fl","64259":"ffi","64260":"ffl","64261":"st","64262":"st","64275":"\u0574\u0576","64276":"\u0574\u0565","64277":"\u0574\u056b","64278":"\u057e\u0576","64279":"\u0574\u056d"};
  var ENTITY = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
  function unescapeHtml(s) {
    if (s.indexOf('&') < 0) return s;
    if (typeof document !== 'undefined' && document.createElement) {
      var t = document.createElement('textarea');   /* RCDATA: entities decode, tags stay text */
      t.innerHTML = s;
      return t.value;
    }
    return s.replace(/&(#[xX][0-9a-fA-F]+|#[0-9]+|[A-Za-z][A-Za-z0-9]*);/g, function (m, e) {
      if (e.charAt(0) === '#') {
        var cp = e.charAt(1) === 'x' || e.charAt(1) === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
        return cp > 0 && cp < 0x110000 && !(cp >= 0xD800 && cp < 0xE000) ? String.fromCodePoint(cp) : '�';
      }
      return Object.prototype.hasOwnProperty.call(ENTITY, e) ? ENTITY[e] : m;
    });
  }
  function foldChar(ch) {
    var cp = ch.codePointAt(0);
    if (cp >= 0x13A0 && cp <= 0x13F5) return ch;
    if (cp >= 0x13F8 && cp <= 0x13FD) return String.fromCodePoint(cp - 8);
    if (cp >= 0xAB70 && cp <= 0xABBF) return String.fromCodePoint(cp - 0xAB70 + 0x13A0);
    var f = FOLD[cp];
    return f !== undefined ? f : ch.toLowerCase();   /* one character at a time: no final-sigma context */
  }
  function casefold(s) {
    var out = '';
    for (var i = 0; i < s.length;) {
      var cp = s.codePointAt(i);
      var ch = String.fromCodePoint(cp);
      out += foldChar(ch);
      i += ch.length;
    }
    return out;
  }
  var UNWRAP = /\\(?:mathbb|mathcal|mathrm|mathbf|text)\s*\{([^{}]*)\}/g;
  var TOKEN = /[\p{L}\p{N}]+(?:-[\p{L}\p{N}]+)*/gu;
  function searchTokens(text) {
    var t = casefold(unescapeHtml(String(text == null ? '' : text)).normalize('NFKC'));
    t = t.replace(UNWRAP, ' $1 ');
    var seen = Object.create(null), out = [], m = t.match(TOKEN) || [];
    for (var i = 0; i < m.length; i++) if (!seen[m[i]]) { seen[m[i]] = 1; out.push(m[i]); }
    return out.sort();
  }
  /* SHA-256, for the shard of a token when crypto.subtle is unavailable (an http page
     outside localhost). Only the first byte is used. */
  var K256 = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  function utf8(s) {
    if (typeof TextEncoder !== 'undefined') return Array.prototype.slice.call(new TextEncoder().encode(s));
    var b = unescape(encodeURIComponent(s)), out = [];
    for (var i = 0; i < b.length; i++) out.push(b.charCodeAt(i));
    return out;
  }
  function sha256FirstByte(s) {
    var bytes = utf8(s), l = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    for (var s8 = 7; s8 >= 0; s8--) bytes.push(s8 >= 4 ? 0 : (l >>> (s8 * 8)) & 0xff);
    var h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var w = new Array(64);
    for (var off = 0; off < bytes.length; off += 64) {
      for (var i = 0; i < 16; i++) w[i] = (bytes[off + 4 * i] << 24) | (bytes[off + 4 * i + 1] << 16) | (bytes[off + 4 * i + 2] << 8) | bytes[off + 4 * i + 3];
      for (i = 16; i < 64; i++) {
        var a0 = w[i - 15], a1 = w[i - 2];
        var s0 = ((a0 >>> 7) | (a0 << 25)) ^ ((a0 >>> 18) | (a0 << 14)) ^ (a0 >>> 3);
        var s1 = ((a1 >>> 17) | (a1 << 15)) ^ ((a1 >>> 19) | (a1 << 13)) ^ (a1 >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }
      var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
      for (i = 0; i < 64; i++) {
        var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        var t1 = (hh + S1 + ((e & f) ^ (~e & g)) + K256[i] + w[i]) | 0;
        var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        var t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) | 0;
        hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      h[0] = (h[0] + a) | 0; h[1] = (h[1] + b) | 0; h[2] = (h[2] + c) | 0; h[3] = (h[3] + d) | 0;
      h[4] = (h[4] + e) | 0; h[5] = (h[5] + f) | 0; h[6] = (h[6] + g) | 0; h[7] = (h[7] + hh) | 0;
    }
    return (h[0] >>> 24) & 0xff;
  }
  function hex2(n) { n = n % 64; return (n < 16 ? '0' : '') + n.toString(16); }
  function shardSync(token) { return hex2(sha256FirstByte(token)); }
  function shardOf(token) {
    var subtle = global.crypto && global.crypto.subtle;
    if (!subtle || typeof TextEncoder === 'undefined') return Promise.resolve(shardSync(token));
    return subtle.digest('SHA-256', new TextEncoder().encode(token))
      .then(function (buf) { return hex2(new Uint8Array(buf)[0]); }, function () { return shardSync(token); });
  }
  /* The Atlas page that reads each object. */
  function urlFor(id, kind) {
    var i = id.indexOf(':'), rest = id.slice(i + 1);
    var k = kind || { f: 'family', l: 'lean', p: 'manuscript', r: 'statement', d: 'discipline' }[id.slice(0, i)];
    if (k === 'family') return 'families/' + encodeURIComponent(rest) + '.html';
    if (k === 'lean') return 'statements/' + encodeURIComponent(rest) + '.html';
    if (k === 'manuscript') return 'papers/' + encodeURIComponent(rest) + '.html';
    if (k === 'discipline') return 'index.html#o=' + encodeURIComponent(id);
    if (k === 'statement') {
      var j = rest.indexOf(':');
      return 'papers/' + encodeURIComponent(rest.slice(0, j)) + '.html#' + encodeURI(rest.slice(j + 1)).replace(/#/g, '%23');
    }
    return null;
  }
  var NORMALISE = { searchTokens: searchTokens, casefold: casefold, shardSync: shardSync, urlFor: urlFor };
  /* search-normalise:end */

  if (typeof document === 'undefined') { global.AtlasSearchNormalise = NORMALISE; return; }

  var doc = document;
  var body = doc.body || doc.documentElement;
  var root = body.getAttribute('data-root') || '';
  var BASE = root + 'data/search/';
  var GEN = body.getAttribute('data-generation') || '';
  var cache = {};

  function getJSON(path) {
    if (!cache[path]) {
      cache[path] = fetch(BASE + path).then(function (r) {
        if (!r.ok) throw new Error(path + ': HTTP ' + r.status);
        return r.json();
      }).then(function (j) {
        /* A page and its search must come from one generation of the backend. */
        if (GEN && j.generation_id !== GEN) throw new Error(path + ' is from another generation');
        return j;
      });
      cache[path].catch(function () { delete cache[path]; });
    }
    return cache[path];
  }
  function index() { return getJSON('search-index.json'); }
  function labels() { return getJSON('labels.json'); }

  function intersect(lists) {
    lists = lists.slice().sort(function (a, b) { return a.length - b.length; });
    var out = lists[0].slice();
    for (var k = 1; k < lists.length && out.length; k++) {
      var set = {};
      for (var i = 0; i < lists[k].length; i++) set[lists[k][i]] = 1;
      out = out.filter(function (x) { return set[x]; });
    }
    return out.sort(function (a, b) { return a - b; });
  }
  function kindOf(lab, i) {
    for (var k = 0; k < lab.kinds.length; k++) if (i >= lab.kinds[k][1] && i <= lab.kinds[k][2]) return lab.kinds[k][0];
    return 'other';
  }
  function entries(idx, list) {
    var size = idx.entry_chunk_size, need = {};
    list.forEach(function (i) { need[Math.floor(i / size)] = 1; });
    var chunks = Object.keys(need).map(Number);
    return Promise.all(chunks.map(function (c) { return getJSON(idx.entry_chunks[c]); })).then(function (docs) {
      var by = {};
      chunks.forEach(function (c, k) { by[c] = docs[k]; });
      return list.map(function (i) {
        var d = by[Math.floor(i / size)];
        if (d.start !== Math.floor(i / size) * size) throw new Error('entry chunk out of order');
        return d.entries[i % size];
      });
    });
  }
  function decorate(e, lab, idx) {
    var paper = null;
    if (e.kind === 'statement') {
      var rest = e.id.slice(2), j = rest.indexOf(':');
      paper = lab.papers['p:' + rest.slice(0, j)] || null;
    }
    var name = (lab.statement_names || {})[e.id] || e.name;
    return { id: e.id, kind: e.kind, name: name, family_ids: e.family_ids || [], url: urlFor(e.id, e.kind), paper: paper, idx: idx };
  }

  /* The front door's search words (scripts/build_universe.py, data/universe-search/):
     the vocabulary by first letter, each statement's printed name, short formula words
     and the text a result line quotes. Every file must carry this page's generation;
     when one is missing the search keeps to the backend's exact words. */
  var WBASE = root + 'data/universe-search/';
  var wcache = {};
  function getWords(path) {
    if (!wcache[path]) {
      wcache[path] = fetch(WBASE + path).then(function (r) {
        if (!r.ok) throw new Error(path + ': HTTP ' + r.status);
        return r.json();
      }).then(function (j) {
        if (GEN && j.generation_id !== GEN) throw new Error(path + ' is from another generation');
        return j;
      });
      wcache[path].catch(function () { delete wcache[path]; });
    }
    return wcache[path];
  }
  function vocabShard(t) { var c = t.charAt(0); return /[a-z0-9]/.test(c) ? c : '_'; }
  var vocabs = {};
  function vocab(c) {
    if (!vocabs[c]) {
      vocabs[c] = getWords('words.json').then(function (meta) {
        if ((meta.vocab_shards || []).indexOf(c) < 0) return { terms: [], df: {}, flat: {} };
        return getWords('vocab-' + c + '.json').then(function (j) {
          var V = { terms: [], df: {}, flat: {} };
          String(j.terms || '').split('\n').forEach(function (row) {
            var k = row.indexOf('\t');
            if (k < 1) return;
            var t = row.slice(0, k);
            V.terms.push(t); V.df[t] = +row.slice(k + 1);
            var f = t.replace(/-/g, '');
            (V.flat[f] = V.flat[f] || []).push(t);
          });
          return V;
        });
      });
      vocabs[c].catch(function () { delete vocabs[c]; });
    }
    return vocabs[c];
  }
  /* The plural or the singular of an English word, both ways ("matrix", "matrices"). */
  function numberForms(t) {
    var c = [];
    if (/ices$/.test(t)) c.push(t.slice(0, -4) + 'ix', t.slice(0, -4) + 'ex');
    if (/(ix|ex)$/.test(t)) c.push(t.slice(0, -2) + 'ices');
    if (/ies$/.test(t)) c.push(t.slice(0, -3) + 'y');
    if (/[^aeiou]y$/.test(t)) c.push(t.slice(0, -1) + 'ies');
    if (/(s|x|z|ch|sh)es$/.test(t)) c.push(t.slice(0, -2));
    if (/[^su]s$/.test(t)) c.push(t.slice(0, -1));
    if (!/s$/.test(t)) c.push(t + 's');
    if (/(s|x|z|ch|sh)$/.test(t)) c.push(t + 'es');
    return c;
  }
  var PREFIX_MAX = 24;
  /* Every indexed word a typed word stands for: itself; its plural or singular; the
     same word with or without a hyphen ("logconcave", "log-concave"); and, for the last
     word while it is being typed, the words it begins ("Sob" for "Sobolev"). */
  function wordForms(t, V, last) {
    var out = [t];
    var add = function (w) { if (V.df[w] && out.indexOf(w) < 0) out.push(w); };
    if (t.length < 3 || /^[0-9.]+$/.test(t)) return out;
    numberForms(t).forEach(add);
    var flat = t.replace(/-/g, '');
    (V.flat[flat] || []).forEach(add);
    numberForms(flat).forEach(function (f) { (V.flat[f] || []).forEach(add); });
    if (last) {
      var lo = 0, hi = V.terms.length;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (V.terms[mid] < t) lo = mid + 1; else hi = mid; }
      var more = [];
      for (var i = lo; i < V.terms.length && V.terms[i].lastIndexOf(t, 0) === 0; i++) if (V.terms[i] !== t) more.push(V.terms[i]);
      more.sort(function (a, b) { return V.df[b] - V.df[a] || (a < b ? -1 : 1); });
      more.slice(0, PREFIX_MAX).forEach(add);
    }
    return out;
  }
  /* A short formula typed as a word ("L^2", "W^{1,p}", "\ell_1"): the key the build
     gives it (braces and spaces dropped; mirrors ATOM in scripts/build_universe.py), or
     null when the word is not exactly one such formula. */
  var ATOM = /(^|[^A-Za-z\\])([A-Za-z]|\\ell|\\mathbb\s*\{[A-Z]\}|\\mathcal\s*\{[A-Z]\})\s*([\^_])\s*(\{[^{}$]{1,12}\}|\\[A-Za-z]+|[0-9A-Za-z])/g;
  function atomKey(base, op, sup) { return base.replace(/[\s{}]/g, '') + op + sup.replace(/[\s{}]/g, ''); }
  function atomWord(w) {
    var s = String(w).replace(/^\$|\$$/g, '');
    ATOM.lastIndex = 0;
    var m = ATOM.exec(s);
    if (!m || m.index + m[1].length !== 0 || m.index + m[0].length !== s.length) return null;
    return atomKey(m[2], m[3], m[4]);
  }
  function isLiteral(w) {
    var toks = searchTokens(w);
    return toks.length > 0 && toks.every(function (t) { return t.length < 2 || /^[0-9]+$/.test(t); });
  }
  /* How the query is read: per typed word, the index words it stands for (one group
     each; an entry must hold a word of every group), formula words, and whether some
     words are only numbers or single letters ("1.1"), which then must appear as typed. */
  function plan(q) {
    var raw = String(q == null ? '' : q), words = raw.trim().split(/\s+/).filter(Boolean);
    var typingLast = !/\s$/.test(raw);
    var groups = [], atoms = [], literal = false, seen = {};
    words.forEach(function (w, wi) {
      var key = /[\^_]/.test(w) ? atomWord(w) : null;
      if (key) { atoms.push(key); return; }
      if (isLiteral(w) && words.length > 1) literal = true;
      var toks = searchTokens(w);
      toks.forEach(function (t, ti) {
        if (seen[t]) return;
        seen[t] = 1;
        groups.push({ t: t, last: typingLast && wi === words.length - 1 && ti === toks.length - 1 });
      });
    });
    return { groups: groups, atoms: atoms, literal: literal, raw: raw.trim() };
  }
  function expand(pl) {
    return Promise.all(pl.groups.map(function (g) {
      return vocab(vocabShard(g.t)).then(function (V) { return wordForms(g.t, V, g.last); }, function () { return [g.t]; });
    }));
  }
  function atomLists(keys) {
    if (!keys.length) return Promise.resolve([]);
    return getWords('atoms.json').then(function (j) {
      var A = j.atoms || {}, lower = null;
      return keys.map(function (k) {
        if (A[k]) return A[k];
        lower = lower || Object.keys(A).reduce(function (m, x) { (m[x.toLowerCase()] = m[x.toLowerCase()] || []).push(x); return m; }, {});
        var out = {};
        (lower[k.toLowerCase()] || []).forEach(function (x) { A[x].forEach(function (i) { out[i] = 1; }); });
        return Object.keys(out).map(Number).sort(function (a, b) { return a - b; });
      });
    }, function () { return null; });
  }
  function union(lists) {
    if (lists.length === 1) return lists[0];
    var set = {};
    lists.forEach(function (l) { for (var i = 0; i < l.length; i++) set[l[i]] = 1; });
    return Object.keys(set).map(Number).sort(function (a, b) { return a - b; });
  }

  /* Postings for a query: for each typed word, the union of the lists of every index word
     it stands for; then the words intersected. */
  function postings(q) {
    var pl = plan(q);
    if (!pl.groups.length && !pl.atoms.length) return Promise.resolve({ tokens: [], missing: [], hits: [], forms: [], plan: pl });
    return Promise.all([index(), expand(pl), atomLists(pl.atoms)]).then(function (r) {
      var idx = r[0], forms = r[1], alists = r[2];
      // A formula word the build has not seen is read as its plain words.
      if (alists === null || alists.some(function (l) { return !l.length; })) {
        if (pl.atoms.length && !pl.fellBack) {
          var plain = postings(pl.raw.replace(/[\^_{}\\$]/g, ' '));
          return plain.then(function (p) { p.plan.atoms = pl.atoms; p.plan.atomMissing = true; return p; });
        }
        alists = [];
      }
      var terms = [];
      forms.forEach(function (f) { f.forEach(function (t) { if (terms.indexOf(t) < 0) terms.push(t); }); });
      return Promise.all(terms.map(shardOf)).then(function (shards) {
        return Promise.all(shards.map(function (s) {
          var path = idx.shards[s];
          return path ? getJSON(path) : Promise.resolve({ terms: {} });
        }));
      }).then(function (docs) {
        var byTerm = {};
        terms.forEach(function (t, k) { byTerm[t] = (docs[k].terms && docs[k].terms[t]) || []; });
        var lists = forms.map(function (f) { return union(f.map(function (t) { return byTerm[t]; })); });
        var missing = pl.groups.filter(function (g, k) { return !lists[k].length; }).map(function (g) { return g.t; });
        var all = lists.concat(alists);
        return { tokens: pl.groups.map(function (g) { return g.t; }), missing: missing, forms: forms, plan: pl,
                 hits: missing.length || !all.length ? [] : intersect(all), idx: idx };
      });
    });
  }
  /* A query with a word made only of numbers or single letters ("Theorem 1.1") keeps the
     entries that hold the words as typed, together: a statement whose printed name is
     Theorem 1.1, or a Lean file, paper or family whose text says it. */
  function foldPhrase(s) { return casefold(String(s || '').normalize('NFKC')).replace(/[~\s ]+/g, ' ').trim(); }
  function hasPhrase(hay, ph) {
    var h = foldPhrase(hay), at = 0;
    while ((at = h.indexOf(ph, at)) >= 0) {
      var before = h.charAt(at - 1), after = h.slice(at + ph.length, at + ph.length + 2);
      if (!/[\p{L}\p{N}]/u.test(before) && !/^([\p{L}\p{N}]|\.[0-9])/u.test(after)) return true;
      at += 1;
    }
    return false;
  }
  function literalFilter(p, lab) {
    var ph = foldPhrase(p.plan.raw);
    if (!p.plan.literal) return Promise.resolve(p.hits);
    var blocks = {};
    p.hits.forEach(function (i) { var k = kindOf(lab, i); if (k !== 'statement' && k !== 'discipline') blocks[Math.floor(i / 64)] = 1; });
    return Promise.all([getWords('names.json'), Promise.all(Object.keys(blocks).map(function (b) { return textBlock(+b * 64); }))]).then(function (r) {
      var names = r[0].names || [], keep = {};
      p.hits.forEach(function (i) {
        var k = kindOf(lab, i);
        if (k === 'statement' || k === 'discipline') return;
        var b = textCache[Math.floor(i / 64)];
        if (b && hasPhrase(b.text[i - b.start], ph)) keep[i] = 1;
      });
      // Every statement whose printed name is the query ("Theorem 1.1"), whatever its text says.
      names.forEach(function (n, i) { if (n && hasPhrase(n, ph) && foldPhrase(n).length <= ph.length + 2) keep[i] = 1; });
      var kept = Object.keys(keep).map(Number).sort(function (a, b) { return a - b; });
      if (kept.length) p.missing = [];
      return kept.length ? kept : p.hits;
    }, function () { return p.hits; });
  }
  var textCache = {};
  function textBlock(i) {
    var b = Math.floor(i / 64), name = 'text-' + ('000' + b).slice(-4) + '.json';
    return getWords(name).then(function (j) { textCache[b] = j; return j; });
  }

  /* query(q, {statements: n}): every matching family, Lean statement, paper and
     discipline, and the first n matching paper statements (default 400). The array
     also carries .counts by kind, .tokens, .missing, .truncated and .forms (the index
     words each typed word stood for). */
  function exactQuery(q, opts) {
    var limit = (opts && opts.statements != null) ? opts.statements : 400;
    return Promise.all([postings(q), labels()]).then(function (r) {
      var p = r[0], lab = r[1];
      return literalFilter(p, lab).then(function (hits) {
        var counts = { family: 0, lean: 0, manuscript: 0, statement: 0, discipline: 0 };
        var pick = [], st = 0;
        hits.forEach(function (i) {
          var k = kindOf(lab, i);
          counts[k] = (counts[k] || 0) + 1;
          if (k !== 'statement' || st++ < limit) pick.push(i);
        });
        return (pick.length ? entries(p.idx, pick) : Promise.resolve([])).then(function (es) {
          var seen = {}, out = [];
          es.forEach(function (e, k) { if (!seen[e.id]) { seen[e.id] = 1; out.push(decorate(e, lab, pick[k])); } });
          // Family numbers are in the map's own search rows. Preserve that lookup
          // when the shared word index answers instead, retaining its other hits.
          var number = String(q == null ? '' : q).trim(), fid = 'f:' + number;
          var family = /^\d{3}$/.test(number) && (lab.families || {})[fid];
          if (family && !out.some(function (x) { return x.id === fid; })) {
            out.unshift({ id: fid, kind: 'family', name: family.n, family_ids: [fid], url: urlFor(fid, 'family'), paper: null });
            counts.family++;
          }
          out.counts = counts; out.tokens = p.tokens; out.missing = family || hits.length ? [] : p.missing;
          out.forms = p.forms || []; out.atoms = p.plan.atoms || []; out.phrase = p.plan.literal ? p.plan.raw : '';
          out.truncated = counts.statement > limit;
          return out;
        });
      });
    });
  }
  /* A name as the paper or the catalogue prints it: TeX dashes as dashes outside
     mathematics, and the catalogue's own italics; every other tag stays text. */
  function richName(s) {
    var t = String(s == null ? '' : s).split(/(\$[^$]*\$)/).map(function (part, j) {
      return j % 2 ? part : part.replace(/---/g, '—').replace(/--/g, '–');
    }).join('');
    var e = doc.createElement('span');
    e.textContent = t;
    return e.innerHTML.replace(/&lt;(\/?)(i|em|sub|sup)&gt;/g, '<$1$2>');
  }
  function richEl(tag, cls, s) { var e = el(tag, cls); e.innerHTML = richName(s); return e; }
  /* A statement the index names only by its LaTeX label ("thm:main") is named by the
     kind the label's prefix declares and the rest of the label in words. */
  var LABEL_KIND = { thm: 'Theorem', theorem: 'Theorem', lem: 'Lemma', lemma: 'Lemma', prop: 'Proposition',
    cor: 'Corollary', def: 'Definition', defn: 'Definition', conj: 'Conjecture', rem: 'Remark', ex: 'Example',
    eq: 'Equation', fact: 'Fact', fac: 'Fact', claim: 'Claim', obs: 'Observation', q: 'Question', question: 'Question',
    prob: 'Problem', hyp: 'Hypothesis', ass: 'Assumption', assump: 'Assumption', cond: 'Condition', alg: 'Algorithm',
    sec: 'Section', op: 'Open problem', not: 'Notation', step: 'Step', app: 'Appendix', fig: 'Figure', tab: 'Table' };
  function statementName(name) {
    var m = /^([A-Za-z]+):(\S+)$/.exec(name || '');
    if (!m) return null;
    return (LABEL_KIND[m[1].toLowerCase()] || 'Statement') + ' (' + m[2].replace(/[-_:.]+/g, ' ').trim() + ')';
  }
  /* When the exact words find nothing, the usual spellings are tried in turn, and the
     result says which one matched (.respelled): a hyphen where the release prints a dash
     ("Landau-Siegel"), hyphens for spaces ("quasi Riemann"), a name without its accents
     ("Kahler", "Erdos") spelled as the titles spell it, the titles themselves read
     without accents, and a Lean statement's exact name. Nothing is guessed beyond the
     release's own words. */
  function bare(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').normalize('NFC'); }
  /* The words of a query as the reader typed them (case kept), once each, in order:
     what the result line echoes. */
  function typedWords(text) {
    var t = unescapeHtml(String(text == null ? '' : text)).normalize('NFKC').replace(UNWRAP, ' $1 ');
    var seen = Object.create(null), out = [], m = t.match(TOKEN) || [];
    for (var i = 0; i < m.length; i++) { var k = casefold(m[i]); if (!seen[k]) { seen[k] = 1; out.push(m[i]); } }
    return out;
  }
  var accented = null;   /* unaccented word -> the word as the titles print it */
  function accentMap(lab) {
    if (accented) return accented;
    accented = {};
    var add = function (t) { typedWords(t).forEach(function (w) { var f = casefold(w), b = bare(f); if (b !== f && !accented[b]) accented[b] = w; }); };
    Object.keys(lab.papers || {}).forEach(function (k) { add(lab.papers[k]); });
    Object.keys(lab.families || {}).forEach(function (k) { add((lab.families[k] || {}).n); });
    return accented;
  }
  function titleMatches(q, lab) {
    var words = searchTokens(bare(q));
    if (!words.length) return [];
    var hit = function (title) { var t = searchTokens(bare(title)).join(' '); return words.every(function (w) { return (' ' + t + ' ').indexOf(w) >= 0; }); };
    var out = [];
    Object.keys(lab.families || {}).forEach(function (id) {
      var f = lab.families[id] || {};
      if (hit(f.n)) out.push({ id: id, kind: 'family', name: f.n, family_ids: [id], url: urlFor(id, 'family'), paper: null });
    });
    Object.keys(lab.papers || {}).forEach(function (id) {
      if (hit(lab.papers[id])) out.push({ id: id, kind: 'manuscript', name: lab.papers[id], family_ids: [], url: urlFor(id, 'manuscript'), paper: null });
    });
    return out;
  }
  function baseQuery(q, opts) {
    return exactQuery(q, opts).then(function (res) {
      if (!searchTokens(q).length) return res;
      if (res.length) {
        // Exact hits for an unaccented name ("Erdos") come with the hits for the name as
        // the titles print it ("Erdős").
        return labels().then(function (lab) {
          var map = accentMap(lab), toks = searchTokens(q);
          if (!toks.some(function (t) { return map[t]; })) return res;
          return exactQuery(toks.map(function (t) { return map[t] || t; }).join(' '), opts).then(function (more) {
            var seen = {}, out = res.slice();
            res.forEach(function (r) { seen[r.id] = 1; });
            more.forEach(function (r) { if (!seen[r.id]) { seen[r.id] = 1; out.push(r); } });
            out.counts = {};
            Object.keys(res.counts).forEach(function (k) { out.counts[k] = (res.counts[k] || 0) + ((more.counts || {})[k] || 0); });
            out.tokens = res.tokens; out.missing = []; out.truncated = res.truncated || more.truncated;
            return out;
          });
        }, function () { return res; });
      }
      return labels().then(function (lab) {
        var alts = [];
        if (/[-‐‑–—]/.test(q)) alts.push(q.replace(/[-‐‑–—]+/g, ' '));
        var words = q.trim().split(/\s+/);
        if (words.length > 1 && words.length < 5) alts.push(words.join('-'));
        var map = accentMap(lab), toks = searchTokens(q);
        if (toks.some(function (t) { return map[t]; })) alts.push(toks.map(function (t) { return map[t] || t; }).join(' '));
        var tryAlt = function (k) {
          if (k < alts.length) {
            return exactQuery(alts[k], opts).then(function (r2) {
              if (r2.length) { r2.respelled = alts[k]; return r2; }
              return tryAlt(k + 1);
            });
          }
          var byTitle = titleMatches(q, lab);
          if (byTitle.length) {
            var out = byTitle.slice();
            out.counts = { family: 0, lean: 0, manuscript: 0, statement: 0, discipline: 0 };
            out.forEach(function (r) { out.counts[r.kind]++; });
            out.tokens = searchTokens(bare(q)); out.missing = []; out.truncated = false; out.respelled = bare(q);
            return out;
          }
          return res;
        };
        return tryAlt(0);
      }, function () { return res; });
    });
  }
  /* A Lean statement by its exact name, in any case ("ErdosReciprocal", "erdosreciprocal"),
     from labels.json's table of every Lean statement: its own row, with its name in words
     and its family. The index holds only some Lean names as words; the host is never
     asked for a page that may not exist (GitHub Pages matches paths by case). */
  var leanFold = null;
  function leanByName(lab, q) {
    var name = String(q == null ? '' : q).trim();
    if (!lab.lean || !/^[A-Za-z][A-Za-z0-9_']*$/.test(name)) return null;
    if (!leanFold) { leanFold = {}; Object.keys(lab.lean).forEach(function (id) { leanFold[id.toLowerCase()] = id; }); }
    var id = leanFold[name.toLowerCase()];
    if (!id) return null;
    var row = lab.lean[id] || [];
    return { id: 'l:' + id, kind: 'lean', name: row[0] || id, family_ids: row[1] || [], url: urlFor('l:' + id, 'lean'), paper: null };
  }
  /* How closely an entry's own name answers the query: 0 for the Lean statement the query
     names exactly; 1 when the name is the query itself, or holds it as one phrase; 2 when
     the name holds every word as typed (accents aside, so "erdos" ranks the Erdős families
     as "Erdős" does); 3 when it holds every word only in a longer form the word stood for
     ("pi" as "Pixton"); 4 otherwise. So "pi" finds the paper on the exponent of pi before
     Pixton's formula. */
  /* A name prints Greek letters as letters ("π"); a reader types their names ("pi"). */
  var GREEK = { 'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon', 'ζ': 'zeta', 'η': 'eta', 'θ': 'theta',
    'ι': 'iota', 'κ': 'kappa', 'λ': 'lambda', 'μ': 'mu', 'ν': 'nu', 'ξ': 'xi', 'π': 'pi', 'ρ': 'rho', 'σ': 'sigma', 'τ': 'tau',
    'φ': 'phi', 'χ': 'chi', 'ψ': 'psi', 'ω': 'omega', 'Γ': 'gamma', 'Δ': 'delta', 'Θ': 'theta', 'Λ': 'lambda', 'Ξ': 'xi',
    'Π': 'pi', 'Σ': 'sigma', 'Φ': 'phi', 'Ψ': 'psi', 'Ω': 'omega' };
  function greekNames(s) { return String(s || '').replace(/[\u0391-\u03c9]/g, function (c) { return GREEK[c] ? ' ' + GREEK[c] + ' ' : c; }); }
  function nameRank(r, q, forms) {
    var words = searchTokens(bare(q));
    r = { kind: r.kind, id: r.id, name: greekNames(r.name) };
    if (r.kind === 'lean' && casefold(r.id.slice(2)) === casefold(String(q == null ? '' : q).trim())) return 0;
    if (!words.length) return 4;
    var own = searchTokens(bare(r.name)), fm = {};
    /* Between names that answer equally, the one with fewer other words is closer. */
    var near = Math.min(own.length, 99) / 100;
    if (own.join(' ') === words.join(' ')) return 1;
    var flat = function (x) { return ' ' + casefold(bare(String(x || ''))).replace(/[^\p{L}\p{N}]+/gu, ' ').trim() + ' '; };
    if (words.length > 1 && flat(r.name).indexOf(flat(q)) >= 0) return 1 + near;
    if (words.every(function (w) { return own.indexOf(w) >= 0; })) return 2 + near;
    (forms || []).forEach(function (f) { fm[bare(f[0])] = f; });
    return words.every(function (w) {
      var f = fm[w] || [w];
      return f.some(function (x) { return own.indexOf(bare(x)) >= 0; });
    }) ? 3 + near : 4;
  }
  /* One order for every list of results, the dialog's and the front door's: the kinds in
     KIND_ORDER, and within a kind the closest names first, then the release's order. A
     kind holding the Lean statement named exactly comes first. */
  var KIND_ORDER = ['discipline', 'family', 'manuscript', 'statement', 'lean'];
  function rankByName(res, q) {
    var keyed = res.map(function (r, i) { return { r: r, i: i, k: nameRank(r, q, res.forms) }; });
    var exact = keyed.some(function (x) { return x.k === 0; });
    var order = function (kind) { return exact && kind === 'lean' ? -1 : KIND_ORDER.indexOf(kind); };
    keyed.sort(function (a, b) { return order(a.r.kind) - order(b.r.kind) || a.k - b.k || a.i - b.i; });
    keyed.forEach(function (x, i) { res[i] = x.r; });
    res.kindOrder = exact ? ['lean'].concat(KIND_ORDER.filter(function (k) { return k !== 'lean'; })) : KIND_ORDER.slice();
    return res;
  }
  function query(q, opts) {
    return baseQuery(q, opts).then(function (res) {
      return labels().then(function (lab) {
        var hit = leanByName(lab, q), out = res;
        if (hit && !res.some(function (r) { return r.id === hit.id; })) {
          out = [hit].concat(res);
          out.counts = {};
          Object.keys(res.counts || {}).forEach(function (k) { out.counts[k] = res.counts[k]; });
          out.counts.lean = (out.counts.lean || 0) + 1;
          out.tokens = res.tokens; out.truncated = res.truncated;
          out.forms = res.forms; out.atoms = res.atoms; out.phrase = res.phrase;
          out.missing = []; out.respelled = res.length ? res.respelled : null;
        }
        return rankByName(out, q);
      }, function () { return res; });
    });
  }

  /* A statement's name in a result list: the name its paper prints ("Proposition 4.2"),
     with its own title where it has one; never the TeX label it was filed under. */
  function displayName(r, names) {
    if (r.kind !== 'statement') return r.name;
    var printed = r.idx != null && names ? names[r.idx] : null;
    var isLabel = /^[A-Za-z]+:\S*$/.test(r.name || '');
    if (printed) return isLabel ? printed : printed + ' (' + r.name + ')';
    return isLabel ? statementName(r.name) : r.name;
  }
  function names() { return getWords('names.json').then(function (j) { return j.names || []; }, function () { return null; }); }

  /* Why an entry matched: one line of its text (a statement, a Lean file's source, an
     abstract or the catalogue's description) around the first word that matched, the
     words marked. Formulas stay whole and are typeset; a Lean line stays code. */
  function escText(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function reEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function snippet(r, res) {
    if (r.idx == null || r.kind === 'discipline') return Promise.resolve(null);
    return textBlock(r.idx).then(function (b) {
      var text = b.text[r.idx - b.start] || '';
      if (!text) return null;
      var words = [];
      (res.forms || []).forEach(function (f) { f.forEach(function (t) { if (t.length > 1 || (res.forms.length === 1 && !res.atoms.length)) words.push(t); }); });
      (res.phrase ? res.phrase.split(/\s+/) : []).forEach(function (w) { if (isLiteral(w)) words.push(w.toLowerCase()); });
      words.sort(function (a, c) { return c.length - a.length; });
      var wordRe = words.length ? new RegExp('(^|[^\\p{L}\\p{N}])(' + words.map(reEsc).join('|') + ')(?![\\p{L}\\p{N}]|-[\\p{L}\\p{N}])', 'giu') : null;
      var atomHit = function (seg) {
        if (!res.atoms || !res.atoms.length) return false;
        var keys = [], m;
        ATOM.lastIndex = 0;
        while ((m = ATOM.exec(seg))) keys.push(atomKey(m[2], m[3], m[4]).toLowerCase());
        return res.atoms.some(function (a) { return keys.indexOf(a.toLowerCase()) >= 0; });
      };
      var code = r.kind === 'lean';
      // Segments: prose and, outside Lean, formulas between dollars.
      var segs = [], parts = code ? [text] : text.split(/(\$[^$]*\$)/), at = 0;
      parts.forEach(function (s, j) { if (s) segs.push({ s: s, m: !code && j % 2 === 1, a: at }); at += s.length; });
      var first = -1;
      segs.forEach(function (g) {
        if (first >= 0) return;
        if (g.m) { if (atomHit(g.s)) first = g.a; return; }
        if (wordRe) { wordRe.lastIndex = 0; var mm = wordRe.exec(g.s); if (mm) first = g.a + mm.index + mm[1].length; }
      });
      var budget = code ? 150 : 200, start = first < 0 ? 0 : Math.max(0, first - (code ? 40 : 60)), end = start + budget;
      if (code && first >= 0) { var ls = text.lastIndexOf('\n', first); if (ls >= start - 80) start = ls + 1; }
      // Never start or stop inside a formula or a word.
      segs.forEach(function (g) {
        if (g.m && start > g.a && start < g.a + g.s.length) start = g.a;
        if (g.m && end > g.a && end < g.a + g.s.length) end = g.a + g.s.length;
      });
      if (start > 0 && /\S/.test(text.charAt(start - 1))) { var sp = text.indexOf(' ', start); if (sp > 0 && sp < (first < 0 ? start + 30 : first)) start = sp + 1; }
      if (end < text.length && /\S/.test(text.charAt(end))) { var sp2 = text.lastIndexOf(' ', end); if (sp2 > start + 40) end = sp2; }
      var html = '';
      segs.forEach(function (g) {
        var a = Math.max(start, g.a), z = Math.min(end, g.a + g.s.length);
        if (z <= a) return;
        var piece = g.s.slice(a - g.a, z - g.a);
        if (g.m) {
          var span = '<span class="m">' + escText(piece.slice(1, -1)) + '</span>';
          html += atomHit(piece) ? '<mark>' + span + '</mark>' : span;
          return;
        }
        if (code) piece = piece.replace(/\s*\n\s*/g, ' ');
        if (!wordRe) { html += escText(piece); return; }
        var last = 0, mm2;
        wordRe.lastIndex = 0;
        while ((mm2 = wordRe.exec(piece))) {
          var w0 = mm2.index + mm2[1].length;
          html += escText(piece.slice(last, w0)) + '<mark>' + escText(mm2[2]) + '</mark>';
          last = w0 + mm2[2].length;
          if (wordRe.lastIndex === mm2.index) wordRe.lastIndex++;
        }
        html += escText(piece.slice(last));
      });
      // The catalogue's own italics, subscripts and superscripts stay; any other tag is text.
      if (!code) html = html.replace(/&lt;(\/?)(i|em|sub|sup)&gt;/g, '<$1$2>');
      html = (start > 0 ? '… ' : '') + html.trim() + (end < text.length ? ' …' : '');
      return { html: html, code: code, matched: first >= 0 };
    }, function () { return null; });
  }

  /* When nothing matches: the title words nearest to the words that found nothing
     (at most two edits, or sharing a long beginning). */
  var titleWords = null;
  function editDistance(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      var best = i;
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1));
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      prev = cur;
    }
    return prev[b.length];
  }
  function suggest(missing) {
    return labels().then(function (lab) {
      if (!titleWords) {
        titleWords = {};
        var add = function (t) { typedWords(t).forEach(function (w) { if (w.length > 3 && !/^[0-9]+$/.test(w)) { var k = bare(casefold(w)); if (!titleWords[k]) titleWords[k] = w; } }); };
        Object.keys(lab.papers || {}).forEach(function (k) { add(lab.papers[k]); });
        Object.keys(lab.families || {}).forEach(function (k) { add((lab.families[k] || {}).n); });
      }
      var out = [];
      (missing || []).forEach(function (m) {
        var b = bare(casefold(m)), scored = [];
        if (b.length < 3) return;
        var max = b.length > 6 ? 2 : 1;
        Object.keys(titleWords).forEach(function (k) {
          var d = editDistance(b, k, max);
          if (d <= max || (b.length >= 5 && k.lastIndexOf(b.slice(0, 5), 0) === 0)) scored.push([d, k]);
        });
        scored.sort(function (x, y) { return x[0] - y[0] || (x[1] < y[1] ? -1 : 1); });
        scored.slice(0, 5).forEach(function (x) { if (out.indexOf(titleWords[x[1]]) < 0) out.push(titleWords[x[1]]); });
      });
      return out.slice(0, 6);
    }, function () { return []; });
  }

  global.AtlasSearch = { query: query, tokens: searchTokens, url: urlFor, labels: labels,
    statementName: function (n) { return statementName(n); }, richName: function (n) { return richName(n); },
    displayName: displayName, names: names, snippet: snippet, suggest: suggest, kindOrder: KIND_ORDER.slice(),
    family: function (fid) { return labels().then(function (l) { return l.families[fid] || null; }); } };

  /* ---- The search dialog ------------------------------------------------ */
  var dlg = doc.getElementById('search-dialog');
  if (!dlg) return;
  var input = dlg.querySelector('.search__input');
  var list = dlg.querySelector('.search__results');
  var status = dlg.querySelector('.search__status');
  var T = function (k) { return dlg.getAttribute('data-' + k) || ''; };
  var fmt = function (s, o) { return s.replace(/\{(\w+)\}/g, function (m, k) { return o[k] != null ? o[k] : m; }); };
  var SHOW = 6, shown = {}, last = null, seq = 0, sel = -1, timer = 0, renderedQuery = null, NAMES = null;

  function el(tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function quoteList(words) { return words.map(function (w) { return '‘' + w + '’'; }).join(', '); }
  function option(r, lab, k) {
    var a = el('a', 'sr');
    a.href = root + r.url;
    a.id = 'sr-' + k;
    a.setAttribute('role', 'option');
    a.tabIndex = -1;
    if (r.kind === 'family') {
      var fam = lab.families[r.id] || {};
      var t = el('span', 'sr__t');
      t.appendChild(richEl('span', 'sr__name md-math', r.name));
      t.appendChild(el('span', 'sr__k', fmt(T('family'), { n: r.id.slice(2) }) + (fam.d ? ', ' + fam.d : '') + (fam.e ? '. ' + fam.e.charAt(0).toUpperCase() + fam.e.slice(1) + '.' : '')));
      a.appendChild(t);
    } else {
      var tt = el('span', 'sr__t');
      if (r.kind === 'statement') {
        tt.appendChild(richEl('span', 'sr__name md-math', displayName(r, NAMES)));
        tt.appendChild(richEl('span', 'sr__k md-math', r.paper ? fmt(T('in-paper'), { title: r.paper }) : ''));
      } else if (r.kind === 'lean') {
        var nm = el('span', 'sr__name');
        nm.appendChild(el('code', 'sr__code', r.id.slice(2)));
        tt.appendChild(nm);
        var lf = (r.family_ids || [])[0];
        var leanCaption = r.name !== r.id.slice(2) ? r.name : '';
        if (lf) leanCaption += (leanCaption ? ', ' : '') + fmt(T('family'), { n: lf.slice(2) });
        if (leanCaption) tt.appendChild(richEl('span', 'sr__k md-math', leanCaption));
      } else {
        tt.appendChild(richEl('span', 'sr__name md-math', r.name));
        var fams = r.family_ids.map(function (f) { return (lab.families[f] || {}).n || f; });
        if (r.kind === 'manuscript') {
          var caption = fams.length ? fmt(T('in-family'), { name: fams[0] }) : '';
          var edition = (lab.paper_editions || {})[r.id];
          if (edition) caption = edition + (caption ? ' · ' + caption : '');
          if (caption) tt.appendChild(richEl('span', 'sr__k md-math', caption));
        }
        if (r.kind === 'discipline') tt.appendChild(el('span', 'sr__k', fmt(T('discipline-n'), { n: r.family_ids.length })));
      }
      a.appendChild(tt);
    }
    if (r.idx != null && r.kind !== 'discipline') {
      var x = el('span', 'sr__x');
      x.setAttribute('data-snip', String(r.idx));
      (a.querySelector('.sr__t') || a).appendChild(x);
    }
    return a;
  }
  /* Each row's line of text with the matched words marked, filled in as its text arrives. */
  function fillSnippets(scope, res, mine) {
    Array.prototype.forEach.call(scope.querySelectorAll('[data-snip]:not([data-done])'), function (x) {
      x.setAttribute('data-done', '1');
      var r = res.filter(function (h) { return String(h.idx) === x.getAttribute('data-snip'); })[0];
      if (!r) return;
      snippet(r, res).then(function (sn) {
        if (!sn || mine !== seq) { x.remove(); return; }
        x.innerHTML = sn.code ? '<code>' + sn.html + '</code>' : sn.html;
        if (window.atlasRenderMath && !sn.code) window.atlasRenderMath(x);
      });
    });
  }
  function suggestions(res) {
    if (!res.missing || !res.missing.length) return;
    var mine = seq;
    suggest(res.missing).then(function (ws) {
      if (mine !== seq || !ws.length) return;
      var p = el('p', 'sr-suggest');
      p.appendChild(el('span', '', (T('suggest') || 'Words in the titles that come close:') + ' '));
      ws.forEach(function (w, i) {
        var b = el('button', 'sr-suggest__w', w);
        b.type = 'button';
        b.addEventListener('click', function () {
          var q = input.value, re = new RegExp(reEsc(res.missing[0]), 'i');
          input.value = re.test(q) ? q.replace(re, w) : w;
          shown = {}; run(); input.focus();
        });
        p.appendChild(b);
        if (i < ws.length - 1) p.appendChild(doc.createTextNode(', '));
      });
      list.appendChild(p);
    });
  }
  function render(res, lab, said) {
    /* The status echoes the words as typed ("SiegelZeros", not "siegelzeros"). */
    var toks = searchTokens(said), typed = typedWords(said), asTyped = {};
    typed.forEach(function (w) { asTyped[casefold(w)] = w; });
    var shownWords = function (ws) { return quoteList(ws.map(function (w) { return asTyped[w] || w; })); };
    list.innerHTML = '';
    sel = -1;
    input.removeAttribute('aria-activedescendant');
    var total = 0, k = 0, kinds = res.kindOrder || KIND_ORDER;
    KIND_ORDER.forEach(function (kind) { total += res.counts[kind] || 0; });
    if (!toks.length) { status.textContent = ''; dlg.removeAttribute('data-state'); return; }
    if (!total) {
      dlg.setAttribute('data-state', 'empty');
      status.textContent = res.missing.length
        ? fmt(res.missing.length === 1 ? T('missing-one') : T('missing-many'), { words: shownWords(res.missing) })
        : fmt(T('apart'), { words: quoteList(typed) });
      suggestions(res);
      return;
    }
    dlg.setAttribute('data-state', 'results');
    status.textContent = fmt(total === 1 ? T('found-one') : T('found'), { n: total.toLocaleString('en-GB'), words: '‘' + typed.join(' ') + '’' });
    kinds.forEach(function (kind) {
      var n = res.counts[kind] || 0;
      if (!n) return;
      var rows = res.filter(function (r) { return r.kind === kind; });
      /* In query()'s order: the Lean statement named exactly, then entries whose own name
         holds every word (accents aside), then the release's order. */
      var g = el('div', 'sr-group');
      g.setAttribute('role', 'group');
      var hid = 'srg-' + kind;
      var h = el('p', 'sr-group__h');
      h.id = hid;
      h.appendChild(el('span', '', T('kind-' + kind)));
      h.appendChild(el('span', 'count', n.toLocaleString('en-GB')));
      g.setAttribute('aria-labelledby', hid);
      g.appendChild(h);
      var cap = shown[kind] || SHOW;
      rows.slice(0, cap).forEach(function (r) { g.appendChild(option(r, lab, k++)); });
      var have = Math.min(rows.length, cap);
      if (have < n) {
        var more = el('button', 'sr sr--more', fmt(T('more'), { n: (n - have).toLocaleString('en-GB'), kind: T('kind-' + kind).toLowerCase() }));
        more.type = 'button';
        more.id = 'sr-' + k++;
        more.setAttribute('role', 'option');
        more.tabIndex = -1;
        more.setAttribute('data-kind', kind);
        g.appendChild(more);
      }
      list.appendChild(g);
    });
    if (res.truncated && (shown.statement || SHOW) >= res.filter(function (r) { return r.kind === 'statement'; }).length) {
      list.appendChild(el('p', 'sr-note', T('truncated')));
    }
    if (window.atlasRenderMath) window.atlasRenderMath(list);
    fillSnippets(list, res, seq);
  }
  function run() {
    var q = input.value, my = ++seq;
    renderedQuery = null;
    dlg.setAttribute('aria-busy', 'true');
    var want = Math.max(400, shown.statement || 0);
    return Promise.all([query(q, { statements: want }), labels(), names()]).then(function (r) {
      if (my !== seq || input.value !== q) return false;
      last = r[0]; NAMES = r[2];
      dlg.removeAttribute('aria-busy');
      render(r[0], r[1], r[0].respelled || q);
      renderedQuery = q;
      return true;
    }).catch(function () {
      if (my !== seq || input.value !== q) return false;
      dlg.removeAttribute('aria-busy');
      list.innerHTML = '';
      dlg.setAttribute('data-state', 'failed');
      status.textContent = T('failed');
      return false;
    });
  }
  function options() { return list.querySelectorAll('[role="option"]'); }
  function moveSel(d) {
    var items = options();
    if (!items.length) return;
    if (sel >= 0 && items[sel]) items[sel].removeAttribute('aria-selected');
    sel = d === 'home' ? 0 : d === 'end' ? items.length - 1 : sel < 0 ? (d > 0 ? 0 : items.length - 1) : (sel + d + items.length) % items.length;
    items[sel].setAttribute('aria-selected', 'true');
    items[sel].scrollIntoView({ block: 'nearest' });
    input.setAttribute('aria-activedescendant', items[sel].id);
  }
  function choose(item) {
    if (!item) return;
    if (item.tagName === 'BUTTON') {
      var kind = item.getAttribute('data-kind');
      shown[kind] = (shown[kind] || SHOW) + 60;
      var keep = item.id;
      run();
      setTimeout(function () { var n = doc.getElementById(keep); if (n && sel >= 0) input.setAttribute('aria-activedescendant', keep); }, 400);
      return;
    }
    location.href = item.href;
  }
  var opener = doc.querySelector('.search-open');
  var returnTo = null;
  function openSearch(ev) {
    if (ev) ev.preventDefault();
    if (dlg.open) return;
    returnTo = doc.activeElement;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    input.focus();
    input.select();
    index().catch(function () {});
    labels().catch(function () {});
    if (input.value) run();
  }
  if (opener) opener.addEventListener('click', openSearch);
  /* Any other link marked data-open-search (the 404 page's) opens the same dialog; without
     scripts it is a plain link to the Families list. */
  Array.prototype.forEach.call(doc.querySelectorAll('[data-open-search]'), function (a) { a.addEventListener('click', openSearch); });
  dlg.addEventListener('close', function () { if (returnTo && returnTo.focus) returnTo.focus(); });
  input.addEventListener('input', function () {
    shown = {};
    clearTimeout(timer);
    timer = setTimeout(run, 120);
  });
  dlg.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); dlg.close(); }
    else if (ev.key === 'ArrowDown') { ev.preventDefault(); moveSel(1); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); moveSel(-1); }
    else if ((ev.key === 'Home' || ev.key === 'End') && ev.ctrlKey) { ev.preventDefault(); moveSel(ev.key === 'Home' ? 'home' : 'end'); }
    else if (ev.key === 'Enter' && ev.target === input) {
      ev.preventDefault();
      clearTimeout(timer);
      var q = input.value;
      var openChosen = function () {
        var items = options();
        choose(items[sel >= 0 ? sel : 0]);
      };
      if (renderedQuery === q) openChosen();
      else run().then(function (ready) {
        if (ready && dlg.hasAttribute('open') && input.value === q) openChosen();
      });
    }
  });
  list.addEventListener('click', function (ev) {
    var b = ev.target.closest('button.sr--more');
    if (b) { ev.preventDefault(); choose(b); }
  });
  dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); });
  var closeBtn = dlg.querySelector('.search__close');
  if (closeBtn) closeBtn.addEventListener('click', function () { dlg.close(); });
  dlg.querySelector('form').addEventListener('submit', function (ev) { ev.preventDefault(); });
  doc.addEventListener('keydown', function (ev) {
    var a = doc.activeElement || {};
    if (ev.key === '/' && !ev.metaKey && !ev.ctrlKey && !ev.altKey && !/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName || '') && !a.isContentEditable) {
      openSearch(ev);
    }
  });
})(typeof window !== 'undefined' ? window : globalThis);

/* ---- How to use the Atlas (the header's ? guide) ------------------------------------ */
/* The guide is server-rendered in every page (build_site.help_dialog); this opens and
   closes it like the search dialog: the ? button, the ? key when not typing, ?help=1 in
   the address, or any element with data-help="<step id>", which opens the guide at that
   step. Escape, the Close button and a click on the backdrop close it, and focus returns
   to where it was. On the map a one-line first-visit hint offers it until dismissed. */
(function (g) {
  'use strict';
  var doc = g.document;
  if (!doc) return;
  var dlg = doc.getElementById('help-dialog');
  if (!dlg) return;
  var btn = doc.querySelector('.help-open');
  var hint = doc.getElementById('first-hint');
  var returnTo = null;
  var KEY = 'atlas-help-hint';
  function store(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function dismissHint() { if (hint) hint.hidden = true; store('off'); }
  function openHelp(ev, step) {
    if (ev) ev.preventDefault();
    if (dlg.open) return;
    returnTo = doc.activeElement;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    if (hint && !hint.hidden) dismissHint();
    var target = step ? doc.getElementById('help-' + step) : null;
    Array.prototype.forEach.call(dlg.querySelectorAll('.help__steps li'), function (li) { li.classList.toggle('is-on', li === target); });
    var close = dlg.querySelector('.help__close');
    if (target) { target.setAttribute('tabindex', '-1'); target.scrollIntoView({ block: 'center' }); target.focus({ preventScroll: true }); }
    else if (close) close.focus();
  }
  function closeHelp() { if (dlg.open) { if (dlg.close) dlg.close(); else { dlg.removeAttribute('open'); dlg.dispatchEvent(new Event('close')); } } }
  if (btn) { btn.setAttribute('aria-expanded', 'false'); btn.addEventListener('click', function (ev) { openHelp(ev); }); }
  doc.addEventListener('click', function (ev) {
    var t = ev.target && ev.target.closest ? ev.target.closest('[data-help], .hint__open') : null;
    if (t) openHelp(ev, t.getAttribute('data-help') || '');
  });
  dlg.addEventListener('close', function () {
    if (btn) btn.setAttribute('aria-expanded', 'false');
    if (returnTo && returnTo.focus) returnTo.focus();
  });
  dlg.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); closeHelp(); } });
  dlg.addEventListener('click', function (ev) { if (ev.target === dlg) closeHelp(); });
  var closeBtn = dlg.querySelector('.help__close');
  if (closeBtn) closeBtn.addEventListener('click', closeHelp);
  doc.addEventListener('keydown', function (ev) {
    var a = doc.activeElement || {};
    if (ev.key !== '?' || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName || '') || a.isContentEditable) return;
    var other = doc.querySelector('dialog[open]:not(#help-dialog)');
    if (other) return;
    openHelp(ev);
  });
  if (hint) {
    var off = null;
    try { off = localStorage.getItem(KEY); } catch (e) {}
    if (off !== 'off') hint.hidden = false;
    var x = hint.querySelector('.hint__x');
    if (x) x.addEventListener('click', dismissHint);
    var ex = hint.querySelector('.hint__ex');
    if (ex) ex.addEventListener('click', function () { store('off'); });
  }
  try {
    var q = new URLSearchParams(g.location.search);
    if (q.get('help') === '1') openHelp(null, q.get('step') || '');
  } catch (e) {}
})(typeof window !== 'undefined' ? window : globalThis);
