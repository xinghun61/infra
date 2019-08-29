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

  it('shortens link text when short is true', () => {
    element.issue = {
      projectName: 'test',
      localId: 13,
    };

    assert.equal(element._linkText, 'Issue test:13');

    element.short = true;

    assert.equal(element._linkText, 'test:13');
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

  it('displays an icon for federated references', async () => {
    element.issue = {
      extIdentifier: 'b/5678',
    };

    await element.updateComplete;

    const dropdown = element.shadowRoot.querySelector('mr-dropdown');
    assert.isNotNull(dropdown);
    const anchor = dropdown.shadowRoot.querySelector('.anchor');
    assert.isNotNull(anchor);
    assert.include(anchor.innerText, 'info_outline');
  });

  it('displays an info popup for federated references', async () => {
    element.issue = {
      extIdentifier: 'b/5678',
    };

    await element.updateComplete;

    const dropdown = element.shadowRoot.querySelector('mr-dropdown');
    const anchor = dropdown.shadowRoot.querySelector('.anchor');
    anchor.click();

    await dropdown.updateComplete;

    assert.isTrue(dropdown.opened);

    const cue = dropdown.querySelector('mr-cue');
    assert.isNotNull(cue);
    const message = cue.shadowRoot.querySelector('#message');
    assert.isNotNull(message);
    assert.include(message.innerText, 'another tracker');
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
