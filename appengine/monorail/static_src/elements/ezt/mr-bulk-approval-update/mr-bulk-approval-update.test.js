// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrBulkApprovalUpdate, NO_APPROVALS_MESSAGE,
  NO_UPDATES_MESSAGE} from './mr-bulk-approval-update.js';
import {prpcClient} from 'prpc-client-instance.js';

let element;
let root;

describe('mr-bulk-approval-update', () => {
  beforeEach(() => {
    element = document.createElement('mr-bulk-approval-update');
    document.body.appendChild(element);

    root = element.shadowRoot;
    sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);
    prpcClient.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrBulkApprovalUpdate);
  });

  it('_computeIssueRefs: missing information', () => {
    element.projectName = 'chromium';
    assert.equal(element.issueRefs.length, 0);

    element.projectName = null;
    element.localIdsStr = '1,2,3,5';
    assert.equal(element.issueRefs.length, 0);

    element.localIdsStr = null;
    assert.equal(element.issueRefs.length, 0);
  });

  it('_computeIssueRefs: normal', () => {
    const project = 'chromium';
    element.projectName = project;
    element.localIdsStr = '1,2,3';
    assert.deepEqual(element.issueRefs, [
      {projectName: project, localId: '1'},
      {projectName: project, localId: '2'},
      {projectName: project, localId: '3'},
    ]);
  });

  it('fetchApprovals: applicable fields exist', async () => {
    const responseFieldDefs = [
      {fieldRef: {type: 'INT_TYPE'}},
      {fieldRef: {type: 'APPROVAL_TYPE'}},
      {fieldRef: {type: 'APPROVAL_TYPE'}},
    ];
    const promise = Promise.resolve({fieldDefs: responseFieldDefs});
    prpcClient.call.returns(promise);

    sinon.spy(element, 'fetchApprovals');

    await element.updateComplete;

    root.querySelector('.js-showApprovals').click();
    assert.isTrue(element.fetchApprovals.calledOnce);

    // Wait for promise in fetchApprovals to resolve.
    await promise;

    assert.deepEqual([
      {fieldRef: {type: 'APPROVAL_TYPE'}},
      {fieldRef: {type: 'APPROVAL_TYPE'}},
    ], element.approvals);
    assert.equal(null, element.errorMessage);
  });

  it('fetchApprovals: applicable fields dont exist', async () => {
    const promise = Promise.resolve({fieldDefs: []});
    prpcClient.call.returns(promise);

    await element.updateComplete;

    root.querySelector('.js-showApprovals').click();

    await promise;

    assert.equal(element.approvals.length, 0);
    assert.equal(NO_APPROVALS_MESSAGE, element.errorMessage);
  });

  it('save: normal', async () => {
    const promise =
      Promise.resolve({issueRefs: [{localId: '1'}, {localId: '3'}]});
    prpcClient.call.returns(promise);
    const fieldDefs = [
      {fieldRef: {fieldName: 'Approval-One', type: 'APPROVAL_TYPE'}},
      {fieldRef: {fieldName: 'Approval-Two', type: 'APPROVAL_TYPE'}},
    ];
    element.approvals = fieldDefs;
    element.projectName = 'chromium';
    element.localIdsStr = '1,2,3';

    await element.updateComplete;

    root.querySelector('#commentText').value = 'comment';
    root.querySelector('#statusInput').value = 'NotApproved';
    root.querySelector('.js-save').click();

    // Wait for promise in save() to resolve.
    await promise;

    // Assert messages correct
    assert.equal(
        true,
        element.responseMessage.includes(
            'Updated Approval-One in issues: 1, 3 (2 of 3).'));
    assert.equal('', element.errorMessage);

    // Assert all inputs not disabled.
    root.querySelectorAll('input, textarea, select').forEach((input) => {
      assert.equal(input.disabled, false);
    });

    // Assert all inputs cleared.
    root.querySelectorAll('input, textarea').forEach((input) => {
      assert.equal(input.value, '');
    });
    root.querySelectorAll('select').forEach((select) => {
      assert.equal(select.selectedIndex, 0);
    });

    // Assert BulkUpdateApprovals correctly called.
    const expectedMessage = {
      approvalDelta: {status: 'NOT_APPROVED'},
      commentContent: 'comment',
      fieldRef: fieldDefs[0].fieldRef,
      issueRefs: element.issueRefs,
      send_email: true,
    };
    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Issues',
        'BulkUpdateApprovals',
        expectedMessage);
  });

  it('save: no updates', async () => {
    const promise = Promise.resolve({issueRefs: []});
    prpcClient.call.returns(promise);
    const fieldDefs = [
      {fieldRef: {fieldName: 'Approval-One', type: 'APPROVAL_TYPE'}},
      {fieldRef: {fieldName: 'Approval-Two', type: 'APPROVAL_TYPE'}},
    ];
    element.approvals = fieldDefs;
    element.projectName = 'chromium';
    element.localIdsStr = '1,2,3';

    await element.updateComplete;

    root.querySelector('#commentText').value = 'comment';
    root.querySelector('#statusInput').value = 'NotApproved';
    root.querySelector('.js-save').click();

    // Wait for promise in save() to resolve
    await promise;

    // Assert messages correct.
    assert.equal('', element.responseMessage);
    assert.equal(NO_UPDATES_MESSAGE, element.errorMessage);

    // Assert inputs not cleared.
    assert.equal(root.querySelector('#commentText').value, 'comment');
    assert.equal(root.querySelector('#statusInput').value, 'NotApproved');

    // Assert inputs not disabled.
    root.querySelectorAll('input, textarea, select').forEach((input) => {
      assert.equal(input.disabled, false);
    });
  });
});
