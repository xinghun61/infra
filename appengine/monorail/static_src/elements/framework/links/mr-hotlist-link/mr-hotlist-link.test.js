// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrHotlistLink} from './mr-hotlist-link.js';

let element;

suite('mr-hotlist-link', () => {
  setup(() => {
    element = document.createElement('mr-hotlist-link');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrHotlistLink);
  });
});
