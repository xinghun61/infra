// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {MrSearchBar} from './mr-search-bar.js';

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

  it('render user saved queries', () => {
    element.userDisplayName = 'test@user.com';
    element.userSavedQueries = [
      {name: 'test query', queryId: 101},
      {name: 'hello world', queryId: 202},
    ];

    flush();

    const queryOptions = element.shadowRoot.querySelectorAll(
      '.user-query');

    assert.equal(queryOptions.length, 2);

    assert.equal(queryOptions[0].value, '101');
    assert.equal(queryOptions[0].textContent, 'test query');

    assert.equal(queryOptions[1].value, '202');
    assert.equal(queryOptions[1].textContent, 'hello world');
  });

  it('render project saved queries', () => {
    element.userDisplayName = 'test@user.com';
    element.projectSavedQueries = [
      {name: 'test query', queryId: 101},
      {name: 'hello world', queryId: 202},
    ];

    flush();

    const queryOptions = element.shadowRoot.querySelectorAll(
      '.project-query');

    assert.equal(queryOptions.length, 2);

    assert.equal(queryOptions[0].value, '101');
    assert.equal(queryOptions[0].textContent, 'test query');

    assert.equal(queryOptions[1].value, '202');
    assert.equal(queryOptions[1].textContent, 'hello world');
  });
});
