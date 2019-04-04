// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueHeader} from './mr-issue-header.js';
import {store, resetState} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {ISSUE_EDIT_PERMISSION,
  ISSUE_FLAGSPAM_PERMISSION} from '../../shared/permissions.js';

let element;
let lockIcon;
let lockTooltip;

suite('mr-issue-header', () => {
  setup(() => {
    element = document.createElement('mr-issue-header');
    document.body.appendChild(element);

    lockIcon = element.shadowRoot.querySelector('.lock-icon');
    lockTooltip = element.shadowRoot.querySelector('.lock-tooltip');
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction(resetState());
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssueHeader);
  });

  test('updating issue id changes header', function() {
    assert.equal(issue.issueRef(store.getState()).localId, 0);
    store.dispatch(issue.setIssueRef(1));
    assert.equal(issue.issueRef(store.getState()).localId, 1);
    store.dispatch({type: issue.FETCH_SUCCESS, issue: {summary: 'test'}});
    assert.deepEqual(issue.issue(store.getState()), {summary: 'test'});
    // TODO(zhangtiff): Figure out how to properly test
    // state changes propagating to the element. As is, state
    // changes don't seem to actually make it to the element.
    // assert.deepEqual(element.issue, {summary: 'test'});
  });

  test('shows restricted icon only when restricted', () => {
    assert.isTrue(lockIcon.hasAttribute('hidden'));

    element.isRestricted = true;

    flush();

    assert.isFalse(lockIcon.hasAttribute('hidden'));

    element.isRestricted = false;

    flush();

    assert.isTrue(lockIcon.hasAttribute('hidden'));
  });

  test('displays view restrictions', () => {
    element.isRestricted = true;

    element.restrictions = {
      view: ['Google', 'hello'],
      edit: ['Editor', 'world'],
      comment: ['commentor'],
    };

    const restrictString =
      'Only users with Google and hello permission can see this issue.';
    assert.equal(element._restrictionText, restrictString);

    assert.equal(lockIcon.title, restrictString);
    assert.include(lockTooltip.textContent, restrictString);
  });

  test('displays edit restrictions', () => {
    element.isRestricted = true;

    element.restrictions = {
      view: [],
      edit: ['Editor', 'world'],
      comment: ['commentor'],
    };

    const restrictString =
      'Only users with Editor and world permission may make changes.';
    assert.equal(element._restrictionText, restrictString);

    assert.equal(lockIcon.title, restrictString);
    assert.include(lockTooltip.textContent, restrictString);
  });

  test('displays comment restrictions', () => {
    element.isRestricted = true;

    element.restrictions = {
      view: [],
      edit: [],
      comment: ['commentor'],
    };

    const restrictString =
      'Only users with commentor permission may comment.';
    assert.equal(element._restrictionText, restrictString);

    assert.equal(lockIcon.title, restrictString);
    assert.include(lockTooltip.textContent, restrictString);
  });

  test('_computeIssueOptions toggles spam', () => {
    element.issuePermissions = [ISSUE_FLAGSPAM_PERMISSION];
    element.issue = {isSpam: false};
    assert.isDefined(findOptionWithText(element._issueOptions,
      'Flag issue as spam'));
    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Un-flag issue as spam'));

    element.issue = {isSpam: true};

    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Flag issue as spam'));
    assert.isDefined(findOptionWithText(element._issueOptions,
      'Un-flag issue as spam'));

    element.issuePermissions = [];

    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Flag issue as spam'));
    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Un-flag issue as spam'));

    element.issue = {isSpam: false};
    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Flag issue as spam'));
    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Un-flag issue as spam'));
  });

  test('_computeIssueOptions toggles convert issue', () => {
    element.issuePermissions = [];
    element.projectTemplates = [];

    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Convert issue template'));

    element.projectTemplates = [{templateName: 'test'}];

    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Convert issue template'));

    element.issuePermissions = [ISSUE_EDIT_PERMISSION];
    element.projectTemplates = [];
    assert.isUndefined(findOptionWithText(element._issueOptions,
      'Convert issue template'));

    element.projectTemplates = [{templateName: 'test'}];
    assert.isDefined(findOptionWithText(element._issueOptions,
      'Convert issue template'));
  });
});

function findOptionWithText(issueOptions, text) {
  return issueOptions.find((option) => option.text === text);
}
