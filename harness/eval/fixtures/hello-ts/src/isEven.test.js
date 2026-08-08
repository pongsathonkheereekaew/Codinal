import test from 'node:test';
import assert from 'node:assert/strict';
import { isEven } from './isEven.js';

test('isEven returns true for even numbers', () => {
  assert.equal(isEven(2), true);
});
