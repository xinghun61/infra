// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrSearchBar} from './mr-search-bar.js';


window.CS_env = {
  token: 'foo-token',
};

let element;

describe('mr-search-bar', () => {
  beforeEach(() => {
    element = document.createElement('mr-search-bar');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrSearchBar);
  });

  it('render user saved queries', async () => {
    element.userDisplayName = 'test@user.com';
    element.userSavedQueries = [
      {name: 'test query', queryId: 101},
      {name: 'hello world', queryId: 202},
    ];

    await element.updateComplete;

    const queryOptions = element.shadowRoot.querySelectorAll(
      '.user-query');

    assert.equal(queryOptions.length, 2);

    assert.equal(queryOptions[0].value, '101');
    assert.equal(queryOptions[0].textContent, 'test query');

    assert.equal(queryOptions[1].value, '202');
    assert.equal(queryOptions[1].textContent, 'hello world');
  });

  it('render project saved queries', async () => {
    element.userDisplayName = 'test@user.com';
    element.projectSavedQueries = [
      {name: 'test query', queryId: 101},
      {name: 'hello world', queryId: 202},
    ];

    await element.updateComplete;

    const queryOptions = element.shadowRoot.querySelectorAll(
      '.project-query');

    assert.equal(queryOptions.length, 2);

    assert.equal(queryOptions[0].value, '101');
    assert.equal(queryOptions[0].textContent, 'test query');

    assert.equal(queryOptions[1].value, '202');
    assert.equal(queryOptions[1].textContent, 'hello world');
  });

  it('spell check is off for search bar', async () => {
    await element.updateComplete;
    const searchElement = element.shadowRoot.querySelector('#searchq');
    assert.equal(searchElement.getAttribute('spellcheck'), 'false');
  });
});
