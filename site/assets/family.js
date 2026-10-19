/* Plectis Atlas: the family page (scripts/family_page.py).

   One reading question per tab panel. Every Lean statement stands in its own row,
   and each keeps its own address (#lean-<name>), so a link to one opens the Lean
   tab at it. Nothing moves on its own: the page answers the reader's choice. */
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
