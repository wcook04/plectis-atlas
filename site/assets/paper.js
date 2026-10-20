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
      if (display && window.atlasFitMath) window.atlasFitMath(node);
      // copy-tex copies the annotation: keep it the paper's TeX, without keepShort's braces.
      var ann = node.querySelector('annotation');
      if (ann) ann.textContent = tex;
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
  var words = {};
  var wsrc = doc.getElementById('pr-words');
  if (wsrc) { try { words = JSON.parse(wsrc.textContent); } catch (e) { words = {}; } }
  function W(key, sub) {
    var s = words[key] || key;
    for (var k in (sub || {})) s = s.split('{' + k + '}').join(sub[k]);
    return s;
  }

  /* ---- The heading of a statement: Lean, Link, Copy TeX ----------------------
     A short link to each Lean statement the atlas pairs with the theorem (from the
     atlas note after it), a button copying the address of the statement, and one
     copying its TeX. The copying is atlas.js's data-copy-text. Added here, not in
     the HTML, so a passage cloned into another page carries none of them. */
  function addTools() {
    var base = art.getAttribute('data-url') || location.href.split('#')[0];
    var thms = art.querySelectorAll('.pr-thm[data-tex]');
    for (var i = 0; i < thms.length; i++) {
      var thm = thms[i];
      var h = thm.querySelector('.pr-thm-h');
      if (!h || !thm.id) continue;
      var name = (h.querySelector('.pr-thm-n') || h).textContent.trim();
      var bar = doc.createElement('span');
      bar.className = 'pr-tools';
      var note = thm.nextElementSibling;
      if (note && note.classList.contains('pr-atlas')) {
        var leans = note.querySelectorAll('.pr-lean a[data-tag]');
        for (var j = 0; j < leans.length; j++) {
          var a = doc.createElement('a');
          a.className = 'pr-tool pr-tool--lean';
          a.href = leans[j].getAttribute('href');
          var lean = leans[j].textContent.trim();
          var tag = leans[j].getAttribute('data-tag');
          a.setAttribute('aria-label', W('lean_label', { lean: lean, tag: tag }));
          a.innerHTML = '<span class="pr-tool__k"></span> <code></code><span class="pr-tool__tag"></span>';
          a.firstChild.textContent = W('lean');
          a.querySelector('code').textContent = lean;
          a.lastChild.textContent = ', ' + tag;
          bar.appendChild(a);
        }
      }
      var link = doc.createElement('button');
      link.type = 'button';
      link.className = 'pr-tool';
      link.textContent = W('link');
      link.setAttribute('aria-label', W('link_label', { name: name }));
      link.setAttribute('data-copy-text', base + '#' + encodeURI(thm.id).replace(/#/g, '%23'));
      link.setAttribute('data-copied', W('copied'));
      var tex = doc.createElement('button');
      tex.type = 'button';
      tex.className = 'pr-tool';
      tex.textContent = W('tex');
      tex.setAttribute('aria-label', W('tex_label', { name: name }));
      tex.setAttribute('data-copy-text', thm.getAttribute('data-tex'));
      tex.setAttribute('data-copied', W('copied'));
      bar.appendChild(link);
      bar.appendChild(tex);
      // Before the statement's paragraph, not inside it, so selecting the statement copies none of it.
      thm.insertBefore(bar, thm.firstChild);
    }
  }

  /* ---- Preview of a reference ------------------------------------------------
     Pointing at a reference or citation (or focusing it from the keyboard) shows the
     statement, equation or bibliography entry it names, cloned with its mathematics
     typeset; a citation of another paper of the release fetches that page once. The
     link still jumps. Escape or moving away closes it; touch has no preview. */
  var pop = null, popFor = null, showT = 0, hideT = 0, lastTouch = 0, pages = {};
  function hostOf(el) {
    var host = el.classList.contains('pr-lbl') ? el.parentElement : el;
    return (host && host.closest('.pr-thm, .pr-eq, .pr-float, .pr-sec, .pr-part, .pr-runin, .pr-list > li, .pr-bib-item, .pr-fn, .pr-proof, p')) || el;
  }
  function render(node, mac) {
    if (!window.katex) return;
    var spans = node.querySelectorAll('span.pr-m:not(.pr-m--ok)');
    for (var i = 0; i < spans.length; i++) {
      var s = spans[i], t = s.textContent, d = s.getAttribute('data-d') === '1';
      try {
        window.katex.render(!d && window.atlasKeepShortMath ? window.atlasKeepShortMath(t) : t, s, {
          displayMode: d, macros: Object.assign({}, mac), throwOnError: true, strict: 'ignore', trust: false,
          maxExpand: 2000, leqno: opts.leqno, fleqn: opts.fleqn });
        s.classList.add('pr-m--ok');
      } catch (e) { s.textContent = t; s.classList.add('pr-m--fail'); }
    }
  }
  function cloneOf(el, mac) {
    var host = hostOf(el);
    var c = host.cloneNode(true);
    c.classList.remove('pr-target');
    var drop = c.querySelectorAll('.pr-tools, .pr-lbl, .copy-fallback');
    for (var i = 0; i < drop.length; i++) drop[i].parentNode.removeChild(drop[i]);
    if (c.removeAttribute) c.removeAttribute('id');
    var ids = c.querySelectorAll('[id]');
    for (var j = 0; j < ids.length; j++) ids[j].removeAttribute('id');
    var links = c.querySelectorAll('a, button');
    for (var k = 0; k < links.length; k++) links[k].setAttribute('tabindex', '-1');
    render(c, mac);
    return c;
  }
  function fetchPage(url) {
    if (!pages[url]) {
      pages[url] = fetch(url, { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error('status ' + r.status);
        return r.text();
      }).then(function (t) { return new DOMParser().parseFromString(t, 'text/html'); });
      pages[url].catch(function () { delete pages[url]; });
    }
    return pages[url];
  }
  function place() {
    if (!pop || !popFor) return;
    var r = popFor.getBoundingClientRect();
    var w = Math.min(560, doc.documentElement.clientWidth - 32);
    pop.style.width = w + 'px';
    var left = Math.max(16, Math.min(r.left, doc.documentElement.clientWidth - 16 - w));
    pop.style.left = (left + window.scrollX) + 'px';
    var below = window.innerHeight - r.bottom;
    var h = pop.offsetHeight;
    var top = (below >= h + 12 || below >= r.top) ? r.bottom + 8 : r.top - 8 - h;
    pop.style.top = (top + window.scrollY) + 'px';
  }
  function hide() {
    clearTimeout(showT);
    if (!pop) return;
    if (popFor) popFor.removeAttribute('aria-describedby');
    pop.hidden = true;
    pop.innerHTML = '';
    popFor = null;
  }
  function fill(a, content) {
    if (popFor !== a) return;
    pop.innerHTML = '';
    if (typeof content === 'string') {
      var p = doc.createElement('p');
      p.className = 'pr-pop__msg';
      p.textContent = content;
      pop.appendChild(p);
    } else pop.appendChild(content);
    pop.hidden = false;
    place();
  }
  function show(a) {
    if (!pop) {
      pop = doc.createElement('div');
      pop.className = 'pr-pop paper';
      pop.id = 'pr-pop';
      pop.setAttribute('role', 'tooltip');
      pop.hidden = true;
      pop.addEventListener('mouseenter', function () { clearTimeout(hideT); });
      pop.addEventListener('mouseleave', function () { hideT = setTimeout(hide, 200); });
      doc.body.appendChild(pop);
    }
    if (popFor === a && !pop.hidden) return;
    hide();
    popFor = a;
    a.setAttribute('aria-describedby', 'pr-pop');
    var href = a.getAttribute('href') || '';
    var hash = href.indexOf('#');
    if (hash < 0) return hide();
    var id = decodeURIComponent(href.slice(hash + 1));
    if (hash === 0) {
      var el = doc.getElementById(id);
      if (!el) return hide();
      fill(a, cloneOf(el, macros));
      return;
    }
    fill(a, W('loading'));
    var url = new URL(href, location.href);
    fetchPage(url.pathname).then(function (page) {
      var el = page.getElementById(id);
      if (!el) return fill(a, W('unavailable'));
      var mac = {};
      var ms = page.getElementById('pr-macros');
      if (ms) { try { mac = JSON.parse(ms.textContent); } catch (e) { mac = {}; } }
      var wrap = doc.createElement('div');
      var t = page.querySelector('h1');
      if (t) {
        var from = doc.createElement('p');
        from.className = 'pr-pop__from';
        from.textContent = t.textContent.trim();
        wrap.appendChild(from);
      }
      wrap.appendChild(cloneOf(doc.importNode(hostOf(el), true), mac));
      fill(a, wrap);
    }, function () { fill(a, W('unavailable')); });
  }
  var SEL = 'a.pr-ref, a.pr-cite, a.pr-xref';
  doc.addEventListener('pointerdown', function (e) { if (e.pointerType === 'touch' || e.pointerType === 'pen') lastTouch = Date.now(); }, true);
  doc.addEventListener('pointerover', function (e) {
    if (e.pointerType !== 'mouse') return;
    var a = e.target.closest && e.target.closest(SEL);
    if (!a || !art.contains(a)) return;
    clearTimeout(hideT);
    clearTimeout(showT);
    showT = setTimeout(function () { show(a); }, 250);
  });
  doc.addEventListener('pointerout', function (e) {
    if (e.pointerType !== 'mouse') return;
    var a = e.target.closest && e.target.closest(SEL);
    if (!a || (e.relatedTarget && a.contains(e.relatedTarget))) return;
    clearTimeout(showT);
    hideT = setTimeout(hide, 200);
  });
  doc.addEventListener('focusin', function (e) {
    var a = e.target.closest && e.target.closest(SEL);
    if (!a || !art.contains(a) || Date.now() - lastTouch < 800) return;
    show(a);
  });
  doc.addEventListener('focusout', function (e) {
    if (popFor && e.target === popFor) hide();
  });
  doc.addEventListener('click', function (e) {
    if (popFor && e.target.closest && e.target.closest(SEL)) hide();
  });
  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && popFor && !pop.hidden) { hide(); }
  });
  window.addEventListener('resize', hide);

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', addTools); else addTools();
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start); else start();
})();

