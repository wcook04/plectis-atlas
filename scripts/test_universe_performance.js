'use strict';
// Counts fitting work through the production paint call and production label fitter.
// Canvas is deliberately replaced with a deterministic width metric: this measures
// cache work, not browser frame time or typographic fidelity.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../site/assets/universe.js'), 'utf8');
const start = source.indexOf('    function labelTokens(');
const end = source.indexOf('    function drawText(', start);
assert.ok(start >= 0 && end > start);
const paintCall = source.match(/var t = famLabel\(fj, ([^;]+?)\), f2 = fams\[fj\]\.data;/);
assert.ok(paintCall, 'production family label paint call is present');
let widths = 0;
const titles = ['Log abundance for compact Kähler spaces under logarithmic Iitaka subadditivity',
  'Function-field reconstruction from Milnor K-theory and Galois data',
  'Restricted geometric Langlands, global Arthur enhancements, and generic Ramanujan'];
const c = vm.createContext({
  D: { families: titles.map(title => ({ title })) }, labelCache: {}, SERIF: 'serif',
  clamp: (x, a, b) => Math.max(a, Math.min(b, x)),
  textWidth: (text, font) => { widths++; return text.length * parseFloat(font.split(' ')[1]) * 0.5; },
  chart: { start: 1, to: { nodes: titles.map(() => ({ r: 70 })) } }, moving: true,
  fams: titles.map(() => ({ data: {} })), n: {}, fj: 0
});
vm.runInContext(source.slice(start, end), c);
const call = `famLabel(fj, ${paintCall[1]})`;
let firstFrameWidths;
for (let frame = 0; frame < 30; frame++) {
  for (let i = 0; i < titles.length; i++) {
    c.fj = i; c.n = { r: 40 + frame * 1.01 };
    vm.runInContext(call, c);
  }
  if (frame === 0) firstFrameWidths = widths;
  else assert.equal(widths, firstFrameWidths, 'later animation frames perform no fresh fitting work');
}
assert.equal(Object.keys(c.labelCache).length, titles.length,
  'animation fits each family once at its stable target radius');
const warm = widths;
c.chart.start = 0; c.moving = false; c.n = { r: 70 };
for (let i = 0; i < titles.length; i++) { c.fj = i; vm.runInContext(call, c); }
assert.equal(widths, warm, 'settled paint reuses animation target fits');
// A tiny radius cannot fit even one glyph plus a discretionary hyphen. The real
// tokenizer must still consume input, rather than spinning on a negative limit.
const tiny = vm.runInContext("labelTokens('UnbreakableWord', 1)", c, { timeout: 1000 });
assert.ok(tiny.length > 0 && tiny.length <= 'UnbreakableWord'.length);
console.log(`universe performance: 30 frames, ${titles.length} cached family fits, ${widths} width calls`);
