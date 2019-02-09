// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrFieldValues} from './mr-field-values.js';


let element;

suite('mr-field-values', () => {
  setup(() => {
    element = document.createElement('mr-field-values');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrFieldValues);
  });
});
