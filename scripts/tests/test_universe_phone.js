/* The release on a phone: every subject circle holds all its families at a fingertip
   spacing, its name and counts at a readable size above them, and no circle leaves the stage.
   On a phone and on a desktop alike, a subject's dots stand in colour order (rows top to
   bottom, left to right: all, part, other, split, none), stable within a colour. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../site/assets/universe.js'), 'utf8');
function range(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `production range missing: ${start}`);
  return source.slice(a, b);
}
const text = range('    function balancedLines(', '\n    /* ---- Palette');
const lattice = range('    function latticeIn(', '    // Seventeen circles');
const phone = range('    var PHONE_DOT', '    /* ---- end of the phone release');
const toneOrder = range('    var TONE_RANK', '    /* ---- The release on a phone');
const desktop = range('    function regionLabel(', '    /* ---- The release on a phone') +
  range('    function releaseLayout()', "    // A discipline's families as one block");
// Predictable metrics, slightly wider than the site's fonts, so the fit has slack in a browser.
const textWidth = (t, font) => {
  const size = +font.match(/([\d.]+)px/)[1];
  return Array.from(t).reduce((s, c) => s + (c === ' ' ? .3 : /[il.,'-]/.test(c) ? .28 : .58) * size, 0);
};
// The seventeen subjects as the release has them (name, family count).
const subjects = [
  ['Algebraic and complex geometry', 36], ['Number theory', 31], ['Real and complex analysis', 16],
  ['Theoretical computer science', 40], ['Convex and metric geometry', 15], ['Dynamical systems and ergodic theory', 12],
  ['Combinatorics', 37], ['Probability and statistical mechanics', 29], ['Algebra', 18], ['Mathematical logic', 6],
  ['Mathematical physics', 25], ['Operator algebras', 19], ['Group theory', 14], ['Functional analysis', 11],
  ['Topology', 18], ['Differential geometry', 29], ['Partial differential equations', 16]
];
let next = 0;
const disciplines = subjects.map(([name, n]) => ({ name, families: Array.from({ length: n }, () => next++) }));
// Tones scattered through each subject's list, as the release has them; one family with none.
const TONES = ['none', 'split', 'all', 'part', 'other', 'all', 'none', 'part', 'all', 'other', 'all'];
const families = Array.from({ length: next }, (_, i) => (i === 5 ? {} : { tone: TONES[(i * 7 + 3) % TONES.length] }));
const RANK = { all: 0, part: 1, other: 2, split: 3, none: 4 };
// Read a subject's dots in place order (rows top to bottom, left to right) and check the tally.
function assertToneOrder(nodes, label) {
  disciplines.forEach(d => {
    const placed = d.families.slice().sort((a, b) => {
      const p = nodes[a], q = nodes[b];
      return Math.abs(p.y - q.y) > 0.5 ? p.y - q.y : p.x - q.x;
    });
    const ranks = placed.map(fi => RANK[families[fi].tone || 'none']);
    for (let k = 1; k < ranks.length; k++) assert.ok(ranks[k - 1] <= ranks[k], `${label}: ${d.name} reads in colour order`);
    // Stable within a colour: the list order survives inside each run.
    for (let k = 1; k < placed.length; k++) if (ranks[k - 1] === ranks[k]) assert.ok(placed[k - 1] < placed[k], `${label}: ${d.name} keeps list order within a colour`);
  });
}
for (const W of [320, 360, 375, 390, 414, 480]) {
  const c = vm.createContext({ Math, Array, Object, String, textWidth, SERIF: 'serif', SANS: 'sans',
    clamp: (v, lo, hi) => v < lo ? lo : v > hi ? hi : v, W, layoutCache: {},
    D: { disciplines, families }, fams: Array.from({ length: next }), famWeight: Array(next).fill(0.5),
    discCounts: d => `${d.families.length} families, ${Math.ceil(d.families.length / 2)} with Lean` });
  vm.runInContext(text + lattice + toneOrder + phone, c);
  const top = 180, pk = c.phonePack(top);
  assert.ok(pk, `a phone layout exists at ${W}px`);
  assert.ok(pk.dot >= 20, `families are at least 20px apart at ${W}px (got ${pk.dot})`);
  const L = c.phoneReleaseLayout(pk);
  assert.equal(L.nodes.filter(Boolean).length, next, 'every family has a dot');
  assertToneOrder(L.nodes, `phone ${W}px`);
  L.regions.forEach((g, di) => {
    assert.ok(g.x - g.r >= 0 && g.x + g.r <= W && g.y - g.r >= top && g.y + g.r <= pk.height, `${subjects[di][0]} stays on the stage at ${W}px`);
    const size = +g.lab.nf.match(/([\d.]+)px/)[1];
    assert.ok(size >= 12 && g.lab.sub >= 11, 'name and counts stay readable');
    const foot = g.ly + g.lab.h;
    disciplines[di].families.forEach(fi => {
      const q = L.nodes[fi];
      assert.ok(q.r >= 6, 'a dot is a dot, not a speck');
      assert.ok(Math.hypot(q.x - g.x, q.y - g.y) + q.r <= g.r, `${subjects[di][0]}: a dot stays inside its circle`);
      assert.ok(q.y - q.r >= foot, `${subjects[di][0]}: dots sit below the name and counts`);
    });
    L.regions.forEach((h, dj) => {
      if (dj > di) assert.ok(Math.hypot(h.x - g.x, h.y - g.y) >= g.r + h.r, 'circles do not overlap');
    });
  });
  for (let i = 0; i < next; i++) for (let j = i + 1; j < next; j++) {
    const a = L.nodes[i], b = L.nodes[j];
    assert.ok(Math.hypot(a.x - b.x, a.y - b.y) >= pk.dot * 0.999, 'dots keep their spacing');
  }
}
// The desktop release: the same packed circles, each subject's dots in colour order; a
// dot's size stays its own family's.
for (const [W, H] of [[1080, 700], [1480, 860]]) {
  const weight = Array.from({ length: next }, (_, i) => (i % 5) / 4);
  const c = vm.createContext({ Math, Array, Object, String, textWidth, SERIF: 'serif', SANS: 'sans',
    clamp: (v, lo, hi) => v < lo ? lo : v > hi ? hi : v, W, H, layoutCache: {}, narrow: () => false,
    topBand: () => 60, bottomBand: () => 50, phonePack: () => null,
    D: { disciplines, families }, fams: Array.from({ length: next }), famWeight: weight,
    discCounts: d => `${d.families.length} families, ${Math.ceil(d.families.length / 2)} with Lean` });
  vm.runInContext(text + lattice + desktop, c);
  const L = c.releaseLayout();
  assert.equal(L.nodes.filter(Boolean).length, next, 'every family has a dot');
  assertToneOrder(L.nodes, `desktop ${W}x${H}`);
  // Each subject's dot radii follow their own families' weights, wherever they stand.
  disciplines.forEach(d => {
    const unit = L.nodes[d.families[0]].r / (0.74 + 0.26 * weight[d.families[0]]);
    d.families.forEach(fi => assert.ok(Math.abs(L.nodes[fi].r - unit * (0.74 + 0.26 * weight[fi])) < 1e-9, `${d.name}: a dot keeps its own family's size`));
  });
}
console.log('PASS phone release: 17 circles, every family drawn, at six widths from 320 to 480px');
console.log('PASS colour order: each subject reads all, part, other, split, none on the phone and desktop layouts');
