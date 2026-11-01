  const floatDifference = (left, right) => {
    if (!(left instanceof Float32Array) || !(right instanceof Float32Array) || left.length !== right.length) {
      throw new TypeError("Expected equal-length Float32Array diagnostics");
    }
    const lhs = new Uint32Array(left.buffer, left.byteOffset, left.length);
    const rhs = new Uint32Array(right.buffer, right.byteOffset, right.length);
    const ordered = (bits) => (bits >>> 31) ? 0x80000000 - (bits & 0x7fffffff) : 0x80000000 + bits;
    let changedSamples = 0, finitePairs = 0, nonFinitePairs = 0, signedZeroDifferences = 0;
    let maximumUlpDistance = 0, maximumAbsoluteDifference = 0;
    for (let index = 0; index < left.length; ++index) {
      if (lhs[index] !== rhs[index]) changedSamples += 1;
      if (!Number.isFinite(left[index]) || !Number.isFinite(right[index])) {
        nonFinitePairs += 1;
        continue;
      }
      finitePairs += 1;
      if (left[index] === 0 && right[index] === 0 && lhs[index] !== rhs[index]) signedZeroDifferences += 1;
      maximumUlpDistance = Math.max(maximumUlpDistance, Math.abs(ordered(lhs[index]) - ordered(rhs[index])));
      maximumAbsoluteDifference = Math.max(maximumAbsoluteDifference, Math.abs(left[index] - right[index]));
    }
    return {samples: left.length, changedSamples, finitePairs, nonFinitePairs, signedZeroDifferences,
      maximumUlpDistance: finitePairs ? maximumUlpDistance : null,
      maximumAbsoluteDifference: finitePairs ? maximumAbsoluteDifference : null};
  };
