/* The front door's map of OpenAI's mathematics release, drawn as an illustrated chart:
   the seventeen disciplines as labelled regions holding their families, a discipline
   as its families' discs with their titles written inside. Choosing a family opens its
   own page. Every object a reader can act on is big enough to read and carries its
   name; distance means only grouping.

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
  // A locale formatter is expensive to construct; labels and count templates reuse it.
  var numberFormat = new Intl.NumberFormat('en-GB');
  function fmtNum(n) { return typeof n === 'number' ? numberFormat.format(n) : String(n); }
  function fill(template, vars) {
    return String(template).replace(/\{(\w+)\}/g, function (m, k) {
      return vars && vars[k] != null ? fmtNum(vars[k]) : m;
    });
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
    var stepEl = root.querySelector('[data-u-step]');
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
    function fetchJson(url, cache) {
      return fetch(url, { credentials: 'same-origin', cache: cache || 'default' }).then(function (r) {
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
    var exampleFi = -1;
    function ingest(data, layout) {
      D = data; L = layout;
      D.papers = []; D.results = []; D.lean = [];
      D.disciplines.forEach(function (d, i) { addObj(d.id, 'd', i); });
      D.families.forEach(function (f, i) {
        addObj(f.id, 'f', i);
        if (COPY.example && f.num === COPY.example.family) exampleFi = i;
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
    var partsReady = false, partsPromise = null, partsFailed = false;
    function loadParts() {
      if (partsPromise) return partsPromise;
      partsPromise = fetchJson(root.getAttribute('data-universe-parts'), partsFailed ? 'reload' : 'default').then(function (pt) {
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
      }).catch(function (error) {
        partsFailed = true;
        partsPromise = null;
        throw error;
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
       stage, each with its title written inside. A family opens its own page
       (openPage). Layouts are computed for the stage's own size; when the level
       changes, each disc moves from where it was to where it goes (CHART_MS). */
    var chart = { shown: null, from: null, to: null, start: 0, ms: 0, level: '', di: -1, fi: -1 };
    var layoutCache = {}, labelCache = {};
    var CHART_MS = 280;
    var capEl = root.querySelector('[data-u-cap]'), barEl = root.querySelector('[data-u-bar]');
    function chromeBoxes() {
      var out = [], sr = canvas.getBoundingClientRect();
      [barEl, hoverLineBox()].forEach(function (el) {
        if (!el || el.hidden || !el.offsetParent) return;
        Array.prototype.forEach.call(el === barEl ? el.children : [el], function (c) {
          if (c.hidden || !c.offsetParent) return;
          var b = c.getBoundingClientRect();
          if (b.width && b.height) out.push({ x0: b.left - sr.left - 6, x1: b.right - sr.left + 6, y0: b.top - sr.top - 6, y1: b.bottom - sr.top + 6 });
        });
      });
      return out;
    }
    function hoverLineBox() { return root.querySelector('[data-u-hoverline]'); }
    var chrome = [];
    // The band the bar (Map key and the caption) takes at the top of the stage.
    function topBand() {
      if (!barEl || !barEl.offsetParent) return 12;
      var sr = canvas.getBoundingClientRect(), b = barEl.getBoundingClientRect();
      return Math.max(12, Math.round(b.bottom - sr.top + 10));
    }
    // The band the hover line takes at the bottom of the stage (none where it is hidden).
    function bottomBand() {
      var el = hoverLineBox();
      if (!el || !el.offsetParent) return 12;
      var sr = canvas.getBoundingClientRect(), b = el.getBoundingClientRect();
      return Math.max(12, Math.round(sr.bottom - b.top + 6));
    }
    function resize() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return false; // the list hides the canvas on a phone
      var w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
      var d = Math.min(2, window.devicePixelRatio || 1);
      if (w === W && h === H && d === dpr) return false;
      W = w; H = h; dpr = d;
      // Old viewport layouts and measurements have no further use. In particular,
      // repeated resizing must not retain thousands of obsolete label variants.
      layoutCache = {}; labelCache = {}; widthCache = {};
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
    function packRegions(top, bot) {
      var n = D.disciplines.length, pad = 8, gap = clamp(Math.min(W, H) * 0.012, 6, 14);
      var rho = D.disciplines.map(function (d) { return Math.sqrt(d.families.length + 16); });
      var Hh = H - top - bot, cols = Math.max(1, Math.round(Math.sqrt(n * W / Math.max(1, Hh)))), rows = Math.ceil(n / cols);
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
            P[q].y = clamp(P[q].y, top + R[q], H - bot - R[q]);
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
      var top = topBand(), bot = bottomBand(), key = 'r|' + W + 'x' + H + '|' + top + '|' + bot;
      if (layoutCache[key]) return layoutCache[key];
      var pk = packRegions(top, bot);
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
      var top = topBand(), bot = bottomBand(), key = 'd' + di + '|' + W + 'x' + H + '|' + top + '|' + bot;
      if (layoutCache[key]) return layoutCache[key];
      var base = releaseLayout(), list = D.disciplines[di].families, n = list.length, pad = 12;
      var avail = Math.max(60, H - top - bot);
      var g = discGrid(n, W - 2 * pad, avail);
      var d = g.d, rows = g.rows, c = g.c;
      // Rows spread down the stage (up to a full diameter apart) instead of leaving a band
      // of empty ground above and below the block; any remainder stays at the bottom.
      var step = rows > 1 ? clamp((avail - d) / (rows - 1), d * 0.866, d) : 0;
      var y0 = top + d / 2;
      var nodes = base.nodes.map(function (b) { return { x: b.x, y: b.y, r: b.r, a: 0 }; });
      list.forEach(function (fi, k) {
        var row = Math.floor(k / c), cnt = row < rows - 1 ? c : n - c * (rows - 1), col = k - row * c;
        var rowW = (cnt - 1) * d, off = rows > 1 && row % 2 ? d / 4 : rows > 1 ? -d / 4 : 0;
        var x = W / 2 - rowW / 2 + col * d + off, y = y0 + row * step;
        nodes[fi] = { x: x, y: y, r: d / 2 * 0.94 * (0.86 + 0.14 * famWeight[fi]), a: 1 };
      });
      var regions = base.regions.map(function (r) { return { x: r.x, y: r.y, r: r.r, a: 0, lab: r.lab, ly: r.ly }; });
      return (layoutCache[key] = { level: 'disc', di: di, nodes: nodes, regions: regions });
    }
    // A family in hand (only while the address still names one): its disc fills the stage.
    function famLayout(fi) {
      var b = discLayout(fams[fi].d);
      var nodes = b.nodes.map(function (q, i) { return { x: q.x, y: q.y, r: q.r, a: i === fi ? 1 : 0 }; });
      var top = topBand(), bot = bottomBand();
      nodes[fi] = { x: W / 2, y: (top + H - bot) / 2, r: Math.max(20, Math.min(W, H - top - bot) * 0.46), a: 1 };
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
      var leavingFamily = chart.level === 'fam';
      chart.level = tg.level; chart.di = tg.di; chart.fi = tg.fi;
      // Into or out of a family the map snaps to its finished layout, rather than
      // moving circles under the reader's next click.
      if (!chart.shown || !animate || reduceMotion || same || leavingFamily || tg.level === 'fam') {
        chart.shown = copyLayout(to); chart.to = to; chart.start = 0;
        draw();
        return;
      }
      chart.from = copyLayout(chart.shown); chart.to = to; chart.start = nowMs(); chart.ms = CHART_MS;
      draw();
    }
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
    // ellipsis (the hover caption and the list carry the whole title).
    // Existing compound separators are safe line breaks. A single word wider than
    // the disc is split only as a last resort; its full spelling remains in the sidebar.
    function labelTokens(text, r) {
      var tokens = [], font = '500 11px ' + SERIF;
      var edge = 11 * 1.17 * 0.45, limit = 2 * Math.sqrt(Math.max(0, r * r - edge * edge)) * 0.9 - 6;
      text.split(/\s+/).filter(Boolean).forEach(function (word, wi) {
        var bits = word.match(/[^–-]+[–-]?/g) || [word];
        bits.forEach(function (bit, bi) {
          var join = wi && !bi ? ' ' : '', chars = Array.from(bit);
          while (chars.length && textWidth(chars.join(''), font) > limit) {
            var n = Math.max(1, chars.length - 1);
            while (n > 1 && textWidth(chars.slice(0, n).join('') + '-', font) > limit) n--;
            tokens.push({ text: chars.splice(0, n).join('') + '-', join: join }); join = '';
          }
          if (chars.length) tokens.push({ text: chars.join(''), join: join });
        });
      });
      return tokens;
    }
    function wrapInCircle(tokens, font, lead, r, n, below) {
      // below: the height of a line set under the title (a family's counts), so the
      // title's lines are measured where they will sit once the block is centred.
      var widths = [], memo = {}, top = -(n * lead + (below || 0)) / 2;
      for (var li = 0; li < n; li++) {
        var edge = Math.abs(top + (li + 0.5) * lead) + lead * 0.45;
        if (edge >= r) return null;
        widths.push(2 * Math.sqrt(r * r - edge * edge) * 0.9 - 6);
      }
      // Explore line breaks: a long middle word may fit the broad centre of the
      // circle even when greedily filling the preceding line would strand it.
      function from(line, at) {
        var key = line + ':' + at;
        if (Object.prototype.hasOwnProperty.call(memo, key)) return memo[key];
        var best = line === n - 1 && textWidth('…', font) <= widths[line] ? { lines: ['…'], k: at } : null, text = '';
        for (var end = at; end < tokens.length; end++) {
          text += (end === at ? '' : tokens[end].join) + tokens[end].text;
          if (textWidth(text, font) > widths[line]) break;
          if (line === n - 1) {
            var shown = text + (end + 1 < tokens.length ? '…' : '');
            if (textWidth(shown, font) <= widths[line]) best = { lines: [shown], k: end + 1 };
          } else if (end + 1 < tokens.length) {
            var rest = from(line + 1, end + 1);
            if (rest && (!best || rest.k > best.k)) best = { lines: [text].concat(rest.lines), k: rest.k };
          }
          if (best && best.k === tokens.length) break;
        }
        return (memo[key] = best);
      }
      return from(0, 0);
    }
    function famLabel(fi, r) {
      var cached = labelCache[fi];
      if (cached && cached.r === r) return cached.label;
      var tokens = labelTokens(D.families[fi].title, r), out = null, last = null;
      // Every family disc carries its counts under its title, so the title is fitted
      // with that line's room reserved: the count never drops out on a long title.
      for (var size = clamp(r * 0.18, 11, 17); size >= 10.5 && !out; size = size - 0.5) {
        var font = '500 ' + size.toFixed(1) + 'px ' + SERIF, lead = size * 1.17, below = cntLead(size);
        for (var n = 1; n <= tokens.length && n * lead + below < r * 1.6 && !out; n++) {
          var got = wrapInCircle(tokens, font, lead, r, n, below);
          var label = got && { lines: got.lines, font: font, lead: lead, size: size };
          if (got && got.k === tokens.length) out = label;
          else if (got && (!last || got.k > last.k)) last = { k: got.k, label: label };
        }
        // Always test the readable lower bound, including fractional starting sizes.
        if (!out && size > 10.5 && size < 11) size = 11;
      }
      if (!out && last && last.k) out = last.label;
      if (!out) {
        var first = Array.from(D.families[fi].title), fallbackFont = '500 11px ' + SERIF;
        // (the one-line fallback sits high enough for the count line under it)
        while (first.length > 1 && textWidth(first.join('') + '…', fallbackFont) > r * 1.7 - 6) first.pop();
        out = { lines: [first.join('').trim() + '…'], font: fallbackFont, lead: 13, size: 11 };
      }
      labelCache[fi] = { r: r, label: out };
      return out;
    }
    function cntLead(size) { return clamp(size * 0.78, 10.5, 13) * 1.3; }
    // A family's counts, as short as the disc needs: "3 papers, 2 Lean", then "3 papers".
    function famCounts(f, font, room) {
      var p = count('papers', f.papers.length);
      var full = f.lean.length ? T('counts.disc_lean', { papers: p, n: f.lean.length }) : p;
      return textWidth(full, font) <= room ? full : p;
    }
    function drawText(lines, x, y, font, color, lead, align, halo) {
      ctx.font = font; ctx.textAlign = align || 'center'; ctx.textBaseline = 'middle';
      if (halo) { ctx.lineJoin = 'round'; ctx.lineWidth = 4; ctx.strokeStyle = halo; }
      lines.forEach(function (l, i) {
        if (halo) ctx.strokeText(l, x, y + lead / 2 + i * lead);
        ctx.fillStyle = color; ctx.fillText(l, x, y + lead / 2 + i * lead);
      });
    }
    var chartBoxes = [];          // words and discs on the drawing, for checks (window.__universe)
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
            ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = 1.8 + 0.6 * Math.log(1 + w);
            ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo(mx, my, x1, y1); ctx.stroke();
            var ex = x1 - mx, ey = y1 - my, el = Math.hypot(ex, ey) || 1, hs = 10;
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
        // Context recedes but stays legible: discs drop further than their names, so the
        // next family to visit can still be read while the selection's citations lead.
        if (lvl === 'disc' && hf >= 0 && !near[fi]) a *= 0.32;
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
      // The worked example in the sidebar (π's family) wears one quiet ring, so the
      // sentence "the ringed dot in Number theory" points at something on the drawing.
      if (exampleFi >= 0 && (lvl === 'release' || lvl === 'disc')) {
        var xq = S.nodes[exampleFi];
        if (xq && xq.a > 0.05) {
          ctx.save();
          ctx.globalAlpha = xq.a * (matchFam && !searchFolded && !matchFam[exampleFi] ? 0.22 : 1) * (lvl === 'disc' && hf >= 0 && !near[exampleFi] ? 0.32 : 1);
          ctx.strokeStyle = palette.focus; ctx.lineWidth = lvl === 'release' ? 1.5 : 2;
          ctx.beginPath(); ctx.arc(xq.x, xq.y, xq.r + (lvl === 'release' ? 3.5 : 5), 0, TAU); ctx.stroke();
          ctx.restore();
        }
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
            var t = famLabel(fj, moving ? chart.to.nodes[fj].r : n.r), f2 = fams[fj].data;
            var labelR = moving ? chart.to.nodes[fj].r : n.r;
            // Every disc says how many papers it holds (and Lean statements, when it has
            // any) in the same place: under its title, in the interface face.
            var cfs = clamp(t.size * 0.78, 10.5, 13), cl = cntLead(t.size);
            var cy2 = (t.lines.length * t.lead + cl) / 2, ce = Math.min(cy2, labelR - 2);
            var room = 2 * Math.sqrt(Math.max(0, labelR * labelR - ce * ce)) * 0.92 - 4;
            var cf = '400 ' + cfs.toFixed(1) + 'px ' + SANS;
            var cntText = famCounts(f2, cf, room);
            while (textWidth(cntText, cf) > room && cfs > 9) { cfs -= 0.5; cf = '400 ' + cfs.toFixed(1) + 'px ' + SANS; }
            var showCnt = true;
            var blockH = t.lines.length * t.lead + cl;
            var a2 = n.a * words * (matchFam && !searchFolded && !matchFam[fj] ? 0.3 : 1) * (hf >= 0 && !near[fj] ? 0.55 : 1);
            ctx.save(); ctx.globalAlpha = a2;
            // Fit once at the destination, then scale that fit with the moving disc.
            // Wrapping at every fractional animation radius stalls slower machines.
            ctx.translate(n.x, n.y);
            ctx.scale(n.r / labelR, n.r / labelR);
            drawText(t.lines, 0, -blockH / 2, t.font, palette.ink, t.lead, 'center');
            if (showCnt) drawText([cntText], 0, -blockH / 2 + t.lines.length * t.lead, cf, palette.muted, cl, 'center');
            ctx.restore();
          }
        }
      }
      paintRing();
      // What the pointer names is said in the caption above the drawing, never in a
      // card on it: a floating card covered the very dots the reader was reaching for.
      updateHoverCap();
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
    // Family dots take precedence over their enclosing discipline at the release.
    function hitAt(x, y, allowMoving) {
      var S = chart.shown;
      if (!S || (chart.start && !allowMoving)) return null;
      if (S.level === 'disc' || S.level === 'release') {
        var closest = null, distance = Infinity;
        for (var fi = 0; fi < fams.length; fi++) {
          var q = S.nodes[fi];
          if (!q || q.a < 0.01) continue;
          var d = Math.hypot(x - q.x, y - q.y);
          if (d <= q.r + 2 && d < distance) { closest = D.families[fi].id; distance = d; }
        }
        if (closest || S.level === 'disc') return closest;
      }
      if (S.level === 'release') {
        for (var di = 0; di < S.regions.length; di++) {
          var g = S.regions[di];
          if (Math.hypot(x - g.x, y - g.y) <= g.r) return D.disciplines[di].id;
        }
      }
      return null;
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
    function updateHash(push, leavingY, leavingViews) {
      if (!window.history || !window.history.replaceState) return;
      var base = window.location.pathname + window.location.search;
      var url = sel ? base + '#o=' + encodeURIComponent(sel) : base;
      var view = root.getAttribute('data-view');
      if (url === window.location.pathname + window.location.search + window.location.hash) return;
      var state = window.history.state || {};
      if (push && window.history.pushState) {
        // The entry being left keeps how far down the list the reader was, so Back
        // returns them to the same row.
        var previous = readHash();
        try { window.history.replaceState(Object.assign({}, state, { o: previous, y: leavingY || 0, v: view, ys: leavingViews, sf: searchFolded }), ''); } catch (e) { /* the address still works */ }
        window.history.pushState({ o: sel, uPrev: previous, v: view, ys: phoneViewY, sf: searchFolded }, '', url);
      } else window.history.replaceState(Object.assign({}, state, { o: sel, v: view, ys: phoneViewY, sf: searchFolded }), '', url);
    }
    // The list scrolls inside the panel on a wide screen and with the page on a narrow one.
    function panelScroller() {
      var narrow = window.matchMedia && window.matchMedia('(max-width: 899px)').matches;
      return narrow ? (document.scrollingElement || document.documentElement) : panelBody;
    }
    function scrollPos() { var s = panelScroller(); return s ? s.scrollTop : 0; }
    // The phone's Map and List/Details share a page scroller, but not a reading place.
    var phoneViewY = { map: 0, list: 0 };
    var pendingViewSwitch = null;
    function savedScrollPos() {
      return narrow() && pendingViewSwitch ? phoneViewY[root.getAttribute('data-view')] : scrollPos();
    }
    function viewPositions() {
      var positions = Object.assign({}, phoneViewY);
      if (narrow()) positions[root.getAttribute('data-view')] = savedScrollPos();
      return positions;
    }
    function restoreViewPositions(state) {
      pendingViewSwitch = null;
      phoneViewY = Object.assign({ map: 0, list: 0 }, state && state.ys);
      if (state && !state.ys && (state.v === 'map' || state.v === 'list') && typeof state.y === 'number') phoneViewY[state.v] = state.y;
    }
    // A position to restore once the panel holds enough to scroll that far.
    var pendingY = null;
    function restorePending() {
      var s = panelScroller();
      if (pendingY == null || !s) return;
      if (!narrow() && pendingY > s.scrollHeight - s.clientHeight) reserveEntryTail();
      s.scrollTop = pendingY;
      if (s.scrollTop >= pendingY - 2) pendingY = null;
    }
    // Select an object: its panel, its plate and, where its level asks, a flight.
    var selectionRequest = 0, historyBackPending = null, historySelection = null;
    function select(key, opts) {
      var request = ++selectionRequest;
      opts = opts || {};
      // A browser traversal settles on the next event turn. Keep a click made in
      // that interval, rather than letting the arriving popstate erase it.
      if (historyBackPending && !opts.fromHistory) { historySelection = { key: key, opts: opts }; return; }
      if (key && !partsReady && !/^d:/.test(key)) {
        // A family, paper, result or Lean statement opens once the parts are in.
        var family = obj(key);
        if (family && family.kind === 'f') {
          var earlyDi = discOf(family);
          if (!shards[earlyDi] && !failedShards[earlyDi]) loadShard(earlyDi).catch(function () {});
        }
        if (statusEl) { statusEl.textContent = T('status.parts_loading'); statusEl.hidden = false; }
        loadParts().then(function () {
          if (request === selectionRequest) select(key, opts);
        }, function () {
          if (request === selectionRequest && statusEl) {
            statusEl.textContent = T('status.parts_failed'); statusEl.hidden = false;
          }
        });
        return;
      }
      var o = key ? obj(key) : null;
      if (key && !o) return;
      // Only an explicit selection may retry a failed detail packet; a redraw or a
      // rejected cached promise never starts another request.
      var retryDi = o ? discOf(o) : -1;
      if (retryDi >= 0 && failedShards[retryDi]) loadShard(retryDi).catch(function () {});
      if (statusEl) statusEl.hidden = true;
      var prev = sel ? obj(sel) : null;
      var leavingY = savedScrollPos();
      var leavingViews = viewPositions();
      pendingViewSwitch = null;
      if (!opts.fromHistory) { pendingY = null; restoreViewPositions(); }
      sel = key || null;
      pin = -1;
      hover = null; hoverVia = '';
      // A discipline the reader chooses gets its ring once the move settles; a step
      // through the history or the first paint gets none.
      var fly = opts.fly !== false;
      ring = null;
      ringWanted = o && o.kind === 'd' && opts.trail && !opts.fromHistory && fly ? key : null;
      if (opts.trail) trail.push({ key: key, prev: prev ? prev.key : null, view: root.getAttribute('data-view'), y: leavingY, views: leavingViews });
      setReading(o);
      renderPanel(opts.quiet);
      updateHash(!!opts.trail && !opts.fromHistory, leavingY, leavingViews);
      if (o && liveEl) liveEl.textContent = nameOf(o);
      chartTo(fly);
      // A fresh selection starts with its heading and breadcrumbs visible. The
      // desktop sidebar's scrollIntoView can otherwise leave the whole map cropped.
      // Returning through history keeps the saved reading position.
      if (!opts.fromHistory) window.scrollTo({ top: 0, behavior: 'auto' });
    }
    // A paper, theorem or Lean statement in hand is read: the panel widens to give the
    // mathematics room, and the chart is laid out again in the rest.
    function setReading(o) {
      var reading = !!(o && (o.kind === 'p' || o.kind === 'r' || o.kind === 'l'));
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
      // A family opens its own page, so the family key stays closed.
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
      if (historyBackPending) return;
      if (trail.length) {
        var last = trail[trail.length - 1], state = window.history && window.history.state;
        if (state && state.o === sel && Object.prototype.hasOwnProperty.call(state, 'uPrev') &&
            state.uPrev === last.prev && window.history.back) {
          historyBackPending = { key: last.prev, trail: trail.slice(0, -1) };
          try {
            window.history.replaceState(Object.assign({}, state, { y: savedScrollPos(), v: root.getAttribute('data-view'), ys: viewPositions(), sf: searchFolded }), '');
            window.history.back();
            return;
          } catch (e) { historyBackPending = null; /* an explicit ancestor still works */ }
        }
        var leavingY = savedScrollPos(), leavingViews = viewPositions();
        last = trail.pop();
        sel = last.prev;
        restoreViewPositions({ ys: last.views, v: last.view, y: last.y });
        pendingY = typeof last.y === 'number' ? last.y : null;
        if (last.view) showView(last.view, true);
        hover = null; hoverVia = ''; ring = null; ringWanted = null;
        setReading(sel ? obj(sel) : null);
        renderPanel();
        // A breadcrumb can skip several levels. Its map ancestor is then a new
        // visit, not necessarily the immediately preceding browser entry.
        updateHash(true, leavingY, leavingViews);
        chartTo(true);
        return;
      }
      if (sel) selectAncestor(parentKey(obj(sel)));
    }
    function selectAncestor(key) {
      if (historyBackPending) { historySelection = { key: key, ancestor: true }; return; }
      var saved = null, remaining = [];
      for (var i = trail.length - 1; i >= 0; i--) {
        if (trail[i].prev === key) {
          saved = trail[i];
          if (key) remaining = trail.slice(0, i);
          break;
        }
      }
      // Browser Back still records the click. Escape and blank-map clicks continue
      // out from this ancestor, rather than reopening the child just left.
      select(key, { trail: true });
      trail = remaining;
      if (!saved) return;
      restoreViewPositions({ ys: saved.views, v: saved.view, y: saved.y });
      pendingY = typeof saved.y === 'number' ? saved.y : null;
      if (saved.view) showView(saved.view, true);
      restorePending();
      if (window.history && window.history.replaceState) {
        try { window.history.replaceState(Object.assign({}, window.history.state, { y: saved.y, v: saved.view, ys: phoneViewY }), ''); } catch (e) { /* navigation still works */ }
      }
    }
    function openPage(o, replace) {
      if (!o) return;
      var href = null;
      if (o.kind === 'f') href = D.families[o.i].href;
      else if (o.kind === 'p') href = D.papers[o.i].href || D.papers[o.i].pdf;
      else if (o.kind === 'r') href = D.results[o.i].href || D.papers[D.results[o.i].p].href || D.papers[D.results[o.i].p].pdf;
      else if (o.kind === 'l') href = D.lean[o.i].href;
      if (!href) return;
      if (replace) window.location.replace(href); else window.location.href = href;
    }

    /* ---- Panel ------------------------------------------------------------ */
    function goBtn(key, inner, cls) {
      return '<button type="button" class="u-go ' + (cls || '') + '" data-go="' + escapeHtml(key) + '">' + inner + '</button>';
    }
    // The site's one breadcrumb grammar (build_site.trail): Map / Subject, every crumb a
    // link except the place you are, which is plain text with aria-current.
    function trailHtml() {
      var o = sel ? obj(sel) : null, items = [];
      var chain = [];
      for (var c = o; c; c = obj(parentKey(c))) chain.unshift(c);
      if (!o) return '';
      items.push('<a class="u-crumb" href="index.html" data-go="">' + escapeHtml(T('levels.release')) + '</a>');
      chain.forEach(function (c, i) {
        var label = c.kind === 'f' ? D.families[c.i].title : c.kind === 'd' ? D.disciplines[c.i].name :
          c.kind === 'r' ? resultName(D.results[c.i]) : c.kind === 'l' ? D.lean[c.i].name : T('levels.paper');
        if (i < chain.length - 1) items.push('<a class="u-crumb" href="index.html#o=' + encodeURIComponent(c.key) + '" data-go="' + escapeHtml(c.key) + '">' + escapeHtml(label) + '</a>');
        else items.push('<span aria-current="page">' + escapeHtml(label) + '</span>');
      });
      return items.join(' <span class="trail__sep" aria-hidden="true">/</span>\u2060');
    }
    // The selection's siblings in reading order: fields of the release, families of a
    // field, and a family's papers (oldest first), results and Lean statements.
    function dateValue(s) { var t = s ? Date.parse(s) : NaN; return isFinite(t) ? t : Infinity; }
    function familyPapers(fi) {
      return D.families[fi].papers.slice().sort(function (a, b) { return dateValue(D.papers[a].date) - dateValue(D.papers[b].date) || a - b; });
    }
    function siblings(o) {
      if (!o) return null;
      var all = function (n) { var out = []; for (var i = 0; i < n; i++) out.push(i); return out; };
      if (o.kind === 'd') return { list: all(D.disciplines.length), key: function (i) { return D.disciplines[i].id; }, name: function (i) { return escapeHtml(D.disciplines[i].name); }, pos: 'step.field' };
      if (o.kind === 'f') {
        var d = fams[o.i].d;
        return { list: all(D.families.length).filter(function (i) { return fams[i].d === d; }), key: function (i) { return D.families[i].id; },
          name: function (i) { return escapeHtml(T('family.short', { num: D.families[i].num }) + ': ' + D.families[i].title); }, pos: 'step.family', where: D.disciplines[d].name };
      }
      var fi = famOf(o), papers = familyPapers(fi);
      if (o.kind === 'p') return { list: papers, key: function (i) { return D.papers[i].id; }, name: function (i) { return escapeHtml(D.papers[i].short); }, pos: 'step.paper' };
      if (o.kind === 'r') {
        var rs = [];
        papers.forEach(function (pi) { rs = rs.concat(D.papers[pi].results); });
        return { list: rs, key: function (i) { return D.results[i].id; }, name: function (i) { var n = resultName(D.results[i]), t = D.papers[D.results[i].p].short; return escapeHtml(n.indexOf(t) < 0 ? n + ', ' + t : n); }, pos: 'step.result' };
      }
      if (o.kind === 'l') return { list: D.families[fi].lean, key: function (i) { return D.lean[i].id; }, name: function (i) { return escapeHtml(D.lean[i].label || D.lean[i].name); }, pos: 'step.lean' };
      return null;
    }
    function siblingKey(o, way) {
      var sb = siblings(o), at = sb ? sb.list.indexOf(o.i) : -1;
      if (at < 0) return null;
      var j = at + way;
      return j >= 0 && j < sb.list.length ? sb.key(sb.list[j]) : null;
    }
    // One compact row under the breadcrumbs: up is the trail, sideways is this.
    function stepperHtml(o) {
      var sb = siblings(o), at = sb ? sb.list.indexOf(o.i) : -1;
      if (at < 0 || sb.list.length < 2) return '';
      var side = function (j, way) {
        var i = j >= 0 && j < sb.list.length ? sb.list[j] : null;
        var label = T(way === 'prev' ? 'step.previous' : 'step.next');
        if (i === null) return '<span class="u-step__go u-step__go--' + way + ' is-end" aria-hidden="true">' + escapeHtml(label) + '</span>';
        var name = sb.name(i);
        return '<button type="button" class="u-go u-step__go u-step__go--' + way + '" data-go="' + escapeHtml(sb.key(i)) + '" title="' + name + '" aria-label="' + escapeHtml(label) + ': ' + name + '" aria-keyshortcuts="' + (way === 'prev' ? 'ArrowLeft' : 'ArrowRight') + '">' + escapeHtml(label) + '</button>';
      };
      return side(at - 1, 'prev') + '<span class="u-step__pos">' + escapeHtml(T(sb.pos, { n: at + 1, of: sb.list.length, where: sb.where || '' })) + '</span>' + side(at + 1, 'next');
    }
    function renderStepper(o) {
      if (!stepEl) return;
      var active = document.activeElement;
      var way = active && stepEl.contains(active) ? (active.classList.contains('u-step__go--prev') ? 'prev' : 'next') : null;
      var html = o ? stepperHtml(o) : '';
      stepEl.innerHTML = html; stepEl.hidden = !html;
      if (way) {
        var target = stepEl.querySelector('button.u-step__go--' + way) || stepEl.querySelector('button') || titleEl;
        if (target) target.focus({ preventScroll: true });
      }
    }
    function scopeName(o) {
      if (!o) return '';
      return o.kind === 'd' ? D.disciplines[o.i].name : D.families[famOf(o)].title;
    }
    /* The hover caption lies over the standing caption in the same grid cell, so the
       bar never changes height and the drawing never moves while the pointer sweeps. */
    var hoverCapEl = root.querySelector('[data-u-hovercap]'), hoverCapKey = '';
    var hoverLineEl = root.querySelector('[data-u-hoverline]'), hoverIdleEl = root.querySelector('[data-u-hoveridle]');
    var keyStripEl = root.querySelector('[data-u-keystrip]');
    var KEY_TONES = ['all', 'part', 'other', 'split', 'none', 'unread'];
    // The colour key standing on the map: a short name for each colour drawn at this
    // level and how many of the families shown carry it; the full sentence is its title.
    function updateKeyStrip(o) {
      if (!keyStripEl) return;
      var list = o && o.kind === 'd' ? D.disciplines[o.i].families : D.families.map(function (f, i) { return i; });
      var n = {};
      list.forEach(function (fi) { var t = D.families[fi].tone || 'none'; n[t] = (n[t] || 0) + 1; });
      keyStripEl.innerHTML = '<span class="u-keystrip__lead">' + escapeHtml(T('keyshort.lead')) + '</span><ul class="u-keystrip__list">' +
        KEY_TONES.filter(function (t) { return n[t]; }).map(function (t) {
          return '<li class="u-chip-k" title="' + escapeHtml(T('key.' + t)) + '">' + dot(t) + escapeHtml(T('keyshort.' + t)) +
            ' <span class="u-chip-k__n">' + fmtNum(n[t]) + '</span></li>';
        }).join('') + '</ul>';
    }
    function hoverCapHtml(o) {
      var strong = function (html) { return '<strong class="u-cap__name">' + html + '</strong> '; };
      if (o.kind === 'd') {
        var d = D.disciplines[o.i];
        return strong(escapeHtml(d.name)) + escapeHtml(discCounts(d) + '. ' + T('chart.hover_disc'));
      }
      var f = D.families[o.i], det = detail(o);
      var n = [count('papers', f.papers.length)];
      if (f.lean.length) n.push(count('lean', f.lean.length));
      var counts = n.length > 1 ? T('card.counts', { papers: n[0], lean: n[1] }) : n[0];
      return strong('<span class="tex-auto">' + (det && det.titleHtml ? det.titleHtml : escapeHtml(f.title)) + '</span>') +
        escapeHtml(T('family.kicker', { num: f.num, discipline: D.disciplines[f.d].name }) + ': ' + counts + '. ') +
        dot(f.tone) + ' ' + escapeHtml(T('key.' + f.tone) + '. ' + T('chart.hover_family'));
    }
    function updateHoverCap() {
      if (!hoverCapEl || !hoverLineEl) return;
      var o = hover && D ? obj(hover) : null;
      var show = !!(o && (o.kind === 'd' || o.kind === 'f') && hover !== sel);
      var key = show ? hover + (detail(o) ? '+' : '') : '';
      if (key === hoverCapKey) return;
      hoverCapKey = key;
      if (!show) { hoverLineEl.classList.remove('is-hovering'); return; }
      hoverCapEl.innerHTML = hoverCapHtml(o);
      if (window.atlasRenderMath) window.atlasRenderMath(hoverCapEl);
      hoverLineEl.classList.add('is-hovering');
    }
    // The words standing with the drawing: what it shows and what choosing does.
    function updateCap(o) {
      updateKeyStrip(o);
      if (hoverIdleEl) hoverIdleEl.textContent = T(o && o.kind === 'd' ? 'chart.hover_idle_disc' : 'chart.hover_idle_release');
      if (!capEl) return;
      if (!o) capEl.textContent = T('chart.release_cap', { families: D.families.length, disciplines: D.disciplines.length });
      else if (o.kind === 'd') {
        capEl.innerHTML = escapeHtml(T('chart.disc_cap', { name: D.disciplines[o.i].name, counts: discCounts(D.disciplines[o.i]) })) +
          // No arrow is drawn until a family is pointed at, so the inks are named in the
          // sentence that says how to make them appear.
          '<span class="u-edge-guide">' + escapeHtml(T('chart.edge_hint')).replace('{cites}', '<span class="u-edge-key u-edge-key--out">' + escapeHtml(T('chart.edge_cites')) + '</span>')
            .replace('{cited}', '<span class="u-edge-key u-edge-key--in">' + escapeHtml(T('chart.edge_cited')) + '</span>') + ' ' + escapeHtml(T('mapkey.arrow')) + '</span>';
      }
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
    var panelDetailVisit = 0, panelShardWaiting = {};
    function watchPanelShard(di, again) {
      var current = panelShardWaiting[di];
      if (current) { current.again = again; return; }
      current = { again: again };
      panelShardWaiting[di] = current;
      var settled = function () {
        if (panelShardWaiting[di] !== current) return;
        delete panelShardWaiting[di];
        current.again();
      };
      loadShard(di).then(settled, settled);
    }
    function renderPanel(quiet) {
      if (!viewEl) return;
      var visit = ++panelDetailVisit;
      var o = sel ? obj(sel) : null;
      var changed = panelKey !== null && panelKey !== (sel || '');
      var listSwitch = root.querySelector('[data-u-show="list"]');
      if (listSwitch) listSwitch.textContent = T(o && o.kind !== 'd' ? 'switch.details' : 'switch.list');
      panelKey = sel || '';
      updateFit();
      updateCap(o);
      updateLegend(o && o.kind !== 'd' ? famOf(o) : -1);
      if (trailEl) trailEl.innerHTML = trailHtml();
      if (trailEl) trailEl.hidden = !o;
      renderStepper(o);
      Array.prototype.forEach.call(root.querySelectorAll('[data-u-ground]'), function (el) { el.hidden = !!o; });
      var html = '';
      if (!o) html = releaseHtml();
      else if (o.kind === 'd') html = disciplineHtml(o.i);
      else if (o.kind === 'f') html = familyHtml(o.i);
      else if (o.kind === 'p') html = paperHtml(o.i);
      else if (o.kind === 'r') html = resultHtml(o.i);
      else if (o.kind === 'l') html = leanHtml(o.i);
      if (titleEl) titleEl.textContent = o ? nameOf(o) : T('page.title');
      if (titleEl) titleEl.className = 'u-title' + (o && o.kind === 'l' ? ' u-title--code' : '') + (o ? ' u-title--deep' : '');
      viewEl.innerHTML = html;
      if (panelBody) panelBody.scrollTop = 0;
      typeset(viewEl, o);
      restorePending();
      if (changed && !quiet) arrive([titleEl, viewEl]);
      if (o) {
        var di = discOf(o);
        if (di >= 0 && !shards[di] && !failedShards[di]) {
          var again = function () {
            if (visit !== panelDetailVisit || sel !== o.key) return;
            var top = scrollPos(), active = document.activeElement;
            var focusedId = viewEl.contains(active) && /^u-section-/.test(active.id) ? active.id : null;
            var focusedButton = viewEl.contains(active) ? active.getAttribute('data-u-section') : null;
            var focusedGo = viewEl.contains(active) ? active.getAttribute('data-go') : null;
            var goIndex = 0;
            if (focusedGo) {
              Array.prototype.some.call(viewEl.querySelectorAll('[data-go]'), function (go) {
                if (go === active) return true;
                if (go.getAttribute('data-go') === focusedGo) goIndex++;
                return false;
              });
            }
            var oldRect = focusedId ? active.getBoundingClientRect() : null;
            var bounds = panelScroller().getBoundingClientRect();
            var followSection = oldRect && oldRect.bottom > bounds.top && oldRect.top < bounds.bottom;
            viewEl.innerHTML = rerender(o);
            typeset(viewEl, o);
            if (panelScroller()) panelScroller().scrollTop = top;
            restorePending();
            syncActive();
            // Loading may replace the section being read. Keep keyboard focus
            // there, but never take it back from another part of the page.
            var replacement = focusedId ? viewEl.querySelector('#' + focusedId) : focusedButton ?
              viewEl.querySelector('[data-u-section="' + focusedButton + '"]') : null;
            if (!replacement && focusedGo) {
              Array.prototype.some.call(viewEl.querySelectorAll('[data-go]'), function (go) {
                if (go.getAttribute('data-go') !== focusedGo || goIndex-- > 0) return false;
                replacement = go; return true;
              });
            }
            if (replacement) {
              if (followSection) showPanelSection(replacement);
              else replacement.focus({ preventScroll: true });
            }
          };
          watchPanelShard(di, again);
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
      var retry = !!failedShards[di];
      failedShards[di] = false;
      shardLoading[di] = fetchJson(url, retry ? 'reload' : 'default').then(function (sh) {
        if (sh.generation_id !== D.generation_id) throw new Error('detail from another build');
        shards[di] = sh;
        failedShards[di] = false;
        return sh;
      }).catch(function (err) {
        shardLoading[di] = null; failedShards[di] = true;
        if (sel && discOf(obj(sel)) === di && statusEl) {
          statusEl.textContent = T('status.parts_failed'); statusEl.hidden = false;
        }
        throw err;
      });
      return shardLoading[di];
    }
    function detail(o) {
      var sh = shards[discOf(o)];
      if (!sh) return null;
      if (o.kind === 'p') return sh.papers && sh.papers[o.key];
      if (o.kind === 'r') return sh.results[o.key];
      if (o.kind === 'l') return sh.lean[o.key];
      if (o.kind === 'f') return sh.families[o.key];
      return null;
    }
    function paperMacros(sh, paper) {
      var macros = {}, k;
      for (k in GLOBAL_MACROS) macros[k] = GLOBAL_MACROS[k];
      var own = sh && sh.macros && paper ? sh.macros[paper] || {} : {};
      for (k in own) {
        var v = own[k];
        if (typeof v === 'string' && !/\\(?:newcommand|def|let|ifx|ifmmode|csname|expandafter)/.test(v)) macros[k] = v;
      }
      return macros;
    }
    // A displayed formula wider than its box scrolls sideways: it takes focus, so a
    // keyboard reader can scroll it with the arrow keys (which then do not step).
    var SCROLLERS = '.m-d, .u-stmt, .u-lean, .u-example, .lean, .tex-fallback';
    function markScrollers(scope) {
      if (!scope) return;
      Array.prototype.forEach.call(scope.querySelectorAll(SCROLLERS), function (x) {
        var wide = x.scrollWidth > x.clientWidth + 1;
        if (wide && !x.hasAttribute('tabindex')) { x.setAttribute('tabindex', '0'); x.setAttribute('data-u-scroller', ''); }
        else if (!wide && x.hasAttribute('data-u-scroller')) { x.removeAttribute('tabindex'); x.removeAttribute('data-u-scroller'); }
      });
    }
    // True when the arrow key belongs to what has focus: a field, or a box that scrolls sideways.
    function arrowsBelongTo(target) {
      for (var n = target; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
        if (/^(INPUT|TEXTAREA|SELECT)$/.test(n.tagName) || n.isContentEditable) return true;
        if (n.matches(SCROLLERS + ', pre, .table-wrap') && n.scrollWidth > n.clientWidth + 1) {
          var ox = getComputedStyle(n).overflowX;
          if (ox === 'auto' || ox === 'scroll') return true;
        }
      }
      return false;
    }
    function typeset(el, o) {
      if (!window.katex) { if (window.atlasRenderMath) window.atlasRenderMath(el); return; }
      var sh = o ? shards[discOf(o)] : null;
      var spans = el.querySelectorAll('span.m:not([data-done])');
      for (var i = 0; i < spans.length; i++) {
        var s = spans[i], tex = s.textContent;
        var scope = s.closest('[data-u-paper]');
        var paper = scope ? scope.getAttribute('data-u-paper') : o && o.kind === 'r' ? D.papers[D.results[o.i].p].id : null;
        var macros = paperMacros(sh, paper);
        s.setAttribute('data-done', '1');
        try {
          // A short inline formula stays on one line (atlas.js keepShort).
          var display = s.getAttribute('data-d') === '1';
          var src = !display && window.atlasKeepShortMath ? window.atlasKeepShortMath(tex) : tex;
          window.katex.render(src, s, { displayMode: display, macros: macros, throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
        } catch (err) { s.textContent = tex; s.classList.add('m-fail'); }
      }
      if (el === viewEl) requestAnimationFrame(function () { markScrollers(viewEl); });
      // Abstracts retain the source's delimiters; render those with the same
      // paper-local macros as explicit theorem spans before the global pass.
      if (window.renderMathInElement) Array.prototype.forEach.call(el.querySelectorAll('.tex-auto[data-u-paper]:not([data-done])'), function (host) {
        host.setAttribute('data-done', '1');
        window.renderMathInElement(host, {
          delimiters: [{ left: '\\(', right: '\\)', display: false }, { left: '\\[', right: '\\]', display: true }],
          macros: paperMacros(sh, host.getAttribute('data-u-paper')), throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000,
          preProcess: window.atlasKeepShortMath || function (tex) { return tex; },
          errorCallback: function () { host.classList.add('m-fail'); }
        });
      });
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
    // The second line of a family row says, in words, what the row shows: the family's
    // number and size, then what its dot's colour means (DESIGN.md, the map sidebar).
    function statusLine(f) {
      var size = count('papers', f.papers.length) + (f.lean.length ? ', ' + count('lean', f.lean.length) : '');
      return T('rowline.size', { num: f.num, counts: size }) + ' ' + T('rowline.' + (f.tone || 'none'));
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
    // Leave enough scroll range to bring even the last family to the reading edge.
    // Keep that range when its synopsis closes, so leaving the map does not jump the list.
    function reserveEntryTail() {
      var entries = viewEl && viewEl.querySelector('.u-entries');
      if (!entries || !panelBody || narrow()) return;
      var last = entries.lastElementChild && entries.lastElementChild.firstElementChild;
      if (!last) return;
      var more = last.querySelector('.u-entry__more');
      var compactHeight = last.offsetHeight - (more ? more.offsetHeight : 0);
      entries.style.paddingBottom = Math.max(0, panelBody.clientHeight - compactHeight - 12) + 'px';
    }
    function revealEntry(entry) {
      if (!entry || !entry.classList.contains('u-entry') || narrow()) return;
      reserveEntryTail();
      panelBody.scrollTop += entry.getBoundingClientRect().top - panelBody.getBoundingClientRect().top - 12;
    }
    // Map previews bring their synopsis to the top of the sidebar. Pointer browsing
    // inside the list stays stationary; keyboard focus follows the same reading edge.
    function syncActive() {
      if (!viewEl) return;
      var hk = hover ? obj(hover) : null, fk = hk ? D.families[famOf(hk)] : null;
      Array.prototype.forEach.call(viewEl.querySelectorAll('.u-entry'), function (e) {
        var active = !!fk && e.getAttribute('data-go') === fk.id;
        e.classList.toggle('is-active', active);
        if (active && hoverVia === 'map') revealEntry(e);
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
    function sectionNav(parts) {
      return '<nav class="u-sections" aria-label="' + escapeHtml(T('panel.sections')) + '">' + parts.map(function (part) {
        return '<button type="button" data-u-section="' + part + '">' + escapeHtml(T('panel.' + part)) + '</button>';
      }).join('') + '</nav>';
    }
    function sectionHeading(key, label) {
      return '<h2 class="u-h2" id="u-section-' + key + '" tabindex="-1">' + escapeHtml(T(label)) + '</h2>';
    }
    // The sidebar has room for source paragraphs, display maths and lists. Keep
    // those blocks intact and take a prefix only; skipping an equation while
    // retaining its following qualifier can change what a preview appears to say.
    function statementPreview(html, budget) {
      var source = document.createElement('template'), preview = document.createElement('div');
      source.innerHTML = html || '';
      var used = 0, cut = false;
      for (var node = source.content.firstChild; node; node = node.nextSibling) {
        var size = (node.textContent || '').trim().length;
        if (used >= budget && size) { cut = true; break; }
        preview.appendChild(node.cloneNode(true));
        used += size;
      }
      return { html: preview.innerHTML, cut: cut };
    }
    function evidenceSection(det) {
      return det && det.readers && det.readers.length ? 'readers' : 'evidence';
    }
    function familyEvidence(det, f, inResult) {
      var section = evidenceSection(det);
      var h = sectionHeading(section, section === 'readers' ? (inResult ? 'result.family_readers_heading' : 'family.readers_heading') : 'family.evidence_heading');
      if (section === 'readers') h += para(T('family.readers_scope'));
      h += '<p class="u-tone">' + dot(f.tone) + '<span>' + escapeHtml(det ? det.evidence : T('key.' + f.tone) + '.') + '</span></p>';
      return h + readersHtml(det);
    }
    function resultRow(ri, preview) {
      var r = D.results[ri], det = detail(obj(r.id));
      var h = '<li>' + goBtn(r.id, '<span class="u-sub__t">' + escapeHtml(resultName(r)) + '</span>', 'u-sub');
      if (preview && det && det.html) {
        var ex = statementPreview(det.html, 700);
        h += '<div class="u-excerpt" data-u-paper="' + escapeHtml(D.papers[r.p].id) + '"><p class="u-role">' + escapeHtml(T('panel.preview')) + '</p>' +
          '<div class="u-excerpt__text">' + ex.html + (ex.cut ? '<p class="u-note">' + escapeHtml(T('panel.preview_continues')) + '</p>' : '') + '</div></div>' +
          goBtn(r.id, escapeHtml(T('panel.open_result')), 'u-inline u-excerpt__open');
      }
      return h + '</li>';
    }
    function leanRow(li) {
      var l = D.lean[li];
      return '<li>' + goBtn(l.id, '<span class="u-sub__t">' + escapeHtml(l.label) + '</span><code class="u-sub__n">' + escapeHtml(l.name) + '</code>', 'u-sub') + '</li>';
    }
    function familyHtml(fi) {
      var f = D.families[fi], det = detail(obj(f.id));
      // The row above already says "3 of 37 families in Combinatorics"; the kicker then
      // names the family by its number in the release, and the discipline only once.
      var stepped = !!stepperHtml(obj(f.id));
      var h = '<p class="u-kicker">' + escapeHtml(stepped ? T('family.short', { num: f.num }) : T('family.kicker', { num: f.num, discipline: D.disciplines[f.d].name })) + '</p>';
      if (!det) return h + loadingHtml(f.d, 'discipline.loading', 'discipline.failed');
      h += sectionNav(['papers', 'lean', evidenceSection(det), 'connections'].filter(function (part) { return part !== 'lean' || f.lean.length; }));
      h += para(T('panel.family_counts', { papers: count('papers', f.papers.length), lean: count('lean', f.lean.length) }), 'u-facts');
      h += '<p class="u-tone">' + dot(f.tone) + '<span>' + escapeHtml(T('key.' + f.tone)) + '</span></p>';
      h += '<figure class="u-cat"><figcaption>' + link(D.catalogue_url, T('family.catalogue')) + ' ' + escapeHtml(T('family.catalogue_says')) + '</figcaption>' +
        '<blockquote class="tex-auto">' + det.desc + '</blockquote>' +
        '</figure>';
      // "Compare the theorem with its Lean" only when a Lean statement is paired with the
      // candidate theorem; it opens that pairing on the family page.
      var co = det.candidate ? obj(det.candidate) : null, cr = co && co.kind === 'r' ? D.results[co.i] : null;
      h += '<p class="u-doors">' + door(f.href, T('family.page_link'), true) + (cr && cr.lean.length ? door(f.href + '#lean-' + D.lean[cr.lean[0]].name, T('family.compare_link')) : '') + '</p>';
      h += sectionHeading('papers', 'family.papers_heading') + '<ol class="u-papers">';
      f.papers.forEach(function (pi, n) {
        var p = D.papers[pi];
        h += '<li>' + goBtn(p.id, '<span class="u-row__t">' + escapeHtml(p.short) + '</span><span class="u-row__n">' +
          escapeHtml([p.date, T('panel.paper_counts', { results: count('results', p.results.length) }), n === 0 && f.papers.length > 1 ? T('family.lead') : ''].filter(Boolean).join(', ')) + '</span>', 'u-row u-row--paper');
        // Results are read after choosing their paper; the family remains an index.
        h += '</li>';
      });
      h += '</ol>';
      if (f.lean.length) h += sectionHeading('lean', 'family.lean_list_heading') + '<ul class="u-subrows u-subrows--lean">' + f.lean.map(leanRow).join('') + '</ul>';
      h += familyEvidence(det, f, false);
      h += para(T(det.headline === 'candidate' ? 'family.headline_candidate' : 'family.headline_unresolved'));
      var more = [];
      if (det.checks) more.push(det.checks);
      if (det.editions) more.push(plural(det.editions, 'family.editions_one', 'family.editions'));
      if (det.withdrawn) more.push(plural(det.withdrawn, 'family.withdrawn_one', 'family.withdrawn'));
      if (det.explained) more.push(plural(det.explained, 'family.explained_one', 'family.explained'));
      if (det.problems) more.push(plural(det.problems, 'family.problems_one', 'family.problems'));
      if (more.length) h += '<div class="u-more">' + more.map(function (t) { return '<p>' + escapeHtml(t) + '</p>'; }).join('') + '<p>' + link(f.href, T('family.page_link')) + '</p></div>';
      h += sectionHeading('connections', 'family.connections_heading');
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
      var p = D.papers[pi], f = D.families[p.f], det = detail(obj(p.id));
      var h = sectionNav(det && det.abstract ? ['abstract', 'results'] : ['results']);
      h += '<p class="u-kicker">' + escapeHtml(T('paper.kicker', { num: f.num })) + (p.date ? ', ' + escapeHtml(p.date) : '') + '</p>';
      h += '<p class="u-doors">' + door(p.href, T('paper.read'), true) + door(p.pdf, T('paper.pdf')) + door(f.href, T('family.page_link')) + '</p>';
      if (det && det.abstract) h += sectionHeading('abstract', 'paper.abstract_heading') +
        '<div class="u-abstract tex-auto" data-u-paper="' + escapeHtml(p.id) + '">' + det.abstract + '</div>';
      if (!det && !shards[f.d]) h += loadingHtml(f.d, 'discipline.loading', 'discipline.failed');
      h += sectionHeading('results', 'paper.results_heading');
      h += p.results.length ? '<ul class="u-subrows u-result-previews">' + p.results.map(function (ri) { return resultRow(ri, true); }).join('') + '</ul>' : para(T('family.results_none'));
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
      var fd = detail(obj(f.id));
      var h = sectionNav(['statement', 'lean', evidenceSection(fd)]);
      h += '<p class="u-context">' + goBtn(p.id, escapeHtml(T('result.in_paper', { paper: p.short })), 'u-inline u-inline--plain') +
        (p.date ? ', <span class="u-nowrap">' + escapeHtml(p.date) + '</span>' : '') + '</p>';
      if (det && det.html) {
        h += '<figure class="u-stmt" id="u-section-statement" tabindex="-1"><p class="u-stmt__head"><strong>' + escapeHtml(resultName(r)) + '.</strong>' +
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
      h += '<h2 class="u-h2" id="u-section-lean" tabindex="-1">' + escapeHtml(T(r.lean.length ? (one ? 'result.lean_heading_' + one : 'result.lean_heading_mixed') : 'result.lean_heading_none')) + '</h2>';
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
      h += familyEvidence(fd, f, true);
      h += '<p class="u-note">' + goBtn(f.id, escapeHtml(T('result.whole_family', { name: f.title })), 'u-inline') + '</p>';
      return h;
    }

    /* A Lean statement: what it is, who re-ran it, and the theorem it is paired with. */
    function leanHtml(li) {
      var l = D.lean[li], f = D.families[l.f], det = detail(obj(l.id));
      var h = sectionNav(['statement', 'results', 'checks']);
      h += '<p class="u-kicker">' + escapeHtml(T('lean.kicker', { num: f.num })) + '</p>';
      h += '<p class="u-lean-label" id="u-section-statement" tabindex="-1">' + escapeHtml(l.label) + '</p>';
      if (l.main) h += para(T('lean.main'));
      if (det && det.snippet) h += '<pre class="lean lean--snippet u-lean"><code>' + det.snippet + '</code></pre>' + para(T('lean.challenge_note'));
      h += '<p class="u-doors">' + door(l.href, T('lean.page'), true) + (l.results.length ? door(f.href + '#lean-' + l.name, T('result.compare')) : '') + door(f.href, T('lean.family_page')) + '</p>';
      var lk = l.pairing === 'candidate-pairing' ? 'candidate' : l.pairing === 'producer-declared-binding' ? 'declared' : l.pairing === 'unavailable' ? 'none' : 'cited';
      h += '<h2 class="u-h2" id="u-section-results" tabindex="-1">' + escapeHtml(T('lean.paper_heading_' + (l.results.length ? lk : 'none'))) + '</h2>';
      if (l.results.length && lk === 'candidate') h += '<p class="u-qual">' + escapeHtml(T('result.lean_sub_candidate')) + '</p>';
      if (l.results.length) {
        var lp = pinnedPair();
        h += '<ul class="u-subrows">' + l.results.map(function (ri) {
          var shown = !!lp && lp[0] === D.results[ri].id;
          return resultRow(ri, true).replace(/<\/li>$/, (l.results.length > 1 ? pairControl(shown, ri) : '') + '</li>');
        }).join('') + '</ul>';
        if (det) h += whyHtml(l, det);
      } else h += para(T('lean.paired_none'));
      h += sectionHeading('checks', 'lean.reruns_heading');
      if (det) {
        h += checksHtml(det);
        if (det.holes.length) h += '<h3 class="u-h3">' + escapeHtml(T('lean.holes_heading')) + '</h3>' + para(T('lean.holes_note')) + '<p>' +
          det.holes.map(function (n) { return '<code>' + escapeHtml(n) + '</code>'; }).join(', ') + '</p>';
      } else h += loadingHtml(discOf(obj(l.id)), 'result.loading', 'result.load_failed');
      return h;
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
    var searchShown = { q: null, kind: '', all: false };   // the kind chip and "Show all" for the current words
    var searchFolded = false;   // the reader opened a match and folded the list away
    var searchEdited = false;
    function rememberSearch() {
      if (!window.history || !window.history.replaceState) return;
      var url = new URL(window.location.href), raw = (searchIn.value || '').trim();
      if (raw) url.searchParams.set('q', raw); else url.searchParams.delete('q');
      window.history.replaceState(Object.assign({}, window.history.state, { sf: searchFolded }), '', url.pathname + url.search + url.hash);
    }
    function restoreSearch(state, initial) {
      if (!searchIn) return;
      var edited = initial && searchEdited;
      var raw = edited ? searchIn.value : new URLSearchParams(window.location.search).get('q') || '';
      var folded = !edited && !!(state && state.sf);
      searchIn.value = raw;
      // Exact result and Lean identifiers need the parts index, including on a
      // direct visit before any family has been opened.
      (raw ? loadParts() : Promise.resolve()).then(function () {
        if (searchIn.value !== raw) return;
        return runSearch(!edited).then(function () {
          if (searchIn.value !== raw) return;
          foldResults(folded, true);
          if (state && typeof state.y === 'number') pendingY = state.y;
          restorePending();
        });
      }).catch(function () {});
    }
    function runSearch(restoring) {
      // Pass the typed query to the site's search; only the map's matching is lower case.
      var raw = (searchIn.value || '').trim();
      var q = raw.toLowerCase();
      query = q;
      if (resultsEl) resultsEl.classList.remove('is-folded');
      searchFolded = false;
      if (!restoring) rememberSearch();
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
        var AS = window.AtlasSearch;
        if (q !== searchShown.q) searchShown = { q: q, kind: '', all: false };
        var want = searchShown.all ? 100000 : 400;
        return Promise.all([AS.query(raw, { statements: want }), AS.names ? AS.names() : null, loadParts()]).then(function (both) {
          if (query !== q) return;
          var hits = both[0] || [], names = both[1];
          // One order with the search dialog (assets/atlas.js rankByName): disciplines,
          // families, papers, statements, Lean statements, the closest names first.
          var kinds = hits.kindOrder || AS.kindOrder || ['discipline', 'family', 'manuscript', 'statement', 'lean'];
          var counts = hits.counts || {};
          matches = {}; matchFam = {}; matchList = [];
          hits.forEach(function (hit) {
            if (obj(hit.id)) { matches[hit.id] = true; matchList.push(hit.id); }
            (hit.family_ids || []).forEach(function (fid) { var fo = obj(fid); if (fo) matchFam[fo.i] = true; });
            var own = obj(hit.id), f = famOf(own);
            if (f >= 0) matchFam[f] = true;
          });
          var total = 0;
          kinds.forEach(function (k) { total += counts[k] || 0; });
          if (!hits.length) total = 0;
          var kind = searchShown.kind && counts[searchShown.kind] ? searchShown.kind : '';
          var pool = kind ? hits.filter(function (h) { return h.kind === kind; }) : hits;
          var poolN = kind ? counts[kind] : total;
          var shown = searchShown.all ? pool : pool.slice(0, 60);
          var kindWord = function (k) { return T('search.kind_' + ({ manuscript: 'paper' }[k] || k)); };
          // A name is the paper's own text: its TeX dashes become dashes outside $...$,
          // and its mathematics is typeset below.
          var words = function (s) {
            return String(s || '').split(/(\$[^$]*\$)/).map(function (part, j) {
              return j % 2 ? part : part.replace(/---/g, '—').replace(/--/g, '–');
            }).join('');
          };
          var head = total ? (total === 1 ? T('search.count_one') : T('search.count', { n: fmtNum(total) })) : T('search.none');
          var h = '<p class="u-note u-results__head" role="status">' + escapeHtml(head) + '</p>';
          // Chips: every kind that matched, with its count; one shows only that kind.
          var present = kinds.filter(function (k) { return counts[k]; });
          if (present.length > 1) {
            h += '<div class="u-chips" role="group" aria-label="' + escapeHtml(T('search.filter_label')) + '">' +
              '<button type="button" class="u-chip" data-u-kind="" aria-pressed="' + (!kind) + '">' + escapeHtml(T('search.all')) + ' <span class="u-chip__n">' + fmtNum(total) + '</span></button>' +
              present.map(function (k) {
                return '<button type="button" class="u-chip" data-u-kind="' + k + '" aria-pressed="' + (kind === k) + '">' + escapeHtml(kindWord(k)) + ' <span class="u-chip__n">' + fmtNum(counts[k]) + '</span></button>';
              }).join('') + '</div>';
          }
          var row = function (hit) {
            var own = obj(hit.id);
            var nameHtml;
            if (hit.kind === 'statement') nameHtml = AS.richName(AS.displayName ? AS.displayName(hit, names) : hit.name);
            else if (hit.kind === 'lean') nameHtml = '<code>' + escapeHtml(hit.id.slice(2)) + '</code>';
            else nameHtml = AS.richName ? AS.richName(hit.name) : escapeHtml(words(hit.name));
            var inner = '<span class="u-row__t md-math">' + nameHtml + '</span>';
            var fo = obj((hit.family_ids || [])[0]);
            var ctx = '';
            if (own && own.kind === 'd') ctx = escapeHtml(discCounts(D.disciplines[own.i]));
            // A family's row names its discipline; a statement its paper; any other row its family.
            else if (fo && hit.kind === 'family') ctx = escapeHtml(T('family.short', { num: D.families[fo.i].num }) + ', ' + D.disciplines[D.families[fo.i].d].name);
            else if (hit.kind === 'statement' && hit.paper) ctx = AS.richName(T('search.in_paper', { title: hit.paper }));
            else if (hit.kind === 'lean' && hit.name && hit.name !== hit.id.slice(2)) ctx = AS.richName(hit.name) + (fo ? escapeHtml(', ' + T('family.short', { num: D.families[fo.i].num })) : '');
            else if (fo) ctx = escapeHtml(T('family.short', { num: D.families[fo.i].num }) + ', ' + D.families[fo.i].title);
            if (ctx) inner += '<span class="u-row__n md-math">' + ctx + '</span>';
            if (hit.idx != null && hit.kind !== 'discipline') inner += '<span class="u-row__x" data-snip="' + hit.idx + '"></span>';
            if (own) return '<li>' + goBtn(hit.id, inner, 'u-row u-row--hit') + '</li>';
            return '<li><a class="u-row u-row--hit" href="' + escapeHtml(hit.url) + '">' + inner + '</a></li>';
          };
          kinds.forEach(function (k) {
            var rows = shown.filter(function (hit) { return hit.kind === k; });
            if (!rows.length) return;
            h += '<h3 class="u-h3 u-results__kind">' + escapeHtml(kindWord(k)) + ' <span class="u-chip__n">' + fmtNum(counts[k] || rows.length) + '</span></h3>';
            h += '<ul class="u-rows">' + rows.map(row).join('') + '</ul>';
          });
          if (poolN > shown.length) {
            h += '<p class="u-results__more"><button type="button" class="u-more-btn" data-u-all>' + escapeHtml(T('search.show_all', { n: fmtNum(poolN) })) + '</button> <span class="u-note">' + escapeHtml(T('search.shown', { shown: fmtNum(shown.length) })) + '</span></p>';
          }
          resultsEl.hidden = false;
          resultsEl.innerHTML = h;
          if (window.atlasRenderMath) window.atlasRenderMath(resultsEl);
          // Each row's line of text with the matched words marked, as it arrives.
          if (AS.snippet) Array.prototype.forEach.call(resultsEl.querySelectorAll('[data-snip]'), function (x) {
            var hit = shown.filter(function (sh) { return String(sh.idx) === x.getAttribute('data-snip'); })[0];
            if (!hit) return;
            AS.snippet(hit, hits).then(function (sn) {
              if (query !== q || !x.isConnected) return;
              if (!sn) { x.remove(); return; }
              x.innerHTML = sn.code ? '<code>' + sn.html + '</code>' : sn.html;
              if (!sn.code && window.atlasRenderMath) window.atlasRenderMath(x);
            });
          });
          // Nothing found: the title words nearest to what was typed.
          if (!total && hits.missing && hits.missing.length && AS.suggest) {
            AS.suggest(hits.missing).then(function (ws) {
              if (query !== q || !ws.length) return;
              var p = document.createElement('p');
              p.className = 'u-note u-suggest';
              p.innerHTML = escapeHtml(T('search.suggest')) + ' ' + ws.map(function (w) {
                return '<button type="button" class="u-suggest__w" data-u-suggest="' + escapeHtml(w) + '" data-u-for="' + escapeHtml(hits.missing[0]) + '">' + escapeHtml(w) + '</button>';
              }).join(', ');
              resultsEl.appendChild(p);
            });
          }
          draw();
          return matchList;
        }, function () {});
      }
      return Promise.all([loadSearch(), loadParts()]).then(function (both) {
        if (query !== q) return;
        var rows = both[0];
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
    var lastPointerType = '', mapPress = null;
    function localXY(e) { var r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    canvas.addEventListener('pointermove', function (e) {
      var p = localXY(e), h = hitAt(p[0], p[1]);
      if (h === hover) return;
      hover = h; hoverVia = e.pointerType === 'touch' ? 'touch' : 'map';
      canvas.classList.toggle('is-over', !!h);
      syncActive();
      draw();
    });
    canvas.addEventListener('pointerleave', function () {
      if (hover && hoverVia !== 'list' && hoverVia !== 'focus') { hover = null; hoverVia = ''; canvas.classList.remove('is-over'); syncActive(); draw(); }
    });
    canvas.addEventListener('pointerdown', function (e) {
      lastPointerType = e.pointerType || '';
      mapPress = null;
      if (e.button !== 0 || e.isPrimary === false) return;
      var p = localXY(e);
      // Keep the object the reader pressed: a moving disc may have left that
      // position (or another may have arrived there) by the time they release.
      mapPress = { key: hitAt(p[0], p[1], true), x: p[0], y: p[1], selection: sel, moving: !!chart.start };
    });
    canvas.addEventListener('pointercancel', function () { mapPress = null; });
    canvas.addEventListener('click', function (e) {
      var p = localXY(e), press = mapPress;
      mapPress = null;
      if (press && (press.selection !== sel || Math.hypot(p[0] - press.x, p[1] - press.y) > 8)) return;
      var key = press && (press.key || press.moving) ? press.key : hitAt(p[0], p[1], true);
      if (!key) { if (sel && !chart.start && !(press && press.moving)) stepBack(); return; }
      if (key === sel) return;
      // Every dot is a family, and choosing one opens that family's page: one place to
      // read a family, rather than a second view of it drawn inside the map.
      var chosen = obj(key);
      if (chosen && chosen.kind === 'f') { openPage(chosen); return; }
      select(key, { trail: true });
    });
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
      var byKey = e.detail === 0 && root.contains(go);
      var target = key ? obj(key) : null;
      if (go.classList.contains('u-crumb')) selectAncestor(key || null);
      // A family, paper, theorem or Lean statement opens its own page; only the release
      // and its disciplines are places on the map.
      else if (target && target.kind !== 'd') { if (fromResults) foldResults(true); openPage(target); return; }
      else select(key || null, { trail: true });
      // A match opened from the search folds the list of matches away, so what was
      // opened starts at the top of the panel; one button brings the matches back.
      if (fromResults) foldResults(true);
      // A row opened from the keyboard was redrawn or folded away: focus goes to what replaced it,
      // the map on a phone's map view, else the panel's heading.
      if (byKey) focusArrival();
    });
    function focusArrival() {
      var phoneMap = narrow() && root.getAttribute('data-view') === 'map';
      var target = phoneMap ? canvas : titleEl;
      if (!target) return;
      if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
      try { target.focus({ preventScroll: narrow() }); } catch (err) { target.focus(); }
    }
    function foldResults(fold, restoring) {
      if (!resultsEl || resultsEl.hidden) return;
      resultsEl.classList.toggle('is-folded', fold);
      searchFolded = !!fold;
      if (!restoring) rememberSearch();
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
    function showPanelSection(target) {
      var scroller = panelScroller(), nav = viewEl.querySelector('.u-sections');
      var offset = narrow() ? 12 : (nav ? nav.offsetHeight : 0) + 12;
      var top = target.getBoundingClientRect().top - (narrow() ? 0 : scroller.getBoundingClientRect().top) + scroller.scrollTop - offset;
      scroller.scrollTo({ top: top, behavior: 'auto' });
      target.focus({ preventScroll: true });
    }
    root.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-u-section]') : null;
      if (!b) return;
      var target = viewEl.querySelector('#u-section-' + b.getAttribute('data-u-section'));
      if (target) showPanelSection(target);
    });
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
      draw();
    });
    // Compact pointer browsing lights the map without reflowing the list.
    root.addEventListener('pointerover', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      var key = go ? go.getAttribute('data-go') : null;
      var via = e.pointerType === 'touch' ? 'touch' : 'list';
      if (go && panelBody && panelBody.contains(go) && key && (key !== hover || hoverVia === 'map')) {
        hover = key; hoverVia = via; draw();
      }
    });
    root.addEventListener('pointerout', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      var next = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('[data-go]') : null;
      // Child transitions stay in this row; another row replaces it on over.
      if (next && panelBody && panelBody.contains(next)) return;
      if (go && panelBody && panelBody.contains(go) && hoverVia !== 'focus' && hover === go.getAttribute('data-go')) { hover = null; hoverVia = ''; draw(); }
    });
    // A row reached by the keyboard lights its place on the map and names it there too.
    root.addEventListener('focusin', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      var key = go ? go.getAttribute('data-go') : null;
      var visible = false;
      try { visible = go && go.matches(':focus-visible'); } catch (err) { visible = false; }
      if (go && visible && panelBody && panelBody.contains(go) && key && obj(key) && (key !== hover || hoverVia !== 'focus')) { hover = key; hoverVia = 'focus'; syncActive(); revealEntry(go); draw(); }
    });
    root.addEventListener('focusout', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      if (go && e.relatedTarget && go.contains(e.relatedTarget)) return;
      if (go && hoverVia === 'focus' && hover === go.getAttribute('data-go')) { hover = null; hoverVia = ''; syncActive(); draw(); }
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
      b.addEventListener('click', function () {
        var v = b.getAttribute('data-u-show');
        if (v === root.getAttribute('data-view')) return;
        phoneViewY = viewPositions();
        var visit = { key: sel, view: v };
        pendingViewSwitch = visit;
        showView(v);
        // Wait for the newly visible content to lay out before restoring its place.
        requestAnimationFrame(function () {
          if (pendingViewSwitch !== visit || sel !== visit.key || root.getAttribute('data-view') !== v) return;
          pendingViewSwitch = null;
          if (narrow()) { pendingY = phoneViewY[v]; restorePending(); }
          if (window.history && window.history.replaceState) {
            try { window.history.replaceState(Object.assign({}, window.history.state, { y: scrollPos(), ys: phoneViewY }), ''); } catch (e) { /* the view still switches */ }
          }
        });
      });
    });
    if (resultsEl) resultsEl.addEventListener('click', function (e) {
      var chip = e.target.closest('[data-u-kind]'), all = e.target.closest('[data-u-all]'), sug = e.target.closest('[data-u-suggest]');
      if (chip) { searchShown.kind = chip.getAttribute('data-u-kind'); searchShown.all = false; runSearch(true).then(function () { var c = resultsEl.querySelector('[data-u-kind="' + searchShown.kind + '"]'); if (c) c.focus(); }); }
      else if (all) { searchShown.all = true; runSearch(true); }
      else if (sug && searchIn) {
        var re = new RegExp(sug.getAttribute('data-u-for').replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
        searchIn.value = re.test(searchIn.value) ? searchIn.value.replace(re, sug.getAttribute('data-u-suggest')) : sug.getAttribute('data-u-suggest');
        searchEdited = true; runSearch(); searchIn.focus();
      }
    });
    if (searchIn) {
      var t = 0;
      searchIn.addEventListener('focus', function () { if (D && !window.AtlasSearch) loadSearch().catch(function () {}); });
      searchIn.addEventListener('input', function () { searchEdited = true; clearTimeout(t); t = setTimeout(runSearch, 120); });
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
        // The input clears its query before a later Escape steps out of the map selection.
        if (e.target === searchIn && searchIn.value) return;
        if (sel) { e.preventDefault(); stepBack(); focusArrival(); }
        return;
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      // Left and right step to the previous or next sibling at the same level.
      if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && sel && !e.shiftKey && !document.querySelector('dialog[open]')) {
        if (arrowsBelongTo(e.target) || arrowsBelongTo(document.activeElement)) return;
        var to = siblingKey(obj(sel), e.key === 'ArrowLeft' ? -1 : 1);
        if (to) { e.preventDefault(); select(to, { trail: true }); focusArrival(); }
        return;
      }
      if (e.key === '/' && searchIn && !document.querySelector('dialog[open]')) {
        // The site's own search owns '/' elsewhere; on this page it finds on the map.
        e.preventDefault(); e.stopImmediatePropagation(); searchIn.focus(); searchIn.select(); return;
      }
    }, true);
    window.addEventListener('hashchange', function () {
      var key = readHash(), o = key ? obj(key) : null;
      if (o && o.kind !== 'd') { openPage(o, true); return; }
      if (key !== sel) select(key, { fromHistory: true });
    });
    window.addEventListener('popstate', function (e) {
      var key = readHash();
      var returning = historyBackPending, queued = historySelection;
      historyBackPending = null; historySelection = null;
      var y = e.state && typeof e.state.y === 'number' ? e.state.y : null;
      restoreViewPositions(e.state);
      if (e.state && (e.state.v === 'map' || e.state.v === 'list')) showView(e.state.v, true);
      if (key !== sel) { trail = returning && returning.key === key ? returning.trail : []; pendingY = y; select(key, { fromHistory: true }); }
      else if (y != null) { pendingY = y; }
      restoreSearch(e.state);
      restorePending();
      if (returning && returning.key === key) focusArrival();
      if (queued) {
        if (queued.ancestor) selectAncestor(queued.key);
        else select(queued.key, queued.opts);
      }
    });
    // Leaving for a paper or a family page, the address's entry keeps the list's place,
    // so coming back finds it.
    window.addEventListener('pagehide', function () {
      try { window.history.replaceState(Object.assign({}, window.history.state, { o: sel, y: savedScrollPos(), v: root.getAttribute('data-view'), ys: viewPositions(), sf: searchFolded }), ''); } catch (e) { /* nothing to keep */ }
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
        if (document.fonts && document.fonts.load) {
          // The chart uses upright text. Italic faces load naturally when the reader
          // opens content that uses them, rather than competing with the first view.
          Promise.all(['400 13px ', '600 13px '].map(function (w) {
            return Promise.all([document.fonts.load(w + SERIF), document.fonts.load(w + SANS)]);
          })).catch(function () {});
        }
      })
      .then(function () {
        widthCache = {};
        weights();
        W = H = 0;
        var start = readHash();
        // Back from a paper or a family page: the entry remembers the list's place.
        var kept = window.history && window.history.state;
        restoreViewPositions(kept);
        if (kept && typeof kept.y === 'number') pendingY = kept.y;
        if (kept && (kept.v === 'map' || kept.v === 'list')) showView(kept.v, true);
        if (start && !/^d:/.test(start)) {
          var initialFamily = obj(start);
          if (initialFamily && initialFamily.kind === 'f') {
            var initialDi = discOf(initialFamily);
            if (!shards[initialDi] && !failedShards[initialDi]) loadShard(initialDi).catch(function () {});
          }
          // An address naming a family, paper, theorem or Lean statement (#o=f:003, from
          // when the map opened families inside itself) opens that object's own page.
          loadParts().then(function () {
            var key = readHash(), o = key ? obj(key) : null;
            if (!o) return;
            openPage(o, true);
          }, function () {});
          start = null;
        }
        // The release and discipline charts need only the first-screen packets.
        // Selection and search load the parts when requested.
        sel = start;
        renderPanel();
        if (statusEl) statusEl.hidden = true;
        root.classList.add('is-ready');
        resize();
        chartTo(false);
        restoreSearch(kept, true);
        window.__universe = {
          select: function (key) { select(key, { trail: true }); },
          state: function () { return { sel: sel, level: chart.level, W: W, H: H, trail: trail.length, moving: !!chart.start }; },
          // Where everything stands on the drawing now, for checks.
          chart: function () { return { shown: chart.shown, boxes: chartBoxes, chrome: chrome }; },
          hover: function (key) { hover = key; paint(); },
          // What the motion is doing now, for checks: the ring's age and whether the
          // step back is still easing.
          motion: function () {
            return { ring: ring ? { key: ring.key, age: nowMs() - ring.start } : null, ringWanted: ringWanted };
          },
          paint: paint
        };
        if (document.fonts && document.fonts.addEventListener) {
          document.fonts.addEventListener('loadingdone', function () {
            widthCache = {}; labelCache = {}; layoutCache = {};
            chartTo(false);
          });
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
