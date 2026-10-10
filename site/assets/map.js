/* OpenAI Math Atlas: the map.
   Level 0: the release as discipline regions, each tiled by its results, every
   tile sized by its manuscripts (a squarified treemap, so tiles stay near
   square at any window shape). Level 1: one discipline fills the field and its
   tiles carry their titles. Level 2: one result's card in the panel, never over
   the tile it describes. Level 3 is the result page itself.
   The camera move between levels is one FLIP transition of transform only. */
(function () {
  'use strict';
  var doc = document;
  var field = doc.querySelector('.field');
  if (!field) return;
  var root = doc.body.getAttribute('data-root') || '';
  var S = {};
  try { S = JSON.parse(doc.getElementById('map-strings').textContent); } catch (e) {}
  var panel = doc.querySelector('.atlas__panel');
  var legendEl = panel.querySelector('.legend');
  var whereEl = panel.querySelector('.where');
  var cardEl = panel.querySelector('.card');
  var captionEl = doc.querySelector('.caption');
  var searchIn = doc.getElementById('map-search');
  var searchList = doc.getElementById('map-search-list');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var D = null;          // data
  var fam = {};          // id -> family
  var tiles = {};        // id -> element
  var regs = [];         // region elements
  var state = { level: 0, disc: -1, sel: null, hover: null, overlay: 'lean', query: '' };
  var geo = { regions: [], tiles: {} };
  var edgesSvg = null;

  function fmt(s, o) { return String(s || '').replace(/\{(\w+)\}/g, function (_, k) { return o[k] != null ? o[k] : ''; }); }
  function n(x) { return Number(x).toLocaleString('en-GB'); }
  function plural(k, one, many) { return n(k) + ' ' + (k === 1 ? one : many); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }

  /* TeX in a title: \( ... \) segments through KaTeX, the rest escaped. */
  function texHTML(s) {
    var out = '';
    var re = /\\\((.+?)\\\)/g, last = 0, m;
    s = String(s || '');
    while ((m = re.exec(s))) {
      out += richText(s.slice(last, m.index));
      var t = m[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
      if (window.katex) {
        try { out += window.katex.renderToString(t, { throwOnError: true, strict: 'ignore' }); }
        catch (e) { out += '<span class="m m-fail">' + esc(t) + '</span>'; }
      } else out += esc(t);
      last = re.lastIndex;
    }
    return out + richText(s.slice(last));
  }
  function richText(t) {
    // Release titles carry <i>, <sub>, <sup> and entities only.
    return esc(t.replace(/&(lt|gt|amp|quot);/g, function (_, k) { return { lt: '<', gt: '>', amp: '&', quot: '"' }[k]; }))
      .replace(/&lt;(\/?)(i|sub|sup|em|b)&gt;/g, '<$1$2>');
  }

  /* ---- Squarified treemap ---------------------------------------------- */
  function squarify(values, x, y, w, h) {
    var total = values.reduce(function (a, b) { return a + b; }, 0);
    var out = [];
    if (total <= 0 || w <= 0 || h <= 0) { values.forEach(function () { out.push([x, y, 0, 0]); }); return out; }
    var scale = w * h / total;
    var areas = values.map(function (v) { return v * scale; });
    var i = 0;
    function worst(row, side) {
      var s = 0, mx = 0, mn = Infinity;
      row.forEach(function (a) { s += a; if (a > mx) mx = a; if (a < mn) mn = a; });
      return Math.max(mx * side * side / (s * s), (s * s) / (side * side * mn));
    }
    while (i < areas.length) {
      var side = Math.min(w, h);
      var row = [areas[i]];
      var j = i + 1;
      while (j < areas.length && worst(row.concat([areas[j]]), side) <= worst(row, side)) { row.push(areas[j]); j++; }
      var s = row.reduce(function (a, b) { return a + b; }, 0);
      var k;
      if (w >= h) {
        var cw = s / h, cy = y;
        for (k = 0; k < row.length; k++) { var ch = row[k] / cw; out.push([x, cy, cw, ch]); cy += ch; }
        x += cw; w -= cw;
      } else {
        var ch2 = s / w, cx = x;
        for (k = 0; k < row.length; k++) { var cw2 = row[k] / ch2; out.push([cx, y, cw2, ch2]); cx += cw2; }
        y += ch2; h -= ch2;
      }
      i = j;
    }
    return out;
  }

  function famOrder(ids) {
    return ids.slice().sort(function (a, b) { return (fam[b].m.length - fam[a].m.length) || (a < b ? -1 : 1); });
  }

  /* ---- Layout ------------------------------------------------------------ */
  var HEAD = 22;
  function layout() {
    var W = field.clientWidth, H = field.clientHeight;
    geo = { W: W, H: H, regions: [], tiles: {}, zoom: {} };
    var vals = D.disciplines.map(function (d, i) {
      return { i: i, v: d.families.reduce(function (a, id) { return a + fam[id].m.length; }, 0) };
    }).sort(function (a, b) { return b.v - a.v || a.i - b.i; });
    var rr = squarify(vals.map(function (x) { return x.v; }), 0, 0, W, H);
    vals.forEach(function (x, k) {
      var r = rr[k];
      var g = 3;
      var reg = { x: r[0] + g / 2, y: r[1] + g / 2, w: r[2] - g, h: r[3] - g };
      var lab = regionLabel(D.disciplines[x.i], reg.w, reg.h);
      var head = lab.top, left = lab.left;
      geo.regions[x.i] = { x: reg.x, y: reg.y, w: reg.w, h: reg.h, head: head, left: left, vert: lab.vert, fs: lab.fs };
      var ids = famOrder(D.disciplines[x.i].families);
      var inner = squarify(ids.map(function (id) { return fam[id].m.length; }), reg.x + 3 + left, reg.y + head + 1, reg.w - 6 - left, reg.h - head - 4);
      ids.forEach(function (id, t) {
        var q = inner[t];
        geo.tiles[id] = { x: q[0] + 1, y: q[1] + 1, w: Math.max(q[2] - 2, 1), h: Math.max(q[3] - 2, 1) };
      });
    });
    // Level 1 layouts, one per discipline, filling the field.
    D.disciplines.forEach(function (d, i) {
      var ids = famOrder(d.families);
      var z = squarify(ids.map(function (id) { return fam[id].m.length; }), 0, 0, W, H);
      var m = {};
      ids.forEach(function (id, t) { var q = z[t]; m[id] = { x: q[0] + 2, y: q[1] + 2, w: Math.max(q[2] - 4, 1), h: Math.max(q[3] - 4, 1) }; });
      geo.zoom[i] = m;
    });
  }
  var measureCtx = null;
  function textW(t, font) {
    if (!measureCtx) measureCtx = doc.createElement('canvas').getContext('2d');
    measureCtx.font = font;
    return measureCtx.measureText(t).width;
  }
  /* A region's label sits inside its own top band, as many lines as its width
     needs (measured in the page's own type), so it never overlaps a tile or
     another label. */
  var probe = null;
  function labelHead(d, w, h) {
    if (!probe) {
      probe = doc.createElement('div');
      probe.className = 'reg__label reg__label--two reg__probe';
      probe.setAttribute('aria-hidden', 'true');
      field.appendChild(probe);
    }
    probe.style.width = Math.max(w, 20) + 'px';
    probe.innerHTML = '<span class="reg__name">' + esc(d.name) + '</span><span class="count">' + n(d.families.length) + '</span>';
    var one = textW(d.name + '  ' + d.families.length, '600 13px "Source Sans 3", sans-serif') <= w - 22;
    if (one) return HEAD;
    return Math.max(HEAD, probe.scrollHeight + 4);
  }
  /* Where a region is too narrow for its name to wrap by whole words, the name
     runs up its left edge instead, in its own band. */
  function regionLabel(d, w, h) {
    var font = '600 13px "Source Sans 3", sans-serif';
    var longest = d.name.split(/\s+/).reduce(function (m, wd) { return Math.max(m, textW(wd, font)); }, 0);
    var full = textW(d.name + '  ' + d.families.length, font);
    if (longest > w - 22) return { top: 0, left: 20, vert: true, fs: Math.max(10, Math.min(13, 13 * (h - 14) / full)) };
    var top = labelHead(d, w, h);
    return { top: top, left: 0, vert: false };
  }
  function camera(rect, disc) {
    // Map a level-0 rectangle into the frame of discipline disc zoomed to fill the field.
    var R = geo.regions[disc];
    var sx = geo.W / (R.w - R.left), sy = geo.H / (R.h - R.head);
    return { x: (rect.x - R.x - R.left) * sx, y: (rect.y - R.y - R.head) * sy, w: rect.w * sx, h: rect.h * sy };
  }
  function targetRect(id) {
    var f = fam[id];
    if (state.level === 0) return geo.tiles[id];
    if (f.d === state.disc) return geo.zoom[state.disc][id];
    return camera(geo.tiles[id], state.disc);
  }

  /* ---- Build the DOM --------------------------------------------------- */
  function build() {
    field.innerHTML = '';
    D.disciplines.forEach(function (d, i) {
      var r = doc.createElement('div');
      r.className = 'reg';
      var b = doc.createElement('button');
      b.type = 'button';
      b.className = 'reg__label';
      var mcount = d.families.reduce(function (a, id) { return a + fam[id].m.length; }, 0);
      b.innerHTML = '<span class="reg__name">' + esc(d.name) + '</span><span class="count">' + n(d.families.length) + '</span>';
      b.setAttribute('aria-label', d.name + ', ' + plural(d.families.length, S.result, S.results) + ', ' + plural(mcount, S.manuscript, S.manuscripts));
      b.title = d.name;
      b.addEventListener('click', function (ev) { ev.stopPropagation(); go({ level: 1, disc: i, sel: null }); });
      b.addEventListener('mouseenter', function () { setCaption(fmt(S.caption_discipline, { name: d.name, families: n(d.families.length), manuscripts: n(mcount) })); });
      b.addEventListener('mouseleave', function () { setCaption(null); });
      r.appendChild(b);
      field.appendChild(r);
      regs[i] = r;
    });
    D.families.forEach(function (f) {
      var t = doc.createElement('button');
      t.type = 'button';
      t.className = 'tile';
      t.tabIndex = -1;
      t.setAttribute('data-id', f.id);
      t.setAttribute('aria-label', f.p);
      t.innerHTML = '<span class="tile__t"></span>';
      t.addEventListener('click', function (ev) {
        ev.stopPropagation();
        if (state.level === 0) go({ level: 1, disc: f.d, sel: f.id });
        else if (f.d === state.disc) go({ level: 1, disc: f.d, sel: state.sel === f.id ? null : f.id });
      });
      t.addEventListener('mouseenter', function () { state.hover = f.id; setCaption(tileCaption(f)); if (state.overlay === 'rests' && !state.sel) drawEdges(); });
      t.addEventListener('mouseleave', function () { state.hover = null; setCaption(null); if (state.overlay === 'rests' && !state.sel) drawEdges(); });
      t.addEventListener('focus', function () { setCaption(tileCaption(f)); });
      field.appendChild(t);
      tiles[f.id] = t;
    });
    edgesSvg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
    edgesSvg.setAttribute('class', 'edges');
    edgesSvg.setAttribute('aria-hidden', 'true');
    field.appendChild(edgesSvg);
    field.addEventListener('click', function () { back(); });
  }

  function tileCaption(f) {
    return '<strong>' + texHTML(f.t) + '</strong> ' + esc(fmt(S.caption_tile, {
      title: '', discipline: D.disciplines[f.d].name,
      manuscripts: plural(f.m.length, S.manuscript, S.manuscripts),
      lean: f.s.length ? plural(f.s.length, S.lean_statement, S.lean_statements) : S.no_lean
    }).replace(/^\.\s*/, ''));
  }
  function setCaption(html) {
    if (html) { captionEl.innerHTML = html; return; }
    if (state.level === 0) captionEl.textContent = fmt(S.caption_idle, { families: n(D.families.length), disciplines: n(D.disciplines.length) });
    else {
      var d = D.disciplines[state.disc];
      captionEl.textContent = fmt(S.caption_discipline, { name: d.name, families: n(d.families.length), manuscripts: n(d.families.reduce(function (a, id) { return a + fam[id].m.length; }, 0)) });
    }
  }

  /* ---- Overlays -------------------------------------------------------- */
  function sizeBin(v) {
    if (v == null) return -1;
    var bins = D.sizeBins;
    for (var i = 0; i < bins.length; i++) if (v >= bins[i][0] && (bins[i][1] == null || v <= bins[i][1])) return i;
    return bins.length - 1;
  }
  function fillOf(f) {
    var o = state.overlay;
    if (o === 'lean') {
      if (!f.s.length) return { fill: 'var(--t-none)', key: 'none' };
      return f.s.some(function (s) { return s[1]; }) ? { fill: 'var(--t-main)', key: 'main', ink: true } : { fill: 'var(--t-sup)', key: 'sup' };
    }
    if (o === 'covers') {
      var g = f.g || 'unknown';
      if (g === 'full') return { fill: 'var(--t-main)', key: 'cfull', ink: true };
      if (g === 'part') return { fill: 'var(--t-sup)', key: 'cpart' };
      if (g === 'less') return { fill: 'var(--t-x1)', key: 'cless' };
      if (g === 'support') return { fill: 'var(--t-none)', key: 'csup', ring: 'ring-steel' };
      return { fill: 'var(--t-none)', key: 'cnone' };
    }
    if (o === 'size') {
      var b = sizeBin(f.v);
      if (b < 0) return { fill: 'var(--t-none)', key: 'none' };
      if (b === 0) return { fill: 'var(--t-none)', key: 's0', ring: 'ring-steel' };
      return { fill: 'var(--t-s' + b + ')', key: 's' + b, ink: b === 3 };
    }
    if (o === 'rests') {
      var c = f.k;
      if (!c) return { fill: 'var(--t-none)', key: 'r0' };
      if (c === 1) return { fill: 'var(--t-r1)', key: 'r1' };
      if (c <= 4) return { fill: 'var(--t-r2)', key: 'r2' };
      return { fill: 'var(--t-r3)', key: 'r3', ink: true };
    }
    if (f.x === 2) return { fill: 'var(--t-x2)', key: 'x2', ink: true };
    if (f.x === 1) return { fill: 'var(--t-x1)', key: 'x1' };
    return { fill: 'var(--t-none)', key: 'x0', ring: 'ring-brick' };
  }
  function legend() {
    var o = state.overlay;
    var counts = {};
    D.families.forEach(function (f) { var k = fillOf(f).key; counts[k] = (counts[k] || 0) + 1; });
    var rows = [];
    function row(sw, label, key) {
      rows.push('<div class="legend__row"><span class="sw ' + sw + '"></span><span>' + esc(label) + '</span>' + (key != null ? '<span class="legend__n">' + n(counts[key] || 0) + '</span>' : '') + '</div>');
    }
    if (o === 'lean') {
      row('sw--main', S.legend_lean_main, 'main'); row('sw--sup', S.legend_lean_support, 'sup'); row('sw--none', S.legend_lean_none, 'none');
    } else if (o === 'covers') {
      row('sw--main', S.legend_covers_full, 'cfull'); row('sw--sup', S.legend_covers_part, 'cpart'); row('sw--x1', S.legend_covers_less, 'cless'); row('sw--none ring-steel', S.legend_covers_support, 'csup'); row('sw--none', S.legend_covers_none, 'cnone');
      rows.push('<p class="legend__note">' + esc(S.legend_covers_note) + '</p>');
    } else if (o === 'size') {
      D.sizeBins.forEach(function (b, i) {
        var label = i === 0 ? S.legend_size_zero : (b[1] == null ? fmt(S.legend_size_bin_open, { lo: n(b[0]) }) : fmt(S.legend_size_bin, { lo: n(b[0]), hi: n(b[1]) }));
        row('sw--s' + i, label, 's' + i);
      });
      row('sw--none', S.legend_size_none, 'none');
      rows.push('<p class="legend__note">' + esc(S.legend_size_note) + '</p>');
    } else if (o === 'rests') {
      row('sw--r3', S.legend_rests_4, 'r3'); row('sw--r2', S.legend_rests_2, 'r2'); row('sw--r1', S.legend_rests_1, 'r1'); row('sw--none', S.legend_rests_0, 'r0');
      rows.push('<div class="legend__row"><span class="sw sw--line"></span><span>' + esc(S.legend_rests_cites) + '</span><span class="sw sw--line-b"></span><span>' + esc(S.legend_rests_cited_by) + '</span></div>');
      rows.push('<p class="legend__note">' + esc(S.legend_rests_note) + '</p>');
    } else {
      row('sw--x2', S.legend_explained_done, 'x2'); row('sw--x1', S.legend_explained_claimed, 'x1'); row('sw--x0', S.legend_explained_open, 'x0');
    }
    legendEl.innerHTML = rows.join('');
  }

  /* ---- Paint ------------------------------------------------------------ */
  var q = [];
  function matches(f) {
    if (!q.length) return true;
    var hay = f._n || (f._n = norm(f.p + ' ' + f.m.map(function (m) { return m[0]; }).join(' ') + ' ' + f.s.map(function (s) { return s[0]; }).join(' ')));
    return q.every(function (t) { return hay.indexOf(t) >= 0; });
  }
  function paint() {
    D.families.forEach(function (f) {
      var t = tiles[f.id];
      var fo = fillOf(f);
      t.style.setProperty('--fill', fo.fill);
      t.classList.toggle('ring-steel', fo.ring === 'ring-steel');
      t.classList.toggle('ring-brick', fo.ring === 'ring-brick');
      t.classList.toggle('tile--ink', !!fo.ink);
      t.classList.toggle('is-sel', state.sel === f.id);
      var inView = state.level === 0 || f.d === state.disc;
      t.classList.toggle('is-hidden', !inView);
      t.classList.toggle('is-dim', inView && !matches(f));
      t.tabIndex = state.level === 1 && f.d === state.disc ? 0 : -1;
    });
    regs.forEach(function (r, i) {
      r.classList.toggle('is-hidden', state.level === 1);
      var lab = r.firstChild;
      lab.tabIndex = state.level === 0 ? 0 : -1;
    });
    legend();
    drawEdges();
  }

  function tileText(f, w, h) {
    var t = tiles[f.id].firstChild;
    if (w < 40 || h < 30) { t.innerHTML = ''; return; }
    var narrow = w < 110;
    var lh = narrow ? 16 : 17.5;
    var showMeta = h >= 58;
    var lines = Math.max(1, Math.floor((h - (showMeta ? 34 : 14)) / lh));
    var meta = plural(f.m.length, S.manuscript, S.manuscripts);
    var withLean = meta + (f.s.length ? ', ' + plural(f.s.length, S.lean_statement, S.lean_statements) : '');
    var mfont = '12px "Source Sans 3", sans-serif';
    if (textW(withLean, mfont) <= w - 18) meta = withLean;
    else if (textW(meta, mfont) > w - 18) meta = n(f.m.length);
    t.classList.toggle('tile__t--narrow', narrow);
    t.innerHTML = '<span class="tile__title" style="--lines:' + lines + '">' + texHTML(f.t) + '</span>' + (showMeta ? '<span class="tile__meta">' + esc(meta) + '</span>' : '');
  }

  function place(animate) {
    var olds = {};
    if (animate && !reduce) {
      D.families.forEach(function (f) { olds[f.id] = tiles[f.id]._r; });
    }
    D.families.forEach(function (f) {
      var r = targetRect(f.id);
      var t = tiles[f.id];
      t._r = r;
      t.style.width = r.w + 'px';
      t.style.height = r.h + 'px';
      var o = olds[f.id];
      if (o && animate && !reduce) {
        t.style.transition = 'none';
        t.style.transform = 'translate(' + o.x + 'px,' + o.y + 'px) scale(' + (o.w / r.w) + ',' + (o.h / r.h) + ')';
      } else {
        t.style.transform = 'translate(' + r.x + 'px,' + r.y + 'px)';
      }
      if (state.level === 1 && f.d === state.disc) tileText(f, r.w, r.h);
    });
    regs.forEach(function (el, i) {
      var R = geo.regions[i];
      var r = state.level === 0 ? R : camera(R, state.disc);
      el.style.width = r.w + 'px';
      el.style.height = r.h + 'px';
      el.style.transform = 'translate(' + r.x + 'px,' + r.y + 'px)';
      el.firstChild.classList.toggle('reg__label--two', R.head > HEAD);
      el.firstChild.classList.toggle('reg__label--vert', !!R.vert);
      el.firstChild.style.fontSize = R.vert ? R.fs.toFixed(1) + 'px' : '';
    });
    if (animate && !reduce) {
      void field.offsetWidth;
      field.classList.add('is-anim');
      D.families.forEach(function (f) {
        var t = tiles[f.id], r = t._r;
        t.style.transition = '';
        t.style.transform = 'translate(' + r.x + 'px,' + r.y + 'px)';
      });
      clearTimeout(place._t);
      place._t = setTimeout(function () { field.classList.remove('is-anim'); drawEdges(); }, 480);
    }
    field.classList.toggle('is-zoomed', state.level === 1);
  }

  /* ---- Edges (Rests on) ------------------------------------------------ */
  function centre(id) { var r = tiles[id]._r; return [r.x + r.w / 2, r.y + r.h / 2]; }
  function drawEdges() {
    if (!edgesSvg) return;
    edgesSvg.innerHTML = '';
    if (state.overlay !== 'rests' || field.classList.contains('is-anim')) return;
    var focus = state.sel || state.hover;
    if (!focus) return;
    var f = fam[focus];
    var a = centre(focus);
    var html = '';
    function visible(id) { return state.level === 0 || fam[id].d === state.disc; }
    function arc(b, cls) {
      var dx = b[0] - a[0], dy = b[1] - a[1];
      var mx = (a[0] + b[0]) / 2 - dy * 0.18, my = (a[1] + b[1]) / 2 + dx * 0.18;
      return '<path class="' + cls + '" d="M' + a[0].toFixed(1) + ',' + a[1].toFixed(1) + ' Q' + mx.toFixed(1) + ',' + my.toFixed(1) + ' ' + b[0].toFixed(1) + ',' + b[1].toFixed(1) + '"/>';
    }
    f.b.forEach(function (id) { if (visible(id)) html += arc(centre(id), 'e-cited'); });
    f.c.forEach(function (id) { if (visible(id)) html += arc(centre(id), 'e-cites'); });
    f.b.forEach(function (id) { if (visible(id)) { var c = centre(id); html += '<circle class="n-cited" cx="' + c[0] + '" cy="' + c[1] + '" r="3.5"/>'; } });
    f.c.forEach(function (id) { if (visible(id)) { var c = centre(id); html += '<circle class="n-cites" cx="' + c[0] + '" cy="' + c[1] + '" r="3.5"/>'; } });
    html += '<circle class="n-cites" cx="' + a[0] + '" cy="' + a[1] + '" r="4.5"/>';
    edgesSvg.setAttribute('viewBox', '0 0 ' + geo.W + ' ' + geo.H);
    edgesSvg.innerHTML = html;
  }

  /* ---- Panel: where am I, and the card -------------------------------- */
  function where() {
    var parts = [];
    if (state.level === 0) parts.push('<span class="where__cur">' + esc(S.where_all) + '</span>');
    else {
      parts.push('<button type="button" data-go="all">' + esc(S.where_all) + '</button>');
      parts.push('<span class="where__sep" aria-hidden="true">/</span>');
      var d = D.disciplines[state.disc];
      if (state.sel) {
        parts.push('<button type="button" data-go="disc">' + esc(d.name) + '</button>');
        parts.push('<span class="where__sep" aria-hidden="true">/</span>');
        parts.push('<span class="where__cur">' + texHTML(fam[state.sel].t) + '</span>');
      } else parts.push('<span class="where__cur">' + esc(d.name) + '</span>');
    }
    whereEl.innerHTML = parts.join('');
  }
  whereEl.addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-go]');
    if (!b) return;
    if (b.getAttribute('data-go') === 'all') go({ level: 0, disc: -1, sel: null });
    else go({ level: 1, disc: state.disc, sel: null });
  });

  function card() {
    if (!state.sel) { cardEl.hidden = true; cardEl.innerHTML = ''; return; }
    var f = fam[state.sel];
    var d = D.disciplines[f.d];
    var h = [];
    h.push('<p class="card__kicker">' + esc((S.result || 'result').replace(/^./, function (c) { return c.toUpperCase(); })) + ' ' + esc(f.id) + ', ' + esc(d.name) + '</p>');
    h.push('<h2 class="card__title">' + texHTML(f.t) + '</h2>');
    if (f.x === 0) h.push('<p class="card__ex">' + esc(S.card_explained_open) + '</p>');
    h.push('<h3>' + esc(S.card_manuscripts) + '</h3><ul>');
    f.m.forEach(function (m) {
      h.push('<li><a href="' + root + 'papers/' + encodeURIComponent(m[3]) + '.html">' + texHTML(m[0]) + '</a><span class="k">' + esc(m[1]) + ' <a class="ext" href="' + esc(D.blob + m[2]) + '" rel="noopener">' + esc(S.card_pdf) + '</a></span></li>');
    });
    h.push('</ul><h3>' + esc(S.card_lean) + '</h3>');
    if (f.s.length) {
      h.push('<ul>');
      f.s.forEach(function (s) {
        h.push('<li><a href="' + root + 'statements/' + encodeURIComponent(s[3]) + '.html">' + esc(s[0]) + '</a><span class="k">' + esc(s[1] ? S.main_result : S.supporting_result) + ', ' + esc(s[2] === 0 ? S.card_vocab_zero : (s[2] === 1 ? S.card_vocab_one : fmt(S.card_vocab, { count: n(s[2]) }))) + '</span></li>');
      });
      h.push('</ul>');
    } else h.push('<p class="card__none">' + esc(S.card_no_lean) + '</p>');
    function relList(title, ids) {
      h.push('<h3>' + esc(title) + '</h3>');
      if (!ids.length) { h.push('<p class="card__none">' + esc(S.card_none) + '</p>'); return; }
      h.push('<ul>');
      ids.forEach(function (id) {
        var g = fam[id];
        h.push('<li><button type="button" class="lnk" data-sel="' + id + '">' + texHTML(g.t) + '</button><span class="k">' + esc(D.disciplines[g.d].name) + '</span></li>');
      });
      h.push('</ul>');
    }
    relList(S.card_cites, f.c);
    relList(S.card_cited_by, f.b);
    if (f.k) h.push('<p class="card__fact">' + esc(fmt(f.k === 1 ? S.card_cited_count_one : S.card_cited_count, { n: n(f.k) })) + (f.s.length ? '' : '; ' + esc(S.no_lean)) + '.</p>');
    h.push('<p class="actions"><a class="btn btn--primary" href="' + root + 'families/' + f.id + '.html">' + esc(S.card_open) + '</a><button type="button" class="btn btn--ghost" data-go="disc">' + esc(fmt(S.card_back, { name: d.name })) + '</button></p>');
    cardEl.innerHTML = h.join('');
    cardEl.hidden = false;
  }
  cardEl.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-sel]');
    if (b) { var id = b.getAttribute('data-sel'); go({ level: 1, disc: fam[id].d, sel: id }); return; }
    if (ev.target.closest('[data-go="disc"]')) go({ level: 1, disc: state.disc, sel: null });
  });

  /* ---- State --------------------------------------------------------- */
  function go(next, opts) {
    var levelChange = next.level !== state.level || next.disc !== state.disc;
    state.level = next.level; state.disc = next.disc; state.sel = next.sel;
    if (levelChange) field.classList.remove('is-zoomed');
    place(levelChange && !(opts && opts.instant));
    paint();
    where();
    card();
    setCaption(null);
    writeHash();
    if (state.sel) {
      if (window.innerWidth <= 980) { if (opts && opts.scrollCard) cardEl.scrollIntoView({ block: 'nearest' }); }
      else panel.scrollTo({ top: Math.max(0, whereEl.offsetTop - panel.offsetTop - 6), behavior: reduce ? 'auto' : 'smooth' });
    } else if (panel.scrollTop && window.innerWidth > 980) panel.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
  }
  function back() {
    if (state.sel) go({ level: 1, disc: state.disc, sel: null });
    else if (state.level === 1) go({ level: 0, disc: -1, sel: null });
  }
  function writeHash() {
    var p = [];
    if (state.level === 1) p.push('d=' + D.disciplines[state.disc].slug);
    if (state.sel) p.push('f=' + state.sel);
    if (state.overlay !== 'lean') p.push('o=' + state.overlay);
    var h = p.length ? '#' + p.join('&') : '';
    if (location.hash !== h) history.replaceState(null, '', h || location.pathname + location.search);
  }
  function readHash() {
    var h = new URLSearchParams(location.hash.replace(/^#/, ''));
    var o = h.get('o');
    if (o && /^(lean|covers|size|rests|explained)$/.test(o)) setOverlay(o, true);
    var f = h.get('f');
    var d = h.get('d');
    if (f && fam[f]) return { level: 1, disc: fam[f].d, sel: f };
    if (d) { for (var i = 0; i < D.disciplines.length; i++) if (D.disciplines[i].slug === d) return { level: 1, disc: i, sel: null }; }
    return { level: 0, disc: -1, sel: null };
  }

  function setOverlay(o, quiet) {
    state.overlay = o;
    doc.querySelectorAll('.seg__b').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-overlay') === o ? 'true' : 'false'); });
    if (!quiet) { paint(); writeHash(); }
  }
  doc.querySelectorAll('.seg__b').forEach(function (b) {
    b.addEventListener('click', function () { setOverlay(b.getAttribute('data-overlay')); });
  });

  /* ---- Search by title -------------------------------------------------- */
  var hits = [], hsel = -1;
  function runSearch() {
    q = norm(searchIn.value).trim().split(/\s+/).filter(function (t) { return t.length > 1; });
    hits = q.length ? D.families.filter(matches).slice(0, 8) : [];
    hsel = -1;
    searchList.innerHTML = hits.map(function (f, k) {
      return '<li role="option" id="ms-' + k + '" data-id="' + f.id + '">' + texHTML(f.t) + '<span class="k">' + esc(D.disciplines[f.d].name) + '</span></li>';
    }).join('');
    searchList.hidden = !hits.length;
    searchIn.setAttribute('aria-expanded', hits.length ? 'true' : 'false');
    paint();
  }
  function pick(id) {
    searchList.hidden = true;
    searchIn.setAttribute('aria-expanded', 'false');
    go({ level: 1, disc: fam[id].d, sel: id }, { scrollCard: true });
  }
  searchIn.addEventListener('input', runSearch);
  searchIn.addEventListener('keydown', function (ev) {
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      if (!hits.length) return;
      ev.preventDefault();
      hsel = (hsel + (ev.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
      searchList.querySelectorAll('li').forEach(function (li, k) { li.setAttribute('aria-selected', k === hsel ? 'true' : 'false'); });
      searchIn.setAttribute('aria-activedescendant', 'ms-' + hsel);
    } else if (ev.key === 'Enter') {
      if (hits.length) { ev.preventDefault(); pick(hits[Math.max(hsel, 0)].id); }
    } else if (ev.key === 'Escape') {
      ev.stopPropagation();
      if (!searchList.hidden) { searchList.hidden = true; searchIn.setAttribute('aria-expanded', 'false'); }
      else if (searchIn.value) { searchIn.value = ''; runSearch(); }
    }
  });
  searchList.addEventListener('mousedown', function (ev) {
    var li = ev.target.closest('li[data-id]');
    if (li) { ev.preventDefault(); pick(li.getAttribute('data-id')); }
  });
  searchIn.addEventListener('blur', function () { setTimeout(function () { searchList.hidden = true; searchIn.setAttribute('aria-expanded', 'false'); }, 120); });

  doc.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    var dlg = doc.getElementById('search-dialog');
    if (dlg && dlg.open) return;
    if (doc.activeElement === searchIn) return;
    back();
  });

  /* ---- Start -------------------------------------------------------------- */
  function start(data) {
    D = data;
    D.families.forEach(function (f) { fam[f.id] = f; });
    build();
    layout();
    var s = readHash();
    state.level = s.level; state.disc = s.disc; state.sel = s.sel;
    place(false);
    paint(); where(); card(); setCaption(null);
    var ro = new ResizeObserver(function () {
      var W = field.clientWidth, H = field.clientHeight;
      if (W === geo.W && H === geo.H) return;
      layout(); place(false); drawEdges();
    });
    ro.observe(field);
    var relayout = function () { layout(); place(false); paint(); };
    if (doc.fonts && doc.fonts.load) {
      Promise.all([doc.fonts.load('600 13px "Source Sans 3"'), doc.fonts.load('14px "STIX Two Text"')]).then(relayout, relayout);
      doc.fonts.ready.then(relayout);
    }
    window.addEventListener('hashchange', function () { var s2 = readHash(); go(s2); });
  }
  function boot() {
    fetch(root + 'data/atlas-map.json').then(function (r) { return r.json(); }).then(function (data) {
      var run = function () { start(data); };
      if (window.katex) run();
      else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
      else run();
    });
  }
  boot();
})();
