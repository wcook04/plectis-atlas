/* Plectis Atlas: the reading view of a paper (papers/<slug>.html).
   Typesets every formula with KaTeX and the paper's own macros, with the options
   scripts/check_paper_math.mjs used to check it, and marks the passage a link
   lands on. A formula KaTeX cannot typeset keeps its TeX source. No frameworks. */
(function () {
  'use strict';
  var doc = document;
  var art = doc.getElementById('pr-paper');
  if (!art) return;
  var scope = doc.querySelector('.pr-page') || doc.body;
  var macros = {};
  var src = doc.getElementById('pr-macros');
  if (src) { try { macros = JSON.parse(src.textContent); } catch (e) { macros = {}; } }
  var opts = {
    leqno: art.getAttribute('data-leqno') === '1',
    fleqn: art.getAttribute('data-fleqn') === '1',
    failed: art.getAttribute('data-math-failed') || ''
  };
  var stats = window.__paperMath = { ok: 0, failed: 0, errors: [], done: false };
  var moved = false;
  ['wheel', 'touchmove', 'keydown', 'mousedown'].forEach(function (ev) {
    window.addEventListener(ev, function () { moved = true; }, { passive: true, once: true });
  });

  function typeset(node) {
    var tex = node.textContent;
    var display = node.getAttribute('data-d') === '1';
    try {
      // A short inline formula stays on one line (atlas.js keepShort).
      window.katex.render(!display && window.atlasKeepShortMath ? window.atlasKeepShortMath(tex) : tex, node, {
        displayMode: display,
        macros: Object.assign({}, macros),
        throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000,
        leqno: opts.leqno, fleqn: opts.fleqn
      });
      node.classList.add('pr-m--ok');
      stats.ok++;
    } catch (err) {
      node.textContent = tex;
      node.classList.add('pr-m--fail');
      node.title = opts.failed;
      stats.failed++;
      if (stats.errors.length < 50) stats.errors.push(String((err && err.message) || err).slice(0, 200));
    }
  }

  /* The passage a link lands on: the whole statement, equation or entry. */
  var current = null;
  function target() {
    var id = decodeURIComponent(location.hash.replace(/^#/, ''));
    if (!id) return null;
    var el = doc.getElementById(id);
    if (!el) return null;
    var host = el.classList.contains('pr-lbl') ? el.parentElement : el;
    return (host && host.closest('.pr-thm, .pr-eq, .pr-float, .pr-sec, .pr-part, .pr-runin, .pr-list > li, .pr-bib-item, .pr-fn, .pr-proof, p')) || el;
  }
  function land(scroll) {
    var el = target();
    if (current && current !== el) current.classList.remove('pr-target');
    if (!el) return;
    el.classList.add('pr-target');
    current = el;
    if (scroll) el.scrollIntoView({ block: 'start' });
  }
  window.addEventListener('hashchange', function () { moved = false; land(true); });

  function start() {
    land(false);
    var nodes = Array.prototype.slice.call(scope.querySelectorAll('span.pr-m'));
    if (!window.katex) {
      doc.documentElement.setAttribute('data-paper-math', 'unavailable');
      return;
    }
    var i = 0;
    function once(node) {
      if (node.__typeset) return;
      node.__typeset = true;
      typeset(node);
    }
    /* What the reader can see comes first: formulas near the viewport are typeset as
       they approach it (a deep link lands mid-paper), and the slices below fill in the
       rest of the paper in order. */
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { once(e.target); io.unobserve(e.target); } });
      }, { rootMargin: '800px 0px' });
      nodes.forEach(function (n) { io.observe(n); });
    }
    /* Typeset in slices so a long paper stays responsive; while the reader has not
       scrolled, keep the linked passage in view as the text above it changes. */
    function slice() {
      var t0 = Date.now();
      while (i < nodes.length && Date.now() - t0 < 40) once(nodes[i++]);
      if (location.hash && !moved) land(true);
      if (i < nodes.length) { requestAnimationFrame(slice); return; }
      stats.done = true;
      doc.documentElement.setAttribute('data-paper-math', stats.failed ? 'partial' : 'ready');
    }
    slice();
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start); else start();
})();
