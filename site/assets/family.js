/* Plectis Atlas: the family page (scripts/family_page.py).

   With several Lean statements, the index above the comparisons chooses which one
   stands beside its paper theorem; the others are hidden, and each keeps its own
   address (#lean-<name>), so a link to one opens it. The build marks every comparison
   but the first (fx-cmp--rest, hidden by family.css when scripts run) and an inline
   script after them swaps in the one a link names before the first paint; this script
   then takes over with the hidden attribute. Without scripts every comparison is
   shown in turn and the index links jump to them.

   The contents in the side column marks the section being read. Nothing moves on
   its own: both answer the reader's choice or scrolling. */
(function () {
  'use strict';
  var doc = document;

  /* ---- Tabs ---------------------------------------------------------------
     One reading question per panel: the result and its papers, the Lean and the
     groups' reports, connections, what people have said, how to contribute. The
     inline script after the panels has already shown the one the address names; this
     keeps tabs, links into a hidden panel, Back and Forward in step with it. */
  var fxTabs = doc.querySelectorAll('[data-fx-tab]');
  var fxPanels = doc.querySelectorAll('[data-fx-panel]');
  if (fxTabs.length > 1) {
    var fxRoot = doc.querySelector('.fx');
    var tabBar = doc.querySelector('.fx-tabs');
    fxRoot.classList.add('fx--tabbed');
    var activePanel = null;
    var panelOf = function (id) {
      var el = id ? doc.getElementById(id) : null;
      if (!el) return null;
      return el.hasAttribute('data-fx-panel') ? el : el.closest('[data-fx-panel]');
    };
    var activate = function (id) {
      if (activePanel === id) return;
      activePanel = id;
      for (var i = 0; i < fxPanels.length; i++) fxPanels[i].hidden = fxPanels[i].id !== id;
      for (var j = 0; j < fxTabs.length; j++) {
        var on = fxTabs[j].getAttribute('data-fx-tab') === id;
        fxTabs[j].setAttribute('aria-selected', on ? 'true' : 'false');
        fxTabs[j].tabIndex = on ? 0 : -1;
      }
    };
    // A chosen tab starts its panel at the tab bar, never mid-way down the last one.
    var toTabs = function () {
      var r = tabBar.getBoundingClientRect();
      if (r.top < 0 || r.top > window.innerHeight * 0.6) window.scrollTo(0, window.scrollY + r.top);
    };
    var fromHash = function (initial) {
      var id = '';
      try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { id = ''; }
      var p = panelOf(id);
      if (!p) { if (initial) activate(fxPanels[0].id); return; }
      activate(p.id);
      var el = doc.getElementById(id);
      if (el === p) { if (!initial) toTabs(); } else el.scrollIntoView({ block: 'start' });
    };
    for (var k = 0; k < fxTabs.length; k++) {
      fxTabs[k].addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        e.preventDefault();
        var id = this.getAttribute('data-fx-tab');
        activate(id);
        if (history.replaceState) history.replaceState(null, '', '#' + id);
        toTabs();
      });
      fxTabs[k].addEventListener('keydown', function (e) {
        var dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
        if (!dir) return;
        e.preventDefault();
        var list = Array.prototype.slice.call(fxTabs), at = list.indexOf(this);
        var next = list[(at + dir + list.length) % list.length];
        next.focus();
        next.click();
      });
    }
    // A link to anything inside a hidden panel opens that panel first; the browser's own
    // jump then lands on the target.
    doc.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href^="#"]');
      if (!a || a.hasAttribute('data-fx-tab')) return;
      var p = panelOf(decodeURIComponent(a.getAttribute('href').slice(1)));
      if (p) activate(p.id);
    }, true);
    window.addEventListener('hashchange', function () { fromHash(false); });
    fromHash(true);
  }

  /* ---- Choosing a Lean statement ------------------------------------------ */
  var host = doc.querySelector('[data-cmp-host]');
  var tabs = host ? host.querySelectorAll('[data-cmp-tab]') : [];
  if (tabs.length > 1) {
    var panels = host.querySelectorAll('[data-cmp]');
    var reduce = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
    var stateMs = parseFloat(getComputedStyle(doc.documentElement).getPropertyValue('--t-state')) || 180;
    /* One mark for the chosen entry, moved to it over the state time (family.css). */
    var nav = host.querySelector('.fx-idx');
    var idxMark = null, current = null;
    if (nav) {
      idxMark = doc.createElement('span');
      idxMark.className = 'fx-idx__mark';
      idxMark.setAttribute('aria-hidden', 'true');
      nav.appendChild(idxMark);
      nav.classList.add('fx-idx--marked');
    }
    var placeMark = function (instant) {
      if (!idxMark || !current) return;
      var li = null;
      for (var j = 0; j < tabs.length; j++) if (tabs[j].getAttribute('data-cmp-tab') === current) li = tabs[j].closest('li');
      if (!li) return;
      if (instant) idxMark.style.transition = 'none';
      idxMark.style.height = Math.max(0, li.offsetHeight - 29) + 'px';
      idxMark.style.transform = 'translateY(' + (li.offsetTop + 14) + 'px)';
      if (instant) { void idxMark.offsetHeight; idxMark.style.transition = ''; }
    };
    var show = function (id, focus) {
      var found = false;
      for (var n = 0; n < panels.length; n++) if (panels[n].id === id) found = true;
      if (!found) return false;
      var changed = current !== null && current !== id;
      for (var i = 0; i < panels.length; i++) {
        panels[i].hidden = panels[i].id !== id;
        panels[i].classList.remove('fx-cmp--rest');
      }
      for (var j = 0; j < tabs.length; j++) {
        if (tabs[j].getAttribute('data-cmp-tab') === id) tabs[j].setAttribute('aria-current', 'true');
        else tabs[j].removeAttribute('aria-current');
      }
      current = id;
      placeMark(!changed);
      var p = doc.getElementById(id);
      /* The chosen comparison swaps in place; on a reader's choice it fades in over the
         state time, never on scroll, and at once under reduced motion. */
      if (changed && p && p.animate && !reduce.matches) {
        p.animate([{ opacity: 0 }, { opacity: 1 }], { duration: stateMs, easing: 'cubic-bezier(0.16, 1, 0.3, 1)' });
      }
      if (focus) {
        var h = p && p.querySelector('h3');
        if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
      }
      return true;
    };
    if (idxMark && 'ResizeObserver' in window) new ResizeObserver(function () { placeMark(true); }).observe(nav);
    var fromHash = function () {
      var id = decodeURIComponent(location.hash.replace(/^#/, ''));
      if (!id) return false;
      var el = doc.getElementById(id);
      var panel = el && el.closest ? el.closest('[data-cmp]') : null;
      if (panel && show(panel.id, false)) { el.scrollIntoView({ block: 'start' }); return true; }
      return false;
    };
    for (var k = 0; k < tabs.length; k++) {
      tabs[k].addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        e.preventDefault();
        var id = this.getAttribute('data-cmp-tab');
        show(id, true);
        if (history.replaceState) history.replaceState(null, '', '#' + id);
      });
    }
    if (!fromHash()) show(tabs[0].getAttribute('data-cmp-tab'), false);
    window.addEventListener('hashchange', fromHash);
  }

  /* ---- The section being read ---------------------------------------------- */
  var toc = doc.querySelectorAll('.fx-toc a[href^="#"]');
  if (toc.length && 'IntersectionObserver' in window) {
    var byId = {};
    var secs = [];
    for (var t = 0; t < toc.length; t++) {
      var id = toc[t].getAttribute('href').slice(1);
      var s = doc.getElementById(id);
      if (s) { byId[id] = toc[t]; secs.push(s); }
    }
    var current = null;
    var mark = function (id) {
      if (id === current) return;
      if (current && byId[current]) byId[current].removeAttribute('aria-current');
      current = id;
      if (id && byId[id]) byId[id].setAttribute('aria-current', 'true');
    };
    var visible = {};
    var io = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) visible[entries[i].target.id] = entries[i].isIntersecting;
      for (var j = 0; j < secs.length; j++) { if (visible[secs[j].id]) { mark(secs[j].id); return; } }
    }, { rootMargin: '0px 0px -65% 0px' });
    for (var q = 0; q < secs.length; q++) io.observe(secs[q]);
  }

  /* ---- A cited passage, read in place ---------------------------------------
     A number a theorem cites, such as (1.5), links to its place on the paper's
     reading page. Activating it fetches that page once, takes the cited passage
     (the whole statement, equation or paragraph, as the reading page marks it on
     arrival, with the sentence that introduces an equation) and shows it under
     the theorem, labelled with the paper and its date, typeset with the paper's
     own macros. Close or Escape removes it and returns focus to the number. If
     the page or the passage cannot be found, the link is followed instead. */
  var pages = {};
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
  function passage(page, id) {
    var el = page.getElementById(id);
    if (!el) return null;
    var host = el.classList.contains('pr-lbl') ? el.parentElement : el;
    host = (host && host.closest('.pr-thm, .pr-eq, .pr-float, .pr-runin, .pr-list > li, .pr-bib-item, .pr-fn, .pr-proof, p')) || null;
    if (!host) return null;
    var out = [];
    if (host.classList.contains('pr-eq')) {
      var lead = host.previousElementSibling;
      if (lead && lead.tagName === 'P') out.push(lead);
    }
    out.push(host);
    return out;
  }
  function typeset(node, macros) {
    var spans = node.querySelectorAll('span.pr-m');
    for (var i = 0; i < spans.length; i++) {
      var tex = spans[i].textContent;
      if (!window.katex) break;
      var display = spans[i].getAttribute('data-d') === '1';
      try {
        // A short inline formula stays on one line (atlas.js keepShort).
        window.katex.render(!display && window.atlasKeepShortMath ? window.atlasKeepShortMath(tex) : tex, spans[i], { displayMode: display, macros: Object.assign({}, macros),
          throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
      } catch (e) { spans[i].textContent = tex; spans[i].classList.add('pr-m--fail'); }
    }
  }
  var openSrc = null;
  function closeSrc(focusBack) {
    if (!openSrc) return;
    var s = openSrc;
    openSrc = null;
    s.box.parentNode && s.box.parentNode.removeChild(s.box);
    s.link.setAttribute('aria-expanded', 'false');
    if (focusBack) { try { s.link.focus({ preventScroll: true }); } catch (e) { s.link.focus(); } }
  }
  doc.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('.fx-st__body a.xref, .fx-st__body a[href*="papers/"][href*="#"]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
    var card = a.closest('.fx-st');
    var href = a.getAttribute('href');
    var hash = href.indexOf('#');
    if (!card || hash < 0) return;
    e.preventDefault();
    if (openSrc && openSrc.link === a) { closeSrc(true); return; }
    closeSrc(false);
    var url = new URL(href, location.href);
    var id = decodeURIComponent(url.hash.slice(1));
    fetchPage(url.pathname).then(function (page) {
      var parts = passage(page, id);
      if (!parts) { location.href = href; return; }
      var macros = {};
      var m = page.getElementById('pr-macros');
      if (m) { try { macros = JSON.parse(m.textContent); } catch (err) { macros = {}; } }
      var box = doc.createElement('section');
      box.className = 'fx-src';
      box.setAttribute('aria-label', (a.textContent || '').trim());
      var head = doc.createElement('p');
      head.className = 'fx-src__h';
      head.tabIndex = -1;
      var date = card.getAttribute('data-date');
      head.textContent = (card.getAttribute('data-from') || 'From {paper}{date}')
        .replace('{paper}', card.getAttribute('data-paper') || '').replace('{date}', date ? ', ' + date : '') + ': ' + (a.textContent || '').trim();
      var body = doc.createElement('div');
      body.className = 'fx-src__body';
      parts.forEach(function (p) { body.appendChild(doc.importNode(p, true)); });
      var strip = body.querySelectorAll('[id]');
      for (var i = 0; i < strip.length; i++) strip[i].removeAttribute('id');
      typeset(body, macros);
      var foot = doc.createElement('p');
      foot.className = 'fx-src__foot';
      var go = doc.createElement('a');
      go.href = href;
      go.textContent = card.getAttribute('data-open') || 'Open in the paper';
      var close = doc.createElement('button');
      close.type = 'button';
      close.className = 'btn btn--small';
      close.textContent = card.getAttribute('data-close') || 'Close';
      close.addEventListener('click', function () { closeSrc(true); });
      foot.appendChild(go);
      foot.appendChild(close);
      box.appendChild(head);
      box.appendChild(body);
      box.appendChild(foot);
      var anchorBlock = card.querySelector('.fx-st__body');
      anchorBlock.parentNode.insertBefore(box, anchorBlock.nextSibling);
      a.setAttribute('aria-expanded', 'true');
      openSrc = { box: box, link: a };
      head.focus({ preventScroll: true });
      var r = box.getBoundingClientRect();
      if (r.bottom > window.innerHeight) box.scrollIntoView({ block: 'nearest' });
    }).catch(function () { location.href = href; });
  });
  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && openSrc && (openSrc.box.contains(doc.activeElement) || doc.activeElement === openSrc.link)) {
      e.stopPropagation();
      closeSrc(true);
    }
  }, true);
})();
