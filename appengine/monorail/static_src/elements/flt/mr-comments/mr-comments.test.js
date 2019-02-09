// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrComments} from './mr-comments.js';
import {actionType} from '../../redux/redux-mixin.js';


let element;

suite('mr-comments', () => {
  setup(() => {
    element = document.createElement('mr-comments');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrComments);
  });
});
