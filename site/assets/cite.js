/* Who cites a person or a work: the lookup on references-outside.html.

   It reads Statement Map's citation packets (statement-map-web/2), copied into
   data/ at their logical paths: citations-index.json names the papers, the
   entry chunks and the shards. A query is turned into the backend's own query words
   (AtlasSearch.queryTokens, atlas.js); each word is looked up as "author:<word>" or
   "text:<word>" in the shard named by the first byte of SHA-256 of that key, modulo
   64; the postings of every word are intersected, so a reference matches when all the
   words are in the same bibliography record. Only the shards and the entry chunks a
   query needs are fetched, and every packet must carry this page's generation.

   A match is a recorded bibliography entry, not a statement that the citing paper
   depends on, or endorses, the cited work. Author lists are missing from some records;
   the page says how many, and every author search also counts the matches anywhere in
   the reference text so those records are not silently left out. */
(function () {
  'use strict';
  var form = document.getElementById('cite-form');
  if (!form || !window.fetch) return;
  var body = document.body;
  var root = body.getAttribute('data-root') || '';
  var BASE = root + 'data/';
  var GEN = (document.querySelector('[data-generation]') || body).getAttribute('data-generation') || '';
  var W = {};
  try { W = JSON.parse(document.getElementById('cite-words').textContent); } catch (e) { W = {}; }
  var input = document.getElementById('cite-q');
  var out = document.getElementById('cite-out');
  var status = document.getElementById('cite-status');
  var PAGE = 12;
  var cache = {};

  function fmt(s, o) { return String(s || '').replace(/\{(\w+)\}/g, function (m, k) { return o[k] != null ? o[k] : m; }); }
  function n(x) { return Number(x).toLocaleString('en-GB'); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function getJSON(path) {
    if (!cache[path]) {
      cache[path] = fetch(BASE + path).then(function (r) {
        if (!r.ok) throw new Error(path + ': HTTP ' + r.status);
        return r.json();
      }).then(function (j) {
        if (GEN && j.generation_id !== GEN) throw new Error(path + ' is from another generation');
        return j;
      });
      cache[path].catch(function () { delete cache[path]; });
    }
    return cache[path];
  }
  function intersect(lists) {
    if (!lists.length) return [];
    lists = lists.slice().sort(function (a, b) { return a.length - b.length; });
    var out = lists[0].slice();
    for (var k = 1; k < lists.length && out.length; k++) {
      var set = {};
      for (var i = 0; i < lists[k].length; i++) set[lists[k][i]] = 1;
      out = out.filter(function (x) { return set[x]; });
    }
    return out.sort(function (a, b) { return a - b; });
  }
  /* The entries every word of the query is posted to, in one namespace. */
  function postings(idx, field, words) {
    var S = window.AtlasSearch;
    return Promise.all(words.map(function (w) {
      var key = field + ':' + w;
      return S.shardOf(key).then(function (h) {
        var path = idx.shards[field + '-' + h];
        if (!path) return [];
        return getJSON(path).then(function (doc) { return doc.terms[key] || []; });
      });
    })).then(intersect);
  }
  function entries(idx, list) {
    var size = idx.entry_chunk_size, need = {};
    list.forEach(function (i) { need[Math.floor(i / size)] = 1; });
    var chunks = Object.keys(need).map(Number);
    return Promise.all(chunks.map(function (c) { return getJSON(idx.entry_chunks[c]); })).then(function (docs) {
      var by = {};
      chunks.forEach(function (c, k) { by[c] = docs[k]; });
      return list.map(function (i) {
        var d = by[Math.floor(i / size)];
        if (d.start !== Math.floor(i / size) * size) throw new Error('entry chunk out of order');
        return d.entries[i % size];
      });
    });
  }
  /* Matching entries grouped by citing paper, current papers only, in the index's order. */
  function byPaper(idx, list) {
    var groups = {}, order = [];
    list.forEach(function (i) {
      var e = idx._entries[i];
      var p = idx.papers[e.paper];
      if (!p || p.status !== 'current') return;
      if (!groups[e.paper]) { groups[e.paper] = []; order.push(e.paper); }
      groups[e.paper].push(e);
    });
    order.sort(function (a, b) { return a - b; });
    return order.map(function (k) { return { paper: idx.papers[k], refs: groups[k] }; });
  }

  function refLine(rec) {
    var li = el('li', 'cite-ref');
    var head = el('p', 'cite-ref__h');
    if (rec.authors) head.appendChild(el('span', 'cite-ref__au', rec.authors));
    if (rec.title) {
      if (rec.authors) head.appendChild(document.createTextNode(', '));
      head.appendChild(el('span', 'cite-ref__ti md-math', rec.title));
    }
    if (!rec.authors && !rec.title) head.appendChild(el('span', 'cite-ref__tx md-math', rec.text || rec.key || ''));
    var tail = [rec.venue, rec.year].filter(Boolean).join(', ');
    if (tail) head.appendChild(document.createTextNode(' (' + tail + ')'));
    li.appendChild(head);
    var uses = (rec.uses || []).map(function (u) { return u.section; }).filter(Boolean);
    var seen = {}, secs = [];
    uses.forEach(function (s) { if (!seen[s]) { seen[s] = 1; secs.push(s); } });
    if (secs.length) li.appendChild(el('p', 'cite-ref__where', fmt(W.cited_in, { sections: secs.join('; ') })));
    return li;
  }
  function bibHref(p, key) {
    var enc = encodeURIComponent(key).replace(/[!'()*]/g, function (c) { return '%' + c.charCodeAt(0).toString(16).toUpperCase(); });
    return root + 'papers/' + encodeURIComponent(p.id) + '.html#bib-' + enc;
  }
  function paperCard(g, lab) {
    var p = g.paper;
    var art = el('article', 'cite-hit');
    var h = el('h3', 'cite-hit__h');
    var a = el('a', null, (lab.papers || {})['p:' + p.id] || p.title);
    a.href = root + 'papers/' + encodeURIComponent(p.id) + '.html';
    h.appendChild(a);
    art.appendChild(h);
    var fam = (lab.families || {})['f:' + p.family];
    if (p.family) {
      var meta = el('p', 'cite-hit__fam');
      var fa = el('a', null, fmt(W.family, { id: p.family }) + (fam ? ': ' + fam.n : ''));
      fa.href = root + 'families/' + encodeURIComponent(p.family) + '.html';
      meta.appendChild(fa);
      art.appendChild(meta);
    }
    var ul = el('ul', 'cite-hit__refs');
    g.refs.forEach(function (e) {
      var li = refLine(e.preview.record || {});
      if (e.key) {
        var go = el('a', 'cite-ref__go', W.in_bibliography);
        go.href = bibHref(p, e.key);
        li.appendChild(go);
      }
      ul.appendChild(li);
    });
    art.appendChild(ul);
    return art;
  }

  var run = 0;
  function show(q, field) {
    var S = window.AtlasSearch;
    var words = S && S.queryTokens ? S.queryTokens(q) : [];
    out.textContent = '';
    if (!words.length) { status.textContent = q ? W.no_words : ''; return; }
    var mine = ++run;
    status.textContent = W.searching;
    var idxP = getJSON('citations-index.json');
    Promise.all([idxP, S.labels().catch(function () { return {}; })]).then(function (r) {
      var idx = r[0], lab = r[1];
      var other = field === 'author' ? 'text' : null;
      return Promise.all([postings(idx, field, words), other ? postings(idx, other, words) : Promise.resolve(null)])
        .then(function (lists) {
          var hits = lists[0], wide = lists[1];
          return entries(idx, hits).then(function (es) {
            idx._entries = idx._entries || {};
            hits.forEach(function (i, k) { idx._entries[i] = es[k]; });
            return { idx: idx, lab: lab, hits: hits, wide: wide };
          });
        });
    }).then(function (res) {
      if (mine !== run) return;
      var groups = byPaper(res.idx, res.hits);
      var refs = groups.reduce(function (s, g) { return s + g.refs.length; }, 0);
      var cov = (res.idx.coverage || {}).current || {};
      var lines = [];
      lines.push(groups.length
        ? fmt(groups.length === 1 ? W.found_one : W.found, { papers: n(groups.length), refs: n(refs), q: q })
        : fmt(field === 'author' ? W.none_author : W.none_text, { q: q }));
      status.textContent = lines.join(' ');
      if (field === 'author') {
        var extra = res.wide ? res.wide.length - res.hits.length : 0;
        var note = el('p', 'cite-note');
        note.appendChild(document.createTextNode(fmt(W.coverage, { missing: n(cov.structured_authors_unavailable || 0), total: n(cov.bibliography_records || 0) }) + ' '));
        if (extra > 0) {
          var b = el('button', 'btn btn--quiet cite-wide', fmt(extra === 1 ? W.wider_one : W.wider, { n: n(extra) }));
          b.type = 'button';
          b.addEventListener('click', function () { setField('text'); show(q, 'text'); });
          note.appendChild(b);
        }
        out.appendChild(note);
      }
      var list = el('div', 'cite-hits');
      out.appendChild(list);
      var shown = 0;
      function more() {
        groups.slice(shown, shown + PAGE).forEach(function (g) { list.appendChild(paperCard(g, res.lab)); });
        shown = Math.min(groups.length, shown + PAGE);
        if (window.atlasRenderMath) window.atlasRenderMath(list);
        btn.hidden = shown >= groups.length;
        btn.textContent = fmt(W.more, { n: n(groups.length - shown) });
      }
      var btn = el('button', 'btn cite-more');
      btn.type = 'button';
      btn.addEventListener('click', more);
      out.appendChild(btn);
      more();
    }).catch(function () {
      if (mine === run) status.textContent = W.failed;
    });
  }

  var radios = form.querySelectorAll('input[name="cite-field"]');
  function field() { for (var i = 0; i < radios.length; i++) if (radios[i].checked) return radios[i].value; return 'author'; }
  function setField(v) { for (var i = 0; i < radios.length; i++) radios[i].checked = radios[i].value === v; }
  function submit() {
    var q = input.value.trim(), f = field();
    try {
      var u = new URL(location.href);
      if (q) { u.searchParams.set('cites', q); u.searchParams.set('in', f); } else { u.searchParams.delete('cites'); u.searchParams.delete('in'); }
      history.replaceState(null, '', u.pathname + u.search + '#find-citations');
    } catch (e) { /* a file: page */ }
    show(q, f);
  }
  form.addEventListener('submit', function (ev) { ev.preventDefault(); submit(); });
  for (var i = 0; i < radios.length; i++) radios[i].addEventListener('change', function () { if (input.value.trim()) submit(); });
  /* Example names fill the box and search. */
  Array.prototype.forEach.call(document.querySelectorAll('[data-cite-try]'), function (b) {
    b.addEventListener('click', function () { input.value = b.getAttribute('data-cite-try'); setField('author'); submit(); });
  });
  try {
    var p = new URLSearchParams(location.search);
    if (p.get('cites')) { input.value = p.get('cites'); setField(p.get('in') === 'text' ? 'text' : 'author'); show(input.value.trim(), field()); }
  } catch (e) { /* no URLSearchParams */ }
})();
