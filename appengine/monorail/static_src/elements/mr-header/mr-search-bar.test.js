// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {MrSearchBar} from './mr-search-bar.js';

let element;

suite('mr-search-bar', () => {
  setup(() => {
    element = document.createElement('mr-search-bar');
    document.body.appendChild(element);

    sinon.stub(window.prpcClient, 'call').callsFake(
      () => Promise.resolve({}));
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, MrSearchBar);
  });

  test('render user saved queries', () => {
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

  test('render project saved queries', () => {
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
