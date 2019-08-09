// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrCommentList} from './mr-comment-list.js';


let element;

describe('mr-comment-list', () => {
  beforeEach(() => {
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

    // Stub RAF to execute immediately.
    sinon.stub(window, 'requestAnimationFrame').callsFake((func) => func());
  });

  afterEach(() => {
    document.body.removeChild(element);
    window.requestAnimationFrame.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCommentList);
  });

  it('scrolls to comment', async () => {
    await element.updateComplete;

    const commentElements = element.shadowRoot.querySelectorAll('mr-comment');
    const commentElement = commentElements[commentElements.length - 1];
    sinon.stub(commentElement, 'scrollIntoView');

    element.focusId = 'c3';

    await element.updateComplete;

    assert.isTrue(element._hideComments);
    assert.isTrue(commentElement.scrollIntoView.calledOnce);

    commentElement.scrollIntoView.restore();
  });

  it('scrolls to hidden comment', async () => {
    await element.updateComplete;

    element.focusId = 'c1';

    await element.updateComplete;

    assert.isFalse(element._hideComments);
    // TODO: Check that the comment has been scrolled into view.
  });

  it('doesnt scroll to unknown comment', async () => {
    await element.updateComplete;

    element.focusId = 'c100';

    await element.updateComplete;

    assert.isTrue(element._hideComments);
  });

  it('edit-metadata is displayed if user has addissuecomment', async () => {
    element.issuePermissions = ['addissuecomment'];

    await element.updateComplete;

    assert.isNull(
        element.shadowRoot.querySelector('.edit-slot').getAttribute('hidden'));
  });

  it('edit-metadata is hidden if user has no addissuecomment', async () => {
    element.issuePermissions = [];

    await element.updateComplete;

    assert.isNotNull(
        element.shadowRoot.querySelector('.edit-slot').getAttribute('hidden'));
  });
});
