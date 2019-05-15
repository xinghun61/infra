// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrLaunchOverview} from './mr-launch-overview.js';


let element;

describe('mr-launch-overview', () => {
  beforeEach(() => {
    element = document.createElement('mr-launch-overview');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrLaunchOverview);
  });
});
