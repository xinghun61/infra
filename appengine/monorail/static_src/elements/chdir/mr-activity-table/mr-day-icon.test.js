// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrDayIcon} from './mr-day-icon.js';


let element;

describe('mr-day-icon', () => {
  beforeEach(() => {
    element = document.createElement('mr-day-icon');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrDayIcon);
  });
});
