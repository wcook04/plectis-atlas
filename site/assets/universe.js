/* The front door's map of OpenAI's mathematics release, drawn as an illustrated chart:
   the seventeen disciplines as labelled regions holding their families, a discipline
   as its families' discs with their titles written inside, and a family as a board of
   cards (its papers, each result's statement, the Lean statements paired with them, the
   families it cites and is cited by). Every object a reader can act on is big enough to
   read and carries its name; distance means only grouping.

   History: the first version was ported from Will Cook's ai_workflow at commit
   4b1ebab611 (the Plectis universe map's wheel, Loom fibres and camera); on 12 October
   2026 the wheel and camera gave way to this chart, after the to-scale drawing proved
   too small to read. Kept from that port: the drill trail with exact Back, #o= deep
   links, reduced motion and the Oklab colour mixing. The rules of
   sites/microcosm/SOURCE_CONTRACT.md still hold: data apart from geometry under one
   generation id; a click selects and never leaves the page; Esc retraces the trail;
   colour belongs to evidence; one flat ground. No libraries. */
(function () {
  'use strict';

  /* ---- Small helpers --------------------------------------------------- */
  var TAU = Math.PI * 2;
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function smooth(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
  function easeInOut(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  // One date format across the site: "8 October 2026".
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  function longDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    return m ? (+m[3]) + ' ' + MONTHS[+m[2] - 1] + ' ' + m[1] : String(iso || '');
  }
  function fmtNum(n) { return typeof n === 'number' ? n.toLocaleString('en-GB') : String(n); }
  function fill(template, vars) {
    return String(template).replace(/\{(\w+)\}/g, function (m, k) {
      return vars && vars[k] != null ? fmtNum(vars[k]) : m;
    });
  }
  function overlap(a, b) {
    var dx = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), dy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    return dx > 0 && dy > 0 ? dx * dy : 0;
  }

  /* ---- Colour, mixed in Oklab (from the Plectis universe map) ----------- */
  var parsedColors = {};
  function parseColor(text) {
    var key = String(text == null ? '' : text).trim();
    if (Object.prototype.hasOwnProperty.call(parsedColors, key)) return parsedColors[key];
    var out = null, m;
    if ((m = /^#([0-9a-f]{3,8})$/i.exec(key))) {
      var hex = m[1];
      if (hex.length === 3 || hex.length === 4) hex = hex.replace(/(.)/g, '$1$1');
      if (hex.length === 6 || hex.length === 8) {
        out = [parseInt(hex.slice(0, 2), 16) / 255, parseInt(hex.slice(2, 4), 16) / 255,
               parseInt(hex.slice(4, 6), 16) / 255, hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1];
      }
    } else if ((m = /^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+([\d.]+%?))?\s*\)$/i.exec(key))) {
      var channel = function (v) { return /%$/.test(v) ? parseFloat(v) / 100 : parseFloat(v) / 255; };
      out = [channel(m[1]), channel(m[2]), channel(m[3]),
             m[4] == null ? 1 : /%$/.test(m[4]) ? parseFloat(m[4]) / 100 : parseFloat(m[4])];
    }
    if (out && !out.every(function (v) { return isFinite(v); })) out = null;
    parsedColors[key] = out;
    return out;
  }
  function toLinear(c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  function toGamma(c) { return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055; }
  function rgbToOklab(c) {
    var r = toLinear(c[0]), g = toLinear(c[1]), b = toLinear(c[2]);
    var l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    var m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    var s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s];
  }
  function oklabToRgb(c) {
    var l = c[0] + 0.3963377774 * c[1] + 0.2158037573 * c[2];
    var m = c[0] - 0.1055613458 * c[1] - 0.0638541728 * c[2];
    var s = c[0] - 0.0894841775 * c[1] - 1.2914855480 * c[2];
    l = l * l * l; m = m * m * m; s = s * s * s;
    return [toGamma(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            toGamma(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            toGamma(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)];
  }
  function rgbText(c) {
    var v = function (x) { return Math.round(Math.max(0, Math.min(1, x)) * 255); };
    return 'rgb(' + v(c[0]) + ', ' + v(c[1]) + ', ' + v(c[2]) + ')';
  }
  function overGround(c, ground) {
    if (c[3] >= 0.999) return c;
    return [c[0] * c[3] + ground[0] * (1 - c[3]), c[1] * c[3] + ground[1] * (1 - c[3]),
            c[2] * c[3] + ground[2] * (1 - c[3]), 1];
  }
  // color-mix(in oklab, a, b t): t of the way from a to b.
  function mixOklab(a, b, t, ground) {
    var ca = parseColor(a), cb = parseColor(b);
    if (!ca || !cb) return a;
    if (ground) { ca = overGround(ca, ground); cb = overGround(cb, ground); }
    var la = rgbToOklab(ca), lb = rgbToOklab(cb);
    return rgbText(oklabToRgb([la[0] + (lb[0] - la[0]) * t, la[1] + (lb[1] - la[1]) * t, la[2] + (lb[2] - la[2]) * t]));
  }

  /* ---- KaTeX macros: the same set the site's pages use (assets/atlas.js) -- */
  var GLOBAL_MACROS = {
    '\\ensuremath': '#1', '\\xspace': '', '\\bm': '\\boldsymbol{#1}', '\\mathbbm': '\\mathbb{#1}',
    '\\textup': '\\textrm{#1}', '\\textsc': '\\textrm{#1}', '\\upshape': '', '\\eqref': '\\text{(#1)}',
    '\\label': '', '\\nobreak': '', '\\allowbreak': '', '\\hbox': '\\text{#1}', '\\mbox': '\\text{#1}',
    '\\dfrac': '\\frac{#1}{#2}', '\\RR': '\\mathbb{R}', '\\NN': '\\mathbb{N}', '\\ZZ': '\\mathbb{Z}',
    '\\QQ': '\\mathbb{Q}', '\\CC': '\\mathbb{C}',
    '\\norm': '\\left\\lVert #1\\right\\rVert', '\\abs': '\\left\\lvert #1\\right\\rvert',
    '\\ip': '\\left\\langle #1\\right\\rangle', '\\floor': '\\left\\lfloor #1\\right\\rfloor',
    '\\ceil': '\\left\\lceil #1\\right\\rceil', '\\set': '\\left\\{ #1\\right\\}'
  };

  // The drawing's type is the page's: the families named by atlas.css's tokens.
  var SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
  var SERIF = 'Georgia, "Times New Roman", serif';
  var MONO = 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace';
  function readFonts() {
    var cs = getComputedStyle(document.documentElement);
    var pick = function (name, fb) { var v = cs.getPropertyValue(name).trim(); return v || fb; };
    SANS = pick('--sans', SANS); SERIF = pick('--serif', SERIF); MONO = pick('--mono', MONO);
  }
  readFonts();

  function mount(root) {
    var canvas = root.querySelector('[data-u-canvas]');
    var stage = root.querySelector('[data-u-stage]');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');
    var COPY = {};
    try { COPY = JSON.parse(document.getElementById('universe-copy').textContent); } catch (e) { COPY = {}; }
    function T(path, vars) {
      var node = COPY;
      path.split('.').forEach(function (p) { node = node && node[p]; });
      if (typeof node !== 'string') return path;
      return vars ? fill(node, vars) : node;
    }
    function count(key, n) { return n === 1 && COPY.counts[key + '_one'] ? T('counts.' + key + '_one') : T('counts.' + key, { n: n }); }

    var panelBody = root.querySelector('[data-u-scroll]');
    var viewEl = root.querySelector('[data-u-view]');
    var trailEl = root.querySelector('[data-u-trail]');
    var titleEl = root.querySelector('#u-title');
    var listSec = root.querySelector('.u-listsec');
    var resultsEl = root.querySelector('[data-u-results]');
    var searchIn = root.querySelector('[data-u-search]');
    var statusEl = root.querySelector('[data-u-status]');
    var liveEl = root.querySelector('[data-u-live]');
    var legendEl = root.querySelector('[data-u-legend]');
    var restViewHtml = viewEl ? viewEl.innerHTML : '';
    // The phone layout: the list and the map take turns under the switch.
    var narrowMQ = window.matchMedia ? window.matchMedia('(max-width: 899px)') : null;
    function narrow() { return !!(narrowMQ && narrowMQ.matches); }

    var reduceQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    var reduceMotion = !!(reduceQuery && reduceQuery.matches);
    if (reduceQuery && reduceQuery.addEventListener) reduceQuery.addEventListener('change', function () { reduceMotion = reduceQuery.matches; });

    /* ---- State ------------------------------------------------------------ */
    var D = null, L = null;           // data and layout
    var fams = [], objects = [], byKey = {};
    var W = 0, H = 0, dpr = 1;
    var sel = null;                   // selected object key
    var hover = null;                 // hovered object key
    var trail = [];                   // [{ key, prev }]
    var palette = {};
    var query = '', matches = null, matchFam = null, searchRows = null, searchLoading = null;
    var shards = {}, shardLoading = {};
    var drawPending = false;
    var pin = -1;                     // the other end of the pair the reader shows (a Lean or result index)
    // Motion (DESIGN.md "Motion and hover"). Pointing previews; selecting commits: when the
    // chart settles on a chosen discipline, one ring widens and fades round it (RING_MS).
    var RING_MS = 700, RING_GROW = 16;
    var ring = null, ringWanted = null;
    var hoverVia = '';                // what set the hover: 'map', 'touch', 'list' or 'focus'
    function nowMs() { return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now(); }
    function easeOut(t) { t = clamp(t, 0, 1); return 1 - (1 - t) * (1 - t) * (1 - t); }

    /* ---- Text ------------------------------------------------------------ */
    var widthCache = {};
    function textWidth(text, font) {
      var key = font + '|' + text;
      var w = widthCache[key];
      if (w === undefined) {
        ctx.font = font;
        w = widthCache[key] = ctx.measureText(text).width;
      }
      return w;
    }
    // The text in exactly n lines, breaking only between words, the longest line as short as it can be.
    function balancedLines(text, n, font) {
      var words = String(text).split(' ').filter(Boolean);
      if (n <= 1 || words.length < 2) return { lines: [words.join(' ')], width: textWidth(words.join(' '), font) };
      n = Math.min(n, words.length);
      var space = textWidth(' ', font), ww = words.map(function (w) { return textWidth(w, font); });
      var span = function (i, j) { var s = 0; for (var q = i; q < j; q++) s += ww[q]; return s + space * (j - i - 1); };
      var m = words.length, best = [], cut = [];
      for (var i = 0; i <= m; i++) { best.push([]); cut.push([]); }
      for (var j = 1; j <= m; j++) { best[1][j] = span(0, j); cut[1][j] = 0; }
      for (var lines = 2; lines <= n; lines++) {
        for (var j2 = lines; j2 <= m; j2++) {
          var b = Infinity, at = lines - 1;
          for (var i2 = lines - 1; i2 < j2; i2++) {
            var v = Math.max(best[lines - 1][i2], span(i2, j2));
            if (v < b - 1e-6) { b = v; at = i2; }
          }
          best[lines][j2] = b; cut[lines][j2] = at;
        }
      }
      var out = [], end = m;
      for (var l2 = n; l2 >= 1; l2--) {
        var st = l2 === 1 ? 0 : cut[l2][end];
        out.unshift(words.slice(st, end).join(' '));
        end = st;
      }
      return { lines: out, width: best[n][m] };
    }
    // The fewest whole lines (up to max) that hold the text within maxW; null when none does.
    function fitLines(text, font, maxW, max) {
      for (var n = 1; n <= max; n++) {
        var b = balancedLines(text, n, font);
        if (b.width <= maxW) return b;
        if (b.lines.length < n) break;
      }
      return null;
    }

    /* ---- Palette from the stylesheet's tokens ------------------------------ */
    function readPalette() {
      var cs = getComputedStyle(root);
      var get = function (name, fb) { var v = cs.getPropertyValue(name).trim(); return v || fb; };
      var p = {
        ground: get('--u-ground', '#1c1526'), ink: get('--u-ink', '#f2e6d4'), muted: get('--u-muted', '#bcb8c6'),
        faint: get('--u-faint', '#a6a2b1'), struct: get('--u-struct', '#6f6878'), structSoft: get('--u-struct-soft', '#4a4453'),
        cloud: get('--u-cloud', 'rgba(242,230,212,0.05)'), slice: get('--u-slice', 'rgba(242,230,212,0.06)'),
        fibre: get('--u-fibre', 'rgba(242,230,212,0.24)'), cites: get('--u-cites', '#e18a79'), cited: get('--u-cited', '#97c1df'),
        steel: get('--u-steel', '#97c1df'), brick: get('--u-brick', '#e18a79'), paired: get('--u-paired', '#7ea6c6'),
        plate: get('--u-plate', '#272132'), plateRule: get('--u-plate-rule', '#484251'), focus: get('--u-focus', '#f2e6d4')
      };
      // A paper's ring or arc inside an open family: the line that says which results it
      // holds, so it keeps 3:1 against the ground in both schemes.
      p.paper = get('--u-paper', p.struct);
      var groundRGB = parseColor(p.ground) || [0, 0, 0, 1];
      // One meaning for colour: what the two outside readers find the release's
      // Lean states for a family's headline (the key in the panel says each in words).
      p.tone = {};
      ['all', 'part', 'other', 'split', 'none', 'unread'].forEach(function (t) {
        var c = get('--u-t-' + t, p.struct);
        p.tone[t] = c;
        p.tone[t + 'Wash'] = mixOklab(c, p.ground, t === 'none' ? 0.62 : 0.78, groundRGB);
        p.tone[t + 'Edge'] = get('--u-e-' + t, c);
        p.tone[t + 'Tint'] = mixOklab(c, p.ground, t === 'none' ? 0.85 : 0.64, groundRGB);
      });
      p.structFaint = mixOklab(p.struct, p.ground, 0.45, groundRGB);
      p.groundRGB = groundRGB;
      palette = p;
    }

    /* ---- Data ------------------------------------------------------------ */
    function fetchJson(url) {
      return fetch(url, { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error(url + ': ' + r.status);
        return r.json();
      });
    }
    function validate(data, layout) {
      var gen = root.getAttribute('data-generation');
      if (!data || !layout || data.generation_id !== layout.generation_id || (gen && data.generation_id !== gen)) {
        throw new Error('the data and the layout come from different builds');
      }
      var finite = function (v) { return typeof v === 'number' && isFinite(v); };
      if (layout.families.length !== data.families.length) throw new Error('the layout does not place every family');
      layout.families.forEach(function (f) { if (!f.every(finite)) throw new Error('a family has no finite place'); });
    }
    var addObj = function (key, kind, idx) {
      if (byKey[key] !== undefined) throw new Error('duplicate id ' + key);
      byKey[key] = objects.length;
      objects.push({ key: key, kind: kind, i: idx });
    };
    function ingest(data, layout) {
      D = data; L = layout;
      D.papers = []; D.results = []; D.lean = [];
      D.disciplines.forEach(function (d, i) { addObj(d.id, 'd', i); });
      D.families.forEach(function (f, i) {
        addObj(f.id, 'f', i);
        var g = L.families[i];
        fams.push({ x: g[0], y: g[1], r: g[2], a: g[3], d: f.d, data: f, hop: {} });
      });
      // Neighbours for the focus tiers (one hop through a citation).
      D.links.forEach(function (row) {
        fams[row[0]].hop[row[1]] = 1;
        fams[row[1]].hop[row[0]] = 1;
      });
    }
    // The papers, results and Lean statements inside the families, loaded after the
    // first screen is drawn; a family opens once they are in.
    var partsReady = false, partsPromise = null;
    function loadParts() {
      if (partsPromise) return partsPromise;
      partsPromise = fetchJson(root.getAttribute('data-universe-parts')).then(function (pt) {
        if (pt.generation_id !== D.generation_id) throw new Error('parts from another build');
        var finite = function (v) { return typeof v === 'number' && isFinite(v); };
        if (L.results.length !== pt.results.length || L.lean.length !== pt.lean.length || L.papers.length !== pt.papers.length) {
          throw new Error('the layout does not place every object');
        }
        L.results.forEach(function (p) { if (!p.every(finite)) throw new Error('a result has no finite place'); });
        L.lean.forEach(function (p) { if (!p.every(finite)) throw new Error('a Lean statement has no finite place'); });
        D.papers = pt.papers; D.results = pt.results; D.lean = pt.lean;
        D.papers.forEach(function (p, i) { addObj(p.id, 'p', i); });
        D.results.forEach(function (r, i) { addObj(r.id, 'r', i); });
        D.lean.forEach(function (l, i) { addObj(l.id, 'l', i); });
        partsReady = true;
        draw();
      });
      return partsPromise;
    }
    function obj(key) { var i = byKey[key]; return i === undefined ? null : objects[i]; }
    function famOf(o) {
      if (!o) return -1;
      if (o.kind === 'f') return o.i;
      if (o.kind === 'p') return D.papers[o.i].f;
      if (o.kind === 'r') return D.results[o.i].f;
      if (o.kind === 'l') return D.lean[o.i].f;
      return -1;
    }
    function discOf(o) {
      if (!o) return -1;
      if (o.kind === 'd') return o.i;
      var f = famOf(o);
      return f >= 0 ? fams[f].d : -1;
    }
    function nameOf(o) {
      if (!o) return '';
      if (o.kind === 'd') return D.disciplines[o.i].name;
      if (o.kind === 'f') return D.families[o.i].title;
      if (o.kind === 'p') return D.papers[o.i].title;
      if (o.kind === 'r') { var r = D.results[o.i]; return resultName(r) + (r.title ? ' (' + r.title + ')' : ''); }
      if (o.kind === 'l') return D.lean[o.i].name;
      return '';
    }
    function resultName(r) {
      if (r.lab) return r.lab;
      if (r.num) return r.num;
      return r.nn ? T('result.unnumbered_label', { kind: r.kind }) : r.kind;
    }
    // A discipline's plain counts ("31 families, 24 with Lean").
    function discCounts(d) {
      var n = d.families.length, k = d.withLean || 0;
      return T(k === 0 ? 'counts.disc_none' : k === n ? 'counts.disc_all' : 'counts.disc_some', { n: n, k: k });
    }
    /* ---- The chart ------------------------------------------------------------
       The release and a discipline are drawn as an illustrated chart, never to scale:
       everything a reader can act on is big enough to read and carries its name, the
       stage is used, and distance means nothing but grouping. The release is its
       seventeen disciplines as labelled regions packed to fill the stage, each holding
       its families as discs in their evidence colour; the discipline is the thing to
       choose there. A discipline is its families as large discs packed to fill the
       stage, each with its title written inside. A family opens as a board of cards
       (syncBoard). Layouts are computed for the stage's own size; when the level
       changes, each disc moves from where it was to where it goes (CHART_MS). */
    var chart = { shown: null, from: null, to: null, start: 0, ms: 0, level: '', di: -1, fi: -1 };
    var layoutCache = {}, labelCache = {};
    var CHART_MS = 640;
    var capEl = root.querySelector('[data-u-cap]'), barEl = root.querySelector('[data-u-bar]');
    function chromeBoxes() {
      var out = [], sr = canvas.getBoundingClientRect();
      [barEl, root.querySelector('[data-u-mapkey-panel]')].forEach(function (el) {
        if (!el || el.hidden || !el.offsetParent) return;
        Array.prototype.forEach.call(el === barEl ? el.children : [el], function (c) {
          if (c.hidden || !c.offsetParent) return;
          var b = c.getBoundingClientRect();
          if (b.width && b.height) out.push({ x0: b.left - sr.left - 6, x1: b.right - sr.left + 6, y0: b.top - sr.top - 6, y1: b.bottom - sr.top + 6 });
        });
      });
      return out;
    }
    var chrome = [];
    // The band the bar (Map key and the caption) takes at the top of the stage.
    function topBand() {
      if (!barEl || !barEl.offsetParent) return 12;
      var sr = canvas.getBoundingClientRect(), b = barEl.getBoundingClientRect();
      return Math.max(12, Math.round(b.bottom - sr.top + 10));
    }
    function resize() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return false; // the list hides the canvas on a phone
      var w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
      var d = Math.min(2, window.devicePixelRatio || 1);
      if (w === W && h === H && d === dpr) return false;
      W = w; H = h; dpr = d;
      canvas.width = Math.round(w * d); canvas.height = Math.round(h * d);
      chrome = chromeBoxes();
      if (D) chartTo(false);
      return true;
    }

    /* ---- Layouts ---------------------------------------------------------------- */
    // A family's weight among its peers (0 to 1): how many results and Lean statements it
    // shows, compressed, so a large family reads larger without dwarfing a small one.
    var famWeight = [];
    function weights() {
      var lo = Infinity, hi = -Infinity;
      fams.forEach(function (f) { lo = Math.min(lo, f.r); hi = Math.max(hi, f.r); });
      famWeight = fams.map(function (f) { return hi > lo ? (f.r - lo) / (hi - lo) : 0.5; });
    }
    function regionLabel(di, R) {
      var d = D.disciplines[di];
      var size = clamp(R * 0.125, 13, 22), sub = clamp(size * 0.7, 11.5, 15);
      var nf = '600 ' + size.toFixed(1) + 'px ' + SERIF, cf = '400 ' + sub.toFixed(1) + 'px ' + SANS;
      var t = fitLines(d.name, nf, R * 1.45, 1) || fitLines(d.name, nf, R * 1.45, 2) || balancedLines(d.name, 2, nf);
      var count = discCounts(d), lead = size * 1.16;
      var c = fitLines(count, cf, R * 1.5, 1) || fitLines(count, cf, R * 1.5, 2) || balancedLines(count, 2, cf);
      return { lines: t.lines, nf: nf, cf: cf, lead: lead, count: c.lines, sub: sub,
               h: t.lines.length * lead + c.lines.length * sub * 1.3 + sub * 0.1, w: Math.max(t.width, c.width) };
    }
    // Points of a hexagonal lattice of spacing d inside a circle, below a top line.
    function latticeIn(cx, cy, R, top, d) {
      var pts = [], row = 0, r = R - d / 2;
      for (var y = Math.max(top + d / 2, cy - r); y <= cy + r + 1e-6; y += d * 0.866, row++) {
        var half = Math.sqrt(Math.max(0, r * r - (y - cy) * (y - cy))), off = row % 2 ? d / 2 : 0;
        for (var k = -Math.ceil(half / d) - 1; k <= Math.ceil(half / d) + 1; k++) {
          var x = cx + k * d + off;
          if (Math.abs(x - cx) <= half + 1e-6) pts.push([x, y]);
        }
      }
      return pts;
    }
    // Seventeen circles, each as large as its families and name need, relaxed apart inside
    // the stage below its bar, then scaled up to the largest size that still fits.
    function packRegions(top) {
      var n = D.disciplines.length, pad = 8, gap = clamp(Math.min(W, H) * 0.012, 6, 14);
      var rho = D.disciplines.map(function (d) { return Math.sqrt(d.families.length + 16); });
      var Hh = H - top - pad, cols = Math.max(1, Math.round(Math.sqrt(n * W / Math.max(1, Hh)))), rows = Math.ceil(n / cols);
      var init = function () {
        return rho.map(function (r, k) {
          var row = Math.floor(k / cols), cnt = row < rows - 1 ? cols : n - cols * (rows - 1), c = k - row * cols;
          return { x: (c + 0.5) * W / cnt + (row % 2 ? 4 : -4), y: top + (row + 0.5) * Hh / rows };
        });
      };
      var run = function (s) {
        var P = init(), R = rho.map(function (r) { return r * s; }), worst = 0;
        for (var it = 0; it < 420; it++) {
          // A gentle pull to the middle closes the gaps, then lets go so the last steps only part.
          var pull = it < 300 ? 0.004 : 0;
          for (var i = 0; i < n; i++) for (var j = i + 1; j < n; j++) {
            var dx = P[j].x - P[i].x, dy = P[j].y - P[i].y, dist = Math.hypot(dx, dy), need = R[i] + R[j] + gap;
            if (dist >= need) continue;
            if (dist < 1e-3) { dx = 1; dy = 0; dist = 1; }
            var m = (need - dist) / 2, ux = dx / dist, uy = dy / dist;
            P[i].x -= ux * m; P[i].y -= uy * m; P[j].x += ux * m; P[j].y += uy * m;
          }
          for (var q = 0; q < n; q++) {
            P[q].x += (W / 2 - P[q].x) * pull; P[q].y += (top + Hh / 2 - P[q].y) * pull;
            P[q].x = clamp(P[q].x, pad + R[q], W - pad - R[q]);
            P[q].y = clamp(P[q].y, top + R[q], H - pad - R[q]);
          }
        }
        for (var a = 0; a < n; a++) for (var b = a + 1; b < n; b++) worst = Math.max(worst, R[a] + R[b] + gap - Math.hypot(P[b].x - P[a].x, P[b].y - P[a].y));
        return { P: P, R: R, worst: worst };
      };
      var area = rho.reduce(function (a, r) { return a + Math.PI * r * r; }, 0);
      var lo = 0, hi = Math.sqrt(W * Hh / area), best = run(hi * 0.5);
      for (var step = 0; step < 14; step++) {
        var mid = (lo + hi) / 2, got = run(mid);
        if (got.worst < 1.5) { lo = mid; best = got; } else hi = mid;
      }
      return best;
    }
    function releaseLayout() {
      var top = topBand(), key = 'r|' + W + 'x' + H + '|' + top;
      if (layoutCache[key]) return layoutCache[key];
      var pk = packRegions(top);
      var nodes = new Array(fams.length), regions = [];
      D.disciplines.forEach(function (d, di) {
        var cx = pk.P[di].x, cy = pk.P[di].y, R = pk.R[di];
        var lab = regionLabel(di, R);
        // The name stands in the region's top cap, where the circle is wide enough for it.
        var halfW = lab.w / 2 + 8, dy = Math.sqrt(Math.max(0, R * R - halfW * halfW));
        var ly = Math.max(cy - dy + 2, cy - R + R * 0.1);
        var below = ly + lab.h + Math.max(4, R * 0.04);
        var list = d.families, need = list.length, cR = R - Math.max(3, R * 0.04);
        var dLo = 2, dHi = cR, pts = null;
        for (var it = 0; it < 24; it++) {
          var dm = (dLo + dHi) / 2, p = latticeIn(cx, cy, cR, below, dm);
          if (p.length >= need) { dLo = dm; pts = p; } else dHi = dm;
        }
        if (!pts) pts = latticeIn(cx, cy, cR, below, dLo);
        var ccy = (below + cy + cR) / 2;
        pts.sort(function (a, b) { return Math.hypot(a[0] - cx, a[1] - ccy) - Math.hypot(b[0] - cx, b[1] - ccy); });
        pts = pts.slice(0, need).sort(function (a, b) { return a[1] - b[1] || a[0] - b[0]; });
        list.forEach(function (fi, k) {
          var p = pts[k] || [cx, cy];
          nodes[fi] = { x: p[0], y: p[1], r: dLo / 2 * 0.86 * (0.74 + 0.26 * famWeight[fi]), a: 1 };
        });
        regions.push({ x: cx, y: cy, r: R, a: 1, lab: lab, ly: ly });
      });
      return (layoutCache[key] = { level: 'release', nodes: nodes, regions: regions });
    }
    // A discipline's families as one block of large discs filling the stage: the column
    // count that gives the largest disc wins. On a phone the stage grows downward instead,
    // so a disc never falls below the size its title needs.
    var PHONE_DISC = 112;
    function discGrid(n, Wp, Hp) {
      var best = null;
      for (var c = 1; c <= n; c++) {
        var rows = Math.ceil(n / c), d = Math.min(Wp / (c + (rows > 1 ? 0.5 : 0)), Hp / (1 + (rows - 1) * 0.866));
        if (!best || d > best.d + 1e-6) best = { c: c, rows: rows, d: d };
      }
      return best;
    }
    function discHeight(di) {
      var n = D.disciplines[di].families.length, pad = 12, Wp = W - 2 * pad;
      var c = Math.max(2, Math.floor((Wp - PHONE_DISC / 2) / PHONE_DISC)), rows = Math.ceil(n / c), d = Wp / (c + (rows > 1 ? 0.5 : 0));
      return Math.ceil(topBand() + d + (rows - 1) * d * 0.866 + pad + 4);
    }
    function discLayout(di) {
      var top = topBand(), key = 'd' + di + '|' + W + 'x' + H + '|' + top;
      if (layoutCache[key]) return layoutCache[key];
      var base = releaseLayout(), list = D.disciplines[di].families, n = list.length, pad = 12;
      var g = discGrid(n, W - 2 * pad, Math.max(60, H - top - pad));
      var d = g.d, rows = g.rows, c = g.c;
      var blockH = d + (rows - 1) * d * 0.866, y0 = top + (H - top - pad - blockH) / 2 + d / 2;
      var nodes = base.nodes.map(function (b) { return { x: b.x, y: b.y, r: b.r, a: 0 }; });
      list.forEach(function (fi, k) {
        var row = Math.floor(k / c), cnt = row < rows - 1 ? c : n - c * (rows - 1), col = k - row * c;
        var rowW = (cnt - 1) * d, off = rows > 1 && row % 2 ? d / 4 : rows > 1 ? -d / 4 : 0;
        var x = W / 2 - rowW / 2 + col * d + off, y = y0 + row * d * 0.866;
        nodes[fi] = { x: x, y: y, r: d / 2 * 0.94 * (0.86 + 0.14 * famWeight[fi]), a: 1 };
      });
      var regions = base.regions.map(function (r) { return { x: r.x, y: r.y, r: r.r, a: 0, lab: r.lab, ly: r.ly }; });
      return (layoutCache[key] = { level: 'disc', di: di, nodes: nodes, regions: regions });
    }
    // Opening a family: its disc grows to fill the stage and the board fades in over it.
    function famLayout(fi) {
      var b = discLayout(fams[fi].d);
      var nodes = b.nodes.map(function (q, i) { return { x: q.x, y: q.y, r: q.r, a: i === fi ? 1 : 0 }; });
      var top = topBand();
      nodes[fi] = { x: W / 2, y: (top + H) / 2, r: Math.max(20, Math.min(W, H - top) * 0.46), a: 1 };
      return { level: 'fam', fi: fi, nodes: nodes, regions: b.regions };
    }
    function chartTarget() {
      var o = sel ? obj(sel) : null;
      if (!o) return { level: 'release', di: -1, fi: -1 };
      if (o.kind === 'd') return { level: 'disc', di: o.i, fi: -1 };
      var fi = famOf(o);
      return { level: 'fam', di: fams[fi].d, fi: fi };
    }
    function copyLayout(l) {
      return { level: l.level, nodes: l.nodes.map(function (q) { return { x: q.x, y: q.y, r: q.r, a: q.a }; }),
               regions: l.regions.map(function (q) { return { x: q.x, y: q.y, r: q.r, a: q.a, lab: q.lab, ly: q.ly }; }) };
    }
    // Move to the layout the selection asks for: animated when the reader chose it.
    function chartTo(animate) {
      if (!D || !W) return;
      var tg = chartTarget();
      // On a phone a discipline's discs keep their size and the stage grows to hold them.
      if (stage) {
        // At the release a phone's stage is three widths tall, so each region keeps room
        // for its name and its families.
        var tall = !narrow() ? 0 : tg.level === 'disc' ? discHeight(tg.di) : tg.level === 'release' ? Math.round(W * 3) : 0;
        var want = tall && tall > Math.round(window.innerHeight * 0.72) ? tall + 'px' : '';
        if (stage.style.height !== want) { stage.style.height = want; if (resize()) return; }
      }
      chrome = chromeBoxes();
      var to = tg.level === 'release' ? releaseLayout() : tg.level === 'disc' ? discLayout(tg.di) : famLayout(tg.fi);
      var same = chart.level === tg.level && chart.di === tg.di && chart.fi === tg.fi;
      chart.level = tg.level; chart.di = tg.di; chart.fi = tg.fi;
      if (!chart.shown || !animate || reduceMotion || same) {
        chart.shown = copyLayout(to); chart.to = to; chart.start = 0;
        draw();
        if (board.pending) showBoard();
        return;
      }
      chart.from = copyLayout(chart.shown); chart.to = to; chart.start = nowMs(); chart.ms = CHART_MS;
      draw();
    }
    function chartAnimating() { return !!chart.start; }
    // Advance the move; returns the eased progress (1 when settled).
    function stepChart() {
      if (!chart.start) return 1;
      var u = clamp((nowMs() - chart.start) / chart.ms, 0, 1), e = easeInOut(u);
      var A = chart.from, B = chart.to, S = chart.shown;
      for (var i = 0; i < B.nodes.length; i++) {
        var a = A.nodes[i], b = B.nodes[i], s = S.nodes[i];
        s.x = a.x + (b.x - a.x) * e; s.y = a.y + (b.y - a.y) * e; s.r = a.r + (b.r - a.r) * e;
        s.a = a.a + (b.a - a.a) * (b.a > a.a ? clamp((e - 0.25) / 0.75, 0, 1) : clamp(e / 0.6, 0, 1));
      }
      for (var j = 0; j < B.regions.length; j++) S.regions[j].a = A.regions[j].a + (B.regions[j].a - A.regions[j].a) * e;
      S.level = B.level;
      if (u >= 1) {
        chart.start = 0; chart.shown = copyLayout(B);
        if (board.pending) showBoard();
        settleRing();
      }
      return u >= 1 ? 1 : e;
    }

    /* ---- Painting -------------------------------------------------------------- */
    function draw() {
      if (drawPending) return;
      drawPending = true;
      requestAnimationFrame(function () { drawPending = false; paint(); });
    }
    // The pair the reader shows: the selected result with its chosen Lean statement, or
    // the selected Lean statement with its chosen paper result. [result id, Lean id] or null.
    function pinnedPair() {
      var o = sel ? obj(sel) : null;
      if (!o || !partsReady) return null;
      if (o.kind === 'r') {
        var r = D.results[o.i], li = r.lean.indexOf(pin) >= 0 ? pin : r.lean[0];
        return li === undefined ? null : [r.id, D.lean[li].id];
      }
      if (o.kind === 'l') {
        var l = D.lean[o.i], ri = l.results.indexOf(pin) >= 0 ? pin : l.results[0];
        return ri === undefined ? null : [D.results[ri].id, l.id];
      }
      return null;
    }
    // One ring, once, round a discipline's region or a family's disc as the move settles.
    function settleRing() {
      if (!ringWanted) return;
      var key = ringWanted;
      ringWanted = null;
      if (reduceMotion || !obj(key)) return;
      ring = { key: key, start: nowMs() };
      draw();
    }
    // A family's title written inside its disc, line by line within the circle's chord at
    // that height: the largest size between 11 and 17 px at which every word fits, with the
    // family's counts beneath when there is room; failing that, cut at a word with an
    // ellipsis (the card and the list carry the whole title).
    function wrapInCircle(words, font, lead, r, n) {
      var h = n * lead, lines = [], k = 0;
      for (var li = 0; li < n; li++) {
        var yc = -h / 2 + (li + 0.5) * lead, edge = Math.abs(yc) + lead * 0.45;
        if (edge >= r) return null;
        var maxW = 2 * Math.sqrt(r * r - edge * edge) * 0.9 - 6, line = '';
        while (k < words.length) {
          var t = line ? line + ' ' + words[k] : words[k];
          if (textWidth(t, font) <= maxW) { line = t; k++; } else break;
        }
        if (!line) return null;
        lines.push({ text: line, maxW: maxW });
        if (k >= words.length) break;
      }
      return k >= words.length ? lines.map(function (l) { return l.text; }) : { partial: lines, k: k };
    }
    function famLabel(fi, r) {
      var key = fi + '|' + Math.round(r);
      if (labelCache[key]) return labelCache[key];
      var words = D.families[fi].title.split(' ').filter(Boolean), out = null, last = null;
      for (var size = clamp(r * 0.18, 11, 17); size >= 11 && !out; size -= 0.5) {
        var font = '500 ' + size.toFixed(1) + 'px ' + SERIF, lead = size * 1.17;
        for (var n = 1; n * lead < r * 1.7 && !out; n++) {
          var got = wrapInCircle(words, font, lead, r, n);
          if (got && got.length) out = { lines: got, font: font, lead: lead, size: size };
          else if (got && got.partial && (!last || got.k > last.got.k)) last = { got: got, font: font, lead: lead, size: size };
        }
      }
      if (!out && last) {
        var lines = last.got.partial.map(function (l) { return l.text; }), tail = last.got.partial[lines.length - 1];
        var lastLine = lines[lines.length - 1];
        while (lastLine.indexOf(' ') > 0 && textWidth(lastLine + '…', last.font) > tail.maxW) lastLine = lastLine.replace(/\s+\S+$/, '');
        // A last word too long for its line with the ellipsis moves the ellipsis up a line.
        if (textWidth(lastLine + '…', last.font) > tail.maxW && lines.length > 1) { lines.pop(); lastLine = lines[lines.length - 1]; }
        lines[lines.length - 1] = lastLine.replace(/[,;:]$/, '') + '…';
        out = { lines: lines, font: last.font, lead: last.lead, size: last.size };
      }
      if (!out) out = { lines: [words.slice(0, 2).join(' ') + '…'], font: '500 11px ' + SERIF, lead: 13, size: 11 };
      return (labelCache[key] = out);
    }
    function drawText(lines, x, y, font, color, lead, align, halo) {
      ctx.font = font; ctx.textAlign = align || 'center'; ctx.textBaseline = 'middle';
      if (halo) { ctx.lineJoin = 'round'; ctx.lineWidth = 4; ctx.strokeStyle = halo; }
      lines.forEach(function (l, i) {
        if (halo) ctx.strokeText(l, x, y + lead / 2 + i * lead);
        ctx.fillStyle = color; ctx.fillText(l, x, y + lead / 2 + i * lead);
      });
    }
    var chartBoxes = [];          // words and discs on the drawing, for the card to keep off
    function paint() {
      if (!D || !W || !chart.shown) return;
      var e = stepChart(), S = chart.shown, moving = !!chart.start;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      chartBoxes = [];
      var hk = hover ? obj(hover) : null, lvl = S.level;
      var words = moving ? clamp((e - 0.55) / 0.45, 0, 1) : 1;
      var hd = hk && hk.kind === 'd' ? hk.i : -1, hf = hk && hk.kind === 'f' ? hk.i : -1;
      // Regions: a flat slice of the ground, edged by a hairline, a heavier edge when pointed at.
      S.regions.forEach(function (g, di) {
        if (g.a < 0.01) return;
        ctx.save();
        ctx.globalAlpha = g.a;
        ctx.beginPath(); ctx.arc(g.x, g.y, g.r, 0, TAU);
        ctx.fillStyle = palette.slice; ctx.fill();
        ctx.lineWidth = di === hd ? 2 : 1; ctx.strokeStyle = di === hd ? palette.focus : palette.structFaint; ctx.stroke();
        ctx.restore();
      });
      // At a discipline, the citations of the family pointed at: brick to the families its
      // papers cite, grey from those that cite it, an arrowhead at the cited end.
      var near = {};
      if (lvl === 'disc' && hf >= 0 && !moving) {
        near[hf] = 1;
        ctx.save();
        D.links.forEach(function (row) {
          [[row[0], row[1], row[2]], [row[1], row[0], row[3]]].forEach(function (lk) {
            var from = lk[0], to = lk[1], w = lk[2];
            if (!w || (from !== hf && to !== hf)) return;
            var A = S.nodes[from], B = S.nodes[to];
            if (A.a < 0.5 || B.a < 0.5) return;
            near[from === hf ? to : from] = 1;
            var dx = B.x - A.x, dy = B.y - A.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
            var bow = Math.min(60, len * 0.15), mx = (A.x + B.x) / 2 - uy * bow, my = (A.y + B.y) / 2 + ux * bow;
            var sa = Math.atan2(my - A.y, mx - A.x), sb = Math.atan2(my - B.y, mx - B.x);
            var x0 = A.x + (A.r + 2) * Math.cos(sa), y0 = A.y + (A.r + 2) * Math.sin(sa), x1 = B.x + (B.r + 3) * Math.cos(sb), y1 = B.y + (B.r + 3) * Math.sin(sb);
            var ink = from === hf ? palette.cites : palette.cited;
            ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = 1.4 + 0.6 * Math.log(1 + w);
            ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(mx, my, x1, y1); ctx.stroke();
            var ex = x1 - mx, ey = y1 - my, el = Math.hypot(ex, ey) || 1, hs = 8;
            ex /= el; ey /= el;
            ctx.beginPath(); ctx.moveTo(x1, y1);
            ctx.lineTo(x1 - ex * hs - ey * hs * 0.5, y1 - ey * hs + ex * hs * 0.5);
            ctx.lineTo(x1 - ex * hs + ey * hs * 0.5, y1 - ey * hs - ex * hs * 0.5);
            ctx.closePath(); ctx.fill();
          });
        });
        ctx.restore();
      }
      // The families.
      var pp = hk ? null : null;
      for (var fi = 0; fi < fams.length; fi++) {
        var q = S.nodes[fi];
        if (!q || q.a < 0.01) continue;
        var f = fams[fi].data, tone = f.tone || 'none', hollow = tone === 'none' || tone === 'unread';
        var a = q.a;
        if (matchFam && !searchFolded && !matchFam[fi]) a *= 0.22;
        if (lvl === 'disc' && hf >= 0 && !near[fi]) a *= 0.45;
        var hot = fi === hf || (sel && obj(sel) && obj(sel).kind === 'f' && obj(sel).i === fi);
        ctx.save();
        ctx.globalAlpha = a;
        ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, TAU);
        ctx.fillStyle = hollow ? palette.ground : (lvl === 'disc' || lvl === 'fam' ? palette.tone[tone + 'Tint'] : palette.tone[tone]);
        ctx.fill();
        ctx.lineWidth = hot ? 2.6 : lvl === 'release' ? (hollow ? 1.1 : 0.8) : clamp(q.r * 0.05, 2, 4);
        ctx.strokeStyle = hot ? palette.focus : palette.tone[tone + 'Edge'];
        if (lvl !== 'release' && !hot) ctx.strokeStyle = hollow ? palette.struct : palette.tone[tone];
        ctx.stroke();
        ctx.restore();
        if (lvl === 'disc' && q.a > 0.5) chartBoxes.push({ x0: q.x - q.r, x1: q.x + q.r, y0: q.y - q.r, y1: q.y + q.r, fi: fi, disc: true });
      }
      // The words: each discipline's name and counts in its region; each family's title in its disc.
      if (words > 0.01) {
        if (lvl === 'release') {
          S.regions.forEach(function (g, di) {
            if (g.a < 0.05) return;
            var lab = g.lab;
            ctx.save(); ctx.globalAlpha = g.a * words;
            drawText(lab.lines, g.x, g.ly, lab.nf, palette.ink, lab.lead, 'center', palette.ground);
            drawText(lab.count, g.x, g.ly + lab.lines.length * lab.lead + 1, lab.cf, palette.muted, lab.sub * 1.3, 'center', palette.ground);
            ctx.restore();
            chartBoxes.push({ x0: g.x - lab.w / 2, x1: g.x + lab.w / 2, y0: g.ly, y1: g.ly + lab.h, di: di });
          });
        } else if (lvl === 'disc') {
          for (var fj = 0; fj < fams.length; fj++) {
            var n = S.nodes[fj];
            if (!n || n.a < 0.5) continue;
            var t = famLabel(fj, n.r), f2 = fams[fj].data;
            var cnt = [count('papers', f2.papers.length)];
            if (f2.lean.length) cnt.push(count('lean', f2.lean.length));
            var cntText = cnt.length > 1 ? T('card.counts', { papers: cnt[0], lean: cnt[1] }) : cnt[0];
            var cf = '400 ' + clamp(t.size * 0.78, 10.5, 13).toFixed(1) + 'px ' + SANS, cl = t.size * 1.05;
            var cy2 = (t.lines.length * t.lead + cl) / 2, ce = cy2 + 2;
            var showCnt = ce < n.r && textWidth(cntText, cf) <= 2 * Math.sqrt(n.r * n.r - ce * ce) * 0.9 - 6;
            var blockH = t.lines.length * t.lead + (showCnt ? cl : 0);
            var a2 = n.a * words * (matchFam && !searchFolded && !matchFam[fj] ? 0.3 : 1) * (hf >= 0 && !near[fj] ? 0.55 : 1);
            ctx.save(); ctx.globalAlpha = a2;
            drawText(t.lines, n.x, n.y - blockH / 2, t.font, palette.ink, t.lead, 'center');
            if (showCnt) drawText([cntText], n.x, n.y - blockH / 2 + t.lines.length * t.lead, cf, palette.muted, cl, 'center');
            ctx.restore();
          }
        }
      }
      paintRing();
      if (!board.on) { cardFor = cardObject(); placeCard(cardFor); }
      if (chart.start || ring) draw();
      if (window.__universeDebug) window.__universeDebug.boxes = chartBoxes;
    }
    function paintRing() {
      if (!ring) return;
      var o = obj(ring.key), u = (nowMs() - ring.start) / RING_MS;
      if (!o || ring.key !== sel || u >= 1 || reduceMotion || !chart.shown) { ring = null; return; }
      var c = null;
      if (o.kind === 'd') c = chart.shown.regions[o.i];
      if (!c) { ring = null; return; }
      ctx.save();
      ctx.globalAlpha = 0.85 * (1 - u) * (1 - u);
      ctx.strokeStyle = palette.focus; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(c.x, c.y, c.r + 3 + RING_GROW * easeOut(u), 0, TAU); ctx.stroke();
      ctx.restore();
    }
    // What is under the point: a family's disc at a discipline, a discipline's region at the release.
    function hitAt(x, y) {
      var S = chart.shown;
      if (!S || chart.start) return null;
      if (S.level === 'disc') {
        for (var fi = 0; fi < fams.length; fi++) {
          var q = S.nodes[fi];
          if (q && q.a > 0.5 && Math.hypot(x - q.x, y - q.y) <= q.r + 2) return D.families[fi].id;
        }
        return null;
      }
      if (S.level === 'release') {
        for (var di = 0; di < S.regions.length; di++) {
          var g = S.regions[di];
          if (Math.hypot(x - g.x, y - g.y) <= g.r) return D.disciplines[di].id;
        }
      }
      return null;
    }

    /* ---- The card: what the pointer names, in words, beside it on the map ---------
       On a screen that hovers, pointing at a family, paper, result or Lean statement
       (or at its row in the list, or focusing that row) shows a small card beside the
       object: its name, where it belongs, its counts and its state, each in words. It
       sits inside the stage, never over the object or under the pointer, and fades in
       over --t-hover. A touch screen gets none: tapping selects. */
    var hoverMQ = window.matchMedia ? window.matchMedia('(hover: hover) and (pointer: fine)') : null;
    var cardEl = null, cardFor = null, cardKey = '', cardOn = false, cardSpot = -1, cardPtr = null, cardBox = null;
    if (stage) {
      cardEl = document.createElement('div');
      cardEl.className = 'u-card';
      cardEl.setAttribute('aria-hidden', 'true');
      stage.appendChild(cardEl);
    }
    function cardObject() {
      if (!cardEl || !hover || !D || board.on || !chart.shown) return null;
      var o = obj(hover);
      if (!o || hover === sel || hover === cardDismissed) return null;
      if (hoverVia === 'touch' || (hoverVia !== 'focus' && !(hoverMQ && hoverMQ.matches))) return null;
      var S = chart.shown;
      if (o.kind === 'd') return S.level === 'release' && !chart.start ? o : null;
      if (o.kind === 'f') return S.nodes[o.i] && S.nodes[o.i].a > 0.5 && !chart.start && S.level !== 'fam' ? o : null;
      return null;
    }
    function pairKind(st) { return st === 'candidate-pairing' ? 'candidate' : st === 'producer-declared-binding' ? 'declared' : 'cited'; }
    function resultCardName(ri) {
      var r = D.results[ri];
      return r.lab ? r.lab : T('card.result_in', { name: resultName(r), paper: D.papers[r.p].short });
    }
    function cardJoin(kind) {
      return '<span class="u-join u-join--' + (kind === 'candidate' ? 'candidate' : 'cited') + '" aria-hidden="true"></span>';
    }
    function cardHtml(o) {
      var det = detail(o), h = '';
      var line = function (cls, html) { h += '<p class="u-card__' + cls + '">' + html + '</p>'; };
      if (o.kind === 'f') {
        var f = D.families[o.i];
        line('t tex-auto', det && det.titleHtml ? det.titleHtml : escapeHtml(f.title));
        line('k', escapeHtml(T('family.kicker', { num: f.num, discipline: D.disciplines[f.d].name })));
        var n = [count('papers', f.papers.length)];
        if (f.lean.length) n.push(count('lean', f.lean.length));
        line('n', escapeHtml(n.length > 1 ? T('card.counts', { papers: n[0], lean: n[1] }) : n[0]));
        line('e', dot(f.tone) + '<span>' + escapeHtml(T('key.' + f.tone)) + '</span>');
      } else if (o.kind === 'd') {
        line('t', escapeHtml(D.disciplines[o.i].name));
        line('n', escapeHtml(discCounts(D.disciplines[o.i])));
        var tally = {};
        D.disciplines[o.i].families.forEach(function (fi) { var t = D.families[fi].tone || 'none'; tally[t] = (tally[t] || 0) + 1; });
        ['all', 'part', 'other', 'split', 'none', 'unread'].forEach(function (t) {
          if (tally[t]) line('e', dot(t) + '<span>' + escapeHtml(T('key.' + t)) + ': ' + tally[t] + '</span>');
        });
      } else if (o.kind === 'p') {
        var p = D.papers[o.i];
        line('t', escapeHtml(p.short));
        line('k', escapeHtml(T('paper.kicker', { num: D.families[p.f].num }) + (p.date ? ', ' + p.date : '')));
        line('n', escapeHtml(count('results', p.results.length)));
      } else if (o.kind === 'r') {
        var r = D.results[o.i], rp = D.papers[r.p];
        line('t', escapeHtml(resultName(r)) + (det && det.titleHtml ? ' <span class="u-card__sub tex-auto">(' + det.titleHtml + ')</span>' : ''));
        line('k', escapeHtml(T('result.in_paper', { paper: rp.short }) + (rp.date ? ', ' + rp.date : '')));
        if (!r.lean.length) line('e', escapeHtml(T('card.result_none')));
        else {
          var kinds = r.lean.map(function (li) { return pairKind(D.lean[li].pairing); });
          var names = r.lean.map(function (li) { return D.lean[li].label; }).join(', ');
          var one = kinds.every(function (k) { return k === kinds[0]; }) ? kinds[0] : null;
          var key = !one ? 'card.result_mixed' : one === 'candidate' ? (kinds.length > 1 ? 'card.result_candidate_many' : 'card.result_candidate') : 'card.result_' + one;
          line('e', cardJoin(one || 'cited') + '<span>' + escapeHtml(T(key, { name: names })) + '</span>');
        }
      } else if (o.kind === 'l') {
        var l = D.lean[o.i];
        line('t u-card__t--lean', escapeHtml(l.label) + (l.label !== l.name ? '<code>' + escapeHtml(l.name) + '</code>' : ''));
        line('k', escapeHtml(T('lean.kicker', { num: D.families[l.f].num })));
        if (!l.results.length) line('e', escapeHtml(T('lean.paired_none')));
        else {
          var lk = pairKind(l.pairing);
          line('e', cardJoin(lk) + '<span>' + escapeHtml(T('card.lean_' + lk, { name: l.results.map(resultCardName).join('; ') })) + '</span>');
        }
      }
      return h;
    }
    function hideCard() {
      if (!cardOn) return;
      cardEl.classList.remove('is-on');
      cardOn = false; cardSpot = -1; cardBox = null;
    }
    // Beside what it names, in the place that covers the fewest other words and discs:
    // eight places round it first, then any place in the stage, never over the thing
    // pointed at (for a discipline, its name) or under the pointer, off the map's bar.
    var cardDismissed = null, cardSwept = -1e9, cardTimer = 0;
    function hoverBox(o) {
      var S = chart.shown;
      if (!o || !S) return null;
      if (o.kind === 'd') { var g = S.regions[o.i]; return { x0: g.x - g.lab.w / 2, x1: g.x + g.lab.w / 2, y0: g.ly, y1: g.ly + g.lab.h }; }
      if (o.kind === 'f') { var q = S.nodes[o.i]; return { x0: q.x - q.r, x1: q.x + q.r, y0: q.y - q.r, y1: q.y + q.r }; }
      return null;
    }
    function placeCard(o) {
      if (!cardEl || cardEl.classList.contains('is-board')) return;
      if (!o) { hideCard(); return; }
      var S = chart.shown, m;
      if (o.kind === 'd') { var g = S.regions[o.i]; m = { x0: g.x - g.lab.w / 2, x1: g.x + g.lab.w / 2, y0: g.ly, y1: g.ly + g.lab.h }; }
      else { var q = S.nodes[o.i]; m = { x0: q.x - q.r - 2, x1: q.x + q.r + 2, y0: q.y - q.r - 2, y1: q.y + q.r + 2 }; }
      var key = o.key + (detail(o) ? '+' : '');
      if (key !== cardKey) {
        // While the pointer sweeps across the drawing the card waits for it to rest (70 ms),
        // so a fast pass costs no typesetting and the frames stay smooth.
        var t = nowMs();
        if (cardOn && t - cardSwept < 70) {
          cardSwept = t;
          hideCard();
          clearTimeout(cardTimer); cardTimer = setTimeout(draw, 80);
          return;
        }
        cardSwept = t;
        cardEl.innerHTML = cardHtml(o);
        if (window.atlasRenderMath) window.atlasRenderMath(cardEl);
        cardKey = key; cardSpot = -1;
      }
      var w = cardEl.offsetWidth, h = cardEl.offsetHeight;
      if (!w || !h) { hideCard(); return; }
      var keep = [m];
      if (cardPtr) keep.push({ x0: cardPtr[0] - 10, x1: cardPtr[0] + 22, y0: cardPtr[1] - 10, y1: cardPtr[1] + 26 });
      var others = chartBoxes.filter(function (b) { return !(o.kind === 'd' && b.di === o.i) && !(o.kind === 'f' && b.fi === o.i); });
      if (o.kind === 'f' && S.level === 'release') {
        // A family's dot at the release: the card keeps off the disciplines' names.
        others = chartBoxes.filter(function (b) { return b.di !== undefined; });
      }
      var g2 = 12, spots = [[m.x1 + g2, (m.y0 + m.y1) / 2 - h / 2], [m.x0 - g2 - w, (m.y0 + m.y1) / 2 - h / 2], [m.x0, m.y1 + g2], [m.x0, m.y0 - g2 - h],
                            [m.x1 + g2, m.y1 - h], [m.x0 - g2 - w, m.y1 - h], [m.x1 - w, m.y1 + g2], [m.x1 - w, m.y0 - g2 - h]];
      var X1 = Math.max(8, W - w - 8), Y1 = Math.max(8, H - h - 8);
      var best = null, bestScore = Infinity, bestI = -1;
      var tryAt = function (sp, i) {
        var x0 = clamp(sp[0], 8, X1), y0 = clamp(sp[1], 8, Y1);
        var b = { x0: x0, x1: x0 + w, y0: y0, y1: y0 + h };
        var gapX = Math.max(0, m.x0 - b.x1, b.x0 - m.x1), gapY = Math.max(0, m.y0 - b.y1, b.y0 - m.y1);
        var score = (sp[2] ? 40 : i * 2) + Math.hypot(gapX, gapY) * 0.8 - (i === cardSpot && !sp[2] ? 25 : 0);
        keep.forEach(function (k) { var ov = overlap(b, k); if (ov > 0) score += 1e5 + ov * 20; });
        others.forEach(function (k) { var ov = overlap(b, k); if (ov > 2) score += 400 + ov * 0.02; });
        chrome.forEach(function (k) { var ov = overlap(b, k); if (ov > 0) score += 600 + ov * 0.05; });
        if (score < bestScore) { bestScore = score; best = b; bestI = sp[2] ? -1 : i; }
      };
      spots.forEach(tryAt);
      if (bestScore >= 400) for (var gx = 8; gx <= X1; gx += 24) for (var gy = 8; gy <= Y1; gy += 24) tryAt([gx, gy, 1], 0);
      cardSpot = bestI; cardBox = best;
      cardEl.style.transform = 'translate(' + Math.round(best.x0) + 'px, ' + Math.round(best.y0) + 'px)';
      if (!cardOn) { cardEl.classList.add('is-on'); cardOn = true; }
    }

    /* ---- The family board ---------------------------------------------------
       Inside a family the drawing gives way to a board of cards: the families whose
       papers cite it on the left, its papers in columns (each result named as its paper
       prints it, with the opening of its statement typeset, and the Lean statements
       paired with it joined beneath), and the families its papers cite on the right.
       Every name is on its card. Hover explains (the card beside it), click selects
       (the panel shows the record), double-click or Enter opens, Escape steps back.
       Lines are the board's only drawing: a result to the Lean statements paired with
       it (dashed for a candidate pairing), and a neighbouring family to the papers that
       carry the citation (brick where this family cites, grey where it is cited). */
    var boardEl = root.querySelector('[data-u-board]');
    var board = { fi: -1, sig: '', page: 0, per: 1, cols: 0, on: false, pending: false, budget: 170, hideT: 0, ringKey: null };
    var SIDE_MAX = 8;
    function boardFamily() { var o = sel ? obj(sel) : null; return partsReady && o && o.kind !== 'd' ? famOf(o) : -1; }
    function dateValue(s) { var t = s ? Date.parse(s) : NaN; return isFinite(t) ? t : Infinity; }
    // The opening of a statement, concisely: its first sentence (the second too when the
    // first is short), formulas whole, a long displayed formula as an ellipsis, cut at a
    // word with an ellipsis past the budget (characters; a formula counts half its TeX).
    function excerpt(html, budget) {
      var tpl = document.createElement('template');
      tpl.innerHTML = html || '';
      var toks = [];
      var walk = function (node) {
        for (var c = node.firstChild; c; c = c.nextSibling) {
          if (c.nodeType === 3) { toks.push({ t: 'text', s: c.nodeValue }); continue; }
          if (c.nodeType !== 1) continue;
          if (c.classList.contains('m')) { toks.push({ t: c.getAttribute('data-d') === '1' ? 'dmath' : 'math', s: c.textContent }); continue; }
          if (c.classList.contains('li-lab')) { toks.push({ t: 'text', s: c.textContent + ' ' }); continue; }
          if (/^(P|DIV|LI|OL|UL|BLOCKQUOTE)$/.test(c.tagName)) { toks.push({ t: 'break' }); walk(c); toks.push({ t: 'break' }); continue; }
          walk(c);
        }
      };
      walk(tpl.content);
      var out = '', used = 0, setup = null;
      var space = function () { if (out && !/\s$/.test(out)) { out += ' '; used += 1; } };
      // A sentence that only fixes notation ("Let X be ...") does not say what is proved:
      // the excerpt runs on into the next one.
      var enough = function () { var s0 = setup; setup = null; return used >= 70 && !s0; };
      var opens = function (word) { if (setup === null) setup = /^(Let|Suppose|Assume|Fix|Write|Denote|Consider|Given|For|Throughout|Set|Define)$/.test(word.replace(/[^A-Za-z]/g, '')); };
      var ends = function (word) { return /[.!?]["”’)]?$/.test(word) && !/^(e\.g|i\.e|cf|resp|viz|al|etc|Thm|Prop|Lem|Cor|Def|Sec|Eq|Fig|No)\.$/.test(word); };
      for (var i = 0; i < toks.length; i++) {
        var k = toks[i];
        if (k.t === 'break') { space(); continue; }
        if (k.t === 'math' || k.t === 'dmath') {
          var tex = k.s.trim(), stop = /[.;,:]$/.exec(tex), body = stop ? tex.slice(0, -1).trim() : tex;
          if (k.t === 'dmath' && body.length > 48) { space(); out += '…'; used += 2; if (stop && stop[0] === '.' && enough()) return { html: out, cut: false }; space(); continue; }
          var w = Math.max(2, body.length * 0.5);
          if (used + w > budget && used > 0) return { html: out.replace(/[\s,;:]+$/, ''), cut: true };
          if (k.t === 'dmath') space();
          out += '<span class="m">' + escapeHtml(body) + '</span>' + (stop ? stop[0] : '');
          used += w;
          if (stop && stop[0] === '.' && enough()) return { html: out, cut: false };
          continue;
        }
        var parts = k.s.split(/(\s+)/);
        for (var j = 0; j < parts.length; j++) {
          var piece = parts[j];
          if (!piece) continue;
          if (/^\s+$/.test(piece)) { space(); continue; }
          if (used + piece.length > budget && used > 0) return { html: out.replace(/[\s,;:]+$/, ''), cut: true };
          opens(piece);
          out += escapeHtml(piece); used += piece.length;
          if (ends(piece) && enough()) return { html: out, cut: false };
        }
      }
      return { html: out.trim(), cut: false };
    }
    // KaTeX for the formulas in el, with the paper's own macros where it has them.
    function katexIn(el, paperId, di) {
      if (!window.katex) { if (window.atlasRenderMath) window.atlasRenderMath(el); return; }
      var spans = el.querySelectorAll('span.m:not([data-done])');
      if (!spans.length) { if (window.atlasRenderMath) window.atlasRenderMath(el); return; }
      var macros = {}, k, sh = shards[di];
      for (k in GLOBAL_MACROS) macros[k] = GLOBAL_MACROS[k];
      var own = sh && sh.macros && paperId ? sh.macros[paperId] || {} : {};
      for (k in own) if (typeof own[k] === 'string' && !/\\(?:newcommand|def|let|ifx|ifmmode|csname|expandafter)/.test(own[k])) macros[k] = own[k];
      for (var i = 0; i < spans.length; i++) {
        var s = spans[i], tex = s.textContent;
        s.setAttribute('data-done', '1');
        try {
          var src = window.atlasKeepShortMath ? window.atlasKeepShortMath(tex) : tex;
          window.katex.render(src, s, { displayMode: false, macros: Object.assign({}, macros), throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
        } catch (err) { s.textContent = tex; s.classList.add('m-fail'); }
      }
      if (window.atlasRenderMath) window.atlasRenderMath(el);
    }
    function bcOpen(cls, key, extra) {
      return '<div class="u-bc ' + cls + '" role="button" tabindex="0" data-bk="' + escapeHtml(key) + '"' + (extra || '') + '>';
    }
    function boardResult(ri, sh) {
      var r = D.results[ri], det = sh && sh.results ? sh.results[r.id] : null, p = D.papers[r.p];
      var h = bcOpen('u-bc--r', r.id, ' data-paper="' + escapeHtml(p.id) + '"');
      // In its paper's column a result needs only the number the paper prints.
      h += '<p class="u-bc__lab">' + escapeHtml(r.num || resultName(r)) + (det && det.titleHtml ? ' <span class="u-bc__ttl tex-auto">(' + det.titleHtml + ')</span>' : '') + '</p>';
      if (!sh) h += '<p class="u-bc__x u-bc__x--none">' + escapeHtml(T('board.loading')) + '</p>';
      else if (det && det.html) {
        var ex = excerpt(det.html, board.budget);
        h += '<div class="u-bc__x">' + ex.html + (ex.cut ? '…' : '') + '</div>';
      } else h += '<p class="u-bc__x u-bc__x--none">' + escapeHtml(T('board.no_statement')) + ' ' + link(r.href || p.href, T('result.read')) + '</p>';
      return h + '</div>';
    }
    function boardLean(li, sh, free) {
      var l = D.lean[li], det = sh && sh.lean ? sh.lean[l.id] : null, kind = pairKind(l.pairing);
      var cand = !free && kind === 'candidate';
      var h = bcOpen('u-bc--l' + (cand ? ' is-cand' : ''), l.id);
      h += '<p class="u-bc__lt">' + escapeHtml(l.label || l.name) + '</p>';
      if (l.label && l.label !== l.name) h += '<p class="u-bc__id"><code>' + escapeHtml(l.name) + '</code></p>';
      h += '<p class="u-bc__ln u-bc__ln--q">' + escapeHtml(free ? T('board.unpaired') : T('board.pair_' + kind)) + '</p>';
      if (det) h += '<p class="u-bc__ln">' + escapeHtml(det.reruns || T('lean.reruns_none')) + '</p>';
      return h + '</div>';
    }
    function boardPaper(pi) {
      var p = D.papers[pi];
      var h = bcOpen('u-bc--p', p.id);
      h += '<p class="u-bc__pt">' + escapeHtml(p.short) + '</p>';
      if (p.date) h += '<p class="u-bc__d">' + escapeHtml(p.date) + '</p>';
      var acts = link(p.href, T('paper.read')) + link(p.pdf, T('paper.pdf'));
      if (acts) h += '<p class="u-bc__acts">' + acts + '</p>';
      return h + '</div>';
    }
    function boardNeighbour(g, n, way) {
      var f = D.families[g], sh = shards[fams[g].d], det = sh && sh.families ? sh.families[f.id] : null;
      var h = bcOpen('u-bc--f', f.id, ' data-g="' + g + '" data-way="' + way + '"');
      h += '<p class="u-bc__k">' + escapeHtml(T('family.short', { num: f.num })) + '</p>';
      h += '<p class="u-bc__ft tex-auto">' + (det && det.titleHtml ? det.titleHtml : escapeHtml(f.title)) + '</p>';
      h += '<p class="u-bc__ln">' + escapeHtml(D.disciplines[fams[g].d].name) + '</p>';
      h += '<p class="u-bc__ln">' + escapeHtml(n === 1 ? T('board.citations_one') : T('board.citations', { n: n })) + '</p>';
      return h + '</div>';
    }
    function boardSide(way, list) {
      var h = '<section class="u-board__side u-board__side--' + way + '"><h3>' + escapeHtml(T(way === 'in' ? 'board.cited_by' : 'board.cites')) + '</h3>';
      if (!list.length) return h + '<p class="u-board__none">' + escapeHtml(T(way === 'in' ? 'board.none_in' : 'board.none_out')) + '</p></section>';
      var sorted = list.slice().sort(function (a, b) { return b[1] - a[1] || a[0] - b[0]; });
      sorted.slice(0, SIDE_MAX).forEach(function (c) { h += boardNeighbour(c[0], c[1], way); });
      var more = sorted.length - SIDE_MAX;
      if (more > 0) h += '<p class="u-board__more">' + escapeHtml(more === 1 ? T('board.more_one') : T('board.more', { n: more })) + '</p>';
      return h + '</section>';
    }
    function boardHtml(fi) {
      var f = D.families[fi], d = D.disciplines[fams[fi].d], sh = shards[fams[fi].d] || null;
      var fdet = sh && sh.families ? sh.families[f.id] : null;
      var h = '<div class="u-board__in" data-u-board-in><svg class="u-board__wires" data-u-wires aria-hidden="true"></svg>';
      h += '<div class="u-board__head"><p class="u-board__k">' + escapeHtml(T('family.kicker', { num: f.num, discipline: d.name })) + '</p>';
      h += '<h2 class="u-board__t tex-auto">' + (fdet && fdet.titleHtml ? fdet.titleHtml : escapeHtml(f.title)) + '</h2>';
      if (!f.lean.length) h += '<p class="u-board__r">' + escapeHtml(T('evidence.no_lean')) + '</p>';
      else if (fdet && (fdet.readers || []).length) {
        // Each reader in their own words, then whether they agree (the backend's sentence).
        var said = fdet.readers.map(function (rd) { return rd.name + ' ' + rd.words; }).join('; ') + '.';
        h += '<p class="u-board__r"><b>' + escapeHtml(T('board.readers')) + '</b> ' + escapeHtml(said + (fdet.agree ? ' ' + fdet.agree : '')) + '</p>';
      } else if (fdet && fdet.agree) h += '<p class="u-board__r"><b>' + escapeHtml(T('board.readers')) + '</b> ' + escapeHtml(fdet.agree) + '</p>';
      h += '</div><div class="u-board__cols">' + boardSide('in', f.citedBy) + '<div class="u-board__main"><div class="u-board__bar">' +
        '<span class="u-pager" data-u-pager hidden>' +
        '<button type="button" data-u-page="-1" aria-label="' + escapeHtml(T('board.earlier')) + '"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3 5 8l5 5"/></svg></button>' +
        '<span data-u-page-n></span>' +
        '<button type="button" data-u-page="1" aria-label="' + escapeHtml(T('board.later')) + '"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3l5 5-5 5"/></svg></button></span></div>' +
        '<div class="u-board__papers" data-u-papers>';
      var papers = f.papers.slice().sort(function (a, b) { return dateValue(D.papers[a].date) - dateValue(D.papers[b].date) || a - b; });
      var anyCand = false;
      papers.forEach(function (pi) {
        h += '<section class="u-col" data-pi="' + pi + '">' + boardPaper(pi) + '<ol>';
        D.papers[pi].results.forEach(function (ri) {
          var r = D.results[ri];
          h += '<li>' + boardResult(ri, sh);
          if (r.lean.length) {
            h += '<div class="u-leans">' + r.lean.map(function (li) { if (pairKind(D.lean[li].pairing) === 'candidate') anyCand = true; return boardLean(li, sh, false); }).join('') + '</div>';
          }
          h += '</li>';
        });
        h += '</ol></section>';
      });
      var free = f.lean.filter(function (li) { return !D.lean[li].results.length; });
      if (free.length) {
        h += '<section class="u-col u-col--free"><h3 class="u-board__colh">' + escapeHtml(T('board.unpaired_heading')) + '</h3><div class="u-leans u-leans--free">' +
          free.map(function (li) { return boardLean(li, sh, true); }).join('') + '</div></section>';
      }
      h += '</div>' + (anyCand ? '<p class="u-board__foot">' + escapeHtml(T('board.dashed')) + '</p>' : '') + '</div>';
      h += boardSide('out', f.cites) + '</div></div>';
      return h;
    }
    // Typeset every card: each result with its own paper's macros.
    function typesetBoard(fi) {
      var di = fams[fi].d;
      Array.prototype.forEach.call(boardEl.querySelectorAll('.u-bc--r'), function (c) { katexIn(c, c.getAttribute('data-paper'), di); });
      katexIn(boardEl.querySelector('.u-board__head'), null, di);
      Array.prototype.forEach.call(boardEl.querySelectorAll('.u-bc--f'), function (c) { katexIn(c, null, fams[+c.getAttribute('data-g')].d); });
    }
    // Paper and unpaired-Lean columns share the board's pagination.
    function layoutBoard() {
      if (!board.on && !board.pending) return;
      var papersEl = boardEl.querySelector('[data-u-papers]');
      if (!papersEl) return;
      var cols = Array.prototype.slice.call(papersEl.children);
      var fpx = parseFloat(getComputedStyle(boardEl).fontSize) || 16;
      var per = narrow() ? cols.length : Math.max(1, Math.floor((papersEl.clientWidth + 1.25 * fpx) / (14 * fpx + 1.25 * fpx)));
      per = Math.min(per, Math.max(1, cols.length));
      board.per = per; board.cols = cols.length;
      var pages = Math.max(1, Math.ceil(cols.length / per));
      board.page = clamp(board.page, 0, pages - 1);
      papersEl.style.gridTemplateColumns = narrow() ? '' : 'repeat(' + per + ', minmax(0, 1fr))';
      papersEl.style.gridAutoFlow = 'row';
      cols.forEach(function (c, i) { c.hidden = i < board.page * per || i >= (board.page + 1) * per; });
      var pager = boardEl.querySelector('[data-u-pager]');
      if (pager) {
        pager.hidden = pages < 2;
        var from = board.page * per + 1, to = Math.min(cols.length, (board.page + 1) * per);
        var mixed = cols.some(function (col) { return col.classList.contains('u-col--free'); });
        pager.querySelector('[data-u-page-n]').textContent = mixed
          ? T('board.mixed_page', { page: board.page + 1, pages: pages })
          : T(from === to ? 'board.page_one' : 'board.page', { from: from, to: to, n: cols.length });
        var prev = pager.querySelector('[data-u-page="-1"]'), next = pager.querySelector('[data-u-page="1"]');
        prev.setAttribute('aria-label', T(mixed ? 'board.previous_page' : 'board.earlier'));
        next.setAttribute('aria-label', T(mixed ? 'board.next_page' : 'board.later'));
        prev.disabled = board.page === 0;
        next.disabled = board.page >= pages - 1;
      }
      // The statements' length follows the column's width: about four lines of it.
      var rc = papersEl.querySelector('.u-col:not([hidden]) .u-bc--r');
      if (rc && rc.clientWidth > 0) {
        var cpl = (rc.clientWidth - 1.5 * fpx) / (fpx * 0.48);
        var want = clamp(Math.round(cpl * 4 / 10) * 10, 90, 420);
        if (Math.abs(want - board.budget) >= 20) { board.budget = want; board.sig = ''; syncBoard(); return; }
      }
      fitExcerpts();
      drawWires();
    }
    // An excerpt that would run past its card's four or five lines (a formula wider or
    // taller than the estimate) is cut shorter, so no statement is ever clipped mid-line.
    function fitExcerpts() {
      var di = fams[board.fi] ? fams[board.fi].d : -1, sh = shards[di];
      if (!sh || !sh.results) return;
      Array.prototype.forEach.call(boardEl.querySelectorAll('.u-col:not([hidden]) .u-bc--r .u-bc__x:not(.u-bc__x--none)'), function (x) {
        var c = x.closest('.u-bc'), det = sh.results[c.getAttribute('data-bk')];
        if (!det || !det.html || !x.clientWidth) return;
        var b = board.budget, n = 0, most = 7.6 * (parseFloat(getComputedStyle(x).fontSize) || 16);
        while ((x.offsetHeight > most || x.scrollWidth > x.clientWidth + 1) && n < 6) {
          b = Math.round(b * 0.8); n++;
          var ex = excerpt(det.html, b);
          x.innerHTML = ex.html + (ex.cut ? '…' : '');
          katexIn(x, c.getAttribute('data-paper'), di);
        }
      });
    }
    function drawWires() {
      var inEl = boardEl && boardEl.querySelector('[data-u-board-in]'), svg = inEl && inEl.querySelector('[data-u-wires]');
      if (!svg || !board.on) return;
      var base = inEl.getBoundingClientRect();
      var R = function (el) { var b = el.getBoundingClientRect(); return { x0: b.left - base.left, x1: b.right - base.left, y0: b.top - base.top, y1: b.bottom - base.top }; };
      var nf = function (v) { return Math.round(v * 10) / 10; };
      var fpx = parseFloat(getComputedStyle(boardEl).fontSize) || 16;
      var hot = function (keys) { return keys.some(function (k) { return k && (k === sel || k === board.hoverKey); }); };
      var paths = [];
      Array.prototype.forEach.call(inEl.querySelectorAll('.u-col:not([hidden]) li'), function (li) {
        var rc = li.querySelector(':scope > .u-bc--r');
        if (!rc) return;
        var a = R(rc), x = a.x0 + 0.7 * fpx;
        Array.prototype.forEach.call(li.querySelectorAll('.u-leans > .u-bc--l'), function (lc) {
          var b = R(lc), y = (b.y0 + Math.min(b.y1, b.y0 + 2.2 * fpx)) / 2, r = Math.min(6, (b.x0 - x) / 2);
          var keys = [rc.getAttribute('data-bk'), lc.getAttribute('data-bk')];
          paths.push('<path class="w-lean' + (lc.classList.contains('is-cand') ? ' w-cand' : '') + (hot(keys) ? ' is-hot' : '') + '" d="M' + nf(x) + ' ' + nf(a.y1) +
            'V' + nf(y - r) + 'Q' + nf(x) + ' ' + nf(y) + ' ' + nf(x + r) + ' ' + nf(y) + 'H' + nf(b.x0) + '"/>');
        });
      });
      // A neighbouring family's citation runs along one band above the paper columns and
      // drops into each paper that carries it; the band bundles them.
      var papersEl = inEl.querySelector('[data-u-papers]');
      if (papersEl && !narrow()) {
        var pr = R(papersEl), band = pr.y0 + 0.75 * fpx, fb = L.fibres[board.fi] || [], f = D.families[board.fi];
        Array.prototype.forEach.call(inEl.querySelectorAll('.u-bc--f'), function (sc) {
          var g = +sc.getAttribute('data-g'), way = sc.getAttribute('data-way');
          var row = null;
          fb.forEach(function (x) { if (x[1] === g) row = x; });
          var local = row ? (way === 'out' ? row[3] : row[4]) || [] : [];
          if (!local.length) local = [0];
          var s = R(sc), sy = (s.y0 + s.y1) / 2, left = way === 'in';
          local.forEach(function (k) {
            var pi = f.papers[k], col = pi === undefined ? null : papersEl.querySelector('.u-col[data-pi="' + pi + '"]:not([hidden])');
            if (!col) return;
            var pc = R(col.querySelector('.u-bc--p')), dx = 0.75 * fpx;
            var sx = left ? s.x1 : s.x0, px = left ? pc.x0 + 1.1 * fpx : pc.x1 - 1.1 * fpx, sg = left ? 1 : -1, r = 6;
            var keys = [sc.getAttribute('data-bk'), D.papers[pi].id];
            paths.push('<path class="' + (left ? 'w-in' : 'w-out') + (hot(keys) ? ' is-hot' : '') + '" d="M' + nf(sx) + ' ' + nf(sy) +
              'C' + nf(sx + sg * dx) + ' ' + nf(sy) + ' ' + nf(sx + sg * dx) + ' ' + nf(band) + ' ' + nf(sx + sg * 2 * dx) + ' ' + nf(band) +
              'H' + nf(px - sg * r) + 'Q' + nf(px) + ' ' + nf(band) + ' ' + nf(px) + ' ' + nf(band + r) + 'V' + nf(pc.y0) + '"/>');
          });
        });
      }
      svg.setAttribute('width', inEl.scrollWidth); svg.setAttribute('height', inEl.scrollHeight);
      svg.innerHTML = paths.join('');
    }
    function markBoard() {
      if (!boardEl) return;
      var pp = pinnedPair();
      Array.prototype.forEach.call(boardEl.querySelectorAll('[data-bk]'), function (c) {
        var k = c.getAttribute('data-bk');
        c.classList.toggle('is-sel', k === sel);
        c.classList.toggle('is-pair', !!pp && k !== sel && (pp[0] === k || pp[1] === k));
        c.setAttribute('aria-pressed', k === sel ? 'true' : 'false');
      });
    }
    // The page that shows the selection.
    function pageToSelection() {
      var c = sel && boardEl.querySelector('.u-col [data-bk="' + (window.CSS && CSS.escape ? CSS.escape(sel) : sel) + '"]');
      if (!c || !board.per) return;
      var col = c.closest('.u-col'), cols = Array.prototype.slice.call(col.parentNode.children);
      board.page = Math.floor(cols.indexOf(col) / board.per);
    }
    function syncBoard() {
      if (!boardEl || !D) return;
      var fi = boardFamily();
      if (fi < 0) { hideBoard(); return; }
      var f = D.families[fi], di = fams[fi].d;
      if (!shards[di]) loadShard(di).then(syncBoard, syncBoard);
      // The neighbours' titles are typeset from their own disciplines' records.
      var near = f.cites.concat(f.citedBy).map(function (c) { return fams[c[0]].d; });
      var ready = near.filter(function (d2) { return shards[d2]; }).length;
      near.forEach(function (d2) { if (!shards[d2] && !failedShards[d2]) loadShard(d2).then(syncBoard, function () {}); });
      var sig = fi + '|' + (shards[di] ? 1 : 0) + '|' + ready + '|' + board.budget;
      var fresh = board.fi !== fi;
      if (sig !== board.sig) {
        var keepScroll = board.fi === fi ? boardEl.scrollTop : 0;
        if (fresh) board.page = 0;
        board.fi = fi; board.sig = sig;
        boardEl.innerHTML = boardHtml(fi);
        typesetBoard(fi);
        boardEl.scrollTop = keepScroll;
        hideBoardCard();
      }
      markBoard();
      if (!board.on) {
        board.pending = true;
        // From the discipline, the family's disc grows to fill the stage first and the
        // board fades in over it once it settles (stepChart calls showBoard).
        requestAnimationFrame(function () { if (board.pending && !chartAnimating()) showBoard(); });
      }
      if (fresh || !board.on) { layoutPages(); }
      else { pageToSelection(); layoutBoard(); }
      if (ringWanted || ring) board.ringKey = sel;
      ringBoard();
    }
    function layoutPages() { var keep = board.on; board.on = true; layoutBoard(); pageToSelection(); layoutBoard(); board.on = keep; }
    function showBoard() {
      if (!board.pending) return;
      board.pending = false;
      board.on = true;
      root.setAttribute('data-board', '');
      boardEl.classList.add('is-on');
      hover = null; hideCard();
      layoutBoard();
      ringBoard();
    }
    function hideBoard() {
      board.pending = false;
      if (!board.on) { board.fi = -1; board.sig = ''; return; }
      board.on = false; board.fi = -1; board.sig = '';
      boardEl.classList.remove('is-on');
      root.removeAttribute('data-board');
      hideBoardCard();
    }
    // The chosen card gets the selection's one ring, once, when it settles.
    function ringBoard() {
      if (!board.on || !board.ringKey || reduceMotion) { board.ringKey = board.on ? null : board.ringKey; return; }
      var key = board.ringKey;
      board.ringKey = null;
      Array.prototype.forEach.call(boardEl.querySelectorAll('[data-bk]'), function (c) {
        if (c.getAttribute('data-bk') !== key) return;
        c.classList.remove('is-ring'); void c.offsetWidth; c.classList.add('is-ring');
      });
    }
    /* The board's hover card: beside the card pointed at or focused, in the stage, never
       over that card or the selected one, and over as few other cards as it can. It can
       itself be pointed at, and Escape dismisses it. */
    function boardCardHtml(key) {
      var o = obj(key);
      if (!o) return '';
      var di = discOf(o), sh = shards[di], h = '';
      var line = function (cls, html) { h += '<p class="u-card__' + cls + '">' + html + '</p>'; };
      if (o.kind === 'r') {
        var det = sh && sh.results ? sh.results[key] : null;
        h = cardHtml(o);
        if (det && det.html) {
          var ex = excerpt(det.html, 520);
          h = h.replace(/(<p class="u-card__e)/, '<div class="u-card__x" data-paper="' + escapeHtml(D.papers[D.results[o.i].p].id) + '">' + ex.html + (ex.cut ? '…' : '') + '</div>$1');
        }
        return h;
      }
      if (o.kind === 'l') {
        var ld = sh && sh.lean ? sh.lean[key] : null, fdet = sh && sh.families ? sh.families[D.families[D.lean[o.i].f].id] : null;
        h = cardHtml(o);
        if (D.lean[o.i].main) line('n', escapeHtml(T('lean.main')));
        if (ld && ld.pairing && D.lean[o.i].results.length) line('n', escapeHtml(ld.pairing));
        if (fdet && fdet.readers && fdet.readers.length) {
          line('n', '<b>' + escapeHtml(T('board.readers')) + '</b> ' + fdet.readers.map(function (rd) { return escapeHtml(rd.name + ' ' + rd.words + '.'); }).join(' '));
        }
        return h;
      }
      if (o.kind === 'f') {
        var f = D.families[o.i], fd = sh && sh.families ? sh.families[key] : null;
        line('t tex-auto', fd && fd.titleHtml ? fd.titleHtml : escapeHtml(f.title));
        line('k', escapeHtml(T('family.kicker', { num: f.num, discipline: D.disciplines[f.d].name })));
        if (fd && fd.first) line('n', escapeHtml(T('family.catalogue') + ' ' + T('family.catalogue_says')));
        if (fd && fd.first) h += '<div class="u-card__x tex-auto">' + fd.first + '</div>';
        line('e', dot(f.tone) + '<span>' + escapeHtml(T('key.' + f.tone)) + '</span>');
        return h;
      }
      if (o.kind === 'p') {
        var p = D.papers[o.i];
        line('t', escapeHtml(p.title));
        line('k', escapeHtml(T('paper.kicker', { num: D.families[p.f].num }) + (p.date ? ', ' + p.date : '')));
        line('n', escapeHtml(count('results', p.results.length)));
        return h;
      }
      return '';
    }
    function hideBoardCard() {
      clearTimeout(board.hideT);
      if (board.hoverKey) { board.hoverKey = null; if (board.on) drawWires(); }
      if (cardEl) cardEl.classList.remove('is-board');
      hideCard();
    }
    function showBoardCard(el, via) {
      if (!cardEl || !board.on || narrow()) return;
      if (via !== 'focus' && !(hoverMQ && hoverMQ.matches)) return;
      var key = el.getAttribute('data-bk');
      clearTimeout(board.hideT);
      if (board.hoverKey !== key) { board.hoverKey = key; drawWires(); }
      cardEl.classList.add('is-board');
      var ck = 'b:' + key + (shards[discOf(obj(key))] ? '+' : '');
      if (ck !== cardKey) {
        cardEl.innerHTML = boardCardHtml(key);
        var px = cardEl.querySelector('[data-paper]');
        katexIn(cardEl, px ? px.getAttribute('data-paper') : null, discOf(obj(key)));
        cardKey = ck;
      }
      var w = cardEl.offsetWidth, h = cardEl.offsetHeight, sr = stage.getBoundingClientRect();
      var rel = function (n) { var b = n.getBoundingClientRect(); return { x0: b.left - sr.left, x1: b.right - sr.left, y0: b.top - sr.top, y1: b.bottom - sr.top }; };
      var me = rel(el), others = [], keep = [me];
      Array.prototype.forEach.call(boardEl.querySelectorAll('.u-bc'), function (c) {
        if (c === el || c.closest('[hidden]')) return;
        var b = rel(c);
        if (b.y1 < 0 || b.y0 > sr.height) return;
        if (c.classList.contains('is-sel')) keep.push(b); else others.push(b);
      });
      // The eight places beside the card first; failing those, any place in the stage
      // (a 24 px lattice), nearest first, that keeps off the card and the selection.
      var g = 10, spots = [[me.x1 + g, me.y0], [me.x0 - g - w, me.y0], [me.x0, me.y1 + g], [me.x0, me.y0 - g - h],
                           [me.x1 + g, me.y1 - h], [me.x0 - g - w, me.y1 - h], [me.x1 - w, me.y1 + g], [me.x1 - w, me.y0 - g - h]];
      var X1 = Math.max(8, sr.width - w - 8), Y1 = Math.max(8, sr.height - h - 8);
      var best = null, bestScore = Infinity;
      var tryAt = function (sp, i) {
        var x0 = clamp(sp[0], 8, X1), y0 = clamp(sp[1], 8, Y1);
        var b = { x0: x0, x1: x0 + w, y0: y0, y1: y0 + h };
        var gapX = Math.max(0, me.x0 - b.x1, b.x0 - me.x1), gapY = Math.max(0, me.y0 - b.y1, b.y0 - me.y1);
        var score = (sp[2] ? 40 : i * 2) + Math.hypot(gapX, gapY) * 0.8;
        // Over the card itself or the selection only where nothing else is free, and then
        // over as little of them as it can.
        keep.forEach(function (q) { var ov = overlap(b, q); if (ov > 0) score += 1e5 + ov * 20; });
        others.forEach(function (q) { var ov = overlap(b, q); if (ov > 0) score += 400 + ov * 0.02; });
        if (score < bestScore) { bestScore = score; best = b; }
      };
      spots.forEach(tryAt);
      if (bestScore >= 400) for (var gx = 8; gx <= X1; gx += 24) for (var gy = 8; gy <= Y1; gy += 24) tryAt([gx, gy, 1], 0);
      cardBox = best;
      cardEl.style.transform = 'translate(' + Math.round(best.x0) + 'px, ' + Math.round(best.y0) + 'px)';
      if (!cardOn) { cardEl.classList.add('is-on'); cardOn = true; }
    }
    function selectFromBoard(key) {
      if (key !== sel) select(key, { trail: true });
      // On a phone the detail panel is a separate view, so reveal the record
      // that a paper, theorem or Lean card just selected.
      if (narrow() && obj(key) && obj(key).kind !== 'f') {
        showView('list');
        window.scrollTo({ top: 0, behavior: 'auto' });
        focusArrival();
      }
    }
    if (boardEl) {
      boardEl.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var pg = e.target.closest('[data-u-page]');
        if (pg) { board.page += +pg.getAttribute('data-u-page'); hideBoardCard(); layoutBoard(); return; }
        if (e.target.closest('a')) return;
        var c = e.target.closest('[data-bk]');
        if (e.detail > 1) return;
        if (!c) {
          // Empty board space backs out just like empty space between map discs.
          // Restrict this to layout containers so selecting words or using controls
          // cannot accidentally navigate away.
          if (e.target.matches('.u-board, .u-board__in, .u-board__cols, .u-board__main, .u-board__papers, .u-board__side, .u-col, .u-leans')) {
            hideBoardCard();
            if (sel) stepBack();
          }
          return;
        }
        var key = c.getAttribute('data-bk');
        selectFromBoard(key);
      });
      boardEl.addEventListener('dblclick', function (e) {
        if (e.target.closest('a')) return;
        var c = e.target.closest('[data-bk]');
        if (c) openFromBoard(c.getAttribute('data-bk'));
      });
      boardEl.addEventListener('keydown', function (e) {
        var c = e.target && e.target.getAttribute && e.target.getAttribute('data-bk') ? e.target : null;
        if (!c) return;
        var key = c.getAttribute('data-bk');
        if (e.key === 'Enter') { e.preventDefault(); openFromBoard(key); }
        else if (e.key === ' ' || e.key === 'Spacebar') { e.preventDefault(); selectFromBoard(key); }
      });
      boardEl.addEventListener('pointerover', function (e) {
        var c = e.target.closest && e.target.closest('[data-bk]');
        if (c && e.pointerType !== 'touch') showBoardCard(c, 'pointer');
      });
      boardEl.addEventListener('pointerout', function (e) {
        var c = e.target.closest && e.target.closest('[data-bk]');
        if (!c || (e.relatedTarget && (c.contains(e.relatedTarget) || (cardEl && cardEl.contains(e.relatedTarget))))) return;
        clearTimeout(board.hideT);
        board.hideT = setTimeout(hideBoardCard, 160);
      });
      boardEl.addEventListener('focusin', function (e) {
        var c = e.target && e.target.getAttribute && e.target.getAttribute('data-bk') ? e.target : null;
        var visible = false;
        try { visible = !!c && c.matches(':focus-visible'); } catch (err) { visible = false; }
        if (visible) showBoardCard(c, 'focus');
      });
      boardEl.addEventListener('focusout', function () { if (cardEl && cardEl.classList.contains('is-board')) hideBoardCard(); });
      boardEl.addEventListener('scroll', function () { if (cardEl && cardEl.classList.contains('is-board')) hideBoardCard(); }, { passive: true });
      if (cardEl) {
        cardEl.addEventListener('pointerenter', function () { if (cardEl.classList.contains('is-board')) clearTimeout(board.hideT); });
        cardEl.addEventListener('pointerleave', function (e) {
          if (!cardEl.classList.contains('is-board')) return;
          var back = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-bk]');
          if (back && back.getAttribute('data-bk') === board.hoverKey) return;
          board.hideT = setTimeout(hideBoardCard, 160);
        });
        cardEl.addEventListener('click', function () {
          if (!cardEl.classList.contains('is-board') || !board.hoverKey) return;
          var key = board.hoverKey;
          hideBoardCard();
          if (key !== sel) select(key, { trail: true });
        });
      }
      if (window.ResizeObserver) new ResizeObserver(function () { if (board.on) layoutBoard(); }).observe(boardEl);
    }
    function openFromBoard(key) {
      var o = obj(key);
      if (!o) return;
      if (o.kind === 'f') { if (key !== sel) select(key, { trail: true }); return; }
      openPage(o);
    }

    /* ---- Selection, trail and address ------------------------------------- */
    function parentKey(o) {
      if (!o) return null;
      if (o.kind === 'd') return null;
      if (o.kind === 'f') return D.disciplines[fams[o.i].d].id;
      return D.families[famOf(o)].id;
    }
    // The selection lives in the address. A selection the reader makes is a new entry
    // in the history, so Back and Forward walk the same steps; one that follows from
    // the drawing (a zoom settling) or from the history itself replaces it.
    function updateHash(push, leavingY) {
      if (!window.history || !window.history.replaceState) return;
      var base = window.location.pathname + window.location.search;
      var url = sel ? base + '#o=' + encodeURIComponent(sel) : base;
      var view = root.getAttribute('data-view');
      if (url === window.location.pathname + window.location.search + window.location.hash) return;
      if (push && window.history.pushState) {
        // The entry being left keeps how far down the list the reader was, so Back
        // returns them to the same row.
        try { window.history.replaceState({ o: (window.history.state || {}).o || null, y: leavingY || 0, v: view }, ''); } catch (e) { /* the address still works */ }
        window.history.pushState({ o: sel, v: view }, '', url);
      } else window.history.replaceState({ o: sel, v: view }, '', url);
    }
    // The list scrolls inside the panel on a wide screen and with the page on a narrow one.
    function panelScroller() {
      var narrow = window.matchMedia && window.matchMedia('(max-width: 899px)').matches;
      return narrow ? (document.scrollingElement || document.documentElement) : panelBody;
    }
    function scrollPos() { var s = panelScroller(); return s ? s.scrollTop : 0; }
    // A position to restore once the panel holds enough to scroll that far.
    var pendingY = null;
    function restorePending() {
      var s = panelScroller();
      if (pendingY == null || !s) return;
      s.scrollTop = pendingY;
      if (s.scrollTop >= pendingY - 2) pendingY = null;
    }
    // Select an object: its panel, its plate and, where its level asks, a flight.
    function select(key, opts) {
      opts = opts || {};
      if (key && !partsReady && !/^d:/.test(key)) {
        // A family, paper, result or Lean statement opens once the parts are in.
        loadParts().then(function () { select(key, opts); }, function () {});
        return;
      }
      var o = key ? obj(key) : null;
      if (key && !o) return;
      var prev = sel ? obj(sel) : null;
      var leavingY = scrollPos();
      if (!opts.fromHistory) pendingY = null;
      sel = key || null;
      pin = -1;
      hover = null; hoverVia = ''; cardDismissed = null;
      // A discipline the reader chooses gets its ring once the move settles; a step
      // through the history or the first paint gets none.
      var fly = opts.fly !== false;
      ring = null;
      ringWanted = o && o.kind === 'd' && opts.trail && !opts.fromHistory && fly ? key : null;
      if (opts.trail) trail.push({ key: key, prev: prev ? prev.key : null, view: root.getAttribute('data-view') });
      renderPanel(opts.quiet);
      updateHash(!!opts.trail && !opts.fromHistory, leavingY);
      if (o && liveEl) liveEl.textContent = nameOf(o);
      setReading(o);
      chartTo(fly);
    }
    // A theorem or a Lean statement in hand is read: the panel widens to give the
    // mathematics room, and the chart is laid out again in the rest.
    function setReading(o) {
      var reading = !!(o && (o.kind === 'r' || o.kind === 'l'));
      if (root.classList.contains('is-reading') === reading) return false;
      root.classList.toggle('is-reading', reading);
      return resize();
    }
    /* At family depth, a small key names the objects and lines this family's
       map actually draws, in words. */
    function swatch(kind, tone) {
      var c = { dot: '<circle cx="9" cy="7" r="4" class="u-lg-dot u-lg-dot--' + tone + '"/>',
        dia: '<path d="M9 2.2 13.8 7 9 11.8 4.2 7Z" class="u-lg-dia"/>',
        ring: '<path d="M2 11 A8 8 0 0 1 16 11" class="u-lg-ring"/>',
        cand: '<path d="M1 7H17" class="u-lg-line u-lg-line--cand"/>',
        cited: '<path d="M1 7H17" class="u-lg-line"/>',
        out: '<path d="M1 7H17" class="u-lg-cite u-lg-cite--out"/>',
        inn: '<path d="M1 7H17" class="u-lg-cite u-lg-cite--in"/>' }[kind];
      return '<svg viewBox="0 0 18 14" width="18" height="14" aria-hidden="true">' + c + '</svg>';
    }
    function updateLegend(fi) {
      if (!legendEl) return;
      // The family's board explains itself in words; its old key stays closed.
      fi = -1;
      if (fi < 0) { if (!legendEl.hidden) { legendEl.hidden = true; chrome = chromeBoxes(); } return; }
      var f = D.families[fi], rows = [];
      var row = function (k, text, tone) { rows.push('<li>' + swatch(k, tone || f.tone) + '<span>' + escapeHtml(text) + '</span></li>'); };
      row('ring', T('maplegend.paper'));
      row('dot', T('maplegend.result'));
      if (f.lean.length) row('dia', T('maplegend.lean'));
      var st = f.lean.map(function (li) { return D.lean[li].results.length ? D.lean[li].pairing : null; });
      if (st.indexOf('candidate-pairing') >= 0) row('cand', T('maplegend.candidate'));
      if (st.some(function (x) { return x && x !== 'candidate-pairing'; })) row('cited', T('maplegend.cited'));
      if (f.cites.length) row('out', T('maplegend.cites'));
      if (f.citedBy.length) row('inn', T('maplegend.cited_by'));
      legendEl.innerHTML = '<p class="u-maplegend__h">' + escapeHtml(T('maplegend.heading')) + '</p><ul>' + rows.join('') + '</ul>';
      legendEl.hidden = false;
      chrome = chromeBoxes();
    }
    function stepBack() {
      if (trail.length) {
        var last = trail.pop();
        sel = last.prev;
        if (last.view) showView(last.view, true);
        hover = null; hoverVia = ''; ring = null; ringWanted = null; cardDismissed = null;
        renderPanel();
        updateHash();
        setReading(sel ? obj(sel) : null);
        chartTo(true);
        return;
      }
      if (sel) select(parentKey(obj(sel)), {});
    }
    function openPage(o) {
      if (!o) return;
      var href = null;
      if (o.kind === 'f') href = D.families[o.i].href;
      else if (o.kind === 'p') href = D.papers[o.i].href || D.papers[o.i].pdf;
      else if (o.kind === 'r') href = D.results[o.i].href || D.papers[D.results[o.i].p].href || D.papers[D.results[o.i].p].pdf;
      else if (o.kind === 'l') href = D.lean[o.i].href;
      if (href) window.location.href = href;
    }

    /* ---- Panel ------------------------------------------------------------ */
    function goBtn(key, inner, cls) {
      return '<button type="button" class="u-go ' + (cls || '') + '" data-go="' + escapeHtml(key) + '">' + inner + '</button>';
    }
    function trailHtml() {
      var o = sel ? obj(sel) : null, items = [];
      var chain = [];
      for (var c = o; c; c = obj(parentKey(c))) chain.unshift(c);
      if (!o) return '';
      items.push(goBtn('', escapeHtml(T('levels.release')), 'u-crumb'));
      chain.forEach(function (c, i) {
        var label = c.kind === 'f' ? D.families[c.i].title : c.kind === 'd' ? D.disciplines[c.i].name :
          c.kind === 'r' ? resultName(D.results[c.i]) : c.kind === 'l' ? D.lean[c.i].name : T('levels.paper');
        if (i < chain.length - 1) items.push(goBtn(c.key, escapeHtml(label), 'u-crumb'));
      });
      return items.join('<span class="u-crumb-sep" aria-hidden="true">/</span>');
    }
    function scopeName(o) {
      if (!o) return '';
      return o.kind === 'd' ? D.disciplines[o.i].name : D.families[famOf(o)].title;
    }
    // The words standing with the drawing: what it shows and what choosing does.
    function updateCap(o) {
      if (!capEl) return;
      if (!o) capEl.textContent = T('chart.release_cap', { families: D.families.length, disciplines: D.disciplines.length });
      else if (o.kind === 'd') capEl.textContent = T('chart.disc_cap', { name: D.disciplines[o.i].name, counts: discCounts(D.disciplines[o.i]) });
    }
    function updateFit() {
      var b = root.querySelector('[data-u-zoom="fit"]');
      if (!b) return;
      var o = sel ? obj(sel) : null, label = o ? T('controls.fit_scope', { name: scopeName(o) }) : T('controls.fit');
      b.setAttribute('aria-label', label); b.setAttribute('title', label);
    }
    // The panel's new content rises 6 px into place when the selection changes: never on
    // the first paint, and never when the same selection is drawn again as data arrives.
    var panelKey = null;
    [titleEl, viewEl].forEach(function (el) {
      if (el) el.addEventListener('animationend', function (e) { if (e.target === el) el.classList.remove('is-arriving'); });
    });
    function arrive(els) {
      if (reduceMotion) return;
      els.forEach(function (el) {
        if (!el) return;
        el.classList.remove('is-arriving');
        void el.offsetWidth;
        el.classList.add('is-arriving');
      });
    }
    function renderPanel(quiet) {
      if (!viewEl) return;
      var o = sel ? obj(sel) : null;
      var changed = panelKey !== null && panelKey !== (sel || '');
      var listSwitch = root.querySelector('[data-u-show="list"]');
      if (listSwitch) listSwitch.textContent = T(o && o.kind !== 'd' ? 'switch.details' : 'switch.list');
      panelKey = sel || '';
      updateFit();
      updateMapKey();
      updateCap(o);
      updateLegend(o && o.kind !== 'd' ? famOf(o) : -1);
      if (trailEl) trailEl.innerHTML = trailHtml();
      if (trailEl) trailEl.hidden = !o;
      var groundEl = root.querySelector('[data-u-ground]');
      if (groundEl) groundEl.hidden = !!o;
      var html = '';
      if (!o) html = releaseHtml();
      else if (o.kind === 'd') html = disciplineHtml(o.i);
      else if (o.kind === 'f') html = familyHtml(o.i);
      else if (o.kind === 'p') html = paperHtml(o.i);
      else if (o.kind === 'r') html = resultHtml(o.i);
      else if (o.kind === 'l') html = leanHtml(o.i);
      syncBoard();
      if (titleEl) titleEl.textContent = o ? nameOf(o) : T('page.title');
      if (titleEl) titleEl.className = 'u-title' + (o && o.kind === 'l' ? ' u-title--code' : '') + (o ? ' u-title--deep' : '');
      viewEl.innerHTML = html;
      if (panelBody) panelBody.scrollTop = 0;
      typeset(viewEl, o);
      restorePending();
      if (changed && !quiet) arrive([titleEl, viewEl]);
      if (o) {
        var di = discOf(o);
        if (di >= 0 && !shards[di]) {
          var again = function () { if (sel === (o && o.key)) { viewEl.innerHTML = rerender(o); typeset(viewEl, o); restorePending(); } };
          loadShard(di).then(again, again);
        }
      }
    }
    function rerender(o) {
      if (o.kind === 'f') return familyHtml(o.i);
      if (o.kind === 'r') return resultHtml(o.i);
      if (o.kind === 'l') return leanHtml(o.i);
      if (o.kind === 'p') return paperHtml(o.i);
      if (o.kind === 'd') return disciplineHtml(o.i);
      return releaseHtml();
    }
    function loadShard(di) {
      if (shards[di]) return Promise.resolve(shards[di]);
      if (shardLoading[di]) return shardLoading[di];
      var url = root.getAttribute('data-universe-detail').replace('{d}', di);
      shardLoading[di] = fetchJson(url).then(function (sh) {
        if (sh.generation_id !== D.generation_id) throw new Error('detail from another build');
        shards[di] = sh;
        return sh;
      }, function (err) { shardLoading[di] = null; failedShards[di] = true; throw err; });
      return shardLoading[di];
    }
    function detail(o) {
      var sh = shards[discOf(o)];
      if (!sh) return null;
      if (o.kind === 'r') return sh.results[o.key];
      if (o.kind === 'l') return sh.lean[o.key];
      if (o.kind === 'f') return sh.families[o.key];
      return null;
    }
    function typeset(el, o) {
      if (!window.katex) { if (window.atlasRenderMath) window.atlasRenderMath(el); return; }
      var macros = {}, k;
      for (k in GLOBAL_MACROS) macros[k] = GLOBAL_MACROS[k];
      var sh = o ? shards[discOf(o)] : null;
      if (sh && o.kind === 'r') {
        var own = sh.macros[D.papers[D.results[o.i].p].id] || {};
        for (k in own) {
          var v = own[k];
          if (typeof v === 'string' && !/\\(?:newcommand|def|let|ifx|ifmmode|csname|expandafter)/.test(v)) macros[k] = v;
        }
      }
      var spans = el.querySelectorAll('span.m:not([data-done])');
      for (var i = 0; i < spans.length; i++) {
        var s = spans[i], tex = s.textContent;
        s.setAttribute('data-done', '1');
        try {
          // A short inline formula stays on one line (atlas.js keepShort).
          var display = s.getAttribute('data-d') === '1';
          var src = !display && window.atlasKeepShortMath ? window.atlasKeepShortMath(tex) : tex;
          window.katex.render(src, s, { displayMode: display, macros: macros, throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
        } catch (err) { s.textContent = tex; s.classList.add('m-fail'); }
      }
      if (window.atlasRenderMath) window.atlasRenderMath(el);
    }
    function releaseHtml() { return restViewHtml; }
    function dot(tone) { return '<span class="u-dot u-dot--' + escapeHtml(tone || 'none') + '" aria-hidden="true"></span>'; }
    function link(href, text, cls) {
      if (!href) return '';
      var ext = /^https?:/.test(href);
      return '<a class="u-link' + (ext ? ' ext' : '') + (cls ? ' ' + cls : '') + '" href="' + escapeHtml(href) + '"' + (ext ? ' rel="noopener"' : '') + '>' + escapeHtml(text) + '</a>';
    }
    function door(href, text, primary) {
      if (!href) return '';
      return '<a class="u-btn' + (primary ? ' u-btn--primary' : '') + '" href="' + escapeHtml(href) + '">' + escapeHtml(text) + '</a>';
    }
    function para(text, cls) { return text ? '<p class="' + (cls || 'u-note') + '">' + escapeHtml(text) + '</p>' : ''; }
    function plural(n, one, many) { return n === 1 ? T(one) : T(many, { n: n }); }
    function loadingHtml(di, waiting, failed) {
      return '<p class="u-note" data-u-loading>' + escapeHtml(failedShards[di] ? T(failed) : T(waiting)) + '</p>';
    }
    var failedShards = {};

    /* A discipline: its families as plain entries a person can read. */
    function statusLine(f) {
      return T('key.' + f.tone) + (f.lean.length ? '. ' + count('lean', f.lean.length) : '') + '.';
    }
    function entryHtml(fi) {
      var f = D.families[fi], det = detail(obj(f.id));
      return '<li><a class="u-entry" href="' + escapeHtml(f.href) + '" data-go="' + escapeHtml(f.id) + '">' +
        '<span class="u-entry__t">' + dot(f.tone) + '<span class="tex-auto">' + (det ? det.titleHtml : escapeHtml(f.title)) + '</span></span>' +
        '<span class="u-entry__s">' + escapeHtml(statusLine(f)) + '</span>' +
        (det ? '<span class="u-entry__more">' +
          (det.first ? '<span class="u-entry__c"><span class="u-role">' + escapeHtml(T('family.catalogue')) + '</span> <span class="tex-auto">' + det.first + '</span></span>' : '') +
          '<span class="u-entry__e">' + escapeHtml(det.evidence) + '</span></span>' : '') + '</a></li>';
    }
    // The entry for the family under the pointer on the map opens to its synopsis;
    // pointing within the list only highlights, so the list never moves under the pointer.
    function syncActive() {
      if (!viewEl) return;
      if (typeof updateMapKey === 'function' && mapKeyEl && !mapKeyEl.hidden) updateMapKey();
      var hk = hover ? obj(hover) : null, fk = hk ? D.families[famOf(hk)] : null;
      Array.prototype.forEach.call(viewEl.querySelectorAll('.u-entry'), function (e) {
        e.classList.toggle('is-active', !!fk && e.getAttribute('data-go') === fk.id);
      });
    }
    function disciplineHtml(di) {
      var d = D.disciplines[di];
      var h = para(T('discipline.lede', { counts: discCounts(d) }), 'u-facts');
      if (!shards[di]) h += loadingHtml(di, 'discipline.loading', 'discipline.failed');
      h += '<ul class="u-entries">' + d.families.map(entryHtml).join('') + '</ul>';
      return h;
    }

    /* A family: what it claims, what its Lean states and who checked it, then its parts. */
    function readersHtml(det) {
      if (!det || !det.readers || !det.readers.length) return '';
      return '<ul class="u-readers">' + det.readers.map(function (rd) {
        var who = rd.url ? '<a class="ext" href="' + escapeHtml(rd.url) + '" rel="noopener">' + escapeHtml(rd.name) + '</a>' : escapeHtml(rd.name);
        return '<li><p>' + who + ' ' + escapeHtml(rd.words) + '.' +
          (rd.term ? ' <span class="u-term">' + escapeHtml(T('family.reader_term', { term: rd.term })) + '</span>' : '') +
          (rd.rec ? ' ' + link(rd.rec, T('family.record')) : '') + '</p>' +
          (rd.note ? '<p class="u-readers__note">' + escapeHtml(rd.note) + '</p>' : '') + '</li>';
      }).join('') + '</ul>';
    }
    function resultRow(ri) {
      var r = D.results[ri];
      var label = resultName(r) + (r.lean.length ? '' : '');
      return '<li>' + goBtn(r.id, '<span class="u-sub__t">' + escapeHtml(label) + '</span>' +
        (r.lean.length ? '<span class="u-sub__n">' + escapeHtml(r.lean.map(function (li) { return D.lean[li].label; }).join(', ')) + '</span>' : ''), 'u-sub') + '</li>';
    }
    function leanRow(li) {
      var l = D.lean[li], det = detail(obj(l.id));
      return '<li>' + goBtn(l.id, '<span class="u-sub__t">' + escapeHtml(l.label) + '</span><code class="u-sub__n">' + escapeHtml(l.name) + '</code>', 'u-sub') +
        (det ? '<p class="u-sub__w">' + escapeHtml(det.reruns) + '</p>' : '') + '</li>';
    }
    function familyHtml(fi) {
      var f = D.families[fi], det = detail(obj(f.id));
      var h = '<p class="u-kicker">' + escapeHtml(T('family.kicker', { num: f.num, discipline: D.disciplines[f.d].name })) + '</p>';
      if (!det) return h + loadingHtml(f.d, 'discipline.loading', 'discipline.failed');
      h += '<figure class="u-cat"><figcaption>' + link(D.catalogue_url, T('family.catalogue')) + ' ' + escapeHtml(T('family.catalogue_says')) + '</figcaption>' +
        '<blockquote class="tex-auto">' + det.desc + '</blockquote>' +
        (det.descMore ? '<p class="u-cat__more">' + link(f.href + '#h-desc', T('family.catalogue_more')) + '</p>' : '') + '</figure>';
      // "Compare the theorem with its Lean" only when a Lean statement is paired with the
      // candidate theorem; it opens that pairing on the family page.
      var co = det.candidate ? obj(det.candidate) : null, cr = co && co.kind === 'r' ? D.results[co.i] : null;
      h += '<p class="u-doors">' + door(f.href, T('family.page_link'), true) + (cr && cr.lean.length ? door(f.href + '#lean-' + D.lean[cr.lean[0]].name, T('family.compare_link')) : '') + '</p>';
      h += '<h2 class="u-h2">' + escapeHtml(T('family.readers_heading')) + '</h2>';
      h += '<p class="u-tone">' + dot(f.tone) + '<span>' + escapeHtml(det.evidence) + '</span></p>';
      h += readersHtml(det);
      if (f.lean.length) h += para(T('family.readers_scope'));
      h += para(T(det.headline === 'candidate' ? 'family.headline_candidate' : 'family.headline_unresolved'));
      h += '<h2 class="u-h2">' + escapeHtml(T('family.papers_heading')) + '</h2><ol class="u-papers">';
      f.papers.forEach(function (pi, n) {
        var p = D.papers[pi];
        h += '<li>' + goBtn(p.id, '<span class="u-row__t">' + escapeHtml(p.short) + '</span><span class="u-row__n">' +
          escapeHtml([p.date, n === 0 && f.papers.length > 1 ? T('family.lead') : ''].filter(Boolean).join(', ')) + '</span>', 'u-row u-row--paper');
        h += p.results.length ? '<ul class="u-subrows">' + p.results.map(resultRow).join('') + '</ul>' : '';
        h += '</li>';
      });
      h += '</ol>';
      if (f.lean.length) h += '<h2 class="u-h2">' + escapeHtml(T('family.lean_list_heading')) + '</h2><ul class="u-subrows u-subrows--lean">' + f.lean.map(leanRow).join('') + '</ul>';
      var more = [];
      if (det.checks) more.push(det.checks);
      if (det.editions) more.push(plural(det.editions, 'family.editions_one', 'family.editions'));
      if (det.withdrawn) more.push(plural(det.withdrawn, 'family.withdrawn_one', 'family.withdrawn'));
      if (det.explained) more.push(plural(det.explained, 'family.explained_one', 'family.explained'));
      if (det.problems) more.push(plural(det.problems, 'family.problems_one', 'family.problems'));
      if (more.length) h += '<div class="u-more">' + more.map(function (t) { return '<p>' + escapeHtml(t) + '</p>'; }).join('') + '<p>' + link(f.href, T('family.page_link')) + '</p></div>';
      h += '<h2 class="u-h2">' + escapeHtml(T('family.connections_heading')) + '</h2>';
      if (!f.cites.length && !f.citedBy.length) h += para(T('family.no_connections'));
      [['cites', f.cites, 'is-cites'], ['cited_by', f.citedBy, 'is-cited']].forEach(function (part) {
        if (!part[1].length) return;
        h += '<h3 class="u-h3 ' + part[2] + '">' + escapeHtml(T('family.' + part[0])) + '</h3><ul class="u-rows">' + part[1].map(function (c) {
          var g = D.families[c[0]];
          return '<li>' + goBtn(g.id, '<span class="u-row__t">' + dot(g.tone) + escapeHtml(g.title) + '</span><span class="u-row__n">' + escapeHtml(count('links', c[1])) + '</span>', 'u-row') + '</li>';
        }).join('') + '</ul>';
      });
      if (f.cites.length || f.citedBy.length) h += para(T('family.connections_note'));
      return h;
    }
    function paperHtml(pi) {
      var p = D.papers[pi], f = D.families[p.f];
      var h = '<p class="u-kicker">' + escapeHtml(T('paper.kicker', { num: f.num })) + (p.date ? ', ' + escapeHtml(p.date) : '') + '</p>';
      h += '<p class="u-paper-title">' + escapeHtml(p.title) + '</p>';
      h += '<p class="u-doors">' + door(p.href, T('paper.read'), true) + door(p.pdf, T('paper.pdf')) + door(f.href, T('family.page_link')) + '</p>';
      h += '<h2 class="u-h2">' + escapeHtml(T('paper.results_heading')) + '</h2>';
      h += p.results.length ? '<ul class="u-subrows">' + p.results.map(resultRow).join('') + '</ul>' : para(T('family.results_none'));
      return h;
    }

    /* Reported checks, each group its own entry in its own term, after the sentence
       that says what Comparator checked. */
    function checksHtml(ld) {
      var h = '<p class="u-sub__w"><span class="u-role">' + escapeHtml(T('lean.runs_role')) + '</span> ' + escapeHtml(ld.reruns) + '</p>';
      if (ld.runs && ld.runs.length) h += '<ul class="u-runs">' + ld.runs.map(function (x) {
        return '<li>' + escapeHtml(T('lean.source_term', { name: x.who, term: x.term || x.state || '' })) +
          (x.date ? ' <span class="u-nowrap">' + escapeHtml(longDate(x.date)) + '</span>' : '') +
          (x.current ? '' : ' (' + escapeHtml(T('lean.run_not_current')) + ')') + '. ' + link(x.url, T('lean.record')) + '</li>';
      }).join('') + '</ul>';
      return h + '<p class="u-sub__w">' + escapeHtml(T('lean.what_it_checks')) + '</p>';
    }
    // Why a pairing is drawn: a candidate's reason and shared words behind a fold;
    // a citation in the Lean source or a declared binding said plainly.
    function whyHtml(l, ld) {
      var join = '<span class="u-join u-join--' + (l.pairing === 'candidate-pairing' ? 'candidate' : 'cited') + '" aria-hidden="true"></span>';
      if (l.pairing !== 'candidate-pairing') return '<p class="u-sub__w">' + join + escapeHtml(ld.pairing) + '</p>';
      return '<details class="u-why"><summary>' + join + escapeHtml(T('lean.why')) + '</summary><p>' + escapeHtml(ld.pairing) +
        (ld.terms && ld.terms.length ? ' ' + escapeHtml(T('lean.shared_words', { words: ld.terms.join(', ') })) : '') + '</p></details>';
    }
    function pairControl(isShown, idx) {
      return isShown ? '<p class="u-shown">' + escapeHtml(T('lean.shown_pair')) + '</p>'
        : '<p><button type="button" class="u-pairbtn" data-pair="' + idx + '">' + escapeHtml(T('lean.show_pair')) + '</button></p>';
    }
    /* A result: the theorem as printed, the Lean paired with it, and the ways on. */
    function resultHtml(ri) {
      var r = D.results[ri], p = D.papers[r.p], f = D.families[r.f], o = obj(r.id), det = detail(o);
      var h = '<p class="u-context">' + goBtn(p.id, escapeHtml(T('result.in_paper', { paper: p.short })), 'u-inline u-inline--plain') +
        (p.date ? ', <span class="u-nowrap">' + escapeHtml(p.date) + '</span>' : '') + '</p>';
      if (det && det.html) {
        h += '<figure class="u-stmt"><p class="u-stmt__head"><strong>' + escapeHtml(resultName(r)) + '.</strong>' +
          (det.titleHtml ? ' <span class="u-stmt__title">(' + det.titleHtml + ')</span>' : '') + '</p>' +
          '<div class="u-stmt__body">' + det.html + '</div><figcaption class="u-note">' + escapeHtml(det.where) +
          (det.source ? '. ' + link(det.source, T('result.tex_source')) : '') + '</figcaption></figure>';
      } else {
        h += loadingHtml(discOf(o), 'result.loading', 'result.load_failed');
      }
      h += '<p class="u-doors">' + door(r.href || p.href || p.pdf, T('result.read'), true) +
        (r.lean.length ? door(f.href + '#lean-' + D.lean[r.lean[0]].name, T('result.compare')) : '') + door(f.href, T('result.family_page')) + '</p>';
      var states = r.lean.map(function (li) { return D.lean[li].pairing; });
      var kind = function (st) { return st === 'candidate-pairing' ? 'candidate' : st === 'producer-declared-binding' ? 'declared' : 'cited'; };
      var one = states.length && states.every(function (st) { return kind(st) === kind(states[0]); }) ? kind(states[0]) : null;
      h += '<h2 class="u-h2">' + escapeHtml(T(r.lean.length ? (one ? 'result.lean_heading_' + one : 'result.lean_heading_mixed') : 'result.lean_heading_none')) + '</h2>';
      if (one === 'candidate') h += '<p class="u-qual">' + escapeHtml(T('result.lean_sub_candidate')) + '</p>';
      if (r.lean.length) {
        var pp = pinnedPair();
        h += '<ul class="u-subrows u-subrows--lean">' + r.lean.map(function (li) {
          var l = D.lean[li], ld = detail(obj(l.id)), shown = !!pp && pp[1] === l.id;
          return '<li class="' + (shown ? 'is-shown' : '') + '" data-lean-row="' + escapeHtml(l.id) + '">' + goBtn(l.id, '<span class="u-sub__t">' + escapeHtml(l.label) + '</span><code class="u-sub__n">' + escapeHtml(l.name) + '</code>', 'u-sub') +
            (r.lean.length > 1 ? pairControl(shown, li) : '') +
            (ld ? whyHtml(l, ld) +
              (ld.snippet ? '<pre class="lean lean--snippet u-lean"><code>' + ld.snippet + '</code></pre><p class="u-sub__w">' + escapeHtml(T('lean.challenge_note')) + '</p>' : '') +
              checksHtml(ld) : '') + '</li>';
        }).join('') + '</ul>';
      } else h += para(T('result.unpaired'));
      h += para(r.num ? T('result.numbering_note') : r.nn ? T('result.unnumbered') : T('result.number_unavailable'));
      var fd = detail(obj(f.id));
      h += '<h2 class="u-h2">' + escapeHtml(T('family.readers_heading')) + '</h2>';
      h += '<p class="u-tone">' + dot(f.tone) + '<span>' + escapeHtml(fd ? fd.evidence : T('key.' + f.tone) + '.') + '</span></p>';
      h += readersHtml(fd);
      if (f.lean.length) h += para(T('family.readers_scope'));
      h += '<p class="u-note">' + goBtn(f.id, escapeHtml(T('result.whole_family', { name: f.title })), 'u-inline') + '</p>';
      return h;
    }

    /* A Lean statement: what it is, who re-ran it, and the theorem it is paired with. */
    function leanHtml(li) {
      var l = D.lean[li], f = D.families[l.f], det = detail(obj(l.id));
      var h = '<p class="u-kicker">' + escapeHtml(T('lean.kicker', { num: f.num })) + '</p>';
      h += '<p class="u-lean-label"><code>' + escapeHtml(l.name) + '</code></p>';
      if (l.main) h += para(T('lean.main'));
      if (det && det.snippet) h += '<pre class="lean lean--snippet u-lean"><code>' + det.snippet + '</code></pre>' + para(T('lean.challenge_note'));
      h += '<p class="u-doors">' + door(l.href, T('lean.page'), true) + (l.results.length ? door(f.href + '#lean-' + l.name, T('result.compare')) : '') + door(f.href, T('lean.family_page')) + '</p>';
      var lk = l.pairing === 'candidate-pairing' ? 'candidate' : l.pairing === 'producer-declared-binding' ? 'declared' : l.pairing === 'unavailable' ? 'none' : 'cited';
      h += '<h2 class="u-h2">' + escapeHtml(T('lean.paper_heading_' + (l.results.length ? lk : 'none'))) + '</h2>';
      if (l.results.length && lk === 'candidate') h += '<p class="u-qual">' + escapeHtml(T('result.lean_sub_candidate')) + '</p>';
      if (l.results.length) {
        var lp = pinnedPair();
        h += '<ul class="u-subrows">' + l.results.map(function (ri) {
          var shown = !!lp && lp[0] === D.results[ri].id;
          return resultRow(ri).replace(/<\/li>$/, (l.results.length > 1 ? pairControl(shown, ri) : '') + '</li>');
        }).join('') + '</ul>';
        if (det) h += whyHtml(l, det);
      } else h += para(T('lean.paired_none'));
      h += '<h2 class="u-h2">' + escapeHtml(T('lean.reruns_heading')) + '</h2>';
      if (det) {
        h += checksHtml(det);
        if (det.holes.length) h += '<h3 class="u-h3">' + escapeHtml(T('lean.holes_heading')) + '</h3>' + para(T('lean.holes_note')) + '<p>' +
          det.holes.map(function (n) { return '<code>' + escapeHtml(n) + '</code>'; }).join(', ') + '</p>';
      } else h += loadingHtml(discOf(obj(l.id)), 'result.loading', 'result.load_failed');
      return h;
    }

    /* The map key, for the release and a discipline: only the encodings drawn there,
       in words, with citation inks named for the scope in hand. */
    var mapKeyBtn = root.querySelector('[data-u-mapkey]'), mapKeyEl = root.querySelector('[data-u-mapkey-panel]');
    function updateMapKey() {
      if (!mapKeyBtn) return;
      var o = sel ? obj(sel) : null, famState = o && o.kind !== 'd';
      mapKeyBtn.hidden = !!famState;
      if (famState) { mapKeyEl.hidden = true; mapKeyBtn.setAttribute('aria-expanded', 'false'); }
      var rows = ['all', 'part', 'other', 'split', 'none'].map(function (t) {
        return '<li>' + dot(t) + '<span>' + escapeHtml(T('key.' + t)) + '</span></li>';
      }).join('');
      var hk = hover ? obj(hover) : null;
      var inks = o && o.kind === 'd' ? (hk && hk.kind === 'f' ? T('mapkey.fam_inks', { name: D.families[hk.i].title }) : T('mapkey.disc_inks', { name: D.disciplines[o.i].name })) : T('mapkey.release_inks');
      mapKeyEl.innerHTML = '<p class="u-mapkey__p">' + escapeHtml(T('mapkey.colour')) + '</p><ul>' + rows + '</ul>' +
        '<p class="u-mapkey__p">' + escapeHtml(T('mapkey.size')) + '</p>' +
        '<p class="u-mapkey__p"><span class="u-arrow" aria-hidden="true"></span>' + escapeHtml(T('mapkey.arrow')) + ' ' + escapeHtml(inks) + '</p>';
    }
    // Pointing at the button previews the key; clicking pins it open; Escape or a second
    // click closes it. The open key can itself be pointed at.
    var mapKeyPinned = false, mapKeyTimer = 0;
    function showMapKey(open) {
      if (!mapKeyEl || mapKeyEl.hidden === !open) return;
      if (open) updateMapKey();
      mapKeyEl.hidden = !open;
      mapKeyBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      chrome = chromeBoxes(); draw();
    }
    if (mapKeyBtn) {
      mapKeyBtn.addEventListener('click', function () { mapKeyPinned = !mapKeyPinned || mapKeyEl.hidden; showMapKey(mapKeyPinned); });
      [mapKeyBtn, mapKeyEl].forEach(function (el) {
        el.addEventListener('pointerenter', function () { clearTimeout(mapKeyTimer); showMapKey(true); });
        el.addEventListener('pointerleave', function () { mapKeyTimer = setTimeout(function () { if (!mapKeyPinned) showMapKey(false); }, 250); });
      });
    }
    /* ---- Search ----------------------------------------------------------- */
    function loadSearch() {
      if (searchRows) return Promise.resolve(searchRows);
      if (searchLoading) return searchLoading;
      resultsEl.hidden = false;
      resultsEl.innerHTML = '<p class="u-note">' + escapeHtml(T('search.loading')) + '</p>';
      searchLoading = fetchJson(root.getAttribute('data-universe-search')).then(function (s) {
        if (s.generation_id !== D.generation_id) throw new Error('search from another build');
        searchRows = s.rows;
        return searchRows;
      }, function (err) {
        searchLoading = null;
        resultsEl.innerHTML = '<p class="u-note">' + escapeHtml(T('search.failed')) + '</p>';
        throw err;
      });
      return searchLoading;
    }
    var matchList = [];
    var searchFolded = false;   // the reader opened a match and folded the list away
    function runSearch() {
      // Pass the typed query to the site's search; only the map's matching is lower case.
      var raw = (searchIn.value || '').trim();
      var q = raw.toLowerCase();
      query = q;
      if (resultsEl) resultsEl.classList.remove('is-folded');
      searchFolded = false;
      if (!q) {
        matches = null; matchFam = null; matchList = [];
        resultsEl.hidden = true; resultsEl.innerHTML = '';
        draw();
        return Promise.resolve([]);
      }
      // The site's own search (assets/atlas.js) answers when it is on the page: its
      // hits light their families here and list beside the map. The map's own rows
      // stand in until it is.
      if (window.AtlasSearch && typeof window.AtlasSearch.query === 'function') {
        return Promise.resolve(window.AtlasSearch.query(raw)).then(function (hits) {
          if (query !== q) return;
          hits = hits || [];
          // Disciplines, families, papers and Lean statements before the paper
          // statements that mention the words; within a kind, an entry whose own name
          // holds every word comes first (the search dialog orders its groups so).
          // Accents folded on both sides, so "erdos" ranks the Erdős families as "Erdős" does.
          var fold = function (list) { return list.map(function (t) { return String(t).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }); };
          var toks = window.AtlasSearch.tokens ? fold(window.AtlasSearch.tokens(q)) : [];
          var order = { discipline: 0, family: 1, manuscript: 2, lean: 3, statement: 4 };
          hits = hits.map(function (h, i) {
            var own = toks.length ? fold(window.AtlasSearch.tokens(h.name || '')) : [];
            var named = toks.every(function (t) { return own.indexOf(t) >= 0; });
            return { h: h, i: i, k: order[h.kind] != null ? order[h.kind] : 5, n: named ? 0 : 1 };
          }).sort(function (a, b) { return a.k - b.k || a.n - b.n || a.i - b.i; }).map(function (x) { return x.h; });
          matches = {}; matchFam = {}; matchList = [];
          hits.forEach(function (hit) {
            if (obj(hit.id)) { matches[hit.id] = true; matchList.push(hit.id); }
            (hit.family_ids || []).forEach(function (fid) { var fo = obj(fid); if (fo) matchFam[fo.i] = true; });
            var own = obj(hit.id), f = famOf(own);
            if (f >= 0) matchFam[f] = true;
          });
          var shown = hits.slice(0, 60);
          var kindKey = { manuscript: 'paper' };
          var kindWord = function (k) { var key = 'search.kind_' + (kindKey[k] || k); return T(key) !== key ? T(key) : k; };
          // A name is the paper's own text: its TeX dashes become dashes outside $...$,
          // and its mathematics is typeset below.
          var words = function (s) {
            return String(s || '').split(/(\$[^$]*\$)/).map(function (part, j) {
              return j % 2 ? part : part.replace(/---/g, '—').replace(/--/g, '–');
            }).join('');
          };
          var head = hits.length ? (hits.length === 1 ? T('search.count_one') : T('search.count', { n: hits.length })) : T('search.none');
          if (hits.length > shown.length) head += ' ' + T('search.shown', { shown: shown.length });
          resultsEl.hidden = false;
          resultsEl.innerHTML = '<p class="u-note" role="status">' + escapeHtml(head) + '</p><ul class="u-rows">' + shown.map(function (hit) {
            // A statement with no title of its own is named by its label in the
            // index ("thm:main"); the map names it as its paper prints it.
            var own = obj(hit.id);
            var AS = window.AtlasSearch, isLabel = /^[A-Za-z]+:\S*$/.test(hit.name || '');
            var nameHtml = own && hit.kind === 'statement' && isLabel ? escapeHtml(nameOf(own))
              : isLabel && AS.statementName ? escapeHtml(AS.statementName(hit.name))
              : AS.richName ? AS.richName(hit.name) : escapeHtml(words(hit.name));
            var inner = '<span class="u-row__k">' + escapeHtml(kindWord(hit.kind)) + '</span><span class="u-row__t md-math">' + nameHtml + '</span>';
            var fo = obj((hit.family_ids || [])[0]);
            if (own && own.kind === 'd') inner += '<span class="u-row__n">' + escapeHtml(discCounts(D.disciplines[own.i])) + '</span>';
            // A family's row names its discipline; any other row names its family.
            else if (fo && hit.kind === 'family') inner += '<span class="u-row__n">' + escapeHtml(T('family.short', { num: D.families[fo.i].num }) + ', ' + D.disciplines[D.families[fo.i].d].name) + '</span>';
            else if (fo) inner += '<span class="u-row__n">' + escapeHtml(T('family.short', { num: D.families[fo.i].num }) + ', ' + D.families[fo.i].title) + '</span>';
            if (obj(hit.id)) return '<li>' + goBtn(hit.id, inner, 'u-row u-row--hit') + '</li>';
            return '<li><a class="u-row u-row--hit" href="' + escapeHtml(hit.url) + '">' + inner + '</a></li>';
          }).join('') + '</ul>';
          if (window.atlasRenderMath) window.atlasRenderMath(resultsEl);
          draw();
          return matchList;
        }, function () {});
      }
      return loadSearch().then(function (rows) {
        if (query !== q) return;
        var words = q.split(/\s+/).filter(Boolean);
        var found = [];
        rows.forEach(function (row) {
          for (var i = 0; i < words.length; i++) if (row[1].indexOf(words[i]) < 0) return;
          found.push(row[0]);
        });
        var rank = { f: 0, r: 1, l: 2, p: 3 };
        found.sort(function (a, b) { return rank[a[0]] - rank[b[0]]; });
        matchList = found;
        matches = {}; matchFam = {};
        found.forEach(function (key) {
          matches[key] = true;
          var o = obj(key), f = famOf(o);
          if (f >= 0) matchFam[f] = true;
        });
        var shown = found.slice(0, 60);
        var kindWord = { f: T('search.kind_family'), p: T('search.kind_paper'), r: T('search.kind_result'), l: T('search.kind_lean') };
        var head = found.length ? (found.length === 1 ? T('search.count_one') : T('search.count', { n: found.length })) : T('search.none');
        if (found.length > shown.length) head += ' ' + T('search.shown', { shown: shown.length });
        resultsEl.hidden = false;
        resultsEl.innerHTML = '<p class="u-note" role="status">' + escapeHtml(head) + '</p><ul class="u-rows">' + shown.map(function (key) {
          var o = obj(key), f = famOf(o);
          var where = f >= 0 && o.kind !== 'f' ? T('family.short', { num: D.families[f].num }) + ', ' + D.families[f].title : D.disciplines[discOf(o)].name;
          return '<li>' + goBtn(key, '<span class="u-row__k">' + escapeHtml(kindWord[o.kind]) + '</span><span class="u-row__t">' + escapeHtml(nameOf(o)) +
            '</span><span class="u-row__n">' + escapeHtml(where) + '</span>', 'u-row u-row--hit') + '</li>';
        }).join('') + '</ul>';
        draw();
        return matchList;
      }, function () {});
    }

    /* ---- Events --------------------------------------------------------- */
    var lastPointerType = '';
    function localXY(e) { var r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    canvas.addEventListener('pointermove', function (e) {
      var p = localXY(e), h = hitAt(p[0], p[1]);
      if (h === hover) return;
      // On the way from the object to its card the pointer may cross the ground or the
      // edge of a neighbour: inside the box spanning both, the card stays.
      if (cardOn && cardBox && hoverVia === 'map' && cardFor && cardFor.key === hover && hover) {
        var hb = hoverBox(obj(hover));
        if (hb && p[0] >= Math.min(hb.x0, cardBox.x0) && p[0] <= Math.max(hb.x1, cardBox.x1) &&
            p[1] >= Math.min(hb.y0, cardBox.y0) && p[1] <= Math.max(hb.y1, cardBox.y1) &&
            (p[0] - (hb.x0 + hb.x1) / 2) * ((cardBox.x0 + cardBox.x1) / 2 - (hb.x0 + hb.x1) / 2) +
            (p[1] - (hb.y0 + hb.y1) / 2) * ((cardBox.y0 + cardBox.y1) / 2 - (hb.y0 + hb.y1) / 2) > 0) return;
      }
      hover = h; hoverVia = e.pointerType === 'touch' ? 'touch' : 'map'; cardPtr = p;
      if (h !== cardDismissed) cardDismissed = null;
      canvas.classList.toggle('is-over', !!h);
      syncActive();
      if (sel && obj(sel) && obj(sel).kind === 'd' && mapKeyEl && !mapKeyEl.hidden) updateMapKey();
      draw();
    });
    canvas.addEventListener('pointerleave', function (e) {
      if (e.relatedTarget && cardEl && cardEl.contains(e.relatedTarget)) return;
      cardPtr = null;
      if (hover && hoverVia !== 'list' && hoverVia !== 'focus') { hover = null; hoverVia = ''; canvas.classList.remove('is-over'); syncActive(); draw(); }
    });
    canvas.addEventListener('pointerdown', function (e) { lastPointerType = e.pointerType || ''; });
    canvas.addEventListener('click', function (e) {
      var p = localXY(e), key = hitAt(p[0], p[1]);
      if (!key) { if (sel) stepBack(); return; }
      if (key === sel) return;
      select(key, { trail: true });
    });
    if (cardEl) {
      cardEl.addEventListener('pointerleave', function (e) {
        if (cardEl.classList.contains('is-board')) return;
        if (e.relatedTarget === canvas) return;
        if (hover && hoverVia === 'map') { hover = null; hoverVia = ''; syncActive(); draw(); }
      });
      cardEl.addEventListener('click', function () {
        if (cardEl.classList.contains('is-board') || !hover) return;
        var key = hover;
        hover = null; hoverVia = '';
        if (key !== sel) select(key, { trail: true });
      });
    }
    document.addEventListener('click', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      if (!go || !D) return;
      if (e.defaultPrevented || e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var key = go.getAttribute('data-go');
      if (key && !obj(key)) return;
      e.preventDefault();
      var outside = !root.contains(go);
      var narrow = window.matchMedia && window.matchMedia('(max-width: 899px)').matches;
      // A way in chosen from beside or below the map brings the map into view: the
      // map's own side of the switch on a phone, the top of the page elsewhere.
      if (key && (outside || go.classList.contains('u-way')) && narrow) showView('map');
      // The map is the page's first screen: going back up to it shows the header too.
      if (outside) window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
      var fromResults = !!(resultsEl && resultsEl.contains(go));
      var byKey = e.detail === 0 && root.contains(go) && !fromResults;
      select(key || null, { trail: true });
      // A match opened from the search folds the list of matches away, so what was
      // opened starts at the top of the panel; one button brings the matches back.
      if (fromResults) foldResults(true);
      // A row opened from the keyboard was redrawn away: focus goes to what replaced it,
      // the family's board on a wide screen, else the panel's heading.
      if (byKey) focusArrival();
    });
    function focusArrival() {
      var target = board.on || board.pending ? (narrow() ? null : boardEl) : null;
      if (!target) target = titleEl;
      if (!target) return;
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
      try { target.focus({ preventScroll: narrow() }); } catch (err) { target.focus(); }
    }
    function foldResults(fold) {
      if (!resultsEl || resultsEl.hidden) return;
      resultsEl.classList.toggle('is-folded', fold);
      searchFolded = !!fold;
      draw();
      var b = resultsEl.querySelector('[data-u-unfold]');
      if (fold && !b) {
        b = document.createElement('button');
        b.type = 'button';
        b.className = 'u-unfold';
        b.setAttribute('data-u-unfold', '');
        b.textContent = T('search.show_again');
        b.addEventListener('click', function () { foldResults(false); });
        resultsEl.insertBefore(b, resultsEl.firstChild);
      }
    }
    // Choosing which recorded pair the map traces: the reader and the map follow, the
    // camera stays where it is.
    root.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-pair]') : null;
      if (!b) return;
      e.preventDefault();
      pin = parseInt(b.getAttribute('data-pair'), 10);
      var top = panelBody ? panelBody.scrollTop : 0;
      var o = sel ? obj(sel) : null;
      if (o) { viewEl.innerHTML = rerender(o); typeset(viewEl, o); }
      if (panelBody) panelBody.scrollTop = top;
      if (board.on) { markBoard(); drawWires(); }
      draw();
    });
    // A row under the pointer in the panel lights its place on the map.
    root.addEventListener('pointerover', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      var key = go ? go.getAttribute('data-go') : null;
      if (go && panelBody && panelBody.contains(go) && key && key !== hover) {
        hover = key; hoverVia = e.pointerType === 'touch' ? 'touch' : 'list'; cardPtr = null; draw();
      }
    });
    root.addEventListener('pointerout', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      if (go && panelBody && panelBody.contains(go) && hover === go.getAttribute('data-go')) { hover = null; hoverVia = ''; draw(); }
    });
    // A row reached by the keyboard lights its place on the map and names it there too.
    root.addEventListener('focusin', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      var key = go ? go.getAttribute('data-go') : null;
      var visible = false;
      try { visible = go && go.matches(':focus-visible'); } catch (err) { visible = false; }
      if (go && visible && panelBody && panelBody.contains(go) && key && obj(key)) { hover = key; hoverVia = 'focus'; cardPtr = null; draw(); }
    });
    root.addEventListener('focusout', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      if (go && hoverVia === 'focus' && hover === go.getAttribute('data-go')) { hover = null; hoverVia = ''; draw(); }
    });
    function showView(v, restoring) {
      root.setAttribute('data-view', v);
      root.querySelectorAll('[data-u-show]').forEach(function (x) { x.setAttribute('aria-pressed', x.getAttribute('data-u-show') === v ? 'true' : 'false'); });
      if (!restoring && window.history && window.history.replaceState) {
        try { window.history.replaceState(Object.assign({}, window.history.state, { v: v }), ''); } catch (e) { /* the view still switches */ }
      }
      if (v === 'map') { resize(); draw(); }
    }
    root.querySelectorAll('[data-u-show]').forEach(function (b) {
      b.addEventListener('click', function () { showView(b.getAttribute('data-u-show')); });
    });
    if (searchIn) {
      var t = 0;
      searchIn.addEventListener('focus', function () { if (D && !window.AtlasSearch) loadSearch().catch(function () {}); });
      searchIn.addEventListener('input', function () { clearTimeout(t); t = setTimeout(runSearch, 120); });
      searchIn.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          clearTimeout(t);
          var q = (searchIn.value || '').trim().toLowerCase();
          Promise.resolve(runSearch()).then(function () {
            if (query === q && (searchIn.value || '').trim().toLowerCase() === q) {
              // Open the first visible result, including links with no map object.
              // Its normal click handler also selects and folds mapped results.
              var first = resultsEl.querySelector('.u-row--hit');
              if (first) first.click();
            }
          });
        } else if (e.key === 'Escape' && searchIn.value) {
          e.preventDefault(); e.stopPropagation();
          searchIn.value = ''; runSearch();
        }
      });
    }
    document.addEventListener('keydown', function (e) {
      var tag = e.target && e.target.tagName;
      var typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target && e.target.isContentEditable);
      if (e.key === 'Escape') {
        if (document.querySelector('dialog[open], .nav-toggle[aria-expanded="true"]')) return;
        if (cardOn && cardEl && cardEl.classList.contains('is-board')) { e.preventDefault(); hideBoardCard(); return; }
        if (mapKeyEl && !mapKeyEl.hidden) { e.preventDefault(); mapKeyPinned = false; showMapKey(false); mapKeyBtn.focus(); return; }
        // The input clears its query before a later Escape steps out of the map selection.
        if (e.target === searchIn && searchIn.value) return;
        if (cardOn && hover && !cardEl.classList.contains('is-board')) { e.preventDefault(); cardDismissed = hover; hideCard(); return; }
        if (sel) { e.preventDefault(); stepBack(); }
        return;
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === '/' && searchIn && !document.querySelector('dialog[open]')) {
        // The site's own search owns '/' elsewhere; on this page it finds on the map.
        e.preventDefault(); e.stopImmediatePropagation(); searchIn.focus(); searchIn.select(); return;
      }
    }, true);
    window.addEventListener('hashchange', function () {
      var key = readHash();
      if (key !== sel) select(key, { fromHistory: true });
    });
    window.addEventListener('popstate', function (e) {
      var key = readHash();
      var y = e.state && typeof e.state.y === 'number' ? e.state.y : null;
      if (e.state && (e.state.v === 'map' || e.state.v === 'list')) showView(e.state.v, true);
      if (key !== sel) { trail = []; pendingY = y; select(key, { fromHistory: true }); }
      else if (y != null) { pendingY = y; }
      restorePending();
    });
    // Leaving for a paper or a family page, the address's entry keeps the list's place,
    // so coming back finds it.
    window.addEventListener('pagehide', function () {
      try { window.history.replaceState({ o: sel, y: scrollPos(), v: root.getAttribute('data-view') }, ''); } catch (e) { /* nothing to keep */ }
    });
    function readHash() {
      var hash = window.location.hash || '';
      var m = /^#o=(.+)$/.exec(hash);
      if (m) {
        var key;
        try { key = decodeURIComponent(m[1]); } catch (e) { key = null; }
        if (key && (obj(key) || (!partsReady && /^[fprl]:/.test(key)))) return key;
      }
      return oldHash(hash);
    }
    /* The treemap that stood here before (now tiles.html) kept its place as
       #d=<discipline slug>&f=<family id>&o=<lens>. Such a link opens the same
       family, or the discipline, and the address takes the map's own form. */
    function oldHash(hash) {
      if (!/^#(?:[^=&]+=[^&]*&)*(?:d|f)=/.test(hash)) return null;
      var params = {};
      hash.slice(1).split('&').forEach(function (kv) {
        var i = kv.indexOf('='), k = i < 0 ? kv : kv.slice(0, i), v = i < 0 ? '' : kv.slice(i + 1);
        try { params[k] = decodeURIComponent(v.replace(/\+/g, ' ')); } catch (e) { params[k] = v; }
      });
      var key = params.f && obj('f:' + params.f) ? 'f:' + params.f : params.d && obj('d:' + params.d) ? 'd:' + params.d : null;
      if (key && window.history && window.history.replaceState) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search + '#o=' + encodeURIComponent(key));
      }
      return key;
    }
    function onTheme() { parsedColors = {}; readPalette(); draw(); }
    window.addEventListener('atlas-theme', onTheme);
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      if (mq.addEventListener) mq.addEventListener('change', onTheme);
    }
    if (window.ResizeObserver) new ResizeObserver(function () { if (resize()) draw(); }).observe(canvas);
    else window.addEventListener('resize', function () { if (resize()) draw(); });

    /* ---- Start ------------------------------------------------------------ */
    readPalette();
    Promise.all([fetchJson(root.getAttribute('data-universe-data')), fetchJson(root.getAttribute('data-universe-layout'))])
      .then(function (both) {
        validate(both[0], both[1]);
        ingest(both[0], both[1]);
        readFonts();
        var ready = Promise.resolve();
        if (document.fonts && document.fonts.load) {
          ready = Promise.all(['400 13px ', '600 13px ', 'italic 400 12px '].map(function (w) {
            return Promise.all([document.fonts.load(w + SERIF), document.fonts.load(w + SANS)]);
          })).then(function () { return document.fonts.ready; });
        }
        return Promise.race([ready, new Promise(function (r) { setTimeout(r, 1500); })]);
      })
      .then(function () {
        widthCache = {};
        weights();
        W = H = 0;
        var start = readHash();
        // Back from a paper or a family page: the entry remembers the list's place.
        var kept = window.history && window.history.state;
        if (kept && typeof kept.y === 'number') pendingY = kept.y;
        if (kept && (kept.v === 'map' || kept.v === 'list')) showView(kept.v, true);
        if (start && !/^d:/.test(start)) {
          loadParts().then(function () {
            var key = readHash(), o = key ? obj(key) : null;
            if (!o) return;
            select(key, { fly: false, fromHistory: true, quiet: true });
          }, function () {});
          start = null;
        } else {
          var idle = window.requestIdleCallback || function (fn) { return setTimeout(fn, 400); };
          idle(function () { loadParts().catch(function () {}); });
        }
        sel = start;
        renderPanel();
        if (statusEl) statusEl.hidden = true;
        root.classList.add('is-ready');
        resize();
        chartTo(false);
        window.__universe = {
          select: function (key) { select(key, { trail: true }); },
          state: function () { return { sel: sel, level: chart.level, W: W, H: H, trail: trail.length, moving: !!chart.start }; },
          // Where everything stands on the drawing now, for checks.
          chart: function () { return { shown: chart.shown, boxes: chartBoxes, chrome: chrome }; },
          hover: function (key) { hover = key; paint(); },
          // What the motion is doing now, for checks: the ring's age, whether the step
          // back is still easing, and what the card says.
          motion: function () {
            return { ring: ring ? { key: ring.key, age: nowMs() - ring.start } : null, ringWanted: ringWanted,
                     card: cardOn ? cardEl.innerText : null, cardBox: cardOn ? cardBox : null };
          },
          paint: paint
        };
        if (document.fonts && document.fonts.addEventListener) {
          document.fonts.addEventListener('loadingdone', function () { widthCache = {}; labelCache = {}; layoutCache = {}; chartTo(false); });
        }
      })
      .catch(function (err) {
        if (statusEl) { statusEl.hidden = false; statusEl.textContent = T('status.load_failed'); }
        root.classList.add('is-failed');
        if (window.console) console.warn('universe:', err && err.message ? err.message : err);
      });
  }

  function boot() {
    var root = document.querySelector('[data-universe]');
    if (root) mount(root);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
