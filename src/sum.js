'use strict';

/**
 * Add two finite numbers.
 * @param {number} a
 * @param {number} b
 * @returns {number}
 */
function sum(a, b) {
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    throw new TypeError('sum expects two finite numbers');
  }
  return a + b;
}

module.exports = { sum };
// pipeline test 20260711
