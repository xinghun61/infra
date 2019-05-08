// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrMoveCopyIssue} from './mr-move-copy-issue.js';

let element;

describe('mr-move-copy-issue', () => {
  beforeEach(() => {
    element = document.createElement('mr-move-copy-issue');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrMoveCopyIssue);
  });
});
