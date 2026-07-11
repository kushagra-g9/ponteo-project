'use strict';

const { sum } = require('../src/sum');

describe('sum', () => {
  test('adds two positive numbers', () => {
    expect(sum(2, 3)).toBe(5);
  });

  test('handles negative numbers', () => {
    expect(sum(-2, 3)).toBe(1);
  });

  test('handles zero', () => {
    expect(sum(0, 0)).toBe(0);
  });

  test('throws on non-finite input', () => {
    expect(() => sum(NaN, 1)).toThrow(TypeError);
  });
});
