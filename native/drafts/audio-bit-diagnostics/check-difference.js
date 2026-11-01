const fs = require('node:fs');
const path = require('node:path');
const floatDifference = new Function(fs.readFileSync(path.join(__dirname, 'difference.js'), 'utf8') + '\nreturn floatDifference;')();

const assert = require("node:assert/strict");
const f32 = (...bits) => new Float32Array(Uint32Array.from(bits).buffer);
const same = floatDifference(f32(0x3f000000), f32(0x3f000000));
assert.equal(same.changedSamples, 0); assert.equal(same.maximumUlpDistance, 0);
for (const value of [0x3f000000, 0xbe800000, 1, 0x80000001]) {
  const diff = floatDifference(f32(value), f32(value ^ 1));
  assert.equal(diff.changedSamples, 1); assert.equal(diff.maximumUlpDistance, 1);
}
const zeros = floatDifference(f32(0), f32(0x80000000));
assert.equal(zeros.changedSamples, 1); assert.equal(zeros.signedZeroDifferences, 1);
assert.equal(zeros.maximumUlpDistance, 0); assert.equal(zeros.maximumAbsoluteDifference, 0);
const nonfinite = floatDifference(f32(0x7f800000, 0x7fc00001), f32(0xff800000, 0x7fc00002));
assert.equal(nonfinite.nonFinitePairs, 2); assert.equal(nonfinite.finitePairs, 0);
assert.equal(nonfinite.maximumUlpDistance, null); assert.equal(nonfinite.changedSamples, 2);
assert.throws(() => floatDifference(new Float32Array(1), new Float32Array(2)), TypeError);
assert.throws(() => floatDifference(new Float64Array(1), new Float32Array(1)), TypeError);
const backing = f32(0x3f000000, 0xbe800000, 0x3f000001);
assert.equal(floatDifference(backing.subarray(1), backing.slice(1)).changedSamples, 0);
assert.deepEqual(floatDifference(new Float32Array(), new Float32Array()), {
  samples: 0, changedSamples: 0, finitePairs: 0, nonFinitePairs: 0, signedZeroDifferences: 0,
  maximumUlpDistance: null, maximumAbsoluteDifference: null});
console.log("10 diagnostic categories passed; no browser or Audio policy repair claimed");