/* The contents beside the text on a wide screen: open, in view, and marking the
   section being read (aria-current) from the last heading above a line a third of
   the way down. On a narrower screen it stays the disclosure the page was built with. */
(function () {
  'use strict';
  var nav = document.querySelector('.pr-grid > .pr-toc');
  if (!nav || !window.matchMedia) return;
  var det = nav.querySelector('details');
  var wide = window.matchMedia('(min-width: 1280px)');
  var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
  var targets = links.map(function (a) { return document.getElementById(decodeURIComponent(a.hash.slice(1))); });
  var userOpen = det ? det.open : false;
  function sync() {
    if (!det) return;
    if (wide.matches) { det.open = true; } else { det.open = userOpen; }
  }
  if (det) det.addEventListener('toggle', function () { if (!wide.matches) userOpen = det.open; });
  if (wide.addEventListener) wide.addEventListener('change', sync); else if (wide.addListener) wide.addListener(sync);
  sync();
  var queued = false, last = -1;
  function mark() {
    queued = false;
    if (!wide.matches) return;
    var line = window.innerHeight / 3, cur = -1;
    for (var i = 0; i < targets.length; i++) {
      var t = targets[i];
      if (!t) continue;
      if (t.getBoundingClientRect().top <= line) cur = i; else break;
    }
    if (cur === last) return;
    if (last >= 0) links[last].removeAttribute('aria-current');
    if (cur >= 0) {
      links[cur].setAttribute('aria-current', 'true');
      var r = links[cur].getBoundingClientRect(), n = nav.getBoundingClientRect();
      if (r.top < n.top || r.bottom > n.bottom) nav.scrollTop += r.top - n.top - n.height / 3;
    }
    last = cur;
  }
  function queue() { if (!queued) { queued = true; requestAnimationFrame(mark); } }
  window.addEventListener('scroll', queue, { passive: true });
  window.addEventListener('resize', queue);
  mark();
})();

/* An inline formula wider than the reading column (on a phone, a long formula with
   no break point) scrolls inside its own box instead of widening the page. Checked
   once the paper's formulas are typeset, and again when the window is resized:
   one pass of reads, then one of writes. */
(function () {
  'use strict';
  var col = document.querySelector('.pr-col');
  if (!col) return;
  function fit() {
    var right = col.getBoundingClientRect().right + 1;
    var all = col.querySelectorAll('.pr-m--ok:not([data-d="1"])');
    var wide = [];
    for (var i = 0; i < all.length; i++) {
      var n = all[i];
      if (n.classList.contains('pr-m--wide')) { wide.push([n, true]); continue; }
      if (n.getBoundingClientRect().right > right) wide.push([n, false]);
    }
    wide.forEach(function (w) { if (!w[1]) w[0].classList.add('pr-m--wide'); });
  }
  function whenReady() {
    if (document.documentElement.hasAttribute('data-paper-math')) { fit(); return; }
    var mo = new MutationObserver(function () {
      if (document.documentElement.hasAttribute('data-paper-math')) { mo.disconnect(); fit(); }
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-paper-math'] });
  }
  var t = null;
  window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(fit, 250); });
  whenReady();
})();
