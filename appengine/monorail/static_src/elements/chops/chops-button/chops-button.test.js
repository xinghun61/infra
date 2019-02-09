// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsButton} from './chops-button.js';

let element;

suite('chops-button', () => {
  setup(() => {
    element = document.createElement('chops-button');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, ChopsButton);
  });

  test('chops-button can be disabled', () => {
    assert.isFalse(element.hasAttribute('disabled'));

    element.disabled = true;

    assert.isTrue(element.hasAttribute('disabled'));
  });
});
