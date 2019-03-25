// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrCrbugLink} from './mr-crbug-link.js';


let element;

suite('mr-crbug-link', () => {
  setup(() => {
    element = document.createElement('mr-crbug-link');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrCrbugLink);
  });

  test('In prod, link to crbug.com with project name specified', () => {
    element._getHost = () => 'bugs.chromium.org';
    element.issue = {
      projectName: 'test',
      localId: 11,
    };
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.href, 'https://crbug.com/test/11');
  });

  test('In prod, link to crbug.com with implicit project name', () => {
    element._getHost = () => 'bugs.chromium.org';
    element.issue = {
      projectName: 'chromium',
      localId: 11,
    };
    const link = element.shadowRoot.querySelector('#bugLink');
    assert.equal(link.href, 'https://crbug.com/11');
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
