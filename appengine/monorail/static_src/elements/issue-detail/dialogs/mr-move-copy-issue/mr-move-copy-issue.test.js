// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrMoveCopyIssue} from './mr-move-copy-issue.js';

let element;

suite('mr-move-copy-issue', () => {
  setup(() => {
    element = document.createElement('mr-move-copy-issue');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrMoveCopyIssue);
  });
});
