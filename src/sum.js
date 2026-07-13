'use strict';

/**
 * Add two finite numbers.
 * Supports integers and decimals (e.g. sum(1.5, 2.5) === 4).
 * @param {number} a
 * @param {number} b
 * @returns {number}
 */
function sum(a, b) {
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    throw new TypeError('sum expects two finite number');
  }
  return a + b;
}

module.exports = { sum };
