// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import {MrListPage} from './mr-list-page.js';

let element;

describe('mr-list-page', () => {
  beforeEach(() => {
    element = document.createElement('mr-list-page');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrListPage);
  });

  it('shows loading only when issues loading', async () => {
    element.fetchingIssueList = true;

    await element.updateComplete;

    let loading = element.shadowRoot.querySelector('.container-no-issues');
    let issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.equal(loading.textContent.trim(), 'Loading...');
    assert.isNull(issueList);

    element.fetchingIssueList = false;

    await element.updateComplete;

    loading = element.shadowRoot.querySelector('.container-no-issues');
    issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.isNull(loading);
    assert.isNotNull(issueList);
  });
});

