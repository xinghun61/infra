// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {hasPrefix, immutableSplice} from './helpers.js';

describe('hasPrefix', () => {
  it('only true when has prefix', () => {
    assert.isFalse(hasPrefix('teststring', 'test-'));
    assert.isFalse(hasPrefix('stringtest-', 'test-'));
    assert.isFalse(hasPrefix('^test-$', 'test-'));
    assert.isTrue(hasPrefix('test-', 'test-'));
    assert.isTrue(hasPrefix('test-fsdfsdf', 'test-'));
  });

  it('ignores case when checking prefix', () => {
    assert.isTrue(hasPrefix('TEST-string', 'test-'));
    assert.isTrue(hasPrefix('test-string', 'test-'));
    assert.isTrue(hasPrefix('tEsT-string', 'test-'));
  });
});

describe('immutableSplice', () => {
  it('does not edit original array', () => {
    const arr = ['apples', 'pears', 'oranges'];

    assert.deepEqual(immutableSplice(arr, 1, 1),
      ['apples', 'oranges']);

    assert.deepEqual(arr, ['apples', 'pears', 'oranges']);
  });

  it('removes multiple items', () => {
    const arr = [1, 2, 3, 4, 5, 6];

    assert.deepEqual(immutableSplice(arr, 1, 0), [1, 2, 3, 4, 5, 6]);
    assert.deepEqual(immutableSplice(arr, 1, 4), [1, 6]);
    assert.deepEqual(immutableSplice(arr, 0, 6), []);
  });

  it('adds items', () => {
    const arr = [1, 2, 3];

    assert.deepEqual(immutableSplice(arr, 1, 1, 4, 5, 6), [1, 4, 5, 6, 3]);
    assert.deepEqual(immutableSplice(arr, 2, 1, 4, 5, 6), [1, 2, 4, 5, 6]);
    assert.deepEqual(immutableSplice(arr, 0, 0, -3, -2, -1, 0),
      [-3, -2, -1, 0, 1, 2, 3]);
  });
});
