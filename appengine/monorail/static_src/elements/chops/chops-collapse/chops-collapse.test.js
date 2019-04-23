// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsCollapse} from './chops-collapse.js';


let element;
suite('chops-collapse', () => {
  setup(() => {
    element = document.createElement('chops-collapse');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, ChopsCollapse);
  });

  test('toggling chops-collapse changes aria-hidden', () => {
    element.opened = true;

    assert.isNull(element.getAttribute('aria-hidden'));

    element.opened = false;

    assert.isDefined(element.getAttribute('aria-hidden'));
  });
});
