// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditIssue} from './mr-edit-issue.js';
import {actionType} from '../../redux/redux-mixin.js';


let element;

suite('mr-edit-issue');

beforeEach(() => {
  element = document.createElement('mr-edit-issue');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
  element.dispatchAction({type: actionType.RESET_STATE});
});

test('initializes', () => {
  assert.instanceOf(element, MrEditIssue);
});
