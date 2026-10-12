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
  function norm(s) { return (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }

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

  /* The Families list: filters by discipline, evidence, each outside reader's finding
     and words, combined; the state lives in the address (?d=&c=&l=&r=&q=) so a
     filtered list can be shared. Without JavaScript the whole list shows and the
     filters stay hidden. */
  Array.prototype.forEach.call(doc.querySelectorAll('[data-filter-families]'), function (wrap) {
    var table = doc.getElementById(wrap.getAttribute('data-filter-families'));
    if (!table) return;
    var empty = doc.querySelector('.filters__empty');
    var reset = wrap.querySelector('.filters__reset');
    var KEYS = ['d', 'c', 'l', 'r', 'q'];
    var state = { d: '', c: '', l: '', r: '', q: '' };
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
          (!state.l || row.getAttribute('data-l') === state.l) &&
          (!state.r || row.getAttribute('data-r') === state.r) &&
          words.every(function (w) { return norm(q).indexOf(w) >= 0; });
        row.hidden = !ok;
        if (ok) n++;
      });
      shownCount(wrap, n);
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
        var u = new URLSearchParams();
        KEYS.forEach(function (k) { if (state[k]) u.set(k, state[k]); });
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
   word is a plain link to the glossary page. */
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
    var top = below ? r.bottom + window.scrollY + 8 : r.top + window.scrollY - h - 8;
    p.style.left = left + 'px'; p.style.top = top + 'px';
  }
  function show(a) {
    load().then(function (d) {
      var t = d && d[a.getAttribute('data-term')];
      if (!t || current !== a) return;
      var p = ensurePop();
      p.innerHTML = '';
      var h = doc.createElement('p'); h.className = 'term-pop__h'; h.textContent = t.term;
      var b = doc.createElement('p'); b.className = 'term-pop__b'; b.textContent = t.short;
      p.appendChild(h); p.appendChild(b);
      p.hidden = false; a.setAttribute('aria-describedby', 'term-pop');
      place(a);
    });
  }
  function hide() {
    if (pop) pop.hidden = true;
    if (current) current.removeAttribute('aria-describedby');
    current = null;
  }
  function scheduleHide() { clearTimeout(showTimer); clearTimeout(hideTimer); hideTimer = setTimeout(hide, 260); }
  function onEnter(e) {
    var a = e.target.closest && e.target.closest('a.term');
    if (!a) return;
    clearTimeout(hideTimer); clearTimeout(showTimer);
    current = a;
    showTimer = setTimeout(function () { show(a); }, e.type === 'focusin' ? 0 : 140);
  }
  function onLeave(e) {
    var a = e.target.closest && e.target.closest('a.term');
    if (a && a === current) scheduleHide();
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

  /* search-normalise:start (scripts/test_search.py runs this block in Node) */
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
  var KIND_ORDER = ['family', 'lean', 'manuscript', 'statement', 'discipline'];
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
  function decorate(e, lab) {
    var paper = null;
    if (e.kind === 'statement') {
      var rest = e.id.slice(2), j = rest.indexOf(':');
      paper = lab.papers['p:' + rest.slice(0, j)] || null;
    }
    return { id: e.id, kind: e.kind, name: e.name, family_ids: e.family_ids || [], url: urlFor(e.id, e.kind), paper: paper };
  }

  /* Postings for a query: every token's list, intersected. */
  function postings(q) {
    var toks = searchTokens(q);
    if (!toks.length) return Promise.resolve({ tokens: [], missing: [], hits: [] });
    return Promise.all([index(), Promise.all(toks.map(shardOf))]).then(function (r) {
      var idx = r[0], shards = r[1];
      return Promise.all(shards.map(function (s) {
        var path = idx.shards[s];
        return path ? getJSON(path) : Promise.resolve({ terms: {} });
      })).then(function (docs) {
        var lists = docs.map(function (d, k) { return (d.terms && d.terms[toks[k]]) || []; });
        var missing = toks.filter(function (t, k) { return !lists[k].length; });
        return { tokens: toks, missing: missing, hits: missing.length ? [] : intersect(lists), idx: idx };
      });
    });
  }

  /* query(q, {statements: n}): every matching family, Lean statement, paper and
     discipline, and the first n matching paper statements (default 400). The array
     also carries .counts by kind, .tokens, .missing and .truncated. */
  function exactQuery(q, opts) {
    var limit = (opts && opts.statements != null) ? opts.statements : 400;
    return Promise.all([postings(q), labels()]).then(function (r) {
      var p = r[0], lab = r[1], counts = { family: 0, lean: 0, manuscript: 0, statement: 0, discipline: 0 };
      var pick = [], st = 0;
      p.hits.forEach(function (i) {
        var k = kindOf(lab, i);
        counts[k] = (counts[k] || 0) + 1;
        if (k !== 'statement' || st++ < limit) pick.push(i);
      });
      return (pick.length ? entries(p.idx, pick) : Promise.resolve([])).then(function (es) {
        var out = es.map(function (e) { return decorate(e, lab); });
        out.counts = counts; out.tokens = p.tokens; out.missing = p.missing;
        out.truncated = counts.statement > limit;
        return out;
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
  function bare(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  var accented = null;   /* unaccented word -> the word as the titles print it */
  function accentMap(lab) {
    if (accented) return accented;
    accented = {};
    var add = function (t) { searchTokens(t).forEach(function (w) { var b = bare(w); if (b !== w && !accented[b]) accented[b] = w; }); };
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
  function query(q, opts) {
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
          // A Lean statement by its exact name, when the index does not hold it as a word.
          if (/^[A-Za-z][A-Za-z0-9_']{3,}$/.test(q.trim()) && typeof fetch === 'function') {
            var name = q.trim();
            return fetch(root + 'statements/' + encodeURIComponent(name) + '.html', { method: 'HEAD' }).then(function (r) {
              if (!r.ok) return res;
              var one = [{ id: 'l:' + name, kind: 'lean', name: name, family_ids: [], url: urlFor('l:' + name, 'lean'), paper: null }];
              one.counts = { family: 0, lean: 1, manuscript: 0, statement: 0, discipline: 0 };
              one.tokens = [name]; one.missing = []; one.truncated = false; one.respelled = name;
              return one;
            }, function () { return res; });
          }
          return res;
        };
        return tryAlt(0);
      }, function () { return res; });
    });
  }
  global.AtlasSearch = { query: query, tokens: searchTokens, url: urlFor, labels: labels,
    statementName: function (n) { return statementName(n); }, richName: function (n) { return richName(n); },
    family: function (fid) { return labels().then(function (l) { return l.families[fid] || null; }); } };

  /* ---- The search dialog ------------------------------------------------ */
  var dlg = doc.getElementById('search-dialog');
  if (!dlg) return;
  var input = dlg.querySelector('.search__input');
  var list = dlg.querySelector('.search__results');
  var status = dlg.querySelector('.search__status');
  var T = function (k) { return dlg.getAttribute('data-' + k) || ''; };
  var fmt = function (s, o) { return s.replace(/\{(\w+)\}/g, function (m, k) { return o[k] != null ? o[k] : m; }); };
  var SHOW = 6, shown = {}, last = null, seq = 0, sel = -1, timer = 0, renderedQuery = null;

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
        var sn = statementName(r.name);
        tt.appendChild(sn ? el('span', 'sr__name', sn) : richEl('span', 'sr__name md-math', r.name));
        tt.appendChild(richEl('span', 'sr__k md-math', r.paper ? fmt(T('in-paper'), { title: r.paper }) : ''));
      } else if (r.kind === 'lean') {
        var nm = el('span', 'sr__name');
        nm.appendChild(el('code', 'sr__code', r.id.slice(2)));
        tt.appendChild(nm);
        tt.appendChild(richEl('span', 'sr__k md-math', r.name));
      } else {
        tt.appendChild(richEl('span', 'sr__name md-math', r.name));
        var fams = r.family_ids.map(function (f) { return (lab.families[f] || {}).n || f; });
        if (r.kind === 'manuscript' && fams.length) tt.appendChild(richEl('span', 'sr__k md-math', fmt(T('in-family'), { name: fams[0] })));
        if (r.kind === 'discipline') tt.appendChild(el('span', 'sr__k', fmt(T('discipline-n'), { n: r.family_ids.length })));
      }
      a.appendChild(tt);
    }
    return a;
  }
  function render(res, lab, toks) {
    list.innerHTML = '';
    sel = -1;
    input.removeAttribute('aria-activedescendant');
    var total = 0, k = 0;
    KIND_ORDER.forEach(function (kind) { total += res.counts[kind] || 0; });
    if (!toks.length) { status.textContent = ''; dlg.removeAttribute('data-state'); return; }
    if (!total) {
      dlg.setAttribute('data-state', 'empty');
      status.textContent = res.missing.length
        ? fmt(res.missing.length === 1 ? T('missing-one') : T('missing-many'), { words: quoteList(res.missing) })
        : fmt(T('apart'), { words: quoteList(toks) });
      return;
    }
    dlg.setAttribute('data-state', 'results');
    status.textContent = fmt(T('found'), { n: total.toLocaleString('en-GB'), words: quoteList(toks) });
    KIND_ORDER.forEach(function (kind) {
      var n = res.counts[kind] || 0;
      if (!n) return;
      var rows = res.filter(function (r) { return r.kind === kind; });
      /* Entries whose own name holds every word come first; otherwise the release's order. */
      rows.sort(function (a, b) {
        var na = searchTokens(a.name), nb = searchTokens(b.name);
        var ha = toks.every(function (t) { return na.indexOf(t) >= 0; }) ? 0 : 1;
        var hb = toks.every(function (t) { return nb.indexOf(t) >= 0; }) ? 0 : 1;
        return ha - hb;
      });
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
  }
  function run() {
    var q = input.value, my = ++seq;
    renderedQuery = null;
    var toks = searchTokens(q);
    dlg.setAttribute('aria-busy', 'true');
    var want = Math.max(400, shown.statement || 0);
    return Promise.all([query(q, { statements: want }), labels()]).then(function (r) {
      if (my !== seq || input.value !== q) return false;
      last = r[0];
      dlg.removeAttribute('aria-busy');
      render(r[0], r[1], r[0].respelled ? searchTokens(r[0].respelled) : toks);
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
