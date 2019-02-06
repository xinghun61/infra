// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueHeader} from './mr-issue-header.js';
import {store, actionType} from '../../redux/redux-mixin.js';

let element;

suite('mr-issue-header');

beforeEach(() => {
  element = document.createElement('mr-issue-header');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, MrIssueHeader);
});

test('updating issue id changes header', function() {
  assert.equal(store.getState().issueId, 0);

  store.dispatch({
    type: actionType.UPDATE_ISSUE_REF,
    issueId: 1,
  });

  assert.equal(store.getState().issueId, 1);

  store.dispatch({
    type: actionType.FETCH_ISSUE_SUCCESS,
    issue: {summary: 'test'},
  });

  assert.deepEqual(store.getState().issue, {summary: 'test'});

  // TODO(zhangtiff): Figure out how to properly test
  // state changes propagating to the element. As is, state
  // changes don't seem to actually make it to the element.
  // assert.deepEqual(element.issue, {summary: 'test'});
});
