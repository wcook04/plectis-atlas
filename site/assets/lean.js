/* Plectis Atlas: the Lean statement page's file view (statements/<id>.html),
   written by scripts/lean_render.py's file_section. Loaded once, deferred. */
(function () {
  'use strict';
  /* The file view's behaviour: the panel's filter, the relations under a row,
     and the card that shows a declaration when its name is hovered or focused.
     The panel follows the Plectis import map (ai_workflow
     tools/meta/dissemination/maths_site_assets/maths.js at 4b1ebab611): the list
     is the object, controls stay hidden until this runs, and every row keeps a
     working link without it. */
  var box = document.querySelector('[data-lx]');
  if (!box) return;
  var cfg;
  try { cfg = JSON.parse(box.querySelector('[data-lx-json]').textContent); } catch (e) { return; }
  var S = cfg.strings || {}, data = cfg.data || { n: [], u: [] };
  var fmt = function (n) { return n.toLocaleString('en-GB'); };
  var list = box.querySelector('[data-lx-list]');
  var rows = list ? Array.prototype.slice.call(list.children) : [];
  var usedBy = data.n.map(function () { return []; });
  data.u.forEach(function (us, i) { us.forEach(function (j) { usedBy[j].push(i); }); });

  var controls = box.querySelector('[data-lx-controls]');
  var search = box.querySelector('[data-lx-search]');
  var direct = box.querySelector('[data-lx-direct]');
  var count = box.querySelector('[data-lx-count]');
  var empty = box.querySelector('[data-lx-empty]');
  function filter() {
    var q = (search && search.value || '').trim().toLowerCase();
    var only = !!(direct && direct.checked);
    var shown = 0;
    rows.forEach(function (row) {
      var hide = (only && !row.classList.contains('is-direct')) || (q && row.getAttribute('data-q').indexOf(q) < 0);
      row.hidden = !!hide;
      if (!hide) shown++;
    });
    if (count) count.textContent = shown === rows.length ? '' : S.shown.replace('{n}', fmt(shown)).replace('{total}', fmt(rows.length));
    if (empty) empty.hidden = shown > 0;
  }
  if (controls) {
    controls.hidden = false;
    if (search) search.addEventListener('input', filter);
    if (direct) direct.addEventListener('change', filter);
  }
  var clear = box.querySelector('[data-lx-clear]');
  if (clear) clear.addEventListener('click', function () {
    if (search) search.value = '';
    if (direct) direct.checked = false;
    filter();
    if (search) search.focus();
  });

  Array.prototype.forEach.call(box.querySelectorAll('.lxp-rel'), function (b) { b.hidden = false; });
  function relLine(label, ids) {
    var p = document.createElement('p');
    p.className = 'lxp-relline';
    var k = document.createElement('span');
    k.className = 'lxp-relk';
    k.textContent = label;
    p.appendChild(k);
    if (!ids.length) {
      var none = document.createElement('span');
      none.className = 'lxp-relnone';
      none.textContent = S.rel_none;
      p.appendChild(none);
      return p;
    }
    ids.forEach(function (i) {
      var a = document.createElement('a');
      a.href = '#L' + data.n[i][0];
      a.textContent = data.n[i][1];
      p.appendChild(a);
    });
    return p;
  }
  if (list) list.addEventListener('click', function (ev) {
    var b = ev.target.closest('.lxp-rel');
    if (!b) return;
    var row = b.closest('.lxp-row');
    var open = b.getAttribute('aria-expanded') === 'true';
    var old = row.querySelector('.lxp-rels');
    if (old) old.remove();
    b.setAttribute('aria-expanded', open ? 'false' : 'true');
    if (open) return;
    var i = +b.getAttribute('data-rel');
    var rel = document.createElement('div');
    rel.className = 'lxp-rels';
    rel.appendChild(relLine(S.uses, data.u[i]));
    rel.appendChild(relLine(S.used_by, usedBy[i]));
    row.appendChild(rel);
  });

  /* The panel row of the declaration a link lands on is marked and kept in view. */
  var marked = null;
  function sync() {
    var id = decodeURIComponent((location.hash || '').slice(1));
    if (!/^L\d+$/.test(id) || !list) return;
    var row = list.querySelector('.lxp-go[href="#' + id + '"]');
    if (marked) marked.classList.remove('is-here');
    marked = row ? row.closest('.lxp-row') : null;
    if (!marked) return;
    marked.classList.add('is-here');
    var pane = list.closest('.lxp');
    if (pane && pane.scrollHeight > pane.clientHeight) {
      var top = marked.offsetTop - pane.offsetTop;
      if (top < pane.scrollTop || top > pane.scrollTop + pane.clientHeight - 40) pane.scrollTop = Math.max(0, top - 60);
    }
  }
  window.addEventListener('hashchange', sync);
  sync();

  var card = box.querySelector('[data-lx-card]');
  var code = box.querySelector('.lx-code');
  var timer = null, current = null;
  var SEL = '.lx-code a, .lxp-go';
  function hide() {
    clearTimeout(timer);
    timer = null;
    current = null;
    if (card && !card.hidden) { card.hidden = true; card.textContent = ''; }
  }
  function nextLine(el) {
    if (el.nextElementSibling) return el.nextElementSibling;
    var chunk = el.parentElement;
    if (chunk && chunk.classList.contains('lx-k') && chunk.nextElementSibling) return chunk.nextElementSibling.firstElementChild;
    return null;
  }
  function para(cls, text) {
    var p = document.createElement('p');
    p.className = cls;
    p.textContent = text;
    return p;
  }
  function fill(a) {
    var href = a.getAttribute('href') || '';
    card.textContent = '';
    if (href.charAt(0) === '#') {
      var line = document.getElementById(href.slice(1));
      if (!line) return false;
      card.appendChild(para('lx-card__t', S.card_local.replace('{line}', fmt(+line.getAttribute('data-n')))));
      var pre = document.createElement('pre');
      pre.className = 'lx-card__code';
      var n = +(line.getAttribute('data-h') || 1), el = line;
      for (var k = 0; k < n && el; k++) {
        var c = el.cloneNode(true);
        c.removeAttribute('id');
        pre.appendChild(c);
        el = nextLine(el);
      }
      card.appendChild(pre);
      return true;
    }
    var m = /pattern=([^#&]+)/.exec(href);
    if (m) {
      card.appendChild(para('lx-card__t', S.card_mathlib));
      card.appendChild(para('lx-card__n', decodeURIComponent(m[1])));
      return true;
    }
    var o = /\/lean\/(.+)#L(\d+)$/.exec(href);
    card.appendChild(para('lx-card__t', (a.classList.contains('lib') ? S.card_library : S.card_oai).replace('{commit}', cfg.commit)));
    card.appendChild(para('lx-card__n', o ? decodeURIComponent(o[1]) + ':' + o[2] : href));
    return true;
  }
  function show(a) {
    if (!card || current === a) return;
    current = a;
    if (!fill(a)) { hide(); return; }
    card.style.left = '0px';
    card.style.top = '0px';
    card.hidden = false;
    var r = a.getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight;
    var left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    card.style.left = left + 'px';
    card.style.top = top + 'px';
  }
  box.addEventListener('mouseover', function (ev) {
    var a = ev.target.closest(SEL);
    if (!a || a === current) return;
    clearTimeout(timer);
    timer = setTimeout(function () { show(a); }, 140);
  });
  box.addEventListener('mouseout', function (ev) {
    var a = ev.target.closest(SEL);
    if (!a || (ev.relatedTarget && a.contains(ev.relatedTarget))) return;
    hide();
  });
  box.addEventListener('focusin', function (ev) { var a = ev.target.closest(SEL); if (a) show(a); });
  box.addEventListener('focusout', hide);
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') hide(); });
  /* Scrolling moves the name away from a card already showing; a card still
     waiting for its dwell is left to the pointer events. */
  function hideShown() { if (card && !card.hidden) hide(); }
  window.addEventListener('scroll', hideShown, { passive: true });
  if (code) code.addEventListener('scroll', hideShown, { passive: true });
  var pane = box.querySelector('.lxp');
  if (pane) pane.addEventListener('scroll', hideShown, { passive: true });
})();

/* The contents rail beside a wide page: the section being read is marked with
   aria-current, from the last heading above a line a third of the way down. */
(function () {
  'use strict';
  var nav = document.querySelector('.lxs-toc');
  if (!nav) return;
  var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
  var targets = links.map(function (a) { return document.getElementById(decodeURIComponent(a.hash.slice(1))); });
  var queued = false;
  function mark() {
    queued = false;
    if (!nav.offsetParent) return;
    var line = window.innerHeight / 3, cur = 0;
    targets.forEach(function (t, i) { if (t && t.getBoundingClientRect().top <= line) cur = i; });
    links.forEach(function (a, i) { if (i === cur) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
  }
  function queue() { if (!queued) { queued = true; requestAnimationFrame(mark); } }
  window.addEventListener('scroll', queue, { passive: true });
  window.addEventListener('resize', queue);
  mark();
})();
