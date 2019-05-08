// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {ChopsCollapse} from './chops-collapse.js';


let element;
describe('chops-collapse', () => {
  beforeEach(() => {
    element = document.createElement('chops-collapse');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsCollapse);
  });

  it('toggling chops-collapse changes aria-hidden', () => {
    element.opened = true;

    assert.isNull(element.getAttribute('aria-hidden'));

    element.opened = false;

    assert.isDefined(element.getAttribute('aria-hidden'));
  });
});
