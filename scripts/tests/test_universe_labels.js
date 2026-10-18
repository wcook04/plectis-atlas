/* Regressions for compound names and the circular bounds of rendered labels. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../site/assets/universe.js'), 'utf8');
const begin = source.indexOf('    function labelTokens(');
const end = source.indexOf('    function drawText(', begin);
assert.ok(begin > 0 && end > begin);
// Deliberately predictable font metrics isolate wrapping from the browser's font loader.
const textWidth = (text, font) => {
  const size = +font.match(/([\d.]+)px/)[1];
  return Array.from(text).reduce((sum, c) => sum + (c === ' ' ? .28 : /[il.,'-]/.test(c) ? .26 : .55) * size, 0);
};
const fixture = [
  'The ordinary-double-point volume gap',
  'Kobayashi’s canonical-ampleness conjecture',
  'A characteristic-zero counterexample to Lipman–Zariski',
  'A stable-coordinate counterexample in four variables',
  'The Campana–Peternell conjecture in dimension six',
  'The irrationality exponent of π is 2',
  'The equivariant cohomological Hikita conjecture',
  'Supercalifragilisticexpialidocious and its applications'
];
const families = process.argv[2] ? JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).families : [];
const titles = fixture.concat(families.map(f => f.title));
const c = vm.createContext({ Math, Array, Object, textWidth, SERIF: 'serif', labelCache: {},
  clamp: (v, lo, hi) => Math.min(hi, Math.max(lo, v)), D: { families: titles.map(title => ({title})) } });
vm.runInContext(source.slice(begin, end), c);
for (const radius of [40, 44.3, 65.2, 90]) {
  for (let i = 0; i < titles.length; i++) {
    const label = c.famLabel(i, radius);
    assert.ok(label.lines.length > 0 && label.size >= 11);
    assert.notEqual(label.lines.join('').trim(), '…', titles[i]);
    assert.ok(!/^(The|A|An)\s*…$/.test(label.lines.join(' ')), JSON.stringify({title:titles[i],radius,label,tokens:c.labelTokens(titles[i],radius)}));
    label.lines.forEach((line, j) => {
      const edge = Math.abs(-label.lines.length * label.lead / 2 + (j + .5) * label.lead) + label.lead * .45;
      const width = 2 * Math.sqrt(radius * radius - edge * edge) * .9 - 6;
      assert.ok(edge < radius && textWidth(line, label.font) <= width + .001,
        `${titles[i]}: ${line} exceeds its circle at radius ${radius}`);
    });
  }
}
const ordinary = c.famLabel(0, 65.2);
assert.ok(!ordinary.lines.join('').includes('…'), 'the reported compound title fits in full');
assert.ok(ordinary.lines.join(' ').includes('volume gap'));
assert.equal(c.labelTokens('The ordinary-double-point volume gap', 65.2).map(t => t.join + t.text).join(''), fixture[0]);
console.log(`PASS circular text fitting: ${titles.length} titles at four radii`);
