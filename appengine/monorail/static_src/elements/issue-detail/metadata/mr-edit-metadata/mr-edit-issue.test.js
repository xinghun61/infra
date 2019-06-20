// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';
import {prpcClient} from 'prpc-client-instance.js';
import {MrEditIssue} from './mr-edit-issue.js';

let element;

describe('mr-edit-issue', () => {
  beforeEach(() => {
    element = document.createElement('mr-edit-issue');
    document.body.appendChild(element);
    sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);
    prpcClient.call.restore();
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

  it('filter out empty or deleted user owners', () => {
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

  it('presubmits issue on change', async () => {
    element.issueRef = 'issueRef';

    await element.updateComplete;
    const editMetadata = element.shadowRoot.querySelector('mr-edit-metadata');
    editMetadata.dispatchEvent(new CustomEvent('change', {
      detail: {
        delta: {
          summary: 'Summary',
        },
      },
    }));

    assert(prpcClient.call.calledWith('monorail.Issues', 'PresubmitIssue',
      {issueDelta: {summary: 'Summary'}, issueRef: 'issueRef'}));
  });

  it('predicts components for chromium', async () => {
    element.issueRef = {projectName: 'chromium'};
    element._commentsText = 'comments text';
    element.issue = {summary: 'summary'};

    await element.updateComplete;
    const editMetadata = element.shadowRoot.querySelector('mr-edit-metadata');
    editMetadata.dispatchEvent(new CustomEvent('change', {
      detail: {
        delta: {},
        commentContent: 'commentContent',
      },
    }));

    const expectedText = 'comments text\nsummary\ncommentContent';
    assert(prpcClient.call.calledWith('monorail.Features', 'PredictComponent',
      {text: expectedText, projectName: 'chromium'}));
  });

  it('does not predict components for other projects', async () => {
    element.issueRef = {projectName: 'proj'};

    await element.updateComplete;
    const editMetadata = element.shadowRoot.querySelector('mr-edit-metadata');
    editMetadata.dispatchEvent(new CustomEvent('change', {
      detail: {
        delta: {},
        commentContent: 'commentContent',
      },
    }));

    assert.isFalse(prpcClient.call.called);
  });
});
