// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueLink} from './mr-issue-link.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;

describe('mr-issue-link', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-link');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssueLink);
  });

  it('strikethrough when closed', () => {
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

  it('shows projectName only when different from global', () => {
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

  it('shows links for issues', () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
    };
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.include(link.href.trim(), '/p/test/issues/detail?id=11');
  });
});
