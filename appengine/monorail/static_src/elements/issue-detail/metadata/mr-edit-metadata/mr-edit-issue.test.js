// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditIssue} from './mr-edit-issue.js';
import sinon from 'sinon';

let element;

describe('mr-edit-issue', () => {
  beforeEach(() => {
    element = document.createElement('mr-edit-issue');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrEditIssue);
  });

  it('scrolls into view', async () => {
    await element.updateComplete;

    const header = element.shadowRoot.querySelector('#makechanges');
    sinon.stub(header, 'scrollIntoView');

    element.focusId = 'makechanges';
    await element.updateComplete;

    assert.isTrue(header.scrollIntoView.calledOnce);

    header.scrollIntoView.restore();
  });

  it('shows current status even if not defined for project', async () => {
    await element.updateComplete;

    const editMetadata = element.shadowRoot.querySelector('mr-edit-metadata');
    assert.deepEqual(editMetadata.statuses, []);

    element.projectConfig = {statusDefs: [
      {status: 'hello'},
      {status: 'world'},
    ]};

    await editMetadata.updateComplete;

    assert.deepEqual(editMetadata.statuses, [
      {status: 'hello'},
      {status: 'world'},
    ]);

    element.issue = {
      statusRef: {status: 'hello'},
    };

    await editMetadata.updateComplete;

    assert.deepEqual(editMetadata.statuses, [
      {status: 'hello'},
      {status: 'world'},
    ]);

    element.issue = {
      statusRef: {status: 'weirdStatus'},
    };

    await editMetadata.updateComplete;

    assert.deepEqual(editMetadata.statuses, [
      {status: 'weirdStatus'},
      {status: 'hello'},
      {status: 'world'},
    ]);
  });

  it('ignores deprecated statuses, unless used on current issue', async () => {
    await element.updateComplete;

    const editMetadata = element.shadowRoot.querySelector('mr-edit-metadata');
    assert.deepEqual(editMetadata.statuses, []);

    element.projectConfig = {statusDefs: [
      {status: 'new'},
      {status: 'accepted', deprecated: false},
      {status: 'compiling', deprecated: true},
    ]};

    await editMetadata.updateComplete;

    assert.deepEqual(editMetadata.statuses, [
      {status: 'new'},
      {status: 'accepted', deprecated: false},
    ]);


    element.issue = {
      statusRef: {status: 'compiling'},
    };

    await editMetadata.updateComplete;

    assert.deepEqual(editMetadata.statuses, [
      {status: 'compiling'},
      {status: 'new'},
      {status: 'accepted', deprecated: false},
    ]);
  });

  it('Filter out empty or deleted user owners', () => {
    assert.equal(element._ownerDisplayName({displayName: '----'}), '');
    assert.equal(
      element._ownerDisplayName({displayName: 'a_deleted_user'}),
      '');
    assert.equal(
      element._ownerDisplayName({
        displayName: 'test@example.com',
        userId: '1234',
      }),
      'test@example.com');
  });
});
