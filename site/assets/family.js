/* Plectis Atlas: the bench on family pages (and wherever a page embeds it).
   When the paper card and the Lean card sit side by side and one is much shorter,
   the shorter one travels (position: sticky) beside the longer as the reader
   scrolls, and the thread goes with it, so neither column shows a tall empty
   stretch. A card travels only when it fits the window. Nothing moves on its own:
   this answers scrolling. Without this script the cards simply stand at the top. */
(function () {
  'use strict';
  var benches = document.querySelectorAll('[data-bench]');
  if (!benches.length) return;
  function setup(bench) {
    var paper = bench.querySelector('.bench__side--paper');
    var lean = bench.querySelector('.bench__side--lean');
    if (!paper || !lean) return;
    var pt = paper.firstElementChild, lt = lean.firstElementChild;
    var thread = bench.querySelector('.bench__thread');
    var pcard = paper.querySelector('.bench__paper') || pt;
    var queued = false;
    function sideBySide() {
      return getComputedStyle(bench).gridTemplateColumns.trim().split(/\s+/).length > 1;
    }
    function update() {
      queued = false;
      var travel = null;
      if (sideBySide()) {
        var ph = pt.offsetHeight, lh = lt.offsetHeight, room = window.innerHeight - 32;
        if (ph + 48 < lh && ph < room) travel = paper;
        else if (lh + 48 < ph && lh < room) travel = lean;
      }
      paper.classList.toggle('is-travel', travel === paper);
      lean.classList.toggle('is-travel', travel === lean);
      if (thread) {
        var onLean = travel === lean;
        var host = onLean ? lt : pcard;
        if (thread.parentNode !== host) host.appendChild(thread);
        thread.classList.toggle('bench__thread--onlean', onLean);
      }
    }
    function queue() { if (!queued) { queued = true; requestAnimationFrame(update); } }
    if ('ResizeObserver' in window) {
      var ro = new ResizeObserver(queue);
      ro.observe(pt); ro.observe(lt); ro.observe(bench);
    }
    window.addEventListener('resize', queue);
    update();
  }
  for (var i = 0; i < benches.length; i++) setup(benches[i]);
})();
