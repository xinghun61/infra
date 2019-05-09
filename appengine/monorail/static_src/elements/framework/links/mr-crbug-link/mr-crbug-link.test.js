// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrCrbugLink} from './mr-crbug-link.js';


let element;

describe('mr-crbug-link', () => {
  beforeEach(() => {
    element = document.createElement('mr-crbug-link');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrCrbugLink);
  });

  it('In prod, link to crbug.com with project name specified', async () => {
    element._getHost = () => 'bugs.chromium.org';
    element.issue = {
      projectName: 'test',
      localId: 11,
    };

    await element.updateComplete;

    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.href, 'https://crbug.com/test/11');
  });

  it('In prod, link to crbug.com with implicit project name', async () => {
    element._getHost = () => 'bugs.chromium.org';
    element.issue = {
      projectName: 'chromium',
      localId: 11,
    };

    await element.updateComplete;

    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.href, 'https://crbug.com/11');
  });

  it('does not redirects to approval page for regular issues', async () => {
    element.issue = {
      projectName: 'test',
      localId: 11,
    };

    await element.updateComplete;

    const link = element.shadowRoot.querySelector('#bugLink');
    assert.include(link.href.trim(), '/p/test/issues/detail?id=11');
  });
});
