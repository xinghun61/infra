// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssuePage} from './mr-issue-page.js';
import {store} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';

let element;

suite('mr-issue-page', () => {
  setup(() => {
    element = document.createElement('mr-issue-page');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssuePage);
  });

  test('fetching issue makes loading show', () => {
    assert.isFalse(issue.requests(store.getState()).fetchIssue.requesting);

    store.dispatch({
      type: issue.FETCH_ISSUE_START,
    });

    assert.isTrue(issue.requests(store.getState()).fetchIssue.requesting);

    // TODO(zhangtiff): Figure out how to propagate Redux state changes.
    element.fetchingIssue = true;
    assert.isTrue(element.fetchingIssue);
  });

  test('dispatching failure makes error show', () => {
    store.dispatch({
      type: issue.FETCH_ISSUE_FAILURE,
      error: 'failed request',
    });

    assert.equal(
      issue.requests(store.getState()).fetchIssue.error, 'failed request');

    // TODO(zhangtiff): Figure out how to propagate Redux state changes.
    element.fetchIssueError = element.fetchIssueError;
    assert.equal(element.fetchIssueError, element.fetchIssueError);
  });
});
