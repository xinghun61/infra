// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrPhase} from './mr-phase.js';


let element;

suite('mr-phase', () => {
  setup(() => {
    element = document.createElement('mr-phase');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrPhase);
  });
});
