// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsHeader} from './chops-header.js';

let element;

suite('chops-header', () => {
  setup(() => {
    element = document.createElement('chops-header');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, ChopsHeader);
  });
});
