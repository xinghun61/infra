// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {hasPrefix} from './helpers.js';

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
