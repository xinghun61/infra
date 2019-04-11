// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrRestrictionIndicator} from './mr-restriction-indicator.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

let element;

suite('mr-restriction-indicator', () => {
  setup(() => {
    element = document.createElement('mr-restriction-indicator');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrRestrictionIndicator);
  });

  test('shows restricted notice only when restricted', () => {
    assert.isTrue(element.hasAttribute('hidden'));

    element.isRestricted = true;

    flush();

    assert.isFalse(element.hasAttribute('hidden'));

    element.isRestricted = false;

    flush();

    assert.isTrue(element.hasAttribute('hidden'));
  });

  test('displays view restrictions', () => {
    element.isRestricted = true;

    element.restrictions = {
      view: ['Google', 'hello'],
      edit: ['Editor', 'world'],
      comment: ['commentor'],
    };

    const restrictString =
      'Only users with Google and hello permission can view this issue.';
    assert.equal(element._restrictionText, restrictString);

    assert.include(element.shadowRoot.textContent, restrictString);
  });

  test('displays edit restrictions', () => {
    element.isRestricted = true;

    element.restrictions = {
      view: [],
      edit: ['Editor', 'world'],
      comment: ['commentor'],
    };

    const restrictString =
      'Only users with Editor and world permission may make changes.';
    assert.equal(element._restrictionText, restrictString);

    assert.include(element.shadowRoot.textContent, restrictString);
  });

  test('displays comment restrictions', () => {
    element.isRestricted = true;

    element.restrictions = {
      view: [],
      edit: [],
      comment: ['commentor'],
    };

    const restrictString =
      'Only users with commentor permission may comment.';
    assert.equal(element._restrictionText, restrictString);

    assert.include(element.shadowRoot.textContent, restrictString);
  });
});
