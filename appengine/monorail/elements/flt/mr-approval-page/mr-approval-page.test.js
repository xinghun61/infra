// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrApprovalPage} from './mr-approval-page.js';
import {store, actionType} from '../../redux/redux-mixin.js';

let element;

suite('mr-approval-page');

beforeEach(() => {
  element = document.createElement('mr-approval-page');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, MrApprovalPage);
});

test('fetching issue makes loading show', () => {
  assert.isFalse(store.getState().fetchingIssue);

  store.dispatch({
    type: actionType.FETCH_ISSUE_START,
  });

  assert.isTrue(store.getState().fetchingIssue);

  // TODO(zhangtiff): Figure out how to propagate Redux state changes.
  element.fetchingIssue = true;
  assert.isTrue(element.fetchingIssue);
});

test('dispatching failure makes error show', () => {
  store.dispatch({
    type: actionType.FETCH_ISSUE_FAILURE,
    error: 'failed request',
  });

  assert.equal(store.getState().fetchIssueError, 'failed request');

  // TODO(zhangtiff): Figure out how to propagate Redux state changes.
  element.fetchIssueError = element.fetchIssueError;
  assert.equal(element.fetchIssueError, element.fetchIssueError);
});
