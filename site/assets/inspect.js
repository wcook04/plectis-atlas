/* Plectis Atlas: one inspection pattern for every supporting record (an outside
   reading, a re-run, a candidate theorem, a Lean name, a number, a citation).
   DESIGN.md, "Inspection".

   Markup. A trigger carries data-inspect="<template id>"; the record is build-time
   HTML inside that <template>, so the page carries the substance with JavaScript
   off and this script only moves it. A trigger that is a link keeps its link and
   pins instead when it also carries data-inspect-click="pin" (a modified click
   still follows the link). Elements inside a [data-hl-scope] with data-hl-key and
   data-hl="<keys>" highlight one another (the family figure's threads).

   Behaviour. Pointing (after a short dwell) or keyboard focus shows a light
   preview beside the trigger; it stays while pointed at and closes on Escape.
   Selecting pins the record in the rail ([data-ins-rail], beside the reading
   column on wide screens and a sheet from the bottom on phones; a floating panel
   on pages without one). Focus moves into the rail; closing returns focus to the
   trigger and the reader to where they were. Hover is never the only way in. */
(function () {
  'use strict';
  var doc = document;
  var DWELL = 300, LINGER = 260;
  var pop = null, popFor = null, showT = 0, hideT = 0;
  var rail = null, railBody = null, railHead = null, pinnedFor = null, returnY = 0;
  var restoring = false;   /* focus handed back by closing the rail */
  var hover = window.matchMedia ? window.matchMedia('(hover: hover) and (pointer: fine)') : { matches: true };

  function trig(t) { return t && t.closest ? t.closest('[data-inspect]') : null; }
  function tpl(el) {
    var id = el && el.getAttribute('data-inspect');
    var t = id && doc.getElementById(id);
    return t && t.content ? t : null;
  }
  function fill(host, t) {
    host.textContent = '';
    host.appendChild(t.content.cloneNode(true));
    if (window.atlasRenderMath) { try { window.atlasRenderMath(host); } catch (e) { /* the TeX stays as text */ } }
  }
  function words(name, fallback) {
    var r = doc.querySelector('[data-ins-rail]');
    return (r && r.getAttribute('data-ins-' + name)) || fallback;
  }

  /* ---- Highlight -------------------------------------------------------- */
  var hlKey = null;
  function highlight(el) {
    var scope = el && el.closest('[data-hl-scope]');
    var key = el && el.getAttribute('data-hl-key');
    var scopes = doc.querySelectorAll('[data-hl-scope].has-hl');
    for (var s = 0; s < scopes.length; s++) {
      scopes[s].classList.remove('has-hl');
      var lit = scopes[s].querySelectorAll('.is-hl');
      for (var i = 0; i < lit.length; i++) lit[i].classList.remove('is-hl');
    }
    hlKey = key;
    if (!scope || !key) return;
    scope.classList.add('has-hl');
    var all = scope.querySelectorAll('[data-hl]');
    for (var j = 0; j < all.length; j++) {
      if ((' ' + all[j].getAttribute('data-hl') + ' ').indexOf(' ' + key + ' ') >= 0) all[j].classList.add('is-hl');
    }
  }
  function restoreHighlight() { highlight(pinnedFor && pinnedFor.isConnected ? pinnedFor : null); }

  /* ---- Preview ---------------------------------------------------------- */
  function ensurePop() {
    if (pop) return pop;
    pop = doc.createElement('div');
    pop.className = 'ins-pop';
    pop.id = 'ins-pop';
    pop.hidden = true;
    pop.addEventListener('mouseenter', function () { clearTimeout(hideT); });
    pop.addEventListener('mouseleave', function () { scheduleHide(); });
    doc.body.appendChild(pop);
    return pop;
  }
  function place(el) {
    var r = el.getBoundingClientRect(), p = pop, vw = doc.documentElement.clientWidth;
    p.style.maxWidth = Math.min(380, vw - 24) + 'px';
    var w = p.offsetWidth, h = p.offsetHeight;
    var left = Math.max(12, Math.min(r.left, vw - w - 12)) + window.scrollX;
    var below = r.bottom + 10 + h < window.innerHeight || r.top < h + 10;
    var top = below ? r.bottom + 8 : r.top - h - 8;
    p.style.left = left + 'px';
    p.style.top = (top + window.scrollY) + 'px';
  }
  function showPop(el) {
    if (el === pinnedFor) return;
    var t = tpl(el);
    if (!t) return;
    ensurePop();
    var body = doc.createElement('div');
    fill(body, t);
    var hint = doc.createElement('p');
    hint.className = 'ins-pop__hint';
    hint.textContent = words('hint', 'Select to keep it open beside the page.');
    pop.textContent = '';
    pop.appendChild(body);
    pop.appendChild(hint);
    pop.hidden = false;
    if (popFor && popFor !== el) popFor.removeAttribute('aria-describedby');
    popFor = el;
    el.setAttribute('aria-describedby', 'ins-pop');
    place(el);
  }
  function hidePop() {
    clearTimeout(showT);
    if (pop) pop.hidden = true;
    if (popFor) popFor.removeAttribute('aria-describedby');
    popFor = null;
  }
  function scheduleHide() {
    clearTimeout(showT);
    clearTimeout(hideT);
    hideT = setTimeout(function () { hidePop(); restoreHighlight(); }, LINGER);
  }

  /* ---- The rail --------------------------------------------------------- */
  function ensureRail() {
    if (rail) return rail;
    rail = doc.querySelector('[data-ins-rail]');
    if (!rail) {
      rail = doc.createElement('section');
      rail.className = 'ins-rail ins-rail--float';
      rail.setAttribute('data-ins-rail', '');
      rail.hidden = true;
      rail.innerHTML = '<div class="ins-rail__bar"><p class="ins-rail__h" tabindex="-1"></p>'
        + '<button class="ins-rail__close" type="button"></button></div><div class="ins-rail__body"></div>';
      doc.body.appendChild(rail);
    }
    railBody = rail.querySelector('.ins-rail__body');
    railHead = rail.querySelector('.ins-rail__h');
    var close = rail.querySelector('.ins-rail__close');
    if (railHead && !railHead.textContent) railHead.textContent = words('pinned', 'Pinned record');
    if (close) {
      if (!close.textContent) close.textContent = words('close', 'Close');
      close.addEventListener('click', unpin);
    }
    rail.setAttribute('role', 'region');
    if (railHead) {
      if (!railHead.id) railHead.id = 'ins-rail-h';
      rail.setAttribute('aria-labelledby', railHead.id);
    }
    return rail;
  }
  function sheet() { return rail && getComputedStyle(rail).position === 'fixed'; }
  function pin(el) {
    var t = tpl(el);
    if (!t) return;
    hidePop();
    ensureRail();
    if (pinnedFor && pinnedFor !== el) { pinnedFor.classList.remove('is-pinned'); pinnedFor.removeAttribute('aria-expanded'); }
    returnY = window.scrollY;
    pinnedFor = el;
    el.classList.add('is-pinned');
    el.setAttribute('aria-expanded', 'true');
    fill(railBody, t);
    rail.hidden = false;
    doc.documentElement.classList.add('ins-open');
    highlight(el);
    if (railHead) railHead.focus({ preventScroll: true });
    if (!sheet() && rail.getBoundingClientRect().top > window.innerHeight) rail.scrollIntoView({ block: 'nearest' });
  }
  function unpin() {
    if (!rail || rail.hidden) return;
    var back = pinnedFor;
    var wasSheet = sheet();
    rail.hidden = true;
    doc.documentElement.classList.remove('ins-open');
    if (railBody) railBody.textContent = '';
    pinnedFor = null;
    highlight(null);
    if (back && back.isConnected) {
      back.classList.remove('is-pinned');
      back.removeAttribute('aria-expanded');
      // Focus goes back to the trigger without opening its preview over the text: the
      // reader has just read that record.
      restoring = true;
      try { back.focus({ preventScroll: true }); } catch (e) { back.focus(); }
      restoring = false;
    }
    if (wasSheet) window.scrollTo(window.scrollX, returnY);
  }

  /* ---- Events ----------------------------------------------------------- */
  doc.addEventListener('mouseover', function (e) {
    var el = trig(e.target);
    if (!el || !hover.matches) return;
    clearTimeout(hideT);
    clearTimeout(showT);
    highlight(el);
    if (popFor === el) return;
    showT = setTimeout(function () { showPop(el); }, popFor ? 60 : DWELL);
  });
  doc.addEventListener('mouseout', function (e) {
    var el = trig(e.target);
    if (!el) return;
    var to = e.relatedTarget;
    if (to && (el.contains(to) || (pop && pop.contains(to)))) return;
    scheduleHide();
  });
  doc.addEventListener('focusin', function (e) {
    var el = trig(e.target);
    if (!el) return;
    var keyboard = true;
    try { keyboard = el.matches(':focus-visible'); } catch (err) { /* older engines: treat as keyboard */ }
    highlight(el);
    clearTimeout(hideT);
    if (keyboard && !restoring) showPop(el);
  });
  doc.addEventListener('focusout', function (e) {
    var el = trig(e.target);
    if (el) scheduleHide();
  });
  doc.addEventListener('click', function (e) {
    var el = trig(e.target);
    if (!el || !tpl(el)) return;
    var isLink = el.tagName.toLowerCase() === 'a' && el.hasAttribute('href');
    if (isLink) {
      if (el.getAttribute('data-inspect-click') !== 'pin') return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
    }
    e.preventDefault();
    if (el === pinnedFor && rail && !rail.hidden) { unpin(); return; }
    pin(el);
  });
  doc.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (pop && !pop.hidden) { hidePop(); restoreHighlight(); return; }
    if (rail && !rail.hidden) { e.preventDefault(); unpin(); }
  });
  window.addEventListener('resize', function () { if (popFor && pop && !pop.hidden) place(popFor); });
})();
