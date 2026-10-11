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
})();
