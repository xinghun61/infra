// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrProfilePage} from './mr-profile-page.js';


let element;

describe('mr-profile-page', () => {
  beforeEach(() => {
    element = document.createElement('mr-profile-page');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrProfilePage);
  });
});
