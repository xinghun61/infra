// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrComment} from './mr-comment.js';


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
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrComment);
  });

  test('scrolls to comment', async () => {
    sinon.stub(element, 'scrollIntoView');

    element.highlighted = true;
    await element.updateComplete;

    assert.isTrue(element.scrollIntoView.calledOnce);

    element.scrollIntoView.restore();
  });
});
