/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import {assert} from 'chai';
import sinon from 'sinon';
import {MrApprovalCard} from './mr-approval-card.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;

suite('mr-approval-card');

beforeEach(() => {
  element = document.createElement('mr-approval-card');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, MrApprovalCard);
});

test('_isApprovalOwner true when user is an approver', () => {
  const userNotInList = element._computeIsApprovalOwner([
    {displayName: 'tester@user.com'},
    {displayName: 'test@notuser.com'},
    {displayName: 'hello@world.com'},
  ], 'test@user.com', []);
  assert.isFalse(userNotInList);

  const userInList = element._computeIsApprovalOwner([
    {displayName: 'tester@user.com'},
    {displayName: 'test@notuser.com'},
    {displayName: 'hello@world.com'},
    {displayName: 'test@user.com'},
  ], 'test@user.com', []);
  assert.isTrue(userInList);

  const userGroupNotInList = element._computeIsApprovalOwner([
    {displayName: 'tester@user.com'},
    {displayName: 'nongroup@group.com'},
    {displayName: 'group@nongroup.com'},
    {displayName: 'ignore@test.com'},
  ], 'test@user.com', [
    {displayName: 'group@group.com'},
    {displayName: 'test@group.com'},
    {displayName: 'group@user.com'},
  ]);
  assert.isFalse(userGroupNotInList);

  const userGroupInList = element._computeIsApprovalOwner([
    {displayName: 'tester@user.com'},
    {displayName: 'group@group.com'},
    {displayName: 'test@notuser.com'},
  ], 'test@user.com', [
    {displayName: 'group@group.com'},
  ]);
  assert.isTrue(userGroupInList);
});

test('site admins have approver privileges', () => {
  const notice = element.shadowRoot.querySelector('.approver-notice');
  assert.equal(notice.textContent.trim(), '');

  element.user = {isSiteAdmin: true};
  assert.isTrue(element._hasApproverPrivileges);

  flush(() => {
    assert.equal(notice.textContent.trim(),
      'Your site admin privileges give you full access to edit this approval.'
    );
  });
});

test('_updateSurveyHandler fired when mr-inline-editor saved', () => {
  element._updateSurveyHandler = sinon.stub();

  const editor = element.shadowRoot.querySelector('mr-inline-editor');

  editor.sendEmail = true;
  editor.setContent('blah');
  editor.save();

  flush(() => {
    const calledWithEvt = element._updateSurveyHandler.args[0][0];
    assert.deepEqual(calledWithEvt.detail, {
      commentContent: 'blah',
      sendEmail: true,
    });
    assert.isTrue(element._updateSurveyHandler.calledOnce);
  });
});
