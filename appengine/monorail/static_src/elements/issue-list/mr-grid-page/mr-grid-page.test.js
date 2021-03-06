// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrGridPage} from './mr-grid-page.js';

let element;

describe('mr-grid-page', () => {
  beforeEach(() => {
    element = document.createElement('mr-grid-page');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrGridPage);
  });

  it('progress bar updates properly', async () => {
    await element.updateComplete;
    element.progress = .2499;
    await element.updateComplete;
    const title =
      element.shadowRoot.querySelector('progress').getAttribute('title');
    assert.equal(title, '25%');
  });

  it('displays error when no issues match query', async () => {
    await element.updateComplete;
    element.progress = 1;
    element.totalIssues = 0;
    await element.updateComplete;
    const error =
      element.shadowRoot.querySelector('.empty-search').textContent;
    assert.equal(error.trim(), 'Your search did not generate any results.');
  });

  it('calls to fetchIssueList made when q changes', async () => {
    await element.updateComplete;
    const issueListCall = sinon.stub(element, '_fetchMatchingIssues');
    element.queryParams = {x: 'Blocked'};
    await element.updateComplete;
    sinon.assert.notCalled(issueListCall);

    element.queryParams = {q: 'cc:me'};
    await element.updateComplete;
    sinon.assert.calledOnce(issueListCall);
  });
});

