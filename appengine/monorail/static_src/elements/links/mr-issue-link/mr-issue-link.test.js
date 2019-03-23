// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueLink} from './mr-issue-link.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;

suite('mr-issue-link', () => {
  setup(() => {
    element = document.createElement('mr-issue-link');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssueLink);
  });

  test('strikethrough when closed', () => {
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.isFalse(
        window.getComputedStyle(link).getPropertyValue(
          'text-decoration').includes('line-through'));
    element.issue = {statusRef: {meansOpen: false}};

    flush();

    assert.isTrue(
        window.getComputedStyle(link).getPropertyValue(
          'text-decoration').includes('line-through'));
  });

  test('shows projectName only when different from global', () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
    };
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.textContent.trim(), 'Issue test:11');

    element.projectName = 'test';

    assert.equal(link.textContent.trim(), 'Issue 11');

    element.projectName = 'other';

    flush();

    assert.equal(link.textContent.trim(), 'Issue test:11');
  });

  test('does not redirects to approval page for regular issues', () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
    };
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.include(link.href.trim(), '/p/test/issues/detail?id=11');
  });

  test('redirects to approval page for approval issues', () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
      approvalValues: [],
    };
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.include(link.href.trim(), '/p/test/issues/approval?id=11');
  });
});
