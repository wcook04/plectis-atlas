/* Plectis Atlas: the family page (scripts/family_page.py).

   With several Lean statements, the index above the comparisons chooses which one
   stands beside its paper theorem; the others are hidden, and each keeps its own
   address (#lean-<name>), so a link to one opens it. Without this script every
   comparison is shown in turn and the index links jump to them.

   The contents in the side column marks the section being read. Nothing moves on
   its own: both answer the reader's choice or scrolling. */
(function () {
  'use strict';
  var doc = document;

  /* ---- Choosing a Lean statement ------------------------------------------ */
  var host = doc.querySelector('[data-cmp-host]');
  var tabs = host ? host.querySelectorAll('[data-cmp-tab]') : [];
  if (tabs.length > 1) {
    var panels = host.querySelectorAll('[data-cmp]');
    var show = function (id, focus) {
      var found = false;
      for (var i = 0; i < panels.length; i++) {
        var on = panels[i].id === id;
        panels[i].hidden = !on;
        if (on) found = true;
      }
      if (!found) return false;
      for (var j = 0; j < tabs.length; j++) {
        if (tabs[j].getAttribute('data-cmp-tab') === id) tabs[j].setAttribute('aria-current', 'true');
        else tabs[j].removeAttribute('aria-current');
      }
      if (focus) {
        var p = doc.getElementById(id);
        var h = p && p.querySelector('h3');
        if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
      }
      return true;
    };
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
      try {
        window.katex.render(tex, spans[i], { displayMode: spans[i].getAttribute('data-d') === '1', macros: Object.assign({}, macros),
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
