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

  test('issue not loaded yet', () => {
    element.fetchingIssue = true;

    populateElementReferences();

    assert.isNotNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('no loading on future issue fetches', () => {
    element.issue = {localId: 222};
    element.fetchingIssue = true;

    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });

  test('fetch error', () => {
    element.fetchingIssue = false;
    element.fetchIssueError = 'error';
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNotNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('deleted issue', () => {
    element.fetchingIssue = false;
    element.issue = {isDeleted: true};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNotNull(deletedElement);
    assert.isNull(issueElement);
  });

  test('normal issue', () => {
    element.fetchingIssue = false;
    element.issue = {localId: 111};
    populateElementReferences();

    assert.isNull(loadingElement);
    assert.isNull(fetchErrorElement);
    assert.isNull(deletedElement);
    assert.isNotNull(issueElement);
  });

  test('code font pref toggles attribute', () => {
    assert.isFalse(element.codeFont);
    assert.isFalse(element.hasAttribute('code-font'));

    element.prefs = new Map([['code_font', 'true']]);

    assert.isTrue(element.codeFont);
    assert.isTrue(element.hasAttribute('code-font'));

    element.prefs = new Map([['code_font', 'false']]);

    assert.isFalse(element.codeFont);
    assert.isFalse(element.hasAttribute('code-font'));
  });
});
