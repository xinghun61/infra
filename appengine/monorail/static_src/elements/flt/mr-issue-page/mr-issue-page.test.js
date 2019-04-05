// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {assert} from 'chai';
import {MrIssuePage} from './mr-issue-page.js';

let element;
let loadingElement;
let fetchErrorElement;
let deletedElement;
let issueElement;

function populateElementReferences() {
  flush();
  loadingElement = element.shadowRoot.querySelector('#loading');
  fetchErrorElement = element.shadowRoot.querySelector('#fetch-error');
  deletedElement = element.shadowRoot.querySelector('#deleted');
  issueElement = element.shadowRoot.querySelector('#issue');
}

suite('mr-issue-page', () => {
  setup(() => {
    element = document.createElement('mr-issue-page');
    element.mapStateToProps = () => {};
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssuePage);
  });

  test('nothing has happened yet', () => {
    populateElementReferences();

    assert.isNotNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('issue not loaded yet', () => {
    element.fetchingIssue = true;
    populateElementReferences();

    assert.isNotNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('comments not loaded yet', () => {
    element.fetchingIssue = false;
    element.fetchingComments = true;
    populateElementReferences();

    assert.isNotNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('fetch error', () => {
    element._hasFetched = true;
    element.fetchingComments = false;
    element.fetchingIssue = false;
    element.fetchIssueError = 'error';
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNotNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('deleted issue', () => {
    element._hasFetched = true;
    element.fetchingComments = false;
    element.fetchingIssue = false;
    element.issue = {isDeleted: true};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNotNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('normal issue', () => {
    element._hasFetched = true;
    element.fetchingComments = false;
    element.fetchingIssue = false;
    element.issue = {};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });
});
