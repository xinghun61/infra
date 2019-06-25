// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueLink} from './mr-issue-link.js';

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

  it('strikethrough when closed', async () => {
    await element.updateComplete;
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.isFalse(
      window.getComputedStyle(link).getPropertyValue(
        'text-decoration').includes('line-through'));
    element.issue = {statusRef: {meansOpen: false}};

    await element.updateComplete;

    assert.isTrue(
      window.getComputedStyle(link).getPropertyValue(
        'text-decoration').includes('line-through'));
  });

  it('shows projectName only when different from global', async () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
    };
    await element.updateComplete;

    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.textContent.trim(), 'Issue test:11');

    element.projectName = 'test';
    await element.updateComplete;

    assert.equal(link.textContent.trim(), 'Issue 11');

    element.projectName = 'other';
    await element.updateComplete;

    await element.updateComplete;

    assert.equal(link.textContent.trim(), 'Issue test:11');
  });

  it('shows links for issues', async () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
    };

    await element.updateComplete;

    const link = element.shadowRoot.querySelector('#bugLink');
    assert.include(link.href.trim(), '/p/test/issues/detail?id=11');
    assert.equal(link.title, '');
  });

  it('shows links for federated issues', async () => {
    element.issue = {
      extIdentifier: 'b/5678',
    };

    await element.updateComplete;

    const link = element.shadowRoot.querySelector('#bugLink');
    assert.include(link.href.trim(), 'https://issuetracker.google.com/issues/5678');
    assert.equal(link.title, '');
  });

  it('shows title when summary is defined', async () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
      summary: 'Summary',
    };

    await element.updateComplete;
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.title, 'Summary');
  });
});
