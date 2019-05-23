// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrCommentTable} from './mr-comment-table.js';


let element;

describe('mr-comment-table', () => {
  beforeEach(() => {
    element = document.createElement('mr-comment-table');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCommentTable);
  });
});
