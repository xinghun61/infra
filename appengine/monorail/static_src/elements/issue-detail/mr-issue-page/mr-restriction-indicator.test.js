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

  test('shows element only when restricted or showNotice', () => {
    assert.isTrue(element.hasAttribute('hidden'));

    element.restrictions = {view: ['Google']};
    flush();
    assert.isFalse(element.hasAttribute('hidden'));

    element.restrictions = {};
    flush();
    assert.isTrue(element.hasAttribute('hidden'));

    element.prefs = new Map([['public_issue_notice', 'true']]);
    flush();
    assert.isFalse(element.hasAttribute('hidden'));

    element.prefs = new Map([['public_issue_notice', 'false']]);
    flush();
    assert.isTrue(element.hasAttribute('hidden'));

    element.prefs = new Map([]);
    flush();
    assert.isTrue(element.hasAttribute('hidden'));

    // It is possible to have an edit or comment restriction on
    // a public issue when the user is opted in to public issue notices.
    // In that case, the lock icon is shown, plus a warning icon and the
    // public issue notice.
    element.restrictions = new Map([['edit', ['Google']]]);
    element.prefs = new Map([['public_issue_notice', 'true']]);
    flush();
    assert.isFalse(element.hasAttribute('hidden'));
  });

  test('displays view restrictions', () => {
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

  test('displays public issue notice, if the user has that pref', () => {
    element.restrictions = {};

    element.prefs = new Map();
    assert.equal(element._restrictionText, '');
    assert.include(element.shadowRoot.textContent, '');

    element.prefs = new Map([['public_issue_notice', 'true']]);
    const noticeString =
      'Public issue: Please do not post confidential information.';
    assert.equal(element._noticeText, noticeString);

    assert.include(element.shadowRoot.textContent, noticeString);
  });

});
