// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueMetadata} from './mr-issue-metadata.js';

let element;

describe('mr-issue-metadata', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-metadata');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssueMetadata);
  });

  it('labels render', async () => {
    element.issue = {
      labelRefs: [
        {label: 'test'},
        {label: 'hello-world', isDerived: true},
      ],
    };

    element.labelDefMap = new Map([
      ['test', {label: 'test', docstring: 'this is a docstring'}],
    ]);

    await element.updateComplete;

    const labels = element.shadowRoot.querySelectorAll('.label');

    assert.equal(labels.length, 2);
    assert.equal(labels[0].textContent.trim(), 'test');
    assert.equal(labels[0].getAttribute('title'), 'test = this is a docstring');
    assert.isUndefined(labels[0].dataset.derived);

    assert.equal(labels[1].textContent.trim(), 'hello-world');
    assert.equal(labels[1].getAttribute('title'), 'Derived: hello-world');
    assert.isDefined(labels[1].dataset.derived);
  });

  it('update hotlist button is shown to users', async () => {
    element.user = {userId: 1234};
    await element.updateComplete;
    assert.isNotNull(element.shadowRoot.querySelector('#user-hotlists'));
  });

  it('update hotlist button is not shown to anon', async () => {
    await element.updateComplete;
    assert.isNull(element.shadowRoot.querySelector('#user-hotlists'));
  });
});
