/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {assert} from 'chai';
import {MrBulkApprovalUpdate, NO_APPROVALS_MESSAGE,
  NO_UPDATES_MESSAGE} from './mr-bulk-approval-update.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import AutoRefreshPrpcClient from '../../static/js/prpc.js';

let element;
let prpcStub;
let root;

suite('mr-bulk-approval-update');

beforeEach(() => {
  element = document.createElement('mr-bulk-approval-update');
  document.body.appendChild(element);

  root = element.shadowRoot;

  window.CS_env = {
    token: 'rutabaga-token',
    tokenExpiresSec: 1234,
    app_version: 'rutabaga-version',
  };
  window.prpcClient = new AutoRefreshPrpcClient(
    CS_env.token, CS_env.tokenExpiresSec);
  prpcStub = sinon.stub(window.prpcClient, 'call');
});

afterEach(() => {
  document.body.removeChild(element);
  prpcStub.restore();
});

test('initializes', () => {
  assert.instanceOf(element, MrBulkApprovalUpdate);
});

test('_computeIssueRefs: missing information', () => {
  element.projectName = 'chromium';
  assert.equal(element.issueRefs.length, 0);

  element.projectName = null;
  element.localIdsStr = '1,2,3,5';
  assert.equal(element.issueRefs.length, 0);

  element.localIdsStr = null;
  assert.equal(element.issueRefs.length, 0);
});

test('_computeIssueRefs: normal', () => {
  let project = 'chromium';
  element.projectName = project;
  element.localIdsStr = '1,2,3';
  assert.deepEqual(element.issueRefs, [
    {projectName: project, localId: '1'},
    {projectName: project, localId: '2'},
    {projectName: project, localId: '3'},
  ]);
});

test('fetchApprovals: applicable fields exist', async () => {
  let responseFieldDefs = [
    {fieldRef: {type: 'INT_TYPE'}},
    {fieldRef: {type: 'APPROVAL_TYPE'}},
    {fieldRef: {type: 'APPROVAL_TYPE'}},
  ];
  const promise = Promise.resolve({fieldDefs: responseFieldDefs});
  prpcStub.returns(promise);

  sinon.spy(element, 'fetchApprovals');
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

test('fetchApprovals: applicable fields dont exist', async () => {
  const promise = Promise.resolve({fieldDefs: []});
  prpcStub.returns(promise);
  root.querySelector('.js-showApprovals').click();

  await promise;

  assert.equal(element.approvals.length, 0);
  assert.equal(NO_APPROVALS_MESSAGE, element.errorMessage);
});

test('save: normal', async () => {
  const promise = Promise.resolve({issueRefs: [{localId: '1'}, {localId: '3'}]});
  prpcStub.returns(promise);
  let fieldDefs = [
    {fieldRef: {fieldName: 'Approval-One', type: 'APPROVAL_TYPE'}},
    {fieldRef: {fieldName: 'Approval-Two', type: 'APPROVAL_TYPE'}},
  ];
  element.set('approvals', fieldDefs);
  element.projectName = 'chromium';
  element.localIdsStr = '1,2,3';

  // Wait for dom-if template stamping.
  flush();

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
  root.querySelectorAll('input, textarea, select').forEach(input => {
    assert.equal(input.disabled, false);
  });

  // Assert all inputs cleared.
  root.querySelectorAll('input, textarea').forEach(input => {
    assert.equal(input.value, '');
  });
  root.querySelectorAll('select').forEach(select => {
    assert.equal(select.selectedIndex, 0);
  });

  // Assert BulkUpdateApprovals correctly called.
  let expectedMessage = {
    approvalDelta: {status: "NOT_APPROVED"},
    commentContent: "comment",
    fieldRef: fieldDefs[0].fieldRef,
    issueRefs: element.issueRefs,
    send_email: true,
  };
  sinon.assert.calledWith(
      prpcStub,
      'monorail.Issues',
      'BulkUpdateApprovals',
      expectedMessage);
});

test('save: no updates', async () => {
  const promise = Promise.resolve({issueRefs: []});
  prpcStub.returns(promise);
  let fieldDefs = [
    {fieldRef: {fieldName: 'Approval-One', type: 'APPROVAL_TYPE'}},
    {fieldRef: {fieldName: 'Approval-Two', type: 'APPROVAL_TYPE'}},
  ];
  element.set('approvals', fieldDefs);
  element.projectName = 'chromium';
  element.localIdsStr = '1,2,3';

  // Wait for dom-if template stamping.
  flush();

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
  root.querySelectorAll('input, textarea, select').forEach(input => {
    assert.equal(input.disabled, false);
  });
});
