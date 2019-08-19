// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrGridDropdown} from './mr-grid-dropdown';

let element;

describe('mr-grid-dropdown', () => {
  beforeEach(() => {
    element = document.createElement('mr-grid-dropdown');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrGridDropdown);
  });
});
