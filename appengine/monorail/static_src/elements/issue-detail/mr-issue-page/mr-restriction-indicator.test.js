// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrRestrictionIndicator} from './mr-restriction-indicator.js';

let element;

describe('mr-restriction-indicator', () => {
  beforeEach(() => {
    element = document.createElement('mr-restriction-indicator');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrRestrictionIndicator);
  });

  it('shows element only when restricted or showWarning', async () => {
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('hidden'));

    element.restrictions = {view: ['Google']};
    await element.updateComplete;

    assert.isFalse(element.hasAttribute('hidden'));

    element.restrictions = {};
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('hidden'));

    element.prefs = new Map([['public_issue_notice', 'true']]);
    await element.updateComplete;

    assert.isFalse(element.hasAttribute('hidden'));

    element.prefs = new Map([['public_issue_notice', 'false']]);
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('hidden'));

    element.prefs = new Map([]);
    await element.updateComplete;

    assert.isTrue(element.hasAttribute('hidden'));

    // It is possible to have an edit or comment restriction on
    // a public issue when the user is opted in to public issue notices.
    // In that case, the lock icon is shown, plus a warning icon and the
    // public issue notice.
    element.restrictions = new Map([['edit', ['Google']]]);
    element.prefs = new Map([['public_issue_notice', 'true']]);
    await element.updateComplete;

    assert.isFalse(element.hasAttribute('hidden'));
  });

  it('displays view restrictions', async () => {
    element.restrictions = {
      view: ['Google', 'hello'],
      edit: ['Editor', 'world'],
      comment: ['commentor'],
    };

    await element.updateComplete;

    const restrictString =
      'Only users with Google and hello permission can view this issue.';
    assert.equal(element._restrictionText, restrictString);

    assert.include(element.shadowRoot.textContent, restrictString);
  });

  it('displays edit restrictions', async () => {
    element.restrictions = {
      view: [],
      edit: ['Editor', 'world'],
      comment: ['commentor'],
    };

    await element.updateComplete;

    const restrictString =
      'Only users with Editor and world permission may make changes.';
    assert.equal(element._restrictionText, restrictString);

    assert.include(element.shadowRoot.textContent, restrictString);
  });

  it('displays comment restrictions', async () => {
    element.restrictions = {
      view: [],
      edit: [],
      comment: ['commentor'],
    };

    await element.updateComplete;

    const restrictString =
      'Only users with commentor permission may comment.';
    assert.equal(element._restrictionText, restrictString);

    assert.include(element.shadowRoot.textContent, restrictString);
  });

  it('displays public issue notice, if the user has that pref', async () => {
    element.restrictions = {};

    element.prefs = new Map();
    assert.equal(element._restrictionText, '');
    assert.include(element.shadowRoot.textContent, '');

    element.prefs = new Map([['public_issue_notice', 'true']]);

    await element.updateComplete;

    const noticeString =
      'Public issue: Please do not post confidential information.';
    assert.equal(element._warningText, noticeString);

    assert.include(element.shadowRoot.textContent, noticeString);
  });
});
