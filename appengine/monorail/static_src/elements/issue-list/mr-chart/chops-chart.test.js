// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsChart} from './chops-chart.js';


let element;

describe('chops-chart', () => {
  beforeEach(() => {
    element = document.createElement('chops-chart');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsChart);
  });
});
