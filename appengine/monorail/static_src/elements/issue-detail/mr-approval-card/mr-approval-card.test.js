// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrApprovalCard} from './mr-approval-card.js';

let element;

describe('mr-approval-card', () => {
  beforeEach(() => {
    element = document.createElement('mr-approval-card');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrApprovalCard);
  });

  it('_isApprover true when user is an approver', () => {
    // User not in approver list.
    element.approvers = [
      {displayName: 'tester@user.com'},
      {displayName: 'test@notuser.com'},
      {displayName: 'hello@world.com'},
    ];
    element.user = {displayName: 'test@user.com', groups: []};
    assert.isFalse(element._isApprover);

    // Use is in approver list.
    element.approvers = [
      {displayName: 'tester@user.com'},
      {displayName: 'test@notuser.com'},
      {displayName: 'hello@world.com'},
      {displayName: 'test@user.com'},
    ];
    assert.isTrue(element._isApprover);

    // User's group is not in the list.
    element.approvers = [
      {displayName: 'tester@user.com'},
      {displayName: 'nongroup@group.com'},
      {displayName: 'group@nongroup.com'},
      {displayName: 'ignore@test.com'},
    ];
    element.user = {
      displayName: 'test@user.com',
      groups: [
        {displayName: 'group@group.com'},
        {displayName: 'test@group.com'},
        {displayName: 'group@user.com'},
      ],
    };
    assert.isFalse(element._isApprover);

    // User's group is in the list.
    element.approvers = [
      {displayName: 'tester@user.com'},
      {displayName: 'group@group.com'},
      {displayName: 'test@notuser.com'},
    ];
    element.user = {
      displayName: 'test@user.com',
      groups: [
        {displayName: 'group@group.com'},
      ],
    };
    assert.isTrue(element._isApprover);
  });

  it('site admins have approver privileges', async () => {
    await element.updateComplete;

    const notice = element.shadowRoot.querySelector('.approver-notice');
    assert.equal(notice.textContent.trim(), '');

    element.user = {isSiteAdmin: true};
    await element.updateComplete;

    assert.isTrue(element._hasApproverPrivileges);

    assert.equal(notice.textContent.trim(),
        'Your site admin privileges give you full access to edit this approval.'
    );
  });

  it('site admins see all approval statuses except NotSet', () => {
    element.user = {isSiteAdmin: true};

    assert.isFalse(element._isApprover);

    element.statusEnum = 'NEEDS_REVIEW';

    assert.equal(element._availableStatuses.length, 7);
    assert.equal(element._availableStatuses[0].status, 'NeedsReview');
    assert.equal(element._availableStatuses[1].status, 'NA');
    assert.equal(element._availableStatuses[2].status, 'ReviewRequested');
    assert.equal(element._availableStatuses[3].status, 'ReviewStarted');
    assert.equal(element._availableStatuses[4].status, 'NeedInfo');
    assert.equal(element._availableStatuses[5].status, 'Approved');
    assert.equal(element._availableStatuses[6].status, 'NotApproved');
  });

  it('approvers see all approval statuses except NotSet', () => {
    element.user = {isSiteAdmin: false, displayName: 'test@email.com'};
    element.approvers = [{displayName: 'test@email.com'}];

    assert.isTrue(element._isApprover);

    element.statusEnum = 'NEEDS_REVIEW';

    assert.equal(element._availableStatuses.length, 7);
    assert.equal(element._availableStatuses[0].status, 'NeedsReview');
    assert.equal(element._availableStatuses[1].status, 'NA');
    assert.equal(element._availableStatuses[2].status, 'ReviewRequested');
    assert.equal(element._availableStatuses[3].status, 'ReviewStarted');
    assert.equal(element._availableStatuses[4].status, 'NeedInfo');
    assert.equal(element._availableStatuses[5].status, 'Approved');
    assert.equal(element._availableStatuses[6].status, 'NotApproved');
  });

  it('non-approvers see non-restricted approval statuses', () => {
    element.user = {isSiteAdmin: false, displayName: 'test@email.com'};
    element.approvers = [{displayName: 'test@otheremail.com'}];

    assert.isFalse(element._isApprover);

    element.statusEnum = 'NEEDS_REVIEW';

    assert.equal(element._availableStatuses.length, 4);
    assert.equal(element._availableStatuses[0].status, 'NeedsReview');
    assert.equal(element._availableStatuses[1].status, 'ReviewRequested');
    assert.equal(element._availableStatuses[2].status, 'ReviewStarted');
    assert.equal(element._availableStatuses[3].status, 'NeedInfo');
  });

  it('non-approvers see restricted approval status when set', () => {
    element.user = {isSiteAdmin: false, displayName: 'test@email.com'};
    element.approvers = [{displayName: 'test@otheremail.com'}];

    assert.isFalse(element._isApprover);

    element.statusEnum = 'APPROVED';

    assert.equal(element._availableStatuses.length, 5);
    assert.equal(element._availableStatuses[0].status, 'NeedsReview');
    assert.equal(element._availableStatuses[1].status, 'ReviewRequested');
    assert.equal(element._availableStatuses[2].status, 'ReviewStarted');
    assert.equal(element._availableStatuses[3].status, 'NeedInfo');
    assert.equal(element._availableStatuses[4].status, 'Approved');
  });

  it('expands to show focused comment', async () => {
    element.focusId = 'c4';
    element.fieldName = 'field';
    element.comments = [
      {
        sequenceNum: 1,
        approvalRef: {fieldName: 'other-field'},
      },
      {
        sequenceNum: 2,
        approvalRef: {fieldName: 'field'},
      },
      {
        sequenceNum: 3,
      },
      {
        sequenceNum: 4,
        approvalRef: {fieldName: 'field'},
      },
    ];

    await element.updateComplete;

    assert.isTrue(element.opened);
  });

  it('does not expand to show focused comment on other elements', async () => {
    element.focusId = 'c3';
    element.comments = [
      {
        sequenceNum: 1,
        approvalRef: {fieldName: 'other-field'},
      },
      {
        sequenceNum: 2,
        approvalRef: {fieldName: 'field'},
      },
      {
        sequenceNum: 4,
        approvalRef: {fieldName: 'field'},
      },
    ];

    await element.updateComplete;

    assert.isFalse(element.opened);
  });
});
