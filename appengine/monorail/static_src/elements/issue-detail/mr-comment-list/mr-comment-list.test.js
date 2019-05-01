// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrCommentList} from './mr-comment-list.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;

suite('mr-comment-list', () => {
  setup(() => {
    element = document.createElement('mr-comment-list');
    document.body.appendChild(element);
    element.comments = [
      {
        canFlag: true,
        localId: 898395,
        canDelete: true,
        projectName: 'chromium',
        commenter: {
          displayName: 'user@example.com',
          userId: '12345',
        },
        content: 'foo',
        sequenceNum: 1,
        timestamp: 1549319989,
      },
      {
        canFlag: true,
        localId: 898395,
        canDelete: true,
        projectName: 'chromium',
        commenter: {
          displayName: 'user@example.com',
          userId: '12345',
        },
        content: 'foo',
        sequenceNum: 2,
        timestamp: 1549320089,
      },
      {
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
        timestamp: 1549320189,
      },
    ];

    sinon.stub(window, 'requestAnimationFrame').callsFake((func) => func());
  });

  teardown(() => {
    document.body.removeChild(element);

    window.requestAnimationFrame.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrCommentList);
  });

  test('scrolls to comment', async () => {
    flush();

    const commentElements = element.shadowRoot.querySelectorAll('mr-comment');
    const commentElement = commentElements[commentElements.length - 1];
    sinon.stub(commentElement, 'scrollIntoView');

    element.focusId = 'c3';

    flush();
    await commentElement.updateComplete;

    assert.isTrue(element._hideComments);
    assert.isTrue(commentElement.scrollIntoView.calledOnce);

    commentElement.scrollIntoView.restore();
  });

  test('scrolls to hidden comment', () => {
    flush();

    element.focusId = 'c1';

    flush();

    assert.isFalse(element._hideComments);
    // TODO: Check that the comment has been scrolled into view.
  });

  test('doesnt scroll to unknown comment', () => {
    flush();

    element.focusId = 'c100';

    flush();

    assert.isTrue(element._hideComments);
  });

  test('edit-metadata is displayed if user has addissuecomment', () => {
    element.issuePermissions = ['addissuecomment'];

    flush();

    assert.isNull(
      element.shadowRoot.querySelector('.edit-slot').getAttribute('hidden'));
  });

  test('edit-metadata is hidden if user has no addissuecomment', () => {
    element.issuePermissions = [];

    flush();

    assert.isNotNull(
      element.shadowRoot.querySelector('.edit-slot').getAttribute('hidden'));
  });
});
