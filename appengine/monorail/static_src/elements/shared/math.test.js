// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {linearRegression} from './math.js';

describe('linearRegression', () => {
  it('calculate slope and intercept using formula', () => {
    const values = [0, 1, 2, 3, 4, 5, 6];
    const [slope, intercept] = linearRegression(values, 7);
    assert.equal(slope, 1);
    assert.equal(intercept, 0);
  });

  it('calculate slope and intercept using last n data points', () => {
    const values = [0, 1, 0, 3, 5, 7, 9];
    const [slope, intercept] = linearRegression(values, 4);
    assert.equal(slope, 2);
    assert.equal(intercept, 3);
  });
});
