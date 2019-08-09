// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueHeader} from './mr-issue-header.js';
import {store} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import {ISSUE_EDIT_PERMISSION, ISSUE_DELETE_PERMISSION,
  ISSUE_FLAGSPAM_PERMISSION} from 'elements/shared/permissions.js';

let element;

describe('mr-issue-header', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-header');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssueHeader);
  });

  it('updating issue id changes header', function() {
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

  it('_issueOptions toggles spam', () => {
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

  it('_issueOptions toggles convert issue', () => {
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

  it('_issueOptions toggles delete', () => {
    element.issuePermissions = [ISSUE_DELETE_PERMISSION];
    assert.isDefined(findOptionWithText(element._issueOptions,
        'Delete issue'));

    element.issuePermissions = [];

    assert.isUndefined(findOptionWithText(element._issueOptions,
        'Delete issue'));
  });

  it('_issueOptions toggles move and copy', () => {
    element.issuePermissions = [ISSUE_DELETE_PERMISSION];
    assert.isDefined(findOptionWithText(element._issueOptions,
        'Move issue'));
    assert.isDefined(findOptionWithText(element._issueOptions,
        'Copy issue'));

    element.isRestricted = true;
    assert.isUndefined(findOptionWithText(element._issueOptions,
        'Move issue'));
    assert.isUndefined(findOptionWithText(element._issueOptions,
        'Copy issue'));

    element.issuePermissions = [];

    assert.isUndefined(findOptionWithText(element._issueOptions,
        'Move issue'));
    assert.isUndefined(findOptionWithText(element._issueOptions,
        'Copy issue'));
  });

  it('_issueOptions toggles edit description', () => {
    element.issuePermissions = [ISSUE_EDIT_PERMISSION];
    assert.isDefined(findOptionWithText(element._issueOptions,
        'Edit issue description'));

    element.issuePermissions = [];

    assert.isUndefined(findOptionWithText(element._issueOptions,
        'Edit issue description'));
  });
});

function findOptionWithText(issueOptions, text) {
  return issueOptions.find((option) => option.text === text);
}
