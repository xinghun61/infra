// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrComment} from './mr-comment.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {resetState} from '../../redux/redux-mixin.js';


let element;

suite('mr-comment', () => {
  setup(() => {
    element = document.createElement('mr-comment');
    element.comment = {
      canFlag: true,
      localId: 898395,
      canDelete: true,
      projectName: 'chromium',
      commenter: {
        displayName: 'user@example.com',
        userId: '12345',
      },
      content: 'foo',
      sequenceNum: 3,
      timestamp: 1549319989,
    };
    document.body.appendChild(element);

    sinon.stub(window, 'requestAnimationFrame').callsFake((func) => func());
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction(resetState());

    window.requestAnimationFrame.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrComment);
  });

  test('scrolls to comment', () => {
    flush();

    sinon.stub(element, 'scrollIntoView');

    element.focusId = 'c3';

    assert.isTrue(element.scrollIntoView.calledOnce);

    element.scrollIntoView.restore();
  });
});
